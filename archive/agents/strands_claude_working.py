#!/usr/bin/env python3
"""
Bedrock AgentCore with Strands Framework - Direct SAP Integration
This agent has SAP functions embedded and decorated as tools for Bedrock.
"""

import json
import os
import sys
import base64
import logging
import urllib.request
import urllib.parse
import urllib.error
import ssl
import time

from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel
from strands.telemetry import StrandsTelemetry

# Try to load environment from .env if available
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get SAP credentials from environment
SAP_HOST = os.getenv("SAP_HOST")
SAP_USER = os.getenv("SAP_USER")
SAP_PASSWORD = os.getenv("SAP_PASSWORD")
SAP_CLIENT = None

# Initialize Langfuse telemetry if available (non-blocking)
try:
    from langfuse import get_client as get_langfuse_client
    _langfuse_client = get_langfuse_client()
except Exception as e:
    logger.warning(f"Langfuse not available: {e}")
    _langfuse_client = None


# ============== SAP API FUNCTIONS ==============

def _basic_auth_header(user, pwd):
    """Create Basic Auth header"""
    token = base64.b64encode(f"{user}:{pwd}".encode()).decode()
    return f"Basic {token}"


def _build_url(path, po_number=None, select=None, orderby=None):
    """Build SAP OData URL with parameters"""
    params = {}
    if po_number:
        q = f"PurchaseOrder eq '{po_number}'"
        params["$filter"] = q
    params["$format"] = "json"
    if select:
        params["$select"] = ",".join(select)
    if orderby:
        params["$orderby"] = orderby
    if SAP_CLIENT:
        params["sap-client"] = SAP_CLIENT
    safe_chars = "'() "
    return f'https://{SAP_HOST}{path}?{urllib.parse.urlencode(params, safe=safe_chars)}'


def make_sap_request(url, timeout=30, retries=3, backoff=0.8):
    """Make HTTP request to SAP OData API"""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE  # For self-signed certs

    opener = urllib.request.build_opener(
        urllib.request.HTTPSHandler(context=context),
        urllib.request.ProxyHandler({})  # No proxies
    )

    for attempt in range(retries):
        try:
            req = urllib.request.Request(url)
            req.add_header("Authorization", _basic_auth_header(SAP_USER, SAP_PASSWORD))
            req.add_header("Accept", "application/json")
            req.add_header("User-Agent", "sap-inventory-agent/1.0")
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
        return {"parse_error": str(e)}


def get_stock_levels(material_number: str) -> dict:
    """Get stock levels for material from SAP"""
    if not all([SAP_HOST, SAP_USER, SAP_PASSWORD]):
        return {"status": "error", "message": "SAP credentials not configured"}

    # Try to get from purchase orders
    path = "/sap/opu/odata/sap/C_PURCHASEORDER_FS_SRV/C_PurchaseOrderItemTP"
    url = _build_url(path, select=["PurchaseOrder", "Material", "OrderQuantity"])

    result = make_sap_request(url)
    if result["status"] != "success":
        return result

    try:
        parsed = parse_json_entries(result["data"])
        entries = parsed.get("entries", [])

        # Filter for material
        matching = [e for e in entries if e.get("Material", "").strip() == material_number.strip()]

        if matching:
            total_qty = sum(float(e.get("OrderQuantity", 0)) for e in matching)
            return {
                "status": "success",
                "data": {
                    "entries": [
                        {
                            "Material": material_number,
                            "AvailableQuantity": total_qty,
                            "Source": "Purchase Orders",
                            "Details": f"Found {len(matching)} PO items with total {total_qty} units"
                        }
                    ],
                    "total_count": 1
                }
            }
        else:
            return {
                "status": "success",
                "data": {
                    "entries": [{"Material": material_number, "Message": "No stock found"}],
                    "total_count": 0
                }
            }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_purchase_orders_for_material(material_number: str) -> dict:
    """Get purchase orders for a material"""
    if not all([SAP_HOST, SAP_USER, SAP_PASSWORD]):
        return {"status": "error", "message": "SAP credentials not configured"}

    path = "/sap/opu/odata/sap/C_PURCHASEORDER_FS_SRV/C_PurchaseOrderItemTP"
    url = _build_url(path, select=["PurchaseOrder", "Material", "OrderQuantity", "DeliveryDate"])

    result = make_sap_request(url)
    if result["status"] != "success":
        return result

    try:
        parsed = parse_json_entries(result["data"])
        entries = parsed.get("entries", [])

        # Filter for material
        matching = [e for e in entries if e.get("Material", "").strip() == material_number.strip()]

        return {
            "status": "success",
            "data": {
                "entries": matching[:10] if matching else [],  # Limit to 10
                "total_count": len(matching)
            }
        }
    except Exception as e:
        return {"status": "error", "message": str(e)}


def get_material_info(material_number: str) -> dict:
    """Get material information"""
    return {"status": "success", "data": {"Material": material_number, "Message": "Material info not fully implemented"}}


# ============== BEDROCK AGENT SETUP ==============

def get_bedrock_model():
    """Initialize Bedrock model"""
    # Use the correct Sonnet model ID for this account
    # IMPORTANT: Account 654537381132 does NOT have access to Haiku
    model_id = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    bedrock_model = BedrockModel(
        model_id=model_id,
        region_name=region,
        temperature=0.0,
        max_tokens=4096
    )
    return bedrock_model


# System prompt in Hebrew (loaded at module level)
system_prompt = os.getenv("SYSTEM_PROMPT", """אתה סוכן מומחה בניהול מלאי בעברית.
התשובות שלך צריכות להיות בעברית בלבד.
השתמש בכלים זמינים כדי לשלוף נתוני מלאי ומזמנות קנייה מ-SAP.
עבור כל שאלה על מלאי, ספק מידע מדויק מ-SAP וכולל:
(1) כמויות במלאי
(2) מזמנות קנייה פתוחות
(3) תאריכי משלוח
(4) המלצות על סמך הנתונים""")

app = BedrockAgentCoreApp()


@app.entrypoint
def strands_agent_bedrock(payload):
    """
    Agent entrypoint for Bedrock AgentCore with proper telemetry and tracing.

    FIX: Initialize telemetry BEFORE Langfuse context to ensure SAP tool calls are traced.

    Trace Structure:
    ├─ invoke_agent_strands_agents (Langfuse observation)
    │  ├─ sap_stock_levels (Tool call) ✅
    │  ├─ execute_event_loop_cycle (Agent loop)
    │  └─ chat (Model invocation)
    """

    user_input = payload.get("prompt")
    trace_id = payload.get("trace_id")
    parent_obs_id = payload.get("parent_obs_id")

    print("=" * 80)
    print(f"User input: {user_input}")
    print(f"Trace ID: {trace_id}")
    print("=" * 80)

    # ✅ STEP 1: Initialize Bedrock model at runtime to pick up environment variables
    bedrock_model = get_bedrock_model()
    print(f"[Agent] Using model: {bedrock_model.model_id}")

    # ✅ STEP 2: Initialize telemetry FIRST (before Langfuse context)
    # This ensures OTEL exporter is ready before tool execution
    print("[Agent] Initializing Strands telemetry...")
    strands_telemetry = StrandsTelemetry()
    strands_telemetry.setup_otlp_exporter()
    print("[Agent] ✓ Telemetry initialized")

    # STEP 3: Define tools using decorators
    @tool
    def sap_stock_levels(material_number: str) -> str:
        """Get current stock levels for a material from SAP"""
        result = get_stock_levels(material_number)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @tool
    def sap_purchase_orders(material_number: str) -> str:
        """Get pending purchase orders for a material"""
        result = get_purchase_orders_for_material(material_number)
        return json.dumps(result, ensure_ascii=False, indent=2)

    @tool
    def sap_material_info(material_number: str) -> str:
        """Get material information from SAP"""
        result = get_material_info(material_number)
        return json.dumps(result, ensure_ascii=False, indent=2)

    # Create agent with tools
    tools = [sap_stock_levels, sap_purchase_orders, sap_material_info]

    print(f"[Agent] ✓ Created with {len(tools)} SAP tools")

    try:
        # STEP 4: Create agent
        agent = Agent(
            model=bedrock_model,
            system_prompt=system_prompt,
            tools=tools
        )
        print("[Agent] ✓ Agent created successfully")

        # ✅ STEP 5: Execute agent in Langfuse context
        # IMPORTANT: Telemetry is already initialized, so tool calls will be traced
        if _langfuse_client:
            print("[Agent] ✓ Starting Langfuse observation...")

            # Create main observation for entire agent invocation
            # All tool calls within this context will be traced
            main_obs = _langfuse_client.start_as_current_observation(
                name='invoke_agent_strands_agents',
                input=user_input,
                trace_context={
                    "trace_id": trace_id,
                    "parent_observation_id": parent_obs_id
                }
            )

            try:
                # Agent executes within telemetry + Langfuse context
                # ✅ All SAP tool calls will be traced to Langfuse
                print("[Agent] Executing agent with tools...")
                response = agent(user_input)

                # Extract response text
                response_text = response.message['content'][0]['text']

                # Log successful execution with metadata
                main_obs.update(
                    output=response_text,
                    metadata={
                        "model": bedrock_model.model_id,
                        "tools_used": len(tools),
                        "language": "Hebrew",
                        "status": "success"
                    }
                )

                print("\n" + "=" * 80)
                print("AGENT RESPONSE")
                print("=" * 80)
                print(response_text)
                print("=" * 80 + "\n")

                return response_text

            except Exception as e:
                # Log error to Langfuse for debugging
                main_obs.update(
                    output=f"Error: {str(e)}",
                    metadata={
                        "error": True,
                        "error_type": type(e).__name__,
                        "status": "failed"
                    }
                )
                error_msg = f"שגיאה בעיבוד הבקשה: {str(e)}"
                print(f"[Agent] ✗ Error: {error_msg}")
                logger.exception("Agent error")
                raise
            finally:
                main_obs.end()
        else:
            print("[Agent] ⚠️ Langfuse not available, running without tracing")
            response = agent(user_input)
            response_text = response.message['content'][0]['text']

            print("\n" + "=" * 80)
            print("AGENT RESPONSE")
            print("=" * 80)
            print(response_text)
            print("=" * 80 + "\n")

            return response_text

    except Exception as e:
        error_msg = f"שגיאה בעיבוד הבקשה: {str(e)}"
        print(f"[Agent] ✗ Error: {error_msg}")
        logger.exception("Agent error")
        return error_msg


if __name__ == "__main__":
    app.run()
