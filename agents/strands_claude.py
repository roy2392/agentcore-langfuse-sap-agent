import base64
import argparse
import json
from bedrock_agentcore.runtime import BedrockAgentCoreApp
import os
from strands import Agent
from strands.models import BedrockModel
from strands.telemetry import StrandsTelemetry

# AWS AgentCore Gateway Architecture:
# Agent → AgentCore Gateway → SAP MCP Server → SAP OData API
#
# The agent accesses tools through AgentCore Gateway, NOT directly.
# Gateway handles authentication, authorization, and credential injection.
# SAP credentials are managed by AgentCore Identity, not embedded in agent code.

# Import MCP client for Gateway connection
try:
    from strands.tools.mcp.mcp_client import MCPClient

    # Gateway endpoint URL (will be set via environment variable)
    gateway_url = os.getenv("GATEWAY_ENDPOINT_URL")

    if gateway_url:
        # Gateway configured with authorizerType=CUSTOM_JWT (OAuth)
        # Use OAuth Bearer token authentication
        from agents.gateway_oauth_transport import gateway_oauth_transport
        from agents.oauth_token_manager import create_token_manager_from_env

        # Create OAuth token manager from environment variables
        token_manager = create_token_manager_from_env()

        if token_manager:
            # Create a callable that returns the OAuth-authenticated MCP transport
            def create_transport():
                return gateway_oauth_transport(gateway_url, token_manager)

            mcp_client = MCPClient(create_transport)
            print(f"[Agent] Connected to AgentCore Gateway (OAuth): {gateway_url}")
        else:
            print("[Agent] ERROR: Failed to initialize OAuth token manager - no Gateway connection")
            mcp_client = None
    else:
        print("[Agent] WARNING: GATEWAY_ENDPOINT_URL not set - agent will have NO tools")
        mcp_client = None
except Exception as e:
    print(f"[Agent] ERROR: Failed to initialize Gateway client: {e}")
    import traceback
    traceback.print_exc()
    mcp_client = None

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

# Tools are provided by AgentCore Gateway, not embedded in agent code
# The Gateway exposes SAP MCP Server tools to the agent

app = BedrockAgentCoreApp()

@app.entrypoint
def strands_agent_bedrock(payload):
    """
    Invoke the agent with a payload
    Agent uses tools from AgentCore Gateway (NOT embedded tools)
    """

    user_input = payload.get("prompt")
    trace_id = payload.get("trace_id")
    parent_obs_id = payload.get("parent_obs_id")
    print("User input:", user_input)

    # Initialize Strands telemetry and setup OTLP exporter
    strands_telemetry = StrandsTelemetry()
    strands_telemetry.setup_otlp_exporter()

    # Get tools from AgentCore Gateway via MCP client
    tools_to_use = []

    if mcp_client:
        try:
            # Tools are dynamically loaded from Gateway
            tools_to_use = [mcp_client]
            print(f"[Agent] Using tools from AgentCore Gateway")
        except Exception as e:
            print(f"[Agent] ERROR: Failed to load Gateway tools: {e}")
    else:
        print("[Agent] WARNING: No Gateway connection - agent will run without tools")

    # Create the agent with Gateway tools
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
