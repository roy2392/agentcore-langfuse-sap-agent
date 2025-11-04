# AgentCore Gateway using AWS CLI (Terraform AWS provider may not have native support yet)
# Using null_resource to execute AWS CLI commands

# Create AgentCore Gateway
resource "null_resource" "agentcore_gateway" {
  triggers = {
    gateway_name = "sap-inventory-gateway-${var.environment}"
    role_arn     = aws_iam_role.gateway_role.arn
    auth_type    = "CUSTOM_JWT"
    cognito_pool = aws_cognito_user_pool.gateway_oauth.endpoint
  }

  provisioner "local-exec" {
    command = <<-EOT
      cat > ${path.module}/gateway_create_config.json <<GATEWAYJSON
{
  "name": "${self.triggers.gateway_name}",
  "description": "Gateway for SAP inventory management via MCP",
  "roleArn": "${self.triggers.role_arn}",
  "protocolType": "MCP",
  "authorizerType": "CUSTOM_JWT",
  "authorizerConfiguration": {
    "customJWTAuthorizer": {
      "discoveryUrl": "https://cognito-idp.us-east-1.amazonaws.com/${aws_cognito_user_pool.gateway_oauth.id}/.well-known/openid-configuration",
      "allowedClients": ["${aws_cognito_user_pool_client.gateway_client.id}"]
    }
  }
}
GATEWAYJSON
      aws bedrock-agentcore-control create-gateway \
        --cli-input-json file://${path.module}/gateway_create_config.json \
        --region ${var.aws_region} \
        --output json > ${path.module}/gateway_output.json
    EOT
  }

  provisioner "local-exec" {
    when    = destroy
    command = <<-EOT
      cd "${path.module}" || exit 0
      if [ -f gateway_output.json ]; then
        GATEWAY_ID=$(cat gateway_output.json | jq -r '.gatewayId' 2>/dev/null || echo "")
        if [ ! -z "$GATEWAY_ID" ] && [ "$GATEWAY_ID" != "null" ]; then
          aws bedrock-agentcore-control delete-gateway \
            --gateway-identifier "$GATEWAY_ID" \
            --region us-east-1 || true
        fi
      fi
    EOT
  }

  depends_on = [
    aws_iam_role.gateway_role
  ]
}

# Data source to read Gateway output
data "local_file" "gateway_output" {
  filename = "${path.module}/gateway_output.json"

  depends_on = [null_resource.agentcore_gateway]
}

locals {
  gateway_data = jsondecode(data.local_file.gateway_output.content)
  gateway_id   = local.gateway_data.gatewayId
  gateway_url  = local.gateway_data.gatewayUrl
}

# Create Gateway Target for Lambda function
resource "null_resource" "gateway_target_get_po" {
  triggers = {
    gateway_id   = local.gateway_id
    lambda_arn   = aws_lambda_function.get_complete_po_data.arn
    target_name  = "sap-get-po-target"
  }

  provisioner "local-exec" {
    command = <<-EOT
      cat > ${path.module}/target_config.json <<EOF
{
  "gatewayIdentifier": "${local.gateway_id}",
  "name": "${self.triggers.target_name}",
  "description": "SAP Purchase Order retrieval tool",
  "targetConfiguration": {
    "mcp": {
      "lambda": {
        "lambdaArn": "${self.triggers.lambda_arn}",
        "toolSchema": {
          "inlinePayload": [
            {
              "name": "get_complete_po_data",
              "description": "Get complete purchase order data including header and items",
              "inputSchema": {
                "type": "object",
                "properties": {
                  "po_number": {
                    "type": "string",
                    "description": "Purchase order number (e.g., '4500000520')"
                  }
                },
                "required": ["po_number"]
              }
            }
          ]
        }
      }
    }
  },
  "credentialProviderConfigurations": [
    {
      "credentialProviderType": "GATEWAY_IAM_ROLE"
    }
  ]
}
EOF
      aws bedrock-agentcore-control create-gateway-target \
        --cli-input-json file://${path.module}/target_config.json \
        --region ${var.aws_region} \
        --output json > ${path.module}/target_output.json
    EOT
  }

  provisioner "local-exec" {
    when    = destroy
    command = <<-EOT
      cd "${path.module}" || exit 0
      if [ -f target_output.json ]; then
        TARGET_ID=$(cat target_output.json | jq -r '.targetId' 2>/dev/null || echo "")
        GATEWAY_ID=$(cat gateway_output.json | jq -r '.gatewayId' 2>/dev/null || echo "")
        if [ ! -z "$TARGET_ID" ] && [ "$TARGET_ID" != "null" ]; then
          aws bedrock-agentcore-control delete-gateway-target \
            --gateway-identifier "$GATEWAY_ID" \
            --target-id "$TARGET_ID" \
            --region us-east-1 || true
        fi
      fi
    EOT
  }

  depends_on = [
    null_resource.agentcore_gateway,
    aws_lambda_function.get_complete_po_data
  ]
}

# Outputs
output "gateway_url" {
  description = "AgentCore Gateway MCP endpoint URL"
  value       = try(local.gateway_url, "")
  depends_on  = [null_resource.agentcore_gateway]
}

output "gateway_id" {
  description = "AgentCore Gateway ID"
  value       = try(local.gateway_id, "")
  depends_on  = [null_resource.agentcore_gateway]
}

output "cognito_user_pool_id" {
  description = "Cognito User Pool ID for OAuth"
  value       = aws_cognito_user_pool.gateway_oauth.id
}

output "cognito_client_id" {
  description = "Cognito OAuth Client ID"
  value       = aws_cognito_user_pool_client.gateway_client.id
  sensitive   = true
}

output "cognito_domain" {
  description = "Cognito Domain for OAuth token endpoint"
  value       = aws_cognito_user_pool_domain.gateway_oauth.domain
}

output "lambda_function_arns" {
  description = "ARNs of SAP tool Lambda functions"
  value = {
    get_complete_po_data = aws_lambda_function.get_complete_po_data.arn
  }
}
