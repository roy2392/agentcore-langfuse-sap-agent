#!/bin/bash
# Get OAuth access token from AWS Cognito for MCP Gateway testing

CLIENT_ID="56d6r0as0inbf6gvjjfrmp0c9v"
CLIENT_SECRET="19aalq8aoj3s3es9dl7furb78lfvtpmoietlobta7l8q1pjki35h"
TOKEN_ENDPOINT="https://sap-gateway-prd-654537381132.auth.us-east-1.amazoncognito.com/oauth2/token"

echo "Getting OAuth token from Cognito..."
echo ""

response=$(curl -s -X POST "$TOKEN_ENDPOINT" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "grant_type=client_credentials&client_id=$CLIENT_ID&client_secret=$CLIENT_SECRET")

# Extract access token using grep/sed (works without jq)
access_token=$(echo "$response" | grep -o '"access_token":"[^"]*"' | sed 's/"access_token":"//;s/"$//')

if [ -n "$access_token" ]; then
    echo "✅ Access Token obtained successfully!"
    echo ""
    echo "Copy this token to use with MCP Inspector:"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "$access_token"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""
    echo "Token expires in: 3600 seconds (1 hour)"
    echo ""
    echo "Export as environment variable:"
    echo "export GATEWAY_TOKEN='$access_token'"
else
    echo "❌ Failed to get access token"
    echo "Response: $response"
    exit 1
fi
