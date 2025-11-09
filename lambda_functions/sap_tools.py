"""
Multi-tool SAP Lambda function for MCP Gateway
Provides multiple SAP operations: list POs, search POs, get material stock, etc.
"""
import json
import urllib.request
import urllib.parse
import urllib.error
import base64
import logging
import re
import ssl
import time
import os
from datetime import datetime, timedelta

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# SAP credentials
def _get_lambda_credentials():
    """Retrieve SAP credentials from AWS Secrets Manager for Lambda"""
    secret_arn = os.getenv('SECRET_ARN')
    if secret_arn:
        import boto3
        try:
            client = boto3.client('secretsmanager', region_name='us-east-1')
            response = client.get_secret_value(SecretId=secret_arn)
            secret = json.loads(response['SecretString'])
            return secret.get('SAP_HOST'), secret.get('SAP_USER'), secret.get('SAP_PASSWORD')
        except Exception as e:
            logger.error(f"Error retrieving secrets: {e}")
            return None, None, None
    return None, None, None

_sm_host, _sm_user, _sm_pass = _get_lambda_credentials()
SAP_HOST = _sm_host or os.getenv("SAP_HOST")
SAP_USER = _sm_user or os.getenv("SAP_USER")
SAP_PASSWORD = _sm_pass or os.getenv("SAP_PASSWORD")
SAP_CLIENT = None
USE_JSON = True

def _build_url(path, filters=None, select=None, orderby=None, top=None):
    """Build SAP OData URL with filters"""
    params = {}
    params["$format"] = "json" if USE_JSON else "xml"

    if filters:
        params["$filter"] = filters
    if select:
        params["$select"] = ",".join(select)
    if orderby:
        params["$orderby"] = orderby
    if top:
        params["$top"] = str(top)
    if SAP_CLIENT:
        params["sap-client"] = SAP_CLIENT

    safe_chars = "'() "
    query_string = urllib.parse.urlencode(params, safe=safe_chars)
    return f'https://{SAP_HOST}{path}?{query_string}'

def _basic_auth_header(user, pwd):
    token = base64.b64encode(f"{user}:{pwd}".encode()).decode()
    return f"Basic {token}"

def _make_opener(context, no_proxies=True):
    handlers = [urllib.request.HTTPSHandler(context=context)]
    if no_proxies:
        handlers.append(urllib.request.ProxyHandler({}))
    return urllib.request.build_opener(*handlers)

def make_sap_request(url, timeout=30, retries=3):
    """Make SAP OData request"""
    context = ssl.create_default_context()
    opener = _make_opener(context, no_proxies=True)

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", _basic_auth_header(SAP_USER, SAP_PASSWORD))
            req.add_header("Accept", "application/json" if USE_JSON else "application/atom+xml")
            req.add_header("User-Agent", "sap-odata-test/1.0")
            req.add_header("Connection", "close")

            with opener.open(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                if resp.status == 200:
                    return {"status": "success", "data": body}
                return {"status": "error", "message": f"HTTP {resp.status}", "details": body}

        except Exception as e:
            if attempt < retries - 1:
                time.sleep(0.8 * (2 ** attempt))
                continue
            return {"status": "error", "message": str(e)}

    return {"status": "error", "message": "Exhausted retries"}

def parse_json_entries(json_text):
    """Parse OData JSON response"""
    try:
        obj = json.loads(json_text)
        d = obj.get("d", {})
        if isinstance(d, dict) and "results" in d:
            results = d.get("results")
            if isinstance(results, list):
                return {"entries": results, "total_count": len(results)}
            if isinstance(results, dict):
                return {"entries": [results], "total_count": 1}
        if d and isinstance(d, dict):
            return {"entries": [d], "total_count": 1}
        return {"entries": [], "total_count": 0}
    except Exception as e:
        return {"parse_error": str(e), "raw_json_preview": json_text[:500]}

def _format_sap_date(value):
    """Format SAP OData date"""
    if not isinstance(value, str):
        return value
    m = re.match(r"/Date\((\d+)([+-]\d{4})?\)/", value)
    if not m:
        return value
    try:
        ms = int(m.group(1))
        return time.strftime("%Y-%m-%d", time.gmtime(ms / 1000))
    except Exception:
        return value

def _clean_entry(entry):
    """Clean and normalize SAP entry"""
    if not isinstance(entry, dict):
        return entry
    cleaned = {k: v for k, v in entry.items() if not k.startswith("__")}

    # Format dates
    for k in list(cleaned.keys()):
        if k.lower().endswith("date") or k.lower().endswith("datetime"):
            cleaned[k] = _format_sap_date(cleaned[k])

    # Convert numeric fields
    for nf in ("NetAmount", "OrderQuantity", "NetPriceAmount", "GrossAmount", "AvailableQuantity"):
        if nf in cleaned and isinstance(cleaned[nf], str):
            try:
                cleaned[nf] = float(cleaned[nf])
            except Exception:
                pass

    return cleaned

# ============================================================================
# TOOL 1: List Purchase Orders
# ============================================================================
def list_purchase_orders(limit=20, date_from=None, supplier=None, status=None):
    """
    List purchase orders with optional filters

    Args:
        limit: Maximum number of orders to return (default 20)
        date_from: Filter orders from this date (YYYY-MM-DD format)
        supplier: Filter by supplier code
        status: Filter by order status
    """
    select = [
        "PurchaseOrder", "PurchasingOrganization", "PurchasingGroup",
        "Supplier", "DocumentCurrency", "PurchaseOrderDate", "CreationDate"
    ]

    filters = []
    if date_from:
        # Convert to SAP date format
        filters.append(f"PurchaseOrderDate ge datetime'{date_from}T00:00:00'")
    if supplier:
        filters.append(f"Supplier eq '{supplier}'")

    filter_str = " and ".join(filters) if filters else None

    url = _build_url(
        "/sap/opu/odata/sap/C_PURCHASEORDER_FS_SRV/I_PurchaseOrder",
        filters=filter_str,
        select=select,
        orderby="PurchaseOrderDate desc",
        top=limit
    )

    res = make_sap_request(url)
    if res["status"] != "success":
        return res

    parsed = parse_json_entries(res["data"])
    if "parse_error" in parsed:
        return {"status": "error", "message": "Failed to parse response", "details": parsed}

    orders = [_clean_entry(e) for e in parsed.get("entries", [])]

    return {
        "status": "success",
        "purchase_orders": orders,
        "total_count": len(orders),
        "filters_applied": {
            "limit": limit,
            "date_from": date_from,
            "supplier": supplier,
            "status": status
        }
    }

# ============================================================================
# TOOL 2: Search Purchase Orders
# ============================================================================
def search_purchase_orders(search_term, search_field="all", limit=10):
    """
    Search purchase orders by various criteria
    Uses client-side filtering since OData filters may not be supported on all entities

    Args:
        search_term: Term to search for
        search_field: Field to search in (po_number, supplier, all)
        limit: Maximum number of results
    """
    # Fetch orders without filters (more reliable than using OData filters)
    # Fetch more than needed to ensure we have enough results after filtering
    fetch_limit = min(limit * 10, 100)  # Fetch 10x limit but cap at 100

    all_orders = list_purchase_orders(limit=fetch_limit)

    if all_orders.get("status") != "success":
        return all_orders

    orders = all_orders.get("purchase_orders", [])

    # Client-side filtering
    search_term_lower = search_term.lower()
    results = []

    for order in orders:
        po_number = str(order.get("PurchaseOrder", "")).lower()
        supplier = str(order.get("Supplier", "")).lower()

        match = False
        if search_field == "po_number":
            match = search_term_lower in po_number
        elif search_field == "supplier":
            match = search_term_lower in supplier
        elif search_field == "all":
            match = search_term_lower in po_number or search_term_lower in supplier

        if match:
            results.append(order)
            if len(results) >= limit:
                break

    return {
        "status": "success",
        "search_results": results,
        "total_orders": len(results),
        "search_criteria": {
            "search_term": search_term,
            "search_field": search_field,
            "limit": limit
        }
    }

# ============================================================================
# TOOL 3: Get Material Stock
# ============================================================================
def get_material_stock(material_number=None, plant=None, low_stock_only=False, threshold=10):
    """
    Get material stock information

    Args:
        material_number: Specific material to check (optional)
        plant: Filter by plant (optional)
        low_stock_only: Only return items with low stock
        threshold: Stock threshold for low_stock_only filter
    """
    select = [
        "Material", "Plant", "StorageLocation", "MaterialBaseUnit",
        "MatlWrhsStkQtyInMatlBaseUnit", "InventoryStockType"
    ]

    filters = []
    if material_number:
        filters.append(f"Material eq '{material_number}'")
    if plant:
        filters.append(f"Plant eq '{plant}'")
    if low_stock_only:
        filters.append(f"MatlWrhsStkQtyInMatlBaseUnit lt {threshold}")

    filter_str = " and ".join(filters) if filters else None

    # Use A_MatlStkInAcctMod entity for actual stock quantities
    url = _build_url(
        "/sap/opu/odata/sap/API_MATERIAL_STOCK_SRV/A_MatlStkInAcctMod",
        filters=filter_str,
        select=select,
        orderby=None,  # Remove orderby to avoid issues
        top=200  # Increase limit to get more materials
    )

    res = make_sap_request(url)
    if res["status"] != "success":
        # Fallback message if stock API is not available
        return {
            "status": "partial",
            "message": "Stock API may not be available in this SAP system",
            "stock_info": [],
            "note": "Contact SAP administrator to enable stock management APIs"
        }

    parsed = parse_json_entries(res["data"])
    if "parse_error" in parsed:
        return {"status": "error", "message": "Failed to parse response", "details": parsed}

    raw_items = [_clean_entry(e) for e in parsed.get("entries", [])]

    # Normalize field names and filter out empty materials
    stock_items = []
    for item in raw_items:
        material = item.get("Material", "").strip()
        if not material:  # Skip entries with no material
            continue

        stock_items.append({
            "Material": material,
            "Plant": item.get("Plant"),
            "StorageLocation": item.get("StorageLocation"),
            "AvailableQuantity": float(item.get("MatlWrhsStkQtyInMatlBaseUnit", 0)),
            "BaseUnit": item.get("MaterialBaseUnit"),
            "StockType": item.get("InventoryStockType")
        })

    # Calculate totals
    total_available = sum(item.get("AvailableQuantity", 0) for item in stock_items)

    return {
        "status": "success",
        "stock_info": stock_items,
        "total_items": len(stock_items),
        "total_available_quantity": total_available,
        "filters_applied": {
            "material_number": material_number,
            "plant": plant,
            "low_stock_only": low_stock_only,
            "threshold": threshold if low_stock_only else None
        }
    }

# ============================================================================
# TOOL 4: Get Material In-Transit Quantities (INVENTORY-FOCUSED)
# ============================================================================
def get_material_in_transit(material_number=None, limit=200):
    """
    Get materials with quantities in transit (not yet delivered)
    INVENTORY-FOCUSED: Returns material-level view of in-transit quantities

    Args:
        material_number: Specific material to check (optional)
        limit: Maximum number of PO items to check (default 200)

    Returns material-centric data showing:
    - Material number
    - Total quantity in transit
    - Associated purchase orders (if needed)
    """
    # Query WITHOUT $select to avoid 404 errors with delivery status fields
    url = _build_url(
        "/sap/opu/odata/sap/C_PURCHASEORDER_FS_SRV/I_PurchaseOrderItem",
        filters=None,
        select=None,  # Must be None to access IsCompletelyDelivered field
        orderby="PurchaseOrder desc",
        top=limit
    )

    res = make_sap_request(url)
    if res["status"] != "success":
        return res

    parsed = parse_json_entries(res["data"])
    if "parse_error" in parsed:
        return {"status": "error", "message": "Failed to parse response", "details": parsed}

    all_items = [_clean_entry(e) for e in parsed.get("entries", [])]

    # Filter for NOT completely delivered items
    in_transit_items = [
        item for item in all_items
        if item.get('IsCompletelyDelivered') == False
    ]

    # Filter by material if specified
    if material_number:
        material_number = material_number.strip().lstrip('0')
        in_transit_items = [
            item for item in in_transit_items
            if item.get('Material', '').strip().lstrip('0') == material_number
        ]

    # Group by MATERIAL (inventory-focused)
    by_material = {}
    for item in in_transit_items:
        mat = item.get('Material')
        if mat not in by_material:
            by_material[mat] = {
                'material': mat,
                'total_in_transit_qty': 0,
                'unit': item.get('PurchaseOrderQuantityUnit'),
                'related_orders': []
            }

        qty = float(item.get('OrderQuantity', 0))
        by_material[mat]['total_in_transit_qty'] += qty
        by_material[mat]['related_orders'].append({
            'purchase_order': item.get('PurchaseOrder'),
            'item': item.get('PurchaseOrderItem'),
            'quantity': qty,
            'is_invoiced': item.get('IsFinallyInvoiced')
        })

    materials_in_transit = list(by_material.values())

    return {
        "status": "success",
        "materials_in_transit": materials_in_transit,
        "total_materials": len(materials_in_transit),
        "note": "Showing materials with quantities in transit (IsCompletelyDelivered = False). This is inventory-focused view."
    }

# ============================================================================
# TOOL 5: Get Orders in Transit/Delivery (ORDER-FOCUSED)
# ============================================================================
def get_orders_in_transit(limit=20):
    """
    Get purchase orders that have items in transit (not yet completely delivered)
    ORDER-FOCUSED: Returns order-level view with items pending delivery

    Args:
        limit: Maximum number of PO items to check (default 20)

    Returns order-centric data showing:
    - Purchase order number
    - Supplier
    - Number of items in transit
    - Total items
    - List of materials pending delivery
    """
    # Query items WITHOUT $select to access IsCompletelyDelivered field
    url = _build_url(
        "/sap/opu/odata/sap/C_PURCHASEORDER_FS_SRV/I_PurchaseOrderItem",
        filters=None,
        select=None,  # Must be None to access IsCompletelyDelivered field
        orderby="PurchaseOrder desc",
        top=200  # Check more items to find orders with pending deliveries
    )

    res = make_sap_request(url)
    if res["status"] != "success":
        return res

    parsed = parse_json_entries(res["data"])
    if "parse_error" in parsed:
        return {"status": "error", "message": "Failed to parse response", "details": parsed}

    all_items = [_clean_entry(e) for e in parsed.get("entries", [])]

    # Filter for NOT completely delivered items
    in_transit_items = [
        item for item in all_items
        if item.get('IsCompletelyDelivered') == False
    ]

    # Group by PURCHASE ORDER (order-focused)
    by_order = {}
    for item in in_transit_items:
        po = item.get('PurchaseOrder')
        if po not in by_order:
            by_order[po] = {
                'purchase_order': po,
                'supplier': item.get('Supplier'),
                'currency': item.get('DocumentCurrency'),
                'items_in_transit': [],
                'total_in_transit_items': 0
            }

        by_order[po]['items_in_transit'].append({
            'item': item.get('PurchaseOrderItem'),
            'material': item.get('Material'),
            'material_description': item.get('PurchaseOrderItemText'),
            'quantity': float(item.get('OrderQuantity', 0)),
            'unit': item.get('PurchaseOrderQuantityUnit'),
            'is_invoiced': item.get('IsFinallyInvoiced')
        })
        by_order[po]['total_in_transit_items'] += 1

    orders_in_transit = list(by_order.values())

    # Limit the number of orders returned
    orders_in_transit = orders_in_transit[:limit]

    return {
        "status": "success",
        "orders_in_transit": orders_in_transit,
        "total_orders": len(orders_in_transit),
        "note": "Showing orders with items not completely delivered (IsCompletelyDelivered = False). This is order-focused view."
    }

# ============================================================================
# TOOL 5: Get Goods Receipts (Material Documents)
# ============================================================================
def get_goods_receipts(po_number=None, material_number=None, limit=50):
    """
    Get goods receipt information from Material Documents API
    Shows what has been received against purchase orders

    Args:
        po_number: Filter by specific purchase order
        material_number: Filter by material number
        limit: Maximum number of records to return
    """
    select = [
        "MaterialDocument", "MaterialDocumentYear", "MaterialDocumentItem",
        "Material", "Plant", "StorageLocation", "GoodsMovementType",
        "QuantityInEntryUnit", "EntryUnit", "PurchaseOrder", "PurchaseOrderItem",
        "PostingDate", "DocumentDate", "MaterialDocumentHeaderText"
    ]

    filters = []
    # Filter for goods receipts (movement type 101)
    filters.append("GoodsMovementType eq '101'")

    if po_number:
        filters.append(f"PurchaseOrder eq '{po_number}'")
    if material_number:
        filters.append(f"Material eq '{material_number}'")

    filter_str = " and ".join(filters) if filters else None

    # Try both possible service names
    # Technical name from SAP docs: API_MATERIAL_DOCUMENT
    # Common variation: API_MATERIAL_DOCUMENT_SRV
    url = _build_url(
        "/sap/opu/odata/sap/API_MATERIAL_DOCUMENT_SRV/A_MaterialDocumentItem",
        filters=filter_str,
        select=select,
        orderby=None,  # Remove orderby to avoid potential issues
        top=limit
    )

    res = make_sap_request(url)
    if res["status"] != "success":
        return {
            "status": "partial",
            "message": "Material Document API may not be available in this SAP system",
            "goods_receipts": [],
            "note": "Contact SAP administrator to enable Material Document APIs"
        }

    parsed = parse_json_entries(res["data"])
    if "parse_error" in parsed:
        return {"status": "error", "message": "Failed to parse response", "details": parsed}

    receipts = [_clean_entry(e) for e in parsed.get("entries", [])]

    # Calculate summary
    total_received = sum(item.get("QuantityInEntryUnit", 0) for item in receipts)

    return {
        "status": "success",
        "goods_receipts": receipts,
        "total_records": len(receipts),
        "total_quantity_received": total_received,
        "filters_applied": {
            "po_number": po_number,
            "material_number": material_number,
            "limit": limit
        }
    }

# ============================================================================
# TOOL 6: Get Open Purchase Orders (simplified for demo system)
# ============================================================================
def get_open_purchase_orders(limit=50):
    """
    Get recent purchase orders (potentially open orders)

    NOTE: Without Material Document API, we return recent POs as they are likely
    still open. In production with Material Document API, this would compare
    ordered vs received quantities.

    Args:
        limit: Maximum number of orders to return
    """
    # Get recent purchase orders (these are likely still open)
    po_result = list_purchase_orders(limit=limit)

    if po_result.get("status") != "success":
        return {
            "status": "error",
            "message": "Could not retrieve purchase orders",
            "details": po_result.get("message"),
            "open_purchase_orders": [],
            "total_open_orders": 0
        }

    po_list = po_result.get("purchase_orders", [])

    if not po_list:
        return {
            "status": "success",
            "open_purchase_orders": [],
            "total_open_orders": 0,
            "note": "No purchase orders found"
        }

    # Format as "open" orders (without goods receipt comparison since API not available)
    open_orders = []
    for po in po_list:
        open_orders.append({
            "purchase_order": po.get("PurchaseOrder"),
            "supplier": po.get("Supplier"),
            "order_date": po.get("PurchaseOrderDate"),
            "purchasing_org": po.get("PurchasingOrganization"),
            "currency": po.get("DocumentCurrency"),
            "status": "Potentially Open (goods receipt data not available)"
        })

    return {
        "status": "success",
        "open_purchase_orders": open_orders,
        "total_open_orders": len(open_orders),
        "note": "Material Document API not available. Showing recent purchase orders which are likely still open. To get actual open/closed status with ordered vs received quantities, enable API_MATERIAL_DOCUMENT_SRV in SAP system."
    }

# ============================================================================
# TOOL 7: Get Inventory with Open Orders
# ============================================================================
def get_inventory_with_open_orders(threshold=10):
    """
    Cross-reference inventory stock with open purchase orders
    Shows materials that have stock AND have open purchase orders

    Args:
        threshold: Minimum stock threshold to consider
    """
    # Get stock info
    stock_res = get_material_stock(low_stock_only=False)
    if stock_res.get("status") != "success":
        return {
            "status": "partial",
            "message": "Could not retrieve stock information",
            "inventory_with_orders": []
        }

    stock_items = stock_res.get("stock_info", [])

    # Get open orders
    open_orders_res = get_open_purchase_orders(limit=100)
    if open_orders_res.get("status") != "success":
        return {
            "status": "partial",
            "message": "Could not retrieve open orders",
            "inventory_with_orders": []
        }

    # Build material->orders map
    material_orders = {}
    for order in open_orders_res.get("open_purchase_orders", []):
        for item in order.get("items", []):
            material = item.get("material")
            if material not in material_orders:
                material_orders[material] = []
            material_orders[material].append({
                "purchase_order": order["purchase_order"],
                "supplier": order["supplier"],
                "order_date": order["order_date"],
                "open_quantity": item["open_quantity"],
                "unit": item["unit"]
            })

    # Cross-reference: materials with stock AND open orders
    inventory_with_orders = []
    for stock_item in stock_items:
        material = stock_item.get("Material")
        available_qty = stock_item.get("AvailableQuantity", 0)

        if material in material_orders:
            open_orders = material_orders[material]
            total_open_qty = sum(o["open_quantity"] for o in open_orders)

            inventory_with_orders.append({
                "material": material,
                "description": stock_item.get("MaterialDescription"),
                "plant": stock_item.get("Plant"),
                "storage_location": stock_item.get("StorageLocation"),
                "available_quantity": available_qty,
                "unit": stock_item.get("BaseUnit"),
                "total_open_quantity": total_open_qty,
                "open_orders_count": len(open_orders),
                "open_orders": open_orders
            })

    return {
        "status": "success",
        "inventory_with_open_orders": inventory_with_orders,
        "total_materials": len(inventory_with_orders),
        "note": "These materials have both current stock and pending purchase orders"
    }

# ============================================================================
# TOOL 8: Get Orders Awaiting Invoice or Delivery
# ============================================================================
def get_orders_awaiting_invoice_or_delivery(limit=100, filter_type="all"):
    """
    Get purchase order items that are not fully delivered or not invoiced
    Returns BOTH total counts across entire dataset AND detailed items (up to limit)

    Args:
        limit: Maximum number of items to return
        filter_type: Filter by status - "not_delivered", "not_invoiced", or "all"
    """
    # Keep field list short to avoid URL length issues (SAP has ~290 char limit max)
    select = [
        "PurchaseOrder", "PurchaseOrderItem", "Material",
        "OrderQuantity", "PurchaseOrderQuantityUnit",
        "IsCompletelyDelivered", "IsFinallyInvoiced"
    ]

    # Build filter based on delivery and invoice status
    # Note: For "all" we just get recent items and filter in code since SAP OData
    # has limited support for complex OR filters
    filters = []
    if filter_type == "not_delivered":
        filters.append("IsCompletelyDelivered eq false")
    elif filter_type == "not_invoiced":
        filters.append("IsFinallyInvoiced eq false")
    # For "all" type, don't add filter - we'll filter in code

    filter_str = " and ".join(filters) if filters else None

    # FIRST: Fetch a larger dataset (300 items) with minimal fields to get full context
    # We need this to accurately report "X out of Y total" and identify patterns
    # NOTE: Keep fields minimal to avoid SAP URL length limit (~250 chars max)
    # SAP rejects requests with Supplier field at top=500, so using top=300 and 3 fields only
    analysis_url = _build_url(
        "/sap/opu/odata/sap/C_PURCHASEORDER_FS_SRV/I_PurchaseOrderItem",
        filters=None,  # Get all items, filter in code
        select=["PurchaseOrder", "IsCompletelyDelivered", "IsFinallyInvoiced"],
        orderby="PurchaseOrder desc",
        top=300  # Max that works reliably with SAP URL limits
    )

    analysis_res = make_sap_request(analysis_url, timeout=60, retries=2)
    total_items_in_system = 0
    all_items_sample = []

    if analysis_res["status"] == "success":
        parsed_analysis = parse_json_entries(analysis_res["data"])
        all_items_sample = [_clean_entry(e) for e in parsed_analysis.get("entries", [])]
        total_items_in_system = len(all_items_sample)
        # If we got 300, there may be more - note this in response
        if total_items_in_system == 300:
            total_items_in_system = "300+"  # Indicate there are more

    # SECOND: Get detailed data for the items we'll show to user (with full fields)
    url = _build_url(
        "/sap/opu/odata/sap/C_PURCHASEORDER_FS_SRV/I_PurchaseOrderItem",
        filters=filter_str,
        select=select,
        orderby="PurchaseOrder desc",
        top=limit
    )

    res = make_sap_request(url, timeout=45, retries=2)
    if res["status"] != "success":
        return {
            "status": "error",
            "message": "Could not retrieve purchase order items",
            "details": res.get("message")
        }

    parsed = parse_json_entries(res["data"])
    if "parse_error" in parsed:
        return {
            "status": "error",
            "message": "Failed to parse response",
            "details": parsed
        }

    items = [_clean_entry(e) for e in parsed.get("entries", [])]

    # Analyze the FULL sample (300 items) to get accurate counts and patterns
    total_not_delivered = 0
    total_not_invoiced = 0
    total_both_pending = 0
    po_numbers_with_issues = set()

    for item in all_items_sample:
        is_delivered = item.get("IsCompletelyDelivered") in [True, "true", "X"]
        is_invoiced = item.get("IsFinallyInvoiced") in [True, "true", "X"]
        po_number = item.get("PurchaseOrder", "")

        if not is_delivered and not is_invoiced:
            total_both_pending += 1
            po_numbers_with_issues.add(po_number)
        elif not is_delivered:
            total_not_delivered += 1
        elif not is_invoiced:
            total_not_invoiced += 1

    # Categorize detailed items to show user (from limited query)
    not_delivered = []
    not_invoiced = []
    both_pending = []

    for item in items:
        is_delivered = item.get("IsCompletelyDelivered") in [True, "true", "X"]
        is_invoiced = item.get("IsFinallyInvoiced") in [True, "true", "X"]

        item_data = {
            "purchase_order": item.get("PurchaseOrder"),
            "item": item.get("PurchaseOrderItem"),
            "material": item.get("Material"),
            "quantity": item.get("OrderQuantity"),
            "unit": item.get("PurchaseOrderQuantityUnit"),
            "is_delivered": is_delivered,
            "is_invoiced": is_invoiced
        }

        if not is_delivered and not is_invoiced:
            both_pending.append(item_data)
        elif not is_delivered:
            not_delivered.append(item_data)
        elif not is_invoiced:
            not_invoiced.append(item_data)

    # Pattern analysis from full sample
    patterns = {
        "unique_po_numbers": sorted(list(po_numbers_with_issues))[:15],  # Show first 15 POs
        "total_unique_pos": len(po_numbers_with_issues),
        "percentage_with_issues": round(total_both_pending/len(all_items_sample)*100 if len(all_items_sample) > 0 else 0, 1)
    }

    return {
        "status": "success",
        "total_items_in_system": total_items_in_system,
        "items_analyzed_for_detailed_view": len(items),
        "items_awaiting_delivery": not_delivered,
        "items_awaiting_invoice": not_invoiced,
        "items_awaiting_both": both_pending,
        "summary": {
            "total_items_in_system": total_items_in_system,
            "total_not_delivered": total_not_delivered,
            "total_not_invoiced": total_not_invoiced,
            "total_both_pending": total_both_pending,
            "patterns": patterns
        },
        "note": f"Analyzed {len(all_items_sample)} items from the system. Found {total_both_pending} items ({round(total_both_pending/len(all_items_sample)*100 if len(all_items_sample) > 0 else 0, 1)}%) with neither delivery nor invoice."
    }

# ============================================================================
# Lambda Handler
# ============================================================================
def lambda_handler(event, context):
    """Handle MCP tool invocations from AgentCore Gateway

    According to AWS docs, the Gateway sends:
    - event: A flat dict of tool parameters (e.g., {"limit": 20, "status": "open"})
    - context: Contains bedrockAgentCoreToolName in format "target-name___tool-name"
    """
    logger.info("event=%s", json.dumps(event))
    logger.info("context=%s", str(context))

    try:
        # Extract tool name from context (AgentCore Gateway format)
        # Tool name format: "sap-tools-target___get_orders_in_transit"
        full_tool_name = None
        if hasattr(context, 'client_context') and context.client_context:
            custom = getattr(context.client_context, 'custom', {})
            if isinstance(custom, dict):
                full_tool_name = custom.get('bedrockAgentCoreToolName', '')

        # If not in context, fallback to checking event for backwards compatibility
        if not full_tool_name:
            full_tool_name = event.get('bedrockAgentCoreToolName', '')

        # Strip target prefix using ___ delimiter (as per AWS docs)
        if '___' in full_tool_name:
            tool_name = full_tool_name.split('___')[-1]
        else:
            tool_name = full_tool_name

        # Parameters are passed directly in the event as a flat dict
        params = event

        logger.info(f"Tool: {tool_name}, Params: {params}")

        # Route to appropriate tool
        result = None
        if tool_name == "list_purchase_orders":
            result = list_purchase_orders(
                limit=int(params.get("limit", 20)),
                date_from=params.get("date_from"),
                supplier=params.get("supplier"),
                status=params.get("status")
            )
        elif tool_name == "search_purchase_orders":
            result = search_purchase_orders(
                search_term=params.get("search_term", ""),
                search_field=params.get("search_field", "all"),
                limit=int(params.get("limit", 10))
            )
        elif tool_name == "get_material_stock":
            result = get_material_stock(
                material_number=params.get("material_number"),
                plant=params.get("plant"),
                low_stock_only=params.get("low_stock_only", False),
                threshold=int(params.get("threshold", 10))
            )
        elif tool_name == "get_material_in_transit":
            result = get_material_in_transit(
                material_number=params.get("material_number"),
                limit=int(params.get("limit", 200))
            )
        elif tool_name == "get_orders_in_transit":
            result = get_orders_in_transit(
                limit=int(params.get("limit", 20))
            )
        elif tool_name == "get_goods_receipts":
            result = get_goods_receipts(
                po_number=params.get("po_number"),
                material_number=params.get("material_number"),
                limit=int(params.get("limit", 50))
            )
        elif tool_name == "get_open_purchase_orders":
            result = get_open_purchase_orders(
                limit=int(params.get("limit", 50))
            )
        elif tool_name == "get_inventory_with_open_orders":
            result = get_inventory_with_open_orders(
                threshold=int(params.get("threshold", 10))
            )
        elif tool_name == "get_orders_awaiting_invoice_or_delivery":
            result = get_orders_awaiting_invoice_or_delivery(
                limit=int(params.get("limit", 100)),
                filter_type=params.get("filter_type", "all")
            )
        else:
            result = {
                "status": "error",
                "message": f"Unknown tool: {tool_name}",
                "available_tools": [
                    "list_purchase_orders",
                    "search_purchase_orders",
                    "get_material_stock",
                    "get_material_in_transit",
                    "get_orders_in_transit",
                    "get_goods_receipts",
                    "get_open_purchase_orders",
                    "get_inventory_with_open_orders",
                    "get_orders_awaiting_invoice_or_delivery"
                ]
            }

        # For AgentCore Gateway, simply return the result dict
        # The Gateway handles the wrapping and formatting
        logger.info("response=%s", json.dumps(result))
        return result

    except Exception as e:
        logger.error(f"Error: {e}", exc_info=True)
        # Return error as a simple dict
        error_response = {
            "status": "error",
            "error": str(e),
            "error_type": type(e).__name__
        }
        logger.error("error=%s", json.dumps(error_response))
        return error_response

if __name__ == "__main__":
    # Test locally
    test_event = {
        "apiPath": "/list_purchase_orders",
        "requestBody": {
            "content": {
                "application/json": {
                    "properties": [
                        {"name": "limit", "value": "10"}
                    ]
                }
            }
        }
    }
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))
