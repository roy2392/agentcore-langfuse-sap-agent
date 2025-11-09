#!/usr/bin/env python3
"""
Test get_complete_po_data fix via MCP gateway
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
        return response.json()["access_token"]
    else:
        print(f"Failed to get token: {response.status_code}")
        sys.exit(1)

def call_tool(token, tool_name, arguments):
    """Call a tool via MCP gateway"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    payload = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/call",
        "params": {
            "name": tool_name,
            "arguments": arguments
        }
    }

    response = requests.post(GATEWAY_URL, headers=headers, json=payload, timeout=60)
    return response.json()

def main():
    print("\nTesting get_complete_po_data fix...")
    print("=" * 80)

    # Get OAuth token
    print("\n1. Authenticating...")
    token = get_oauth_token()
    print("   ✓ Authenticated\n")

    # Test get_complete_po_data with PO 4500001827
    print("2. Testing get_complete_po_data with PO 4500001827...")
    result = call_tool(token, "sap-get-po-target___get_complete_po_data", {
        "po_number": "4500001827"
    })

    print("\n3. Result:")
    print(json.dumps(result, indent=2))

    # Check for error
    if "error" in result:
        print("\n✗ FAILED: Tool returned error")
        print(f"   Error: {result['error'].get('message', 'Unknown error')}")
        sys.exit(1)

    # Check for result
    if "result" in result and "content" in result["result"]:
        content_list = result["result"]["content"]
        if isinstance(content_list, list) and len(content_list) > 0:
            content_text = content_list[0].get("text", "")
            try:
                # Parse the MCP response
                mcp_data = json.loads(content_text)

                # Extract the actual PO data from the Bedrock response wrapper
                if "response" in mcp_data and "responseBody" in mcp_data["response"]:
                    response_body = mcp_data["response"]["responseBody"]
                    if "TEXT" in response_body and "body" in response_body["TEXT"]:
                        po_data_str = response_body["TEXT"]["body"]
                        data = json.loads(po_data_str)
                    else:
                        data = mcp_data
                else:
                    data = mcp_data

                # Now check the actual PO data
                po_number = data.get("purchase_order")
                if po_number == "4500001827":
                    print("\n✓ SUCCESS: Tool correctly returned data for PO 4500001827")
                    summary = data.get('summary', {})
                    print(f"   PO Number: {summary.get('po_number')}")
                    print(f"   Header Found: {summary.get('header_found')}")
                    print(f"   Items Count: {summary.get('items_count')}")
                    print(f"   Total Value: ${summary.get('total_value', 0):,.2f}")
                else:
                    print(f"\n✗ FAILED: Expected PO 4500001827 but got {po_number}")
                    sys.exit(1)
            except json.JSONDecodeError as e:
                print(f"\n✗ FAILED: Could not parse JSON response: {e}")
                print(f"   Content: {content_text[:200]}...")
                sys.exit(1)
        else:
            print("\n✗ FAILED: No content in response")
            sys.exit(1)
    else:
        print("\n✗ FAILED: No result field in response")
        sys.exit(1)

    print("\n" + "=" * 80)
    print("All tests passed!\n")

if __name__ == "__main__":
    main()
