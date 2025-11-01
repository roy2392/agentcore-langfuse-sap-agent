import base64
import argparse
import json
from bedrock_agentcore.runtime import BedrockAgentCoreApp
import os
from strands import Agent, tool
from strands.models import BedrockModel
from strands.telemetry import StrandsTelemetry

# Import SAP API functions for direct tool integration
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

try:
    # Try to import SAP API functions directly
    from utils.test_sap_api import (
        get_stock_levels,
        get_low_stock_materials,
        get_material_info,
        get_warehouse_stock,
        get_purchase_orders_for_material,
        get_goods_receipt,
        forecast_material_demand,
        get_complete_po_data,
    )
    SAP_API_AVAILABLE = True
except ImportError as e:
    print(f"Warning: SAP API functions not available: {e}")
    SAP_API_AVAILABLE = False

# Optional: Also try MCP client connection as fallback
try:
    from mcp.client.streamable_http import streamablehttp_client
    from strands.tools.mcp.mcp_client import MCPClient

    sap_mcp_host = os.getenv("SAP_MCP_HOST", "localhost")
    sap_mcp_port = os.getenv("SAP_MCP_PORT", "8000")
    sap_mcp_url = f"http://{sap_mcp_host}:{sap_mcp_port}/mcp"

    sap_mcp_client = MCPClient(lambda: streamablehttp_client(sap_mcp_url))
    print(f"[Agent] MCP client initialized: {sap_mcp_url}")
except Exception as e:
    print(f"Warning: MCP client initialization failed: {e}")
    sap_mcp_client = None

# Optional: Initialize Langfuse telemetry if available (non-blocking)
try:
    from langfuse import get_client as get_langfuse_client
    _langfuse_client = get_langfuse_client()
except Exception as e:
    print(f"Warning: Langfuse not available for telemetry: {e}")
    _langfuse_client = None

# Function to initialize Bedrock model
def get_bedrock_model():
    model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
    region = os.getenv("AWS_DEFAULT_REGION", "us-west-2")
    
    bedrock_model = BedrockModel(
        model_id=model_id,
        region_name=region,
        temperature=0.0,
        max_tokens=4096
    )
    return bedrock_model

# Initialize the Bedrock model
bedrock_model = get_bedrock_model()

# Define the agent's system prompt - Hebrew Inventory Management
system_prompt = os.getenv("SYSTEM_PROMPT", "אתה סוכן מומחה בניהול מלאי. התשובות שלך צריכות להיות בעברית בלבד. השתמש ב-SAP OData API כדי לשלוף נתוני מלאי, מזמנות קנייה וכמויות של מוצרים. עבור כל שאלה על מלאי, ספק מידע מדויק וממוגן מה-SAP. ודא שהתשובה שלך כוללת: (1) פרטי מלאי נוכחי, (2) כמויות שהוזמנו, (3) תאריכים רלוונטיים, ו-(4) המלצות על סמך סטטוס המלאי.")

# Define SAP inventory tools if SAP API is available
sap_tools = []
if SAP_API_AVAILABLE:
    @tool
    def sap_get_stock_levels(material_number: str) -> str:
        """Get current stock levels for a specific material from SAP"""
        result = get_stock_levels(material_number)
        return json.dumps(result, ensure_ascii=False)

    @tool
    def sap_get_low_stock_materials(threshold: int = None) -> str:
        """Get list of materials with low stock levels from SAP"""
        result = get_low_stock_materials(threshold)
        return json.dumps(result, ensure_ascii=False)

    @tool
    def sap_get_material_info(material_number: str) -> str:
        """Get detailed information about a material from SAP"""
        result = get_material_info(material_number)
        return json.dumps(result, ensure_ascii=False)

    @tool
    def sap_get_warehouse_stock(plant: str = None, storage_location: str = None) -> str:
        """Get warehouse stock summary from SAP"""
        result = get_warehouse_stock(plant, storage_location)
        return json.dumps(result, ensure_ascii=False)

    @tool
    def sap_get_purchase_orders(material_number: str) -> str:
        """Get pending purchase orders for a material from SAP"""
        result = get_purchase_orders_for_material(material_number)
        return json.dumps(result, ensure_ascii=False)

    @tool
    def sap_get_goods_receipt(po_number: str) -> str:
        """Get goods receipt information for a purchase order from SAP"""
        result = get_goods_receipt(po_number)
        return json.dumps(result, ensure_ascii=False)

    @tool
    def sap_forecast_demand(material_number: str, days_ahead: int = 30) -> str:
        """Get demand forecast for a material from SAP"""
        result = forecast_material_demand(material_number, days_ahead)
        return json.dumps(result, ensure_ascii=False)

    @tool
    def sap_get_po_data(po_number: str) -> str:
        """Get complete purchase order data from SAP"""
        result = get_complete_po_data(po_number)
        return json.dumps(result, ensure_ascii=False)

    # Collect all SAP tools
    sap_tools = [
        sap_get_stock_levels,
        sap_get_low_stock_materials,
        sap_get_material_info,
        sap_get_warehouse_stock,
        sap_get_purchase_orders,
        sap_get_goods_receipt,
        sap_forecast_demand,
        sap_get_po_data,
    ]

    print(f"[Agent] Loaded {len(sap_tools)} SAP tools")

app = BedrockAgentCoreApp()

@app.entrypoint
def strands_agent_bedrock(payload):
    """
    Invoke the agent with a payload
    """

    user_input = payload.get("prompt")
    trace_id = payload.get("trace_id")
    parent_obs_id = payload.get("parent_obs_id")
    print("User input:", user_input)

    # Initialize Strands telemetry and setup OTLP exporter
    strands_telemetry = StrandsTelemetry()
    strands_telemetry.setup_otlp_exporter()

    # Prepare tools list
    tools_to_use = []

    # Prefer direct SAP tools if available
    if sap_tools:
        tools_to_use = sap_tools
        print(f"[Agent] Using direct SAP tools ({len(tools_to_use)} tools)")
    elif sap_mcp_client:
        # Fall back to MCP client if direct tools not available
        try:
            with sap_mcp_client:
                tools_to_use = sap_mcp_client.list_tools_sync()
                print(f"[Agent] Using MCP client tools ({len(tools_to_use)} tools)")
        except Exception as e:
            print(f"[Agent] Error getting MCP tools: {e}")
    else:
        print("[Agent] Warning: No SAP tools available!")

    # Create the agent
    agent = Agent(
        model=bedrock_model,
        system_prompt=system_prompt,
        tools=tools_to_use
    )

    # Use Langfuse telemetry if available
    if _langfuse_client:
        with _langfuse_client.start_as_current_observation(name='strands-agent', trace_context={"trace_id": trace_id, "parent_observation_id": parent_obs_id}):
            response = agent(user_input)
    else:
        response = agent(user_input)

    return response.message['content'][0]['text']

if __name__ == "__main__":
    app.run()
# Updated for production deployment with Hebrew inventory management
# Agent runs on Claude 3 Sonnet with Bedrock AgentCore  
# Region: us-east-1
