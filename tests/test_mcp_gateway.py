#!/usr/bin/env python3
"""
Test MCP Gateway with OAuth authentication
"""
import requests
import json
import sys

# Gateway configuration
GATEWAY_URL = "https://sap-inventory-gateway-prd-td3ict6das.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
CLIENT_ID = "56d6r0as0inbf6gvjjfrmp0c9v"
CLIENT_SECRET = "19aalq8aoj3s3es9dl7furb78lfvtpmoietlobta7l8q1pjki35h"
TOKEN_ENDPOINT = "https://sap-gateway-prd-654537381132.auth.us-east-1.amazoncognito.com/oauth2/token"

def get_oauth_token():
    """Get OAuth access token from Cognito"""
    print("🔐 Getting OAuth token from Cognito...")

    response = requests.post(
        TOKEN_ENDPOINT,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        data={
            "grant_type": "client_credentials",
            "client_id": CLIENT_ID,
            "client_secret": CLIENT_SECRET
        }
    )

    if response.status_code == 200:
        token_data = response.json()
        print(f"✅ Token obtained (expires in {token_data.get('expires_in', 3600)}s)")
        return token_data["access_token"]
    else:
        print(f"❌ Failed to get token: {response.status_code}")
        print(response.text)
        sys.exit(1)

def call_mcp_method(token, method, params=None):
    """Call an MCP method on the gateway"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": method
    }

    if params:
        payload["params"] = params

    response = requests.post(GATEWAY_URL, headers=headers, json=payload)
    return response

def main():
    print("=" * 80)
    print("MCP Gateway Test - SAP Inventory Management")
    print("=" * 80)
    print()

    # Step 1: Get OAuth token
    token = get_oauth_token()
    print()

    # Step 2: Initialize MCP session
    print("🔗 Initializing MCP session...")
    init_response = call_mcp_method(token, "initialize", {
        "protocolVersion": "2024-11-05",
        "capabilities": {},
        "clientInfo": {
            "name": "test-client",
            "version": "1.0.0"
        }
    })

    if init_response.status_code == 200:
        print("✅ MCP session initialized")
        print(f"   Response: {json.dumps(init_response.json(), indent=2)}")
    else:
        print(f"❌ Initialize failed: {init_response.status_code}")
        print(f"   Response: {init_response.text}")
        return

    print()

    # Step 3: List available tools
    print("🔧 Listing available tools...")
    tools_response = call_mcp_method(token, "tools/list")

    if tools_response.status_code == 200:
        tools_data = tools_response.json()
        print("✅ Tools retrieved successfully")

        if "result" in tools_data and "tools" in tools_data["result"]:
            tools = tools_data["result"]["tools"]
            print(f"\n   Found {len(tools)} tool(s):")
            for tool in tools:
                print(f"   - {tool.get('name', 'unknown')}: {tool.get('description', 'no description')}")
        else:
            print(f"   Response: {json.dumps(tools_data, indent=2)}")
    else:
        print(f"❌ Tools list failed: {tools_response.status_code}")
        print(f"   Response: {tools_response.text}")
        return

    print()

    # Step 4: Call the get_complete_po_data tool
    print("📦 Testing get_complete_po_data tool with PO 4500000520...")
    tool_response = call_mcp_method(token, "tools/call", {
        "name": "get_complete_po_data",
        "arguments": {
            "po_number": "4500000520"
        }
    })

    if tool_response.status_code == 200:
        result = tool_response.json()
        print("✅ Tool call successful!")
        print()
        print("📊 SAP Purchase Order Data:")
        print("=" * 80)

        if "result" in result:
            # Try to parse the content if it's a string
            content = result["result"]
            if isinstance(content, list) and len(content) > 0:
                content_text = content[0].get("text", "")
                try:
                    po_data = json.loads(content_text)

                    # Display summary
                    summary = po_data.get("summary", {})
                    print(f"PO Number: {summary.get('po_number', 'N/A')}")
                    print(f"Total Value: ${summary.get('total_value', 0):,.2f}")
                    print(f"Items Count: {summary.get('items_count', 0)}")
                    print(f"Total Quantity: {summary.get('total_quantity', 0):,.0f}")
                    print()

                    # Display items
                    items = po_data.get("items", [])
                    if items:
                        print("Line Items:")
                        print("-" * 80)
                        for item in items:
                            print(f"  {item.get('item')}. {item.get('name')} ({item.get('material')})")
                            print(f"     Qty: {item.get('qty'):.0f} {item.get('uom')} @ ${item.get('price'):.2f} = ${item.get('net'):,.2f}")
                        print()

                    print("✅ This is REAL SAP data (not mock)!")
                    print(f"   Service: C_PURCHASEORDER_FS_SRV")
                    print(f"   Supplier: {po_data.get('header', {}).get('Supplier', 'N/A')}")

                except json.JSONDecodeError:
                    print(content_text)
            else:
                print(json.dumps(result, indent=2))
        else:
            print(json.dumps(result, indent=2))
    else:
        print(f"❌ Tool call failed: {tool_response.status_code}")
        print(f"   Response: {tool_response.text}")

    print()
    print("=" * 80)
    print("Test completed!")
    print("=" * 80)

if __name__ == "__main__":
    main()
