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

# Load system prompt from file (avoids 4000-byte env var limit)
def load_system_prompt():
    """Load system prompt from bundled file"""
    prompt_file = os.path.join(os.path.dirname(__file__), '..', 'cicd', 'system_prompt_english.txt')
    try:
        with open(prompt_file, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        # Fallback if file not found
        return "אתה סוכן מומחה בניהול מלאי. התשובות שלך צריכות להיות בעברית בלבד."

system_prompt = load_system_prompt()

# Tools are provided by AgentCore Gateway, not embedded in agent code
# The Gateway exposes SAP MCP Server tools to the agent

app = BedrockAgentCoreApp()

@app.entrypoint
async def strands_agent_bedrock(payload):
    """
    Invoke the agent with a payload
    Agent uses tools from AgentCore Gateway (NOT embedded tools)
    """

    user_input = payload.get("prompt")
    trace_id = payload.get("trace_id")
    parent_obs_id = payload.get("parent_obs_id")
    print("User input:", user_input)
    print(f"[DEBUG] Full payload keys: {list(payload.keys())}")
    print(f"[DEBUG] Full payload: {payload}")

    # Try to get session ID from Flask request context
    try:
        from flask import request as flask_request
        print(f"[DEBUG] Flask request headers: {dict(flask_request.headers)}")
        print(f"[DEBUG] Flask request environ keys: {list(flask_request.environ.keys())}")
    except Exception as e:
        print(f"[DEBUG] Could not access Flask request: {e}")

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

    # Get conversation history from BedrockAgentCore memory if available
    conversation_history = []
    try:
        memory_id = os.getenv("BEDROCK_AGENTCORE_MEMORY_ID")
        session_id = payload.get("session_id")  # Now passed in payload from utils/agent.py

        if memory_id and session_id:
            print(f"[Agent] Fetching conversation history from memory: {memory_id}, session: {session_id}")
            import boto3
            memory_client = boto3.client('bedrock-agentcore', region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))

            # Retrieve recent conversation records from memory
            response = memory_client.list_events(
                memoryId=memory_id,
                actorId=session_id,  # Use session_id as actorId for user-specific memory
                sessionId=session_id,
                maxResults=20  # Get last 20 events
            )

            # Convert memory events to conversation history format
            for event in response.get('events', []):
                payload = event.get('payload', [])
                # Payload is a list of conversational events
                for item in payload:
                    conversational = item.get('conversational', {})
                    if conversational:
                        role = conversational.get('role', '').lower()  # Convert USER/ASSISTANT to lowercase
                        content_obj = conversational.get('content', {})
                        content_text = content_obj.get('text', '')
                        if role and content_text:
                            conversation_history.append({"role": role, "content": content_text})

            print(f"[Agent] Loaded {len(conversation_history)} messages from memory")
        else:
            print(f"[Agent] No memory or session ID available (memory_id={memory_id}, session_id={session_id})")
    except Exception as e:
        print(f"[Agent] Warning: Could not fetch conversation history: {e}")
        # Continue without history rather than failing

    # Create the agent with Gateway tools
    agent = Agent(
        model=bedrock_model,
        system_prompt=system_prompt,
        tools=tools_to_use
    )

    # Build input with conversation history context
    if conversation_history:
        # Construct a prompt that includes conversation history
        history_context = "\n\nPrevious conversation:\n"
        for msg in conversation_history[-10:]:  # Last 10 messages
            role = msg['role'].capitalize()
            content = msg['content']
            history_context += f"{role}: {content}\n"
        history_context += f"\nUser: {user_input}"
        full_input = history_context
    else:
        full_input = user_input

    # Collect the full response for saving to memory
    full_response = []

    # Use Langfuse telemetry if available
    if _langfuse_client:
        with _langfuse_client.start_as_current_observation(name='strands-agent', trace_context={"trace_id": trace_id, "parent_observation_id": parent_obs_id}):
            async for chunk in agent.stream_async(full_input):
                full_response.append(str(chunk))
                yield chunk
    else:
        async for chunk in agent.stream_async(full_input):
            full_response.append(str(chunk))
            yield chunk

    # Save conversation to memory after response completes
    try:
        memory_id = os.getenv("BEDROCK_AGENTCORE_MEMORY_ID")
        session_id = payload.get("session_id")  # Now passed in payload from utils/agent.py

        if memory_id and session_id:
            import boto3
            import time
            memory_client = boto3.client('bedrock-agentcore', region_name=os.getenv("AWS_DEFAULT_REGION", "us-east-1"))

            response_text = ''.join(full_response)

            # Save user message to memory
            memory_client.create_event(
                memoryId=memory_id,
                actorId=session_id,  # Use session_id as actorId for user-specific memory
                sessionId=session_id,
                payload=[{
                    'conversational': {
                        'role': 'USER',
                        'content': {
                            'text': user_input
                        }
                    }
                }],
                eventTimestamp=int(time.time())
            )

            # Save assistant response to memory
            memory_client.create_event(
                memoryId=memory_id,
                actorId=session_id,  # Use session_id as actorId for user-specific memory
                sessionId=session_id,
                payload=[{
                    'conversational': {
                        'role': 'ASSISTANT',
                        'content': {
                            'text': response_text
                        }
                    }
                }],
                eventTimestamp=int(time.time())
            )

            print(f"[Agent] Saved conversation to memory (user + assistant)")
    except Exception as e:
        print(f"[Agent] Warning: Could not save conversation to memory: {e}")

if __name__ == "__main__":
    app.run()
# Updated for production deployment with Hebrew inventory management
# Agent runs on Claude 3 Sonnet with Bedrock AgentCore  
# Region: us-east-1
