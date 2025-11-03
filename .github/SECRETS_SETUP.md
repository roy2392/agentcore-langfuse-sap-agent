# GitHub Secrets Setup

This document describes the GitHub Secrets that need to be configured for the CI/CD pipeline to work correctly.

## Required Secrets

### AWS Credentials

- `AWS_ACCESS_KEY_ID`: AWS access key for deploying agents
- `AWS_SECRET_ACCESS_KEY`: AWS secret access key
- `AWS_REGION`: AWS region (e.g., `us-east-1`)

### MCP Gateway OAuth Configuration

These secrets are required for the agent to connect to the MCP Gateway with OAuth authentication:

- `GATEWAY_ENDPOINT_URL`: The MCP Gateway endpoint URL
  - Example: `https://sap-inventory-gateway-prd-g33wqycje0.gateway.bedrock-agentcore.us-east-1.amazonaws.com/mcp`

- `COGNITO_CLIENT_ID`: AWS Cognito OAuth 2.0 client ID
  - Example: `56d6r0as0inbf6gvjjfrmp0c9v`

- `COGNITO_CLIENT_SECRET`: AWS Cognito OAuth 2.0 client secret
  - Example: `19aalq8aoj3s3es9dl7furb78lfvtpmoietlobta7l8q1pjki35h`

- `COGNITO_DOMAIN`: AWS Cognito domain (without https:// or /oauth2/token)
  - Example: `sap-gateway-prd-654537381132`

## How to Add GitHub Secrets

1. Go to your GitHub repository
2. Click on **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret with its name and value
5. Click **Add secret**

## Finding the Values

### Gateway Configuration

You can find the Gateway configuration values in:

- `utils/test_mcp_gateway.py` - Contains the Gateway URL and Cognito configuration
- `utils/get_oauth_token.sh` - Contains the OAuth token endpoint configuration

### AWS Credentials

AWS credentials should be from an IAM user or role with the following permissions:

- `bedrock:*` - For Bedrock AgentCore operations
- `ecr:*` - For ECR repository management
- `iam:PassRole` - For agent execution role
- `ssm:GetParameter` - For retrieving Langfuse configuration

## Testing

After adding the secrets, you can test the workflow by:

1. Making a change to files in `cicd/`, `utils/`, or `agents/` directories
2. Pushing to the main branch
3. Checking the **Actions** tab to see the workflow run

## Security Notes

- Never commit secrets to the repository
- Rotate secrets regularly
- Use the minimum required permissions for AWS credentials
- The Cognito client secret should be kept secure and not shared
