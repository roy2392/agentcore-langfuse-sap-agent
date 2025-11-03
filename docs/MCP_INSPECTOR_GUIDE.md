# Testing SAP MCP Gateway in MCP Inspector

## Gateway Configuration

Your MCP Gateway is configured with OAuth 2.0 authentication using AWS Cognito.

### Gateway Details
- **Gateway URL**: `https://sap-inventory-gateway-prd-g33wqycje0.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp`
- **Authorization Type**: CUSTOM_JWT (OAuth 2.0 Client Credentials)
- **Cognito User Pool**: `us-east-1_7m45pE9la`
- **Client ID**: `56d6r0as0inbf6gvjjfrmp0c9v`
- **Client Secret**: `19aalq8aoj3s3es9dl7furb78lfvtpmoietlobta7l8q1pjki35h`
- **Cognito Domain**: `sap-gateway-prd-654537381132`
- **Token Endpoint**: `https://sap-gateway-prd-654537381132.auth.us-east-1.amazoncognito.com/oauth2/token`

## Method 1: Using MCP Inspector with OAuth

### Step 1: Get OAuth Access Token

First, obtain an access token from Cognito:

```bash
# Use the helper script
cd /Users/royzalta/Documents/GitHub/agentcore-langfuse-sap-agent
./utils/get_oauth_token.sh
```

This will return an access token that's valid for 1 hour.

### Step 2: Connect MCP Inspector

1. Install MCP Inspector (if not already installed):
```bash
npm install -g @modelcontextprotocol/inspector
```

2. Launch MCP Inspector:
```bash
npx @modelcontextprotocol/inspector
```

3. In the MCP Inspector UI:
   - **Server URL**: `https://sap-inventory-gateway-prd-g33wqycje0.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp`
   - **Transport Type**: SSE (Server-Sent Events)
   - **Authentication**: Custom Headers
     - Add header: `Authorization: Bearer <YOUR_ACCESS_TOKEN>`
     - Replace `<YOUR_ACCESS_TOKEN>` with the token from Step 1

### Step 3: Test the Gateway

Once connected, you should see available tools:
- `get_complete_po_data` - Get complete purchase order data including header and line items

Test it by calling:
```json
{
  "tool": "get_complete_po_data",
  "arguments": {
    "po_number": "4500000520"
  }
}
```

Expected response: Real SAP data with 7 bicycle component items (Frame, Handle Bars, Seat, Wheels, Forks, Brakes, Drive Train) totaling $209,236.00.

## Method 2: Using curl for Quick Testing

### Get OAuth Token
```bash
curl -X POST https://sap-gateway-prd-654537381132.auth.us-east-1.amazoncognito.com/oauth2/token \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'grant_type=client_credentials&client_id=56d6r0as0inbf6gvjjfrmp0c9v&client_secret=19aalq8aoj3s3es9dl7furb78lfvtpmoietlobta7l8q1pjki35h'
```

### Test Gateway (replace TOKEN with the access_token from above)
```bash
curl -X POST https://sap-inventory-gateway-prd-g33wqycje0.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp \
  -H 'Authorization: Bearer TOKEN' \
  -H 'Content-Type: application/json' \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/list"
  }'
```

## Method 3: Using Python Test Script

A test script has been created for you:

```bash
cd /Users/royzalta/Documents/GitHub/agentcore-langfuse-sap-agent
python utils/test_mcp_gateway.py
```

This script will:
1. Automatically get an OAuth token from Cognito
2. Connect to the MCP Gateway
3. List available tools
4. Test the `get_complete_po_data` tool with PO 4500000520
5. Display the real SAP data

## Troubleshooting

### 401 Unauthorized
- Token expired (tokens last 1 hour) - get a new token
- Invalid token - verify you're using the correct client_id and client_secret

### 403 Forbidden
- Client ID not in allowedClients list
- Check gateway configuration in `terraform/gateway_output.json`

### Connection Timeout
- Gateway may still be initializing (status: CREATING)
- Check gateway status: `aws bedrock-agentcore get-gateway --gateway-id sap-inventory-gateway-prd-g33wqycje0 --region us-east-1`

### No Tools Listed
- Gateway targets may not be configured
- Check Lambda function exists and is accessible
- Verify IAM role permissions

## Verify Real SAP Data

The Lambda function uses the **real SAP OData API** at:
- Service: `C_PURCHASEORDER_FS_SRV`
- Endpoints:
  - Header: `/sap/opu/odata/sap/C_PURCHASEORDER_FS_SRV/I_PurchaseOrder`
  - Items: `/sap/opu/odata/sap/C_PURCHASEORDER_FS_SRV/I_PurchaseOrderItem`

Test PO 4500000520 should return:
- 7 line items (bicycle components)
- Total value: $209,236.00
- Supplier: USSU-VSF08
- Currency: USD

This confirms the Lambda is **NOT using mock data** as requested!
