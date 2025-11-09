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

# For Lambda: get credentials from Secrets Manager
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

# Try Secrets Manager first (for Lambda), then fall back to environment variables
_sm_host, _sm_user, _sm_pass = _get_lambda_credentials()
SAP_HOST = _sm_host or os.getenv("SAP_HOST")
SAP_USER = _sm_user or os.getenv("SAP_USER")
SAP_PASSWORD = _sm_pass or os.getenv("SAP_PASSWORD")
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

    # Try MCP gateway format first (parameters as key-value pairs)
    if "parameters" in event:
        params = event.get("parameters", [])
        if isinstance(params, list):
            for param in params:
                if isinstance(param, dict) and param.get("name") == "po_number":
                    po_number = param.get("value")
                    break
        elif isinstance(params, dict):
            po_number = params.get("po_number")

    # Try Bedrock format
    if not po_number:
        body = event.get("requestBody", {}).get("content", {}).get("application/json", {})
        props = body.get("properties")
        if isinstance(props, list):
            for prop in props:
                if prop.get("name") == "po_number":
                    po_number = prop.get("value")
                    break

    # Try direct parameter access
    if not po_number:
        po_number = event.get("po_number")

    # Try inputText extraction
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
        po_number = extract_po_number_from_bedrock_event(event)

        if not po_number:
            # No PO number provided - return error instead of using default
            err_body = {
                "error": "Purchase order number is required",
                "message": "Please provide a valid purchase order number. Example: '4500001818'",
                "hint": "For multiple POs or delivery dates, consider using 'list_purchase_orders' or 'search_purchase_orders' tools instead."
            }
            response_body = {"TEXT": {"body": json.dumps(err_body)}}
            return {
                "messageVersion": "1.0",
                "response": {
                    "actionGroup": event.get("actionGroup", ""),
                    "apiPath": event.get("apiPath", ""),
                    "httpMethod": event.get("httpMethod", "POST"),
                    "httpStatusCode": 400,
                    "responseBody": response_body,
                },
            }

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
    miss = _missing_env()
    if miss:
        print("Missing env vars:", ", ".join(miss))
    md = fetch_metadata()
    print("metadata_probe:", md)
    event = {"inputText": "PO 4500000520"}
    po = get_complete_po_data("4500000520")
    print(json.dumps(po, indent=2))
    # Also print the lambda-shaped response for parity
    print(json.dumps(lambda_handler(event, None), indent=2))