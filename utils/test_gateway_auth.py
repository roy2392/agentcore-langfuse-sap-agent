#!/usr/bin/env python3
"""
Test Gateway OAuth authentication and tool availability
This script tests:
1. OAuth token acquisition from Cognito
2. Gateway connectivity with OAuth
3. Tool listing from Gateway
4. Direct tool invocation
"""
import os
import sys
import json
import requests
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent))

# Gateway configuration from terraform output
GATEWAY_URL = "https://sap-inventory-gateway-prd-td3ict6das.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
COGNITO_CLIENT_ID = "56d6r0as0inbf6gvjjfrmp0c9v"
COGNITO_DOMAIN = "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_7m45pE9la"
COGNITO_CLIENT_SECRET = os.getenv("COGNITO_CLIENT_SECRET", "")

print("=" * 80)
print("🔐 Gateway OAuth Authentication Test")
print("=" * 80)
print()

# Step 1: Check environment
print("📋 Configuration:")
print(f"   Gateway URL: {GATEWAY_URL}")
print(f"   Cognito Client ID: {COGNITO_CLIENT_ID}")
print(f"   Cognito Domain: {COGNITO_DOMAIN}")
print(f"   Cognito Secret: {'✅ Set' if COGNITO_CLIENT_SECRET else '❌ NOT SET'}")
print()

if not COGNITO_CLIENT_SECRET:
    print("❌ ERROR: COGNITO_CLIENT_SECRET environment variable is not set!")
    print("   Please set it with: export COGNITO_CLIENT_SECRET=<your-secret>")
    sys.exit(1)

# Step 2: Get OAuth token
print("🔑 Step 1: Acquiring OAuth token from Cognito...")
print("-" * 80)

try:
    # Use OAuth 2.0 Client Credentials flow
    token_url = f"{COGNITO_DOMAIN}/oauth2/token"

    token_response = requests.post(
        token_url,
        headers={
            "Content-Type": "application/x-www-form-urlencoded"
        },
        data={
            "grant_type": "client_credentials",
            "client_id": COGNITO_CLIENT_ID,
            "client_secret": COGNITO_CLIENT_SECRET,
        }
    )

    print(f"   Token request status: {token_response.status_code}")

    if token_response.status_code == 200:
        token_data = token_response.json()
        access_token = token_data.get("access_token")
        token_type = token_data.get("token_type")
        expires_in = token_data.get("expires_in")

        print(f"   ✅ Token acquired successfully!")
        print(f"   Token type: {token_type}")
        print(f"   Expires in: {expires_in} seconds")
        print(f"   Token (first 50 chars): {access_token[:50]}...")
        print()
    else:
        print(f"   ❌ Failed to acquire token!")
        print(f"   Response: {token_response.text}")
        sys.exit(1)

except Exception as e:
    print(f"   ❌ Error acquiring token: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# Step 3: Test Gateway connectivity
print("🌐 Step 2: Testing Gateway connectivity...")
print("-" * 80)

try:
    # Try to list tools from the Gateway using MCP protocol
    # MCP uses JSON-RPC 2.0 over HTTP

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json"
    }

    # MCP initialize request
    initialize_request = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {
                "roots": {"listChanged": True},
                "sampling": {}
            },
            "clientInfo": {
                "name": "test-client",
                "version": "1.0.0"
            }
        }
    }

    print(f"   Sending initialize request to Gateway...")
    response = requests.post(
        GATEWAY_URL,
        headers=headers,
        json=initialize_request,
        timeout=30
    )

    print(f"   Response status: {response.status_code}")

    if response.status_code == 200:
        print(f"   ✅ Gateway responded successfully!")
        try:
            response_data = response.json()
            print(f"   Response: {json.dumps(response_data, indent=2)}")
        except:
            print(f"   Response text: {response.text[:500]}")
        print()
    else:
        print(f"   ❌ Gateway returned error status!")
        print(f"   Response: {response.text[:500]}")
        print()

except Exception as e:
    print(f"   ❌ Error connecting to Gateway: {e}")
    import traceback
    traceback.print_exc()
    print()

# Step 4: List available tools
print("🔧 Step 3: Listing available tools...")
print("-" * 80)

try:
    # MCP tools/list request
    tools_list_request = {
        "jsonrpc": "2.0",
        "id": 2,
        "method": "tools/list",
        "params": {}
    }

    print(f"   Sending tools/list request...")
    response = requests.post(
        GATEWAY_URL,
        headers=headers,
        json=tools_list_request,
        timeout=30
    )

    print(f"   Response status: {response.status_code}")

    if response.status_code == 200:
        print(f"   ✅ Tools list retrieved!")
        try:
            response_data = response.json()
            if "result" in response_data and "tools" in response_data["result"]:
                tools = response_data["result"]["tools"]
                print(f"   Found {len(tools)} tool(s):")
                for tool in tools:
                    print(f"      - {tool.get('name', 'unknown')}: {tool.get('description', 'no description')}")
                print()
                print(f"   Full response: {json.dumps(response_data, indent=2)}")
            else:
                print(f"   Response: {json.dumps(response_data, indent=2)}")
        except Exception as e:
            print(f"   Could not parse response: {e}")
            print(f"   Response text: {response.text[:500]}")
        print()
    else:
        print(f"   ❌ Failed to list tools!")
        print(f"   Response: {response.text[:500]}")
        print()

except Exception as e:
    print(f"   ❌ Error listing tools: {e}")
    import traceback
    traceback.print_exc()
    print()

# Step 5: Test tool invocation
print("🎯 Step 4: Testing tool invocation...")
print("-" * 80)

try:
    # MCP tools/call request for get_complete_po_data
    tool_call_request = {
        "jsonrpc": "2.0",
        "id": 3,
        "method": "tools/call",
        "params": {
            "name": "get_complete_po_data",
            "arguments": {
                "po_number": "4500000520"
            }
        }
    }

    print(f"   Calling tool: get_complete_po_data")
    print(f"   Arguments: po_number=4500000520")
    response = requests.post(
        GATEWAY_URL,
        headers=headers,
        json=tool_call_request,
        timeout=60
    )

    print(f"   Response status: {response.status_code}")

    if response.status_code == 200:
        print(f"   ✅ Tool executed successfully!")
        try:
            response_data = response.json()
            print(f"   Response: {json.dumps(response_data, indent=2)[:1000]}")
        except:
            print(f"   Response text: {response.text[:1000]}")
        print()
    else:
        print(f"   ❌ Tool execution failed!")
        print(f"   Response: {response.text[:500]}")
        print()

except Exception as e:
    print(f"   ❌ Error calling tool: {e}")
    import traceback
    traceback.print_exc()
    print()

print("=" * 80)
print("✅ Gateway authentication test complete!")
print("=" * 80)
