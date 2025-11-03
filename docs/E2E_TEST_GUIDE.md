# End-to-End Testing Guide

## Complete Flow Test

This guide helps you verify the **complete end-to-end flow**:

```
User Question (Hebrew)
    ↓
AWS Bedrock Agent
    ↓
MCP Gateway (OAuth Protected)
    ↓
Lambda Function
    ↓
Real SAP OData API
    ↓
Response with Real Data
```

## Quick Start

### Test the Complete E2E Flow

Run this single command to test everything:

```bash
cd /Users/royzalta/Documents/GitHub/agentcore-langfuse-sap-agent
python utils/test_e2e_agent.py
```

This will:
1. Connect to your deployed agent
2. Ask questions in Hebrew about PO 4500000520
3. Verify the agent uses the MCP Gateway
4. Confirm OAuth authentication works
5. Validate responses contain REAL SAP data

### Expected Output

```
🧪 End-to-End Agent Test
Testing: User → Agent → MCP Gateway (OAuth) → Lambda → Real SAP
================================================================================

📡 Connecting to agent: strands_s3_hebinv_PRD-9BFPdlAkq9
   Session ID: e2e-test-xxxxx

📝 Test 1/2: Hebrew: What is the information about purchase order 4500000520?
   Question: מה המידע על הזמנת רכש 4500000520?
--------------------------------------------------------------------------------

   Agent Response:
   הזמנת רכש 4500000520 כוללת 7 פריטים של רכיבי אופניים BKC-990...

   ✅ Found expected data: 4500000520, BKC-990, Frame, 209236

================================================================================

📊 Test Summary
✅ PASS: Hebrew: What is the information about purchase order 4500000520?
✅ PASS: Hebrew: How many items are in purchase order 4500000520?

Results: 2/2 tests passed

🎉 SUCCESS! End-to-end flow is working correctly!
   ✅ Agent → MCP Gateway (OAuth) → Lambda → Real SAP Data
```

## What Gets Tested

### 1. Agent Invocation
- Agent receives Hebrew language question
- Agent processes natural language query
- Agent determines which tool to use

### 2. MCP Gateway Communication
- Agent connects to Gateway URL with OAuth
- Gateway validates JWT token from Cognito
- Gateway routes request to correct Lambda

### 3. Lambda Execution
- Lambda receives tool parameters
- Lambda calls SAP OData API
- Lambda returns structured JSON response

### 4. Real SAP Data Verification
The test verifies responses contain:
- **PO Number**: 4500000520
- **Product Names**: BKC-990 Frame, Handle Bars, Seat, Wheels, Forks, Brakes, Drive Train
- **Supplier**: USSU-VSF08
- **Total Value**: $209,236.00
- **Item Count**: 7 items

This confirms the Lambda is using **REAL SAP** data from `C_PURCHASEORDER_FS_SRV` service, NOT mock data!

## Manual Testing

If you want to test interactively:

### Using Python Console

```python
import boto3

client = boto3.client('bedrock-agentcore', region_name='us-east-1')

response = client.invoke_agent_runtime(
    agentRuntimeArn='arn:aws:bedrock-agentcore:us-east-1:654537381132:runtime/strands_s3_hebinv_PRD-9BFPdlAkq9',
    runtimeSessionId='test-123',
    payload={'message': 'מה המידע על הזמנת רכש 4500000520?'}
)

# Process response stream...
```

### Using AWS CLI (if available)

```bash
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-arn "arn:aws:bedrock-agentcore:us-east-1:654537381132:runtime/strands_s3_hebinv_PRD-9BFPdlAkq9" \
  --runtime-session-id "test-$(date +%s)" \
  --payload '{"message": "מה המידע על הזמנת רכש 4500000520?"}' \
  --region us-east-1
```

## Troubleshooting

### Agent Not Responding
- Check agent status: Is it deployed and running?
- Verify agent ARN in `.bedrock_agentcore.yaml`
- Check CloudWatch Logs for agent runtime errors

### OAuth Errors (401/403)
- Gateway OAuth configuration might have issues
- Verify Cognito client credentials are correct
- Check if agent has proper IAM permissions to call Gateway

### No SAP Data in Response
- Lambda might not be calling SAP API correctly
- Check Lambda CloudWatch logs
- Verify SAP credentials in Secrets Manager
- Test Lambda directly: `aws lambda invoke --function-name sap-get-complete-po-data-prd`

### Mock Data Appearing
If you see mock data instead of real SAP data:
- This should NOT happen anymore!
- Lambda was updated to use real `C_PURCHASEORDER_FS_SRV` service
- Check `lambda_functions/get_complete_po_data.py` - it should NOT have mock data fallback

## Architecture Flow Diagram

```
┌─────────────┐
│    User     │
│  (Hebrew)   │
└──────┬──────┘
       │ "מה המידע על הזמנת רכש 4500000520?"
       ↓
┌──────────────────────────┐
│  Bedrock Agent Runtime   │
│  strands_s3_hebinv_PRD   │
└──────────┬───────────────┘
           │ Tool: get_complete_po_data
           │ Args: {po_number: "4500000520"}
           ↓
┌──────────────────────────────────────┐
│  MCP Gateway (OAuth Protected)       │
│  sap-inventory-gateway-prd-g33wqycje0│
│  ✓ Validates JWT from Cognito        │
│  ✓ Routes to Lambda                  │
└──────────┬───────────────────────────┘
           │ HTTP POST with OAuth Bearer token
           ↓
┌──────────────────────────────────────┐
│  Lambda Function                     │
│  sap-get-complete-po-data-prd        │
│  ✓ Gets SAP credentials from Secrets │
│  ✓ Calls C_PURCHASEORDER_FS_SRV      │
└──────────┬───────────────────────────┘
           │ OData API Call
           ↓
┌──────────────────────────────────────┐
│  SAP Demo System                     │
│  aws-saptfc-demosystems-sapsbx       │
│  ✓ Returns REAL purchase order data  │
└──────────┬───────────────────────────┘
           │ JSON Response
           ↓
    [Agent formats and responds in Hebrew]
```

## Success Criteria

The E2E test passes when:
- ✅ Agent responds to Hebrew questions
- ✅ OAuth authentication succeeds (no 401/403 errors)
- ✅ Lambda is invoked through Gateway
- ✅ Response contains real SAP data fields:
  - PO number 4500000520
  - Product names (BKC-990 series)
  - Supplier USSU-VSF08
  - Total value $209,236
- ✅ NO mock data in responses

## Next Steps

After successful E2E testing:
1. Test with other PO numbers from SAP system
2. Add more test cases for error scenarios
3. Set up monitoring/alerting for production
4. Document additional SAP OData endpoints to integrate

---

**Last Updated**: 2025-11-03
**System Status**: ✅ All components deployed and tested
**Data Source**: Real SAP C_PURCHASEORDER_FS_SRV (NOT mock)
