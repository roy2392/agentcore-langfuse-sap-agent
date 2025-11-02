# Cognito User Pool for OAuth 2.0 authentication
resource "aws_cognito_user_pool" "gateway_oauth" {
  name = "sap-gateway-oauth-${var.environment}"

  # OAuth 2.0 client credentials flow
  account_recovery_setting {
    recovery_mechanism {
      name     = "admin_only"
      priority = 1
    }
  }

  tags = {
    Name        = "sap-gateway-oauth-${var.environment}"
    Environment = var.environment
    ManagedBy   = "Terraform"
  }
}

# Cognito User Pool Domain
resource "aws_cognito_user_pool_domain" "gateway_oauth" {
  domain       = "sap-gateway-${var.environment}-${data.aws_caller_identity.current.account_id}"
  user_pool_id = aws_cognito_user_pool.gateway_oauth.id
}

# Cognito Resource Server (for OAuth scopes)
resource "aws_cognito_resource_server" "gateway" {
  identifier   = "sap-gateway-${var.environment}"
  name         = "SAP Gateway ${var.environment}"
  user_pool_id = aws_cognito_user_pool.gateway_oauth.id

  scope {
    scope_name        = "tools.invoke"
    scope_description = "Invoke SAP tools through Gateway"
  }
}

# Cognito OAuth Client (for AgentCore Gateway)
resource "aws_cognito_user_pool_client" "gateway_client" {
  name         = "sap-gateway-client-${var.environment}"
  user_pool_id = aws_cognito_user_pool.gateway_oauth.id

  # OAuth 2.0 Client Credentials Flow
  generate_secret = true

  allowed_oauth_flows_user_pool_client = true
  allowed_oauth_flows                  = ["client_credentials"]
  allowed_oauth_scopes = [
    "${aws_cognito_resource_server.gateway.identifier}/tools.invoke"
  ]

  explicit_auth_flows = [
    "ALLOW_REFRESH_TOKEN_AUTH",
    "ALLOW_CUSTOM_AUTH"
  ]

  # Prevent user existence errors
  prevent_user_existence_errors = "ENABLED"
}

# Data source for current AWS account
data "aws_caller_identity" "current" {}
