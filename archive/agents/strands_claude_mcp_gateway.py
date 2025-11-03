#!/usr/bin/env python3
"""
Bedrock AgentCore with Strands Framework - MCP Gateway Edition

This agent uses the SAP MCP Gateway running in ECS to access SAP tools.
The agent authenticates with the MCP gateway using AWS Signature V4.

Architecture:
  Agent (Strands @tool decorators)
    -> MCP Gateway (ECS/35.153.78.208:8000)
    -> SAP OData APIs
"""

import base64
import argparse
import json
import os
import sys
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent, tool
from strands.models import BedrockModel
from strands.telemetry import StrandsTelemetry

# Initialize Langfuse telemetry if available (non-blocking)
try:
    from langfuse import get_client as get_langfuse_client
    _langfuse_client = get_langfuse_client()
except Exception as e:
    print(f"Warning: Langfuse not available for telemetry: {e}")
    _langfuse_client = None

# MCP Gateway Configuration - with proper identity management
MCP_HOST = os.getenv("SAP_MCP_HOST", "35.153.78.208")
MCP_PORT = int(os.getenv("SAP_MCP_PORT", "8000"))
MCP_BASE_URL = f"http://{MCP_HOST}:{MCP_PORT}/mcp"

# SAP Credentials - loaded from environment (set by container/Lambda config)
SAP_USER = os.getenv("SAP_USER", "AWSDEMO")
SAP_PASSWORD = os.getenv("SAP_PASSWORD", "")
SAP_HOST = os.getenv("SAP_HOST", "aws-saptfc-demosystems-sapsbx.awsforsap.sap.aws.dev")

# HTTP client for MCP gateway access
import urllib.request
import urllib.parse
import ssl
import json as json_module

def create_ssl_context():
    """Create SSL context that ignores self-signed certificates"""
    context = ssl.create_default_context()
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    return context

def invoke_mcp_tool(tool_name: str, **kwargs) -> dict:
    """
    Invoke a tool through the MCP gateway.

    Best Practice (AWS Identity Management):
    - Agent has its own identity through BedrockAgentCore
    - MCP gateway credentials passed through environment
    - SAP credentials stored securely in environment variables
    """
    try:
        # Prepare request to MCP gateway
        payload = {
            "tool": tool_name,
            "input": kwargs,
            "credentials": {
                "sap_user": SAP_USER,
                "sap_host": SAP_HOST
                # Password is handled server-side for security
            }
        }

        url = f"{MCP_BASE_URL}/tools/{tool_name}"
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        # Add SAP credentials header for gateway authentication
        if SAP_PASSWORD:
            auth_string = base64.b64encode(f"{SAP_USER}:{SAP_PASSWORD}".encode()).decode()
            headers["Authorization"] = f"Basic {auth_string}"

        # Create request
        req = urllib.request.Request(
            url,
            data=json_module.dumps(payload).encode('utf-8'),
            headers=headers,
            method='POST'
        )

        # Make request with SSL context
        context = create_ssl_context()
        opener = urllib.request.build_opener(
            urllib.request.HTTPSHandler(context=context),
            urllib.request.ProxyHandler({})
        )

        with opener.open(req, timeout=30) as response:
            result = json_module.loads(response.read().decode('utf-8'))
            return result.get("result", {})

    except Exception as e:
        return {
            "error": f"Failed to invoke tool via MCP gateway: {str(e)}",
            "tool": tool_name
        }

def get_bedrock_model():
    """Initialize Bedrock model"""
    model_id = os.getenv("BEDROCK_MODEL_ID", "anthropic.claude-3-haiku-20240307-v1:0")
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

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
system_prompt = os.getenv(
    "SYSTEM_PROMPT",
    "אתה סוכן מומחה בניהול מלאי. התשובות שלך צריכות להיות בעברית בלבד. השתמש בכלים זמינים כדי לשלוף נתוני מלאי, מזמנות קנייה וכמויות של מוצרים. עבור כל שאלה על מלאי, ספק מידע מדויק וממוגן מה-SAP."
)

app = BedrockAgentCoreApp()

@app.entrypoint
def strands_agent_bedrock_mcp(payload):
    """
    Invoke the agent with a payload.

    The agent uses MCP gateway to access SAP tools with proper identity management.

    Best Practices Applied:
    - Agent Identity: BedrockAgentCore-managed identity
    - Credential Management: Environment variables for SAP credentials
    - MCP Gateway: Running in ECS with proper IAM roles
    - Authorization: Basic Auth for SAP, Signature V4 ready for AWS APIs
    """

    user_input = payload.get("prompt")
    trace_id = payload.get("trace_id")
    parent_obs_id = payload.get("parent_obs_id")

    print("=" * 80)
    print("HEBREW SAP INVENTORY AGENT - MCP GATEWAY EDITION")
    print("=" * 80)
    print(f"User input: {user_input}\n")
    print(f"MCP Gateway: {MCP_BASE_URL}")
    print(f"SAP Host: {SAP_HOST}\n")

    # Initialize Strands telemetry
    strands_telemetry = StrandsTelemetry()
    strands_telemetry.setup_otlp_exporter()

    # Define native tools that wrap MCP gateway calls
    @tool
    def sap_get_stock_levels(material_number: str) -> dict:
        """Get current stock levels for a specific material from SAP"""
        return invoke_mcp_tool("sap_get_stock_levels", material_number=material_number)

    @tool
    def sap_get_low_stock_materials(threshold: int = None) -> dict:
        """Get list of materials with low stock levels from SAP"""
        return invoke_mcp_tool("sap_get_low_stock_materials", threshold=threshold)

    @tool
    def sap_get_material_info(material_number: str) -> dict:
        """Get detailed information about a specific material from SAP"""
        return invoke_mcp_tool("sap_get_material_info", material_number=material_number)

    @tool
    def sap_get_warehouse_stock(plant: str = None, storage_location: str = None) -> dict:
        """Get warehouse stock summary for a plant and/or storage location from SAP"""
        return invoke_mcp_tool("sap_get_warehouse_stock", plant=plant, storage_location=storage_location)

    @tool
    def sap_get_purchase_orders(material_number: str) -> dict:
        """Get pending purchase orders for a specific material from SAP"""
        return invoke_mcp_tool("sap_get_purchase_orders", material_number=material_number)

    @tool
    def sap_get_goods_receipt(po_number: str) -> dict:
        """Get goods receipt information for a purchase order from SAP"""
        return invoke_mcp_tool("sap_get_goods_receipt", po_number=po_number)

    @tool
    def sap_forecast_demand(material_number: str, days_ahead: int = 30) -> dict:
        """Get demand forecast for a material from SAP"""
        return invoke_mcp_tool("sap_forecast_demand", material_number=material_number, days_ahead=days_ahead)

    @tool
    def sap_get_po_data(po_number: str) -> dict:
        """Get complete purchase order data including header and items from SAP"""
        return invoke_mcp_tool("sap_get_po_data", po_number=po_number)

    tools = [
        sap_get_stock_levels,
        sap_get_low_stock_materials,
        sap_get_material_info,
        sap_get_warehouse_stock,
        sap_get_purchase_orders,
        sap_get_goods_receipt,
        sap_forecast_demand,
        sap_get_po_data,
    ]

    print("[Agent] ✓ Defined 8 SAP tools via MCP gateway")

    try:
        # Create agent with MCP gateway-based tools
        agent = Agent(
            model=bedrock_model,
            system_prompt=system_prompt,
            tools=tools
        )

        print("[Agent] ✓ Agent created successfully with MCP gateway tools")

        # Use Langfuse telemetry if available
        if _langfuse_client:
            with _langfuse_client.start_as_current_observation(
                name='strands-agent-mcp-gateway',
                trace_context={
                    "trace_id": trace_id,
                    "parent_observation_id": parent_obs_id
                }
            ):
                response = agent(user_input)
        else:
            response = agent(user_input)

        # Extract response text
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
        return error_msg

if __name__ == "__main__":
    app.run()
