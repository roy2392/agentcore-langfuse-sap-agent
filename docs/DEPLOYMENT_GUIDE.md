# SAP Inventory Agent - Complete Deployment Guide

This guide walks through deploying the SAP inventory management agent using AWS Bedrock AgentCore Gateway with Lambda-based tool implementation.

## Quick Summary

- **Architecture**: Agent → AgentCore Gateway (OAuth) → Lambda Functions → SAP OData API
- **Authentication**: AWS Cognito OAuth 2.0 (Client Credentials flow)
- **Tools**: 9 SAP inventory tools via AWS Lambda functions
- **Deployment**: Terraform infrastructure + Python agent deployment scripts

## Prerequisites

1. **AWS Account** with Bedrock AgentCore preview access
2. **AWS CLI** configured with credentials (`aws configure`)
3. **Terraform** >= 1.0 installed
4. **Python 3.12+** installed
5. **SAP OData API** credentials:
   - SAP_HOST
   - SAP_USER
   - SAP_PASSWORD

## Phase 1: Deploy Infrastructure (15 minutes)

### Step 1.1: Clone and Configure

```bash
# Clone the repository
git clone <your-repo-url>
cd agentcore-langfuse-sap-agent

# Navigate to terraform directory
cd terraform

# Copy and edit terraform variables
cp terraform.tfvars.example terraform.tfvars
nano terraform.tfvars
```

**terraform.tfvars:**
```hcl
aws_region   = "us-east-1"
environment  = "prd"

sap_host     = "your-sap-host.example.com"
sap_user     = "your_sap_username"
sap_password = "your_sap_password"
```

### Step 1.2: Prepare Lambda Dependencies

```bash
# Create Lambda layer with Python dependencies
mkdir -p lambda_layer/python
pip install requests -t lambda_layer/python/
cd lambda_layer
zip -r ../lambda_layer.zip python/
cd ..
```

### Step 1.3: Deploy Terraform Infrastructure

```bash
# Initialize Terraform
terraform init

# Review what will be created
terraform plan

# Deploy infrastructure
terraform apply
```

**Expected Output:**
```
Outputs:

cognito_client_id = "xxxxx"
cognito_domain = "sap-gateway-prd-123456789"
gateway_endpoint_url = "https://gateway-id.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp"
gateway_id = "sap-inventory-gateway-prd-xxxxx"
lambda_function_arns = {
  get_complete_po_data = "arn:aws:lambda:us-east-1:123456789:function:sap-get-complete-po-data-prd"
  sap_tools = "arn:aws:lambda:us-east-1:123456789:function:sap-tools-prd"
}
```

**What this created:**
- ✅ AWS Secrets Manager secret with SAP credentials
- ✅ Lambda functions for SAP tools (get_complete_po_data, sap_tools)
- ✅ AgentCore Gateway with Lambda targets
- ✅ Cognito User Pool for OAuth authentication
- ✅ IAM roles and policies with least-privilege access

### Step 1.4: Save Gateway Configuration

```bash
# Terraform automatically saves output to gateway_output.json
cat gateway_output.json
```

This file is used by the agent deployment scripts in Phase 2.

---

## Phase 2: Deploy Agent (10 minutes)

### Step 2.1: Set Up Environment

```bash
# Return to project root
cd ..

# Install Python dependencies
pip install -r requirements.txt
```

### Step 2.2: Configure Cognito Client Secret

```bash
# Get the Cognito client secret from AWS
export COGNITO_CLIENT_SECRET=$(aws cognito-idp describe-user-pool-client \
  --user-pool-id <from gateway_output.json> \
  --client-id <from gateway_output.json> \
  --query 'UserPoolClient.ClientSecret' \
  --output text \
  --region us-east-1)

# Verify it's set
echo $COGNITO_CLIENT_SECRET
```

### Step 2.3: Deploy Agent to TST Environment

```bash
# Deploy to TEST environment first
python cicd/deploy_agent.py --environment TST

# Expected output:
# Loading agent hyperparameters...
# Reading system prompt from cicd/system_prompt_english.txt...
# Deploying agent with:
#   Model: s3 (anthropic.claude-3-5-sonnet-20240620-v1:0)
#   System Prompt: english
#   Environment: TST
#   Gateway URL: https://gateway-id.gateway...
# Agent deployment successful!
# Agent Name: strands_s3_english_TST-xxxxx
# Agent ARN: arn:aws:bedrock-agentcore:us-east-1:...
```

### Step 2.4: Test TST Agent

```bash
# Run end-to-end test
python cicd/tst.py

# Expected output:
# Testing agent: strands_s3_english_TST-xxxxx
# Query: "What are the details of purchase order 4500000520?"
# ✓ Agent responded successfully
# ✓ Used get_complete_po_data tool
# ✓ Response contains PO details
```

### Step 2.5: Deploy to Production

```bash
# Once TST tests pass, deploy to PRD
python cicd/deploy_agent.py --environment PRD

# Expected output:
# Agent deployment successful!
# Agent Name: strands_s3_english_PRD-xxxxx
```

---

## Phase 3: Verify Deployment (5 minutes)

### Step 3.1: Test Gateway Connectivity

```bash
# Get OAuth token
python utils/test_mcp_gateway.py

# This will:
# 1. Get OAuth token from Cognito
# 2. List tools from Gateway
# 3. Invoke a test tool
# 4. Verify response
```

### Step 3.2: Test Agent via UI (Optional)

If you deployed the App Runner UI:

```bash
cd terraform
terraform apply -target=aws_apprunner_service.ui

# Get UI URL from output
# Visit the URL in your browser
# Test queries like: "What purchase orders are open?"
```

### Step 3.3: Monitor Agent Performance

```bash
# Check Langfuse traces (if configured)
# Visit: https://cloud.langfuse.com

# Check CloudWatch logs
aws logs tail /aws/lambda/sap-get-complete-po-data-prd --follow
```

---

## Available SAP Tools

The deployed agent has access to these tools via Lambda:

1. **get_material_stock** - Get material inventory levels
2. **get_open_purchase_orders** - List open purchase orders
3. **get_orders_awaiting_invoice_or_delivery** - Find orders missing invoices/deliveries
4. **get_inventory_with_open_orders** - Materials with both stock and open orders
5. **get_goods_receipts** - Recent goods receipts
6. **list_purchase_orders** - List POs with filters
7. **search_purchase_orders** - Search for specific PO
8. **get_material_in_transit** - Materials currently in transit
9. **get_complete_po_data** - Complete PO details (header + items)

---

## Customizing System Prompts

The agent's behavior is controlled by system prompts in `cicd/`:

```bash
# Edit the active prompt
nano cicd/system_prompt_english.txt

# The hp_config.json references this file
# Changes take effect on next deployment
python cicd/deploy_agent.py --environment TST --force-redeploy
```

**Available prompts:**
- `system_prompt_english.txt` - Current production prompt (tool-focused, concise)
- `system_prompt_conversational.txt` - More conversational style
- `system_prompt_smart.txt` - Advanced analytical style

---

## Updating the Agent

### Update System Prompt Only

```bash
# Edit prompt
nano cicd/system_prompt_english.txt

# Force redeploy to update
python cicd/deploy_agent.py --environment TST --force-redeploy
```

### Update Lambda Functions

```bash
# Edit lambda function code
nano lambda_functions/get_complete_po_data.py

# Redeploy terraform
cd terraform
terraform apply -target=aws_lambda_function.get_complete_po_data

# Test updated function
cd ..
python utils/test_e2e_agent.py
```

### Update Agent Model

```bash
# Edit hp_config.json
nano cicd/hp_config.json

# Change model_id to desired model
# Example: anthropic.claude-3-7-sonnet-20250219-v1:0

# Redeploy
python cicd/deploy_agent.py --environment TST --force-redeploy
```

---

## Troubleshooting

### Agent Can't Access Tools

**Symptom**: Agent says "I don't have access to that tool"

**Fix**:
```bash
# Check Gateway target status
aws bedrock-agentcore-control list-gateway-targets \
  --gateway-identifier <gateway_id> \
  --region us-east-1

# Verify Lambda permissions
aws lambda get-policy \
  --function-name sap-tools-prd
```

### OAuth Authentication Failures

**Symptom**: "Unauthorized" or "Invalid token"

**Fix**:
```bash
# Verify Cognito client secret is set
echo $COGNITO_CLIENT_SECRET

# Test OAuth flow manually
python -c "
from utils.gateway import get_oauth_token
token = get_oauth_token('<client_id>', '<client_secret>', '<domain>')
print(f'Token: {token[:20]}...')
"
```

### Lambda Timeout Errors

**Symptom**: "Task timed out after 30 seconds"

**Fix**:
```bash
# Increase Lambda timeout in terraform/lambda.tf
# Change timeout = 30 to timeout = 60

cd terraform
terraform apply -target=aws_lambda_function.get_complete_po_data
```

### SAP Connection Failures

**Symptom**: "Failed to connect to SAP host"

**Fix**:
```bash
# Verify SAP credentials in Secrets Manager
aws secretsmanager get-secret-value \
  --secret-id agentcore/sap/credentials-prd \
  --query SecretString \
  --output text

# Test SAP connection directly
python utils/test_sap_api.py
```

---

## Cleanup

### Delete Agent Only

```bash
# Delete specific agent
python cicd/delete_agent.py --environment TST

# Or specify agent ID
python cicd/delete_agent.py --agent-id strands_s3_english_TST-xxxxx
```

### Delete All Infrastructure

```bash
# Delete all AWS resources
cd terraform
terraform destroy

# Confirm with 'yes'
```

**What gets deleted:**
- ✅ AgentCore Gateway and targets
- ✅ Lambda functions
- ✅ Cognito User Pool
- ✅ Secrets Manager secret
- ✅ IAM roles and policies
- ✅ CloudWatch log groups

---

## Cost Estimation

**Monthly costs for development workload (us-east-1):**

| Service | Cost |
|---------|------|
| AgentCore Gateway | ~$0 (preview pricing TBD) |
| Lambda (10K invocations) | ~$0.20 |
| Secrets Manager | $0.40 per secret |
| Cognito | Free (< 50K MAU) |
| CloudWatch Logs | ~$0.50 |
| **Total** | **< $2/month** |

**Production workload (100K invocations/month):**
- Lambda: ~$2.00
- Other services: ~$1.00
- **Total: < $5/month**

---

## Security Best Practices

✅ **Implemented:**
- SAP credentials stored in AWS Secrets Manager (encrypted at rest)
- OAuth 2.0 for Gateway authentication
- IAM roles with least-privilege access
- No credentials in code or environment variables
- Terraform state includes sensitive data (`.gitignore`d)

✅ **Recommended:**
- Enable VPC for Lambda functions (if SAP is in private network)
- Enable CloudWatch Logs encryption
- Rotate SAP credentials regularly
- Use AWS Organizations for multi-account setup
- Enable AWS CloudTrail for audit logging

---

## Next Steps

1. **Integrate with Slack/Teams**: Use the deployed agent API
2. **Add More Tools**: Extend `lambda_functions/sap_tools.py`
3. **Improve Prompts**: Iterate on system prompts for better responses
4. **Monitor Performance**: Set up CloudWatch dashboards
5. **Scale Up**: Increase Lambda memory/timeout for production load

---

## References

- [AWS AgentCore Documentation](https://docs.aws.amazon.com/bedrock-agentcore/latest/devguide/)
- [Terraform Configuration](../terraform/README.md)
- [Architecture Overview](ARCHITECTURE.md)
- [MCP Protocol Specification](https://modelcontextprotocol.io/)
- [Langfuse Observability](https://langfuse.com/docs)
