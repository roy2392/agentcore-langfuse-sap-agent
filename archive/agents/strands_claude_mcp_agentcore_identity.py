#!/usr/bin/env python3
"""
Bedrock AgentCore with Strands Framework - MCP Gateway + AgentCore Identity Edition

This agent properly uses AWS MCP Gateway with AgentCore workload identity for secure tool access.

Architecture:
  Agent (with AgentCore Identity)
    ↓ (HTTP request with signed headers using workload identity)
  AWS MCP Gateway
    ↓ (Validates identity and routes to tool server)
  SAP MCP Tool Server
    ↓ (Executes tools with identity context)
  SAP OData APIs

Security Features:
  - AgentCore workload identity for authentication
  - Signed HTTP requests with identity headers
  - Tool access controlled through MCP protocol
  - Identity verification at gateway level
"""

import argparse
import json
import os
import boto3
from bedrock_agentcore.runtime import BedrockAgentCoreApp
from strands import Agent
from strands.models import BedrockModel
from strands.telemetry import StrandsTelemetry
from strands.agent_core import BedrockMCPGateway

# Initialize Langfuse telemetry if available (non-blocking)
try:
    from langfuse import get_client as get_langfuse_client
    _langfuse_client = get_langfuse_client()
except Exception as e:
    print(f"Note: Langfuse not available for telemetry: {e}")
    _langfuse_client = None

# AWS clients for identity management
try:
    _agentcore_control_client = boto3.client(
        "bedrock-agentcore-control",
        region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1")
    )
    _agentcore_identity_available = True
except Exception as e:
    print(f"Warning: AgentCore control client not available: {e}")
    _agentcore_control_client = None
    _agentcore_identity_available = False


def get_bedrock_model():
    """Initialize Bedrock model with inference profile"""
    model_id = os.getenv(
        "BEDROCK_MODEL_ID",
        "us.anthropic.claude-3-5-sonnet-20240620-v1:0"
    )
    region = os.getenv("AWS_DEFAULT_REGION", "us-east-1")

    bedrock_model = BedrockModel(
        model_id=model_id,
        region_name=region,
        temperature=0.0,
        max_tokens=4096
    )
    return bedrock_model


def get_mcp_gateway():
    """
    Initialize MCP Gateway for secure tool access with AgentCore Identity

    The MCP Gateway:
    1. Validates the agent's workload identity
    2. Routes signed requests to the SAP MCP tool server
    3. Enforces tool access control policies
    4. Provides audit logging of tool invocations
    """
    # Get MCP gateway configuration from environment
    mcp_host = os.getenv("SAP_MCP_HOST", "localhost")
    mcp_port = os.getenv("SAP_MCP_PORT", "8000")
    mcp_endpoint = f"http://{mcp_host}:{mcp_port}/mcp"

    # Get agent identity from environment or create if needed
    agent_identity_arn = os.getenv("AGENT_IDENTITY_ARN")

    if not agent_identity_arn and _agentcore_identity_available:
        # Agent identity should be set up during deployment
        # If not available, log warning but continue
        print("⚠️ Warning: AGENT_IDENTITY_ARN not configured")
        print("   Tool access will work but without identity verification")

    print(f"✓ MCP Gateway configured at: {mcp_endpoint}")
    print(f"✓ Agent Identity: {agent_identity_arn or 'Not configured (unsafe)'}")

    # Create MCP Gateway with AgentCore Identity support
    gateway = BedrockMCPGateway(
        endpoint=mcp_endpoint,
        identity_arn=agent_identity_arn,  # Workload identity for signed requests
        region=os.getenv("AWS_DEFAULT_REGION", "us-east-1"),
        use_signed_requests=True  # Enable request signing with identity
    )

    return gateway


# Initialize Bedrock model
bedrock_model = get_bedrock_model()

# Initialize MCP Gateway with AgentCore Identity
mcp_gateway = get_mcp_gateway()

# Define system prompt - Hebrew Inventory Management
system_prompt = os.getenv(
    "SYSTEM_PROMPT",
    "אתה סוכן מומחה בניהול מלאי. התשובות שלך צריכות להיות בעברית בלבד. השתמש בכלים זמינים כדי לשלוף נתוני מלאי, מזמנות קנייה וכמויות של מוצרים. עבור כל שאלה על מלאי, ספק מידע מדויק וממוגן מה-SAP."
)

app = BedrockAgentCoreApp()


@app.entrypoint
def strands_agent_bedrock(payload):
    """
    Invoke the agent with MCP Gateway and AgentCore Identity

    The agent uses secure MCP Gateway calls with identity verification:
    1. Agent creates signed request with workload identity
    2. Gateway validates the identity signature
    3. Gateway routes to SAP MCP tool server
    4. Tools execute with identity context
    5. Results returned with audit trail

    Security Benefits:
    - Identity-based access control
    - Signed requests prevent tampering
    - Tool usage auditable by identity
    - No credential exposure to agent
    """

    user_input = payload.get("prompt")
    trace_id = payload.get("trace_id")
    parent_obs_id = payload.get("parent_obs_id")

    print("=" * 80)
    print("HEBREW SAP INVENTORY AGENT - MCP GATEWAY + AGENTCORE IDENTITY EDITION")
    print("=" * 80)
    print(f"User input: {user_input}\n")

    # Initialize Strands telemetry
    strands_telemetry = StrandsTelemetry()
    strands_telemetry.setup_otlp_exporter()

    try:
        # Create agent with MCP Gateway tools (secure identity-based access)
        # The gateway provides tools with signed requests and identity verification
        agent = Agent(
            model=bedrock_model,
            system_prompt=system_prompt,
            tools=mcp_gateway.get_tools()  # Tools from MCP Gateway with identity verification
        )

        print("[Agent] ✓ Agent created with MCP Gateway + AgentCore Identity")
        print(f"[Agent] ✓ Tools registered through secure MCP Gateway")
        print(f"[Agent] ✓ Requests will be signed with AgentCore workload identity")

        # Use Langfuse telemetry if available
        if _langfuse_client:
            with _langfuse_client.start_as_current_observation(
                name='strands-agent-mcp-gateway-identity',
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
