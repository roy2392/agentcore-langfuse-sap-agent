# ============================================================================
# AWS App Runner Service for SAP Agent Web UI
# ============================================================================

# ECR Repository for storing the container image
resource "aws_ecr_repository" "sap_agent_ui" {
  name                 = "sap-agent-ui-${var.environment}"
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name        = "sap-agent-ui-${var.environment}"
    Environment = var.environment
  }
}

# IAM role for App Runner instance
resource "aws_iam_role" "apprunner_instance" {
  name = "SAPAgentUIAppRunnerInstance-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "tasks.apprunner.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = {
    Name        = "SAPAgentUIAppRunnerInstance-${var.environment}"
    Environment = var.environment
  }
}

# Policy for App Runner instance to invoke AgentCore
resource "aws_iam_role_policy" "apprunner_agentcore_access" {
  name = "AgentCoreAccess"
  role = aws_iam_role.apprunner_instance.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock-agentcore-runtime:*"
        ]
        Resource = "*"
      }
    ]
  })
}

# IAM role for App Runner service (ECR access)
resource "aws_iam_role" "apprunner_service" {
  name = "SAPAgentUIAppRunnerService-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "build.apprunner.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = {
    Name        = "SAPAgentUIAppRunnerService-${var.environment}"
    Environment = var.environment
  }
}

# Attach ECR access policy to service role
resource "aws_iam_role_policy_attachment" "apprunner_ecr_access" {
  role       = aws_iam_role.apprunner_service.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess"
}

# App Runner service
resource "aws_apprunner_service" "sap_agent_ui" {
  service_name = "sap-agent-ui-${var.environment}"

  source_configuration {
    image_repository {
      image_identifier      = "${aws_ecr_repository.sap_agent_ui.repository_url}:latest"
      image_repository_type = "ECR"

      image_configuration {
        port = "8080"

        runtime_environment_variables = {
          PORT           = "8080"
          AGENT_ENV      = upper(var.environment)
          PYTHONUNBUFFERED = "1"
        }
      }
    }

    authentication_configuration {
      access_role_arn = aws_iam_role.apprunner_service.arn
    }

    auto_deployments_enabled = true
  }

  instance_configuration {
    instance_role_arn = aws_iam_role.apprunner_instance.arn
    cpu               = "1024"  # 1 vCPU
    memory            = "2048"  # 2 GB
  }

  health_check_configuration {
    protocol            = "HTTP"
    path                = "/health"
    interval            = 10
    timeout             = 5
    healthy_threshold   = 1
    unhealthy_threshold = 5
  }

  tags = {
    Name        = "sap-agent-ui-${var.environment}"
    Environment = var.environment
  }
}

# Output the service URL
output "apprunner_service_url" {
  description = "URL of the App Runner service"
  value       = "https://${aws_apprunner_service.sap_agent_ui.service_url}"
}

output "ecr_repository_url" {
  description = "ECR repository URL for the UI container"
  value       = aws_ecr_repository.sap_agent_ui.repository_url
}
