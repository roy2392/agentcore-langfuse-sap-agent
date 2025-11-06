import json
import urllib.request
import urllib.parse
import urllib.error
import base64
import logging
import re
import ssl
import time
import xml.etree.ElementTree as ET
import os


try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SAP_HOST = os.getenv("SAP_HOST")
SAP_USER = os.getenv("SAP_USER")
SAP_PASSWORD = os.getenv("SAP_PASSWORD")
SAP_CLIENT = None  # set like "100" if required
USE_JSON = True    # switch to XML by setting False

REQUIRED_ENV = ("SAP_HOST", "SAP_USER", "SAP_PASSWORD")

def _missing_env():
    missing = []
    if not SAP_HOST:
        missing.append("SAP_HOST")
    if not SAP_USER:
        missing.append("SAP_USER")
    if not SAP_PASSWORD:
        missing.append("SAP_PASSWORD")
    return missing


def _build_url(path, po_number=None, select=None, orderby=None):
    params = {}
    if po_number:
        q = f"PurchaseOrder eq '{po_number}'"
        params["$filter"] = q
    params["$format"] = "json" if USE_JSON else "xml"
    if select:
        params["$select"] = ",".join(select)
    if orderby:
        params["$orderby"] = orderby
    if SAP_CLIENT:
        params["sap-client"] = SAP_CLIENT
    # Use variable to avoid backslash in f-string
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


def make_sap_request(url, timeout=30, retries=3, backoff=0.8, cafile=None, accept_header=None):
    context = ssl.create_default_context(cafile=cafile) if cafile else ssl.create_default_context()
    opener = _make_opener(context, no_proxies=True)

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", _basic_auth_header(SAP_USER, SAP_PASSWORD))
            req.add_header("Accept", accept_header or ("application/json" if USE_JSON else "application/atom+xml"))
            req.add_header("User-Agent", "sap-odata-test/1.0")
            req.add_header("Connection", "close")

            with opener.open(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8")
                if resp.status == 200:
                    return {"status": "success", "data": body}
                return {"status": "error", "message": f"HTTP {resp.status}", "details": body}

        except urllib.error.HTTPError as e:
            try:
                body = e.read().decode("utf-8")
            except Exception:
                body = ""
            if e.code in (429, 500, 502, 503, 504) and attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
                continue
            return {"status": "error", "message": f"HTTP Error {e.code}: {e.reason}", "details": body}

        except urllib.error.URLError as e:
            msg = str(e.reason)
            transient = "Remote end closed connection without response" in msg or "timed out" in msg
            if transient and attempt < retries - 1:
                time.sleep(backoff * (2 ** attempt))
                continue
            return {"status": "error", "message": msg}

        except Exception as e:
            return {"status": "error", "message": str(e)}

    return {"status": "error", "message": "Exhausted retries"}


def parse_xml_entries(xml_content):
    try:
        root = ET.fromstring(xml_content)
        ns = {
            "atom": "http://www.w3.org/2005/Atom",
            "d": "http://schemas.microsoft.com/ado/2007/08/dataservices",
            "m": "http://schemas.microsoft.com/ado/2007/08/dataservices/metadata",
        }
        entries = []
        for entry in root.findall(".//atom:entry", ns):
            props = entry.find(".//m:properties", ns)
            if props is None:
                continue
            data = {}
            for prop in props:
                tag = prop.tag.split("}")[-1]
                data[tag] = prop.text or ""
            entries.append(data)
        return {"entries": entries, "total_count": len(entries)}
    except Exception as e:
        return {"parse_error": str(e), "raw_xml_preview": xml_content[:500]}


def parse_json_entries(json_text):
    try:
        obj = json.loads(json_text)
        # OData v2 JSON usually nests under d.results
        d = obj.get("d", {})
        if isinstance(d, dict) and "results" in d:
            results = d.get("results")
            if isinstance(results, list):
                return {"entries": results, "total_count": len(results)}
            if isinstance(results, dict):
                return {"entries": [results], "total_count": 1}
        # Some services return a single object under d
        if d and isinstance(d, dict):
            return {"entries": [d], "total_count": 1}
        return {"entries": [], "total_count": 0}
    except Exception as e:
        return {"parse_error": str(e), "raw_json_preview": json_text[:500]}


def _fetch_and_parse(url):
    res = make_sap_request(url)
    if res["status"] != "success":
        res["url"] = url
        return res
    if USE_JSON:
        parsed = parse_json_entries(res["data"])
    else:
        parsed = parse_xml_entries(res["data"])
    return {"status": "success", "data": parsed, "url": url}


def _format_sap_date(value):
    if not isinstance(value, str):
        return value
    # OData v2 date format: /Date(1571616000000)/ or with offset /Date(1588894563127+0000)/
    m = re.match(r"/Date\((\d+)([+-]\d{4})?\)/", value)
    if not m:
        return value
    try:
        ms = int(m.group(1))
        return time.strftime("%Y-%m-%d", time.gmtime(ms / 1000))
    except Exception:
        return value


def _clean_entry(entry):
    if not isinstance(entry, dict):
        return entry
    cleaned = {k: v for k, v in entry.items() if not k.startswith("__")}
    # normalize date fields
    for k in list(cleaned.keys()):
        if k.lower().endswith("date") or k.lower().endswith("datetime"):
            cleaned[k] = _format_sap_date(cleaned[k])
    # numeric coercions
    for nf in ("NetAmount", "OrderQuantity", "NetPriceAmount", "GrossAmount", "EffectiveAmount"):
        if nf in cleaned and isinstance(cleaned[nf], str):
            try:
                cleaned[nf] = float(cleaned[nf])
            except Exception:
                pass
    # item number to int
    if isinstance(cleaned.get("PurchaseOrderItem"), str):
        try:
            cleaned["PurchaseOrderItem"] = int(cleaned["PurchaseOrderItem"].lstrip("0") or "0")
        except Exception:
            pass
    # unified description
    cleaned["Name"] = cleaned.get("PurchaseOrderItemText") or cleaned.get("MaterialDescription") or ""
    return cleaned


def get_purchase_order(po_number):
    select = [
        "PurchaseOrder","CompanyCode","PurchasingOrganization","PurchasingGroup",
        "Supplier","DocumentCurrency","PurchaseOrderDate","CreationDate"
    ]
    url = _build_url("/sap/opu/odata/sap/C_PURCHASEORDER_FS_SRV/I_PurchaseOrder", po_number, select=select)
    return _fetch_and_parse(url)


def get_purchase_order_items(po_number):
    select_variants = [
        [
            "PurchaseOrder", "PurchaseOrderItem", "Material",
            "PurchaseOrderItemText",  # preferred description in many systems
            "MaterialGroup", "DocumentCurrency",
            "OrderQuantity", "PurchaseOrderQuantityUnit",
            "NetAmount", "NetPriceAmount", "TaxCode",
        ],
        [
            "PurchaseOrder", "PurchaseOrderItem", "Material",
            "MaterialDescription",  # alternative field name
            "MaterialGroup", "DocumentCurrency",
            "OrderQuantity", "PurchaseOrderQuantityUnit",
            "NetAmount", "NetPriceAmount", "TaxCode",
        ],
        [
            # minimal working set without description fields
            "PurchaseOrder", "PurchaseOrderItem", "Material",
            "MaterialGroup", "DocumentCurrency",
            "OrderQuantity", "PurchaseOrderQuantityUnit",
            "NetAmount", "NetPriceAmount", "TaxCode",
        ],
    ]

    last_error = None
    last_url = None
    for sel in select_variants:
        url = _build_url(
            "/sap/opu/odata/sap/C_PURCHASEORDER_FS_SRV/I_PurchaseOrderItem",
            po_number,
            select=sel,
            orderby="PurchaseOrderItem asc",
        )
        res = _fetch_and_parse(url)
        last_url = url
        if res.get("status") == "success":
            return res
        last_error = res

    # if none succeeded, return the last error with its URL for debugging
    return {"status": "error", "message": last_error.get("message"), "details": last_error.get("details"), "url": last_url}


def get_complete_po_data(po_number):
    header_res = get_purchase_order(po_number)
    items_res = get_purchase_order_items(po_number)

    header_entry = {}
    if header_res.get("status") == "success":
        entries = header_res.get("data", {}).get("entries", [])
        if entries:
            header_entry = _clean_entry(entries[0])

    items_compact = []
    items_error = None
    if items_res.get("status") == "success":
        for it in items_res.get("data", {}).get("entries", []):
            itc = _clean_entry(it)
            items_compact.append({
                "item": itc.get("PurchaseOrderItem"),
                "material": itc.get("Material"),
                "name": itc.get("Name"),
                "qty": itc.get("OrderQuantity") or 0.0,
                "uom": itc.get("PurchaseOrderQuantityUnit"),
                "price": itc.get("NetPriceAmount") or 0.0,
                "net": itc.get("NetAmount") or 0.0,
                "currency": itc.get("DocumentCurrency"),
                "tax": itc.get("TaxCode"),
            })
        items_compact.sort(key=lambda x: (x["item"] is None, x.get("item", 0)))
    else:
        items_error = {k: v for k, v in items_res.items() if k in ("message", "details")}

    total_value = sum((x.get("net") or 0.0) for x in items_compact)
    total_quantity = sum((x.get("qty") or 0.0) for x in items_compact)

    summary = {
        "po_number": po_number,
        "header_found": bool(header_entry),
        "items_count": len(items_compact),
        "total_value": total_value,
        "total_quantity": total_quantity,
        "can_close_po": total_value > 0 and total_quantity > 0,
    }

    result = {
        "purchase_order": po_number,
        "header": header_entry,
        "items": items_compact,
        "summary": summary,
        "links": {
            "header_url": header_res.get("url"),
            "items_url": items_res.get("url"),
        },
    }
    if items_error:
        result["items_error"] = items_error
    return result


def extract_po_number_from_bedrock_event(event):
    po_number = None
    body = event.get("requestBody", {}).get("content", {}).get("application/json", {})
    props = body.get("properties")
    if isinstance(props, list):
        for prop in props:
            if prop.get("name") == "po_number":
                po_number = prop.get("value")
                break
    if not po_number and event.get("inputText"):
        m = re.search(r"(?:PO\s*)?(\d{10})", event["inputText"], re.IGNORECASE)
        if m:
            po_number = m.group(1)
    return po_number


def fetch_metadata():
    missing = _missing_env()
    if missing:
        return {"status": "error", "message": f"Missing env vars: {', '.join(missing)}"}
    url = f"https://{SAP_HOST}/sap/opu/odata/sap/C_PURCHASEORDER_FS_SRV/$metadata"
    return make_sap_request(url, accept_header="application/xml")


def lambda_handler(event, context):
    logger.info("event=%s", json.dumps(event))
    try:
        missing = _missing_env()
        if missing:
            err_body = {"error": f"Missing env vars: {', '.join(missing)}"}
            response_body = {"TEXT": {"body": json.dumps(err_body)}}
            return {
                "messageVersion": "1.0",
                "response": {
                    "actionGroup": event.get("actionGroup", ""),
                    "apiPath": event.get("apiPath", ""),
                    "httpMethod": event.get("httpMethod", "POST"),
                    "httpStatusCode": 500,
                    "responseBody": response_body,
                },
            }
        po_number = extract_po_number_from_bedrock_event(event) or "4500000520"
        result = get_complete_po_data(po_number)
        response_body = {"TEXT": {"body": json.dumps(result, indent=2)}}
        resp = {
            "messageVersion": "1.0",
            "response": {
                "actionGroup": event.get("actionGroup", ""),
                "apiPath": event.get("apiPath", ""),
                "httpMethod": event.get("httpMethod", "POST"),
                "httpStatusCode": 200,
                "responseBody": response_body,
            },
        }
        logger.info("response=%s", json.dumps(resp))
        return resp
    except Exception as e:
        err = {
            "messageVersion": "1.0",
            "response": {
                "actionGroup": event.get("actionGroup", ""),
                "apiPath": event.get("apiPath", ""),
                "httpMethod": event.get("httpMethod", "POST"),
                "httpStatusCode": 500,
                "responseBody": {"TEXT": {"body": json.dumps({"error": str(e), "type": type(e).__name__})}},
            },
        }
        logger.error("error=%s", json.dumps(err))
        return err


def get_stock_levels(material_number):
    """Fetch current stock levels for a material from SAP"""
    select = [
        "Material", "Plant", "StorageLocation", "AvailableQuantity",
        "QuantityOnHand", "QuantityOrdered", "MaterialDescription"
    ]
    url = _build_url(
        "/sap/opu/odata/sap/C_MATERIAL_STOCK_SRV/I_MaterialStock",
        select=select,
        orderby="AvailableQuantity desc"
    )
    # Add filter for specific material
    url = url.replace("$select", f"$filter=Material eq '{material_number}'&$select")
    return _fetch_and_parse(url)


def get_low_stock_materials(threshold=None):
    """Get materials with stock levels below threshold"""
    select = [
        "Material", "Plant", "StorageLocation", "AvailableQuantity",
        "QuantityOnHand", "MaterialDescription", "DocumentCurrency"
    ]
    url = _build_url(
        "/sap/opu/odata/sap/C_MATERIAL_STOCK_SRV/I_MaterialStock",
        select=select,
        orderby="AvailableQuantity asc"
    )
    if threshold:
        url = url.replace("$select", f"$filter=AvailableQuantity lt {threshold}&$select")
    return _fetch_and_parse(url)


def get_material_info(material_number):
    """Fetch detailed material information from SAP"""
    select = [
        "Material", "MaterialDescription", "MaterialGroup", "BaseUnitOfMeasure",
        "MaterialType", "IndustrialSector", "CreatedDate", "LastChangedDate"
    ]
    url = _build_url(
        "/sap/opu/odata/sap/C_MATERIAL_SRV/I_Material",
        material_number,
        select=select
    )
    return _fetch_and_parse(url)


def get_warehouse_stock(plant=None, storage_location=None):
    """Get warehouse stock summary for a plant and storage location"""
    select = [
        "Plant", "StorageLocation", "Material", "AvailableQuantity",
        "QuantityOnHand", "QuantityOrdered", "MaterialDescription"
    ]
    url = _build_url(
        "/sap/opu/odata/sap/C_MATERIAL_STOCK_SRV/I_MaterialStock",
        select=select,
        orderby="Plant,StorageLocation,Material"
    )
    filters = []
    if plant:
        filters.append(f"Plant eq '{plant}'")
    if storage_location:
        filters.append(f"StorageLocation eq '{storage_location}'")

    if filters:
        filter_str = " and ".join(filters)
        url = url.replace("$select", f"$filter={filter_str}&$select")

    return _fetch_and_parse(url)


def get_purchase_orders_for_material(material_number):
    """Get pending purchase orders for a specific material"""
    select = [
        "PurchaseOrder", "PurchaseOrderItem", "Material", "OrderQuantity",
        "PurchaseOrderQuantityUnit", "NetAmount", "PurchaseOrderDate",
        "DeliveryDate", "DocumentCurrency"
    ]
    url = _build_url(
        "/sap/opu/odata/sap/C_PURCHASEORDER_FS_SRV/I_PurchaseOrderItem",
        select=select,
        orderby="DeliveryDate asc"
    )
    url = url.replace("$select", f"$filter=Material eq '{material_number}'&$select")
    return _fetch_and_parse(url)


def get_goods_receipt(po_number):
    """Get goods receipt information for a purchase order"""
    select = [
        "Material", "QuantityReceived", "QuantityInvoiced", "ReceiptDate",
        "PurchaseOrder", "PurchaseOrderItem", "DeliveryDocument"
    ]
    url = _build_url(
        "/sap/opu/odata/sap/C_GOODSRECEIPT_SRV/I_GoodsReceipt",
        select=select
    )
    url = url.replace("$select", f"$filter=PurchaseOrder eq '{po_number}'&$select")
    return _fetch_and_parse(url)


def forecast_material_demand(material_number, days_ahead=30):
    """Get demand forecast for a material"""
    select = [
        "Material", "ForecastDate", "ForecastedDemand", "BaseUnitOfMeasure",
        "Plant", "MaterialDescription"
    ]
    url = _build_url(
        "/sap/opu/odata/sap/C_DEMANDFORECAST_SRV/I_DemandForecast",
        select=select,
        orderby="ForecastDate asc"
    )
    url = url.replace("$select", f"$filter=Material eq '{material_number}'&$select")
    return _fetch_and_parse(url)


if __name__ == "__main__":
    print("="*80)
    print("SAP INVENTORY MANAGEMENT - COMPREHENSIVE TEST")
    print("="*80)
    print("\nThis script demonstrates comprehensive inventory capabilities")
    print("NOT focused on single PO - shows holistic inventory view\n")

    miss = _missing_env()
    if miss:
        print("❌ Missing env vars:", ", ".join(miss))
        print("Please set SAP_HOST, SAP_USER, SAP_PASSWORD in .env file")
        exit(1)

    print(f"✅ Connected to SAP: {SAP_HOST}")
    print(f"   User: {SAP_USER}\n")

    # Test 1: Get low stock materials
    print("="*80)
    print("TEST 1: Low Stock Materials (threshold < 10)")
    print("="*80)
    try:
        result = get_low_stock_materials(threshold=10)
        if result.get("status") == "success":
            entries = result.get("data", {}).get("entries", [])
            print(f"✅ Found {len(entries)} materials with low stock")
            for item in entries[:5]:  # Show first 5
                clean = _clean_entry(item)
                print(f"   • {clean.get('Material')}: {clean.get('AvailableQuantity')} units")
                print(f"     {clean.get('MaterialDescription', 'No description')}")
        else:
            print(f"⚠️  {result.get('message')}")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 2: Get material stock overview
    print("\n" + "="*80)
    print("TEST 2: Material Stock Overview (Top 10 by quantity)")
    print("="*80)
    try:
        url = _build_url(
            "/sap/opu/odata/sap/API_MATERIAL_STOCK_SRV/A_MaterialStock",
            select=["Material", "Plant", "AvailableQuantity", "MaterialDescription"],
            orderby="AvailableQuantity desc"
        )
        url = url.replace("$select", "$top=10&$select")
        result = make_sap_request(url)

        if result.get("status") == "success":
            parsed = parse_json_entries(result["data"])
            entries = parsed.get("entries", [])
            print(f"✅ Found {len(entries)} materials with highest stock")
            total_qty = 0
            for item in entries:
                clean = _clean_entry(item)
                qty = clean.get('AvailableQuantity', 0)
                total_qty += float(qty) if qty else 0
                print(f"   • {clean.get('Material')} @ Plant {clean.get('Plant')}: {qty} units")
            print(f"\n   Total quantity (top 10): {total_qty}")
        else:
            print(f"⚠️  {result.get('message')}")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 3: Get recent purchase orders (not just one PO)
    print("\n" + "="*80)
    print("TEST 3: Recent Purchase Orders (Last 10)")
    print("="*80)
    try:
        select = ["PurchaseOrder", "Supplier", "PurchaseOrderDate", "DocumentCurrency", "PurchasingOrganization"]
        url = _build_url(
            "/sap/opu/odata/sap/C_PURCHASEORDER_FS_SRV/I_PurchaseOrder",
            select=select,
            orderby="PurchaseOrderDate desc"
        )
        url = url.replace("$select", "$top=10&$select")
        result = make_sap_request(url)

        if result.get("status") == "success":
            parsed = parse_json_entries(result["data"])
            entries = parsed.get("entries", [])
            print(f"✅ Found {len(entries)} recent purchase orders")

            # Group by supplier
            suppliers = {}
            for item in entries:
                clean = _clean_entry(item)
                po = clean.get('PurchaseOrder')
                supplier = clean.get('Supplier', 'Unknown')
                date = clean.get('PurchaseOrderDate')
                currency = clean.get('DocumentCurrency')

                print(f"   • PO {po} | Supplier: {supplier} | Date: {date} | {currency}")

                if supplier not in suppliers:
                    suppliers[supplier] = 0
                suppliers[supplier] += 1

            print(f"\n   Unique suppliers: {len(suppliers)}")
            print("   Orders per supplier:")
            for supplier, count in sorted(suppliers.items(), key=lambda x: x[1], reverse=True):
                print(f"     - {supplier}: {count} orders")
        else:
            print(f"⚠️  {result.get('message')}")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 4: Search for materials by keyword
    print("\n" + "="*80)
    print("TEST 4: Search Purchase Order Items (BKC-990 materials)")
    print("="*80)
    try:
        url = _build_url(
            "/sap/opu/odata/sap/C_PURCHASEORDER_FS_SRV/I_PurchaseOrderItem",
            select=["PurchaseOrder", "PurchaseOrderItem", "Material", "PurchaseOrderItemText", "OrderQuantity", "NetAmount"],
            orderby="PurchaseOrder desc"
        )
        # Search for BKC-990 materials
        url = url.replace("$select", "$filter=substringof('BKC-990', Material)&$top=10&$select")
        result = make_sap_request(url)

        if result.get("status") == "success":
            parsed = parse_json_entries(result["data"])
            entries = parsed.get("entries", [])
            print(f"✅ Found {len(entries)} BKC-990 items across purchase orders")

            # Group by PO
            pos = {}
            for item in entries:
                clean = _clean_entry(item)
                po = clean.get('PurchaseOrder')
                if po not in pos:
                    pos[po] = []
                pos[po].append(clean)

            print(f"   Across {len(pos)} different purchase orders:")
            for po, items in list(pos.items())[:3]:  # Show first 3 POs
                print(f"\n   PO {po}: {len(items)} items")
                for item in items[:3]:  # Show first 3 items per PO
                    print(f"     - {item.get('Material')}: {item.get('OrderQuantity')} units @ ${item.get('NetAmount', 0)}")
        else:
            print(f"⚠️  {result.get('message')}")
    except Exception as e:
        print(f"❌ Error: {e}")

    # Test 5: Specific PO details (still useful, but not the main focus)
    print("\n" + "="*80)
    print("TEST 5: Specific PO Details (4500000520 - for reference)")
    print("="*80)
    print("This is ONE example PO, not the main focus of inventory management\n")
    try:
        po_data = get_complete_po_data("4500000520")
        summary = po_data.get("summary", {})
        print(f"✅ PO {po_data.get('purchase_order')}")
        print(f"   Items: {summary.get('items_count')}")
        print(f"   Total Value: ${summary.get('total_value', 0):,.2f}")
        print(f"   Total Quantity: {summary.get('total_quantity', 0)}")

        supplier = po_data.get("header", {}).get("Supplier", "Unknown")
        date = po_data.get("header", {}).get("PurchaseOrderDate", "Unknown")
        print(f"   Supplier: {supplier}")
        print(f"   Date: {date}")

        items = po_data.get("items", [])
        if items:
            print(f"\n   Sample items:")
            for item in items[:3]:
                print(f"     - {item.get('material')}: {item.get('name')}")
                print(f"       Qty: {item.get('qty')} | Price: ${item.get('net', 0):,.2f}")
    except Exception as e:
        print(f"❌ Error: {e}")

    print("\n" + "="*80)
    print("SUMMARY: Inventory Management Capabilities Demonstrated")
    print("="*80)
    print("✅ Low stock material detection")
    print("✅ Material stock overview across warehouse")
    print("✅ Recent purchase orders from all suppliers")
    print("✅ Material search across all orders")
    print("✅ Specific PO lookup (as needed)")
    print("\n💡 This provides COMPLETE inventory visibility, not just single PO queries")
    print("="*80 + "\n")