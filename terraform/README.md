# AWS AgentCore Gateway - Terraform Infrastructure

This Terraform configuration deploys the complete AWS AgentCore Gateway infrastructure for SAP inventory management following AWS best practices.

## Architecture

```
Agent → AgentCore Gateway (OAuth) → Lambda Targets → SAP OData API
```

**Components:**
- **Cognito User Pool**: OAuth 2.0 authentication for Gateway
- **AgentCore Gateway**: MCP server endpoint with semantic search
- **Lambda Functions**: SAP tool implementations (get_complete_po_data, etc.)
- **Secrets Manager**: Secure SAP credential storage
- **IAM Roles**: Least-privilege access control

## Prerequisites

1. **AWS CLI** configured with credentials
2. **Terraform** >= 1.0
3. **Python 3.12** for Lambda functions
4. **SAP OData API** access credentials
5. **AWS Bedrock AgentCore** preview access enabled

## Setup Instructions

### 1. Install Dependencies

```bash
# Install Terraform
brew install terraform  # macOS
# or download from https://www.terraform.io/downloads

# Verify installation
terraform version
```

### 2. Configure Credentials

```bash
cd terraform

# Copy example tfvars
cp terraform.tfvars.example terraform.tfvars

# Edit with your actual credentials
nano terraform.tfvars
```

**terraform.tfvars:**
```hcl
aws_region   = "us-east-1"
environment  = "prd"

sap_host     = "aws-saptfc-demosystems-sapsbx.awsforsap.sap.aws.dev"
sap_user     = "AWSDEMO"
sap_password = "your-actual-password"
```

### 3. Prepare Lambda Layer (Python Dependencies)

```bash
# Create Lambda layer with dependencies
mkdir -p lambda_layer/python
pip install requests -t lambda_layer/python/
cd lambda_layer
zip -r ../lambda_layer.zip python/
cd ..
```

### 4. Deploy Infrastructure

```bash
# Initialize Terraform
terraform init

# Review planned changes
terraform plan

# Apply configuration
terraform apply
```

**Expected output:**
```
gateway_url = "https://gateway-id.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
gateway_id = "sap-inventory-gateway-prd-xxxxx"
cognito_client_id = "xxxxx"
lambda_function_arns = {
  get_complete_po_data = "arn:aws:lambda:us-east-1:xxxxx:function:sap-get-complete-po-data-prd"
}
```

### 5. Get OAuth Access Token

```bash
# Get Cognito client secret
aws cognito-idp describe-user-pool-client \
  --user-pool-id <USER_POOL_ID> \
  --client-id <CLIENT_ID> \
  --query 'UserPoolClient.ClientSecret' \
  --output text

# Get access token
python3 << EOF
import boto3
import base64

client = boto3.client('cognito-idp', region_name='us-east-1')

# Your Cognito details
client_id = '<CLIENT_ID>'
client_secret = '<CLIENT_SECRET>'
user_pool_id = '<USER_POOL_ID>'

# Encode credentials
secret = f'{client_id}:{client_secret}'
encoded = base64.b64encode(secret.encode()).decode()

# Get token
import urllib.request
import json

domain = f'sap-gateway-prd-<ACCOUNT_ID>.auth.us-east-1.amazoncognito.com'
url = f'https://{domain}/oauth2/token'

data = 'grant_type=client_credentials&scope=sap-gateway-prd/tools.invoke'
headers = {
    'Authorization': f'Basic {encoded}',
    'Content-Type': 'application/x-www-form-urlencoded'
}

req = urllib.request.Request(url, data.encode(), headers)
with urllib.request.urlopen(req) as response:
    token_data = json.loads(response.read())
    print(f"Access Token: {token_data['access_token']}")
EOF
```

## Testing the Gateway

### Test with curl

```bash
# Set variables
GATEWAY_URL="<gateway_url from terraform output>"
ACCESS_TOKEN="<token from above>"

# List available tools
curl -X POST $GATEWAY_URL \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/list"
  }'

# Invoke get_complete_po_data tool
curl -X POST $GATEWAY_URL \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "method": "tools/call",
    "params": {
      "name": "get_complete_po_data",
      "arguments": {
        "po_number": "4500000520"
      }
    }
  }'
```

### Test with Agent

```python
from strands import Agent
from strands.models import BedrockModel
from strands.tools.mcp.mcp_client import MCPClient
from mcp.client.streamable_http import streamablehttp_client

def create_transport(gateway_url, access_token):
    return streamablehttp_client(
        gateway_url,
        headers={"Authorization": f"Bearer {access_token}"}
    )

# Configure
gateway_url = "<gateway_url>"
access_token = "<access_token>"

# Create agent
model = BedrockModel(
    inference_profile_id="anthropic.claude-3-7-sonnet-20250219-v1:0"
)

mcp_client = MCPClient(lambda: create_transport(gateway_url, access_token))

with mcp_client:
    tools = mcp_client.list_tools_sync()
    agent = Agent(model=model, tools=tools)

    # Test query
    response = agent("What are the details of purchase order 4500000520?")
    print(response)
```

## Infrastructure Components

### Cognito OAuth
- **User Pool**: `sap-gateway-oauth-prd`
- **Resource Server**: `sap-gateway-prd`
- **OAuth Scope**: `sap-gateway-prd/tools.invoke`
- **Client**: OAuth 2.0 Client Credentials flow

### Gateway
- **Name**: `sap-inventory-gateway-prd`
- **Protocol**: MCP
- **Auth**: AWS IAM + Cognito JWT
- **Targets**: Lambda functions for SAP tools

### Lambda Functions
- **get_complete_po_data**: Retrieve PO header + items
- **Runtime**: Python 3.12
- **Timeout**: 30 seconds
- **Memory**: 512 MB

### Secrets Manager
- **Secret Name**: `agentcore/sap/credentials-prd`
- **Contents**: SAP_HOST, SAP_USER, SAP_PASSWORD

## Cleanup

```bash
# Destroy all infrastructure
terraform destroy

# Confirm with 'yes' when prompted
```

## Troubleshooting

### Lambda Function Errors
```bash
# Check Lambda logs
aws logs tail /aws/lambda/sap-get-complete-po-data-prd --follow
```

### Gateway Target Issues
```bash
# Check target status
aws bedrock-agentcore-control get-gateway-target \
  --gateway-identifier <gateway_id> \
  --target-id <target_id> \
  --region us-east-1
```

### OAuth Token Issues
```bash
# Verify Cognito configuration
aws cognito-idp describe-user-pool \
  --user-pool-id <user_pool_id>
```

## Security Best Practices

✅ **Implemented:**
- SAP credentials in Secrets Manager (not environment variables)
- OAuth 2.0 for Gateway authentication
- IAM least-privilege roles
- Lambda in VPC (optional, configure if needed)

❌ **Not committed to repo:**
- `terraform.tfvars` (actual credentials)
- `*.tfstate` files (contain sensitive data)
- `lambda_layer.zip` (binary dependencies)

## Cost Estimation

**Monthly costs (us-east-1):**
- AgentCore Gateway: ~$0 (preview, pricing TBD)
- Lambda invocations: ~$0.20/million requests
- Secrets Manager: $0.40/secret/month
- Cognito: Free tier (50,000 MAUs)

**Total estimated**: < $5/month for development workloads

## References

- [AWS AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [AgentCore Starter Toolkit](https://github.com/aws/bedrock-agentcore-starter-toolkit)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
