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

    Args:
        search_term: Term to search for
        search_field: Field to search in (po_number, supplier, material, all)
        limit: Maximum number of results
    """
    # For now, search in PO items to find materials
    select = [
        "PurchaseOrder", "PurchaseOrderItem", "Material",
        "PurchaseOrderItemText", "Supplier", "DocumentCurrency",
        "OrderQuantity", "NetAmount", "PurchaseOrderDate"
    ]

    filters = None
    if search_field == "po_number":
        filters = f"PurchaseOrder eq '{search_term}'"
    elif search_field == "supplier":
        filters = f"substringof('{search_term}', Supplier)"
    elif search_field == "material":
        filters = f"Material eq '{search_term}'"

    url = _build_url(
        "/sap/opu/odata/sap/C_PURCHASEORDER_FS_SRV/I_PurchaseOrderItem",
        filters=filters,
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

    results = [_clean_entry(e) for e in parsed.get("entries", [])]

    # Group by PO number
    orders_dict = {}
    for item in results:
        po = item.get("PurchaseOrder")
        if po not in orders_dict:
            orders_dict[po] = {
                "purchase_order": po,
                "supplier": item.get("Supplier"),
                "currency": item.get("DocumentCurrency"),
                "date": item.get("PurchaseOrderDate"),
                "items": []
            }
        orders_dict[po]["items"].append({
            "item": item.get("PurchaseOrderItem"),
            "material": item.get("Material"),
            "description": item.get("PurchaseOrderItemText"),
            "quantity": item.get("OrderQuantity"),
            "net_amount": item.get("NetAmount")
        })

    return {
        "status": "success",
        "search_results": list(orders_dict.values()),
        "total_orders": len(orders_dict),
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
        "Material", "Plant", "StorageLocation", "MaterialDescription",
        "AvailableQuantity", "QuantityOnHand", "BaseUnit"
    ]

    filters = []
    if material_number:
        filters.append(f"Material eq '{material_number}'")
    if plant:
        filters.append(f"Plant eq '{plant}'")
    if low_stock_only:
        filters.append(f"AvailableQuantity lt {threshold}")

    filter_str = " and ".join(filters) if filters else None

    # Note: This endpoint may not exist in all SAP systems
    # Adjust the path based on your SAP system
    url = _build_url(
        "/sap/opu/odata/sap/API_MATERIAL_STOCK_SRV/A_MaterialStock",
        filters=filter_str,
        select=select,
        orderby="AvailableQuantity asc",
        top=50
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

    stock_items = [_clean_entry(e) for e in parsed.get("entries", [])]

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
# TOOL 4: Get Orders in Transit/Delivery
# ============================================================================
def get_orders_in_transit(limit=20):
    """
    Get purchase orders that are in transit/delivery
    This checks for orders with pending deliveries

    Args:
        limit: Maximum number of orders to return
    """
    # Get recent POs (within last 90 days)
    date_from = (datetime.now() - timedelta(days=90)).strftime("%Y-%m-%d")

    select = [
        "PurchaseOrder", "Supplier", "DocumentCurrency",
        "PurchaseOrderDate", "CreationDate", "PurchasingOrganization"
    ]

    filters = f"PurchaseOrderDate ge datetime'{date_from}T00:00:00'"

    url = _build_url(
        "/sap/opu/odata/sap/C_PURCHASEORDER_FS_SRV/I_PurchaseOrder",
        filters=filters,
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
        "orders_in_transit": orders,
        "total_count": len(orders),
        "date_range": {
            "from": date_from,
            "to": datetime.now().strftime("%Y-%m-%d")
        },
        "note": "These are recent purchase orders. For actual delivery status, check goods receipt data."
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
        elif tool_name == "get_orders_in_transit":
            result = get_orders_in_transit(
                limit=int(params.get("limit", 20))
            )
        else:
            result = {
                "status": "error",
                "message": f"Unknown tool: {tool_name}",
                "available_tools": [
                    "list_purchase_orders",
                    "search_purchase_orders",
                    "get_material_stock",
                    "get_orders_in_transit"
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
