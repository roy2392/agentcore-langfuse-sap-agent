# ============================================================================
# AWS ECS Fargate Deployment for SAP Agent Web UI
# ============================================================================

# Get default VPC
data "aws_vpc" "default" {
  default = true
}

# Get default subnets
data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# ECS Cluster
resource "aws_ecs_cluster" "sap_agent_ui" {
  name = "sap-agent-ui-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name        = "sap-agent-ui-${var.environment}"
    Environment = var.environment
  }
}

# CloudWatch Log Group
resource "aws_cloudwatch_log_group" "sap_agent_ui" {
  name              = "/ecs/sap-agent-ui-${var.environment}"
  retention_in_days = 7

  tags = {
    Name        = "sap-agent-ui-${var.environment}"
    Environment = var.environment
  }
}

# IAM Role for ECS Task Execution
resource "aws_iam_role" "ecs_task_execution" {
  name = "SAPAgentUIECSTaskExecution-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = {
    Name        = "SAPAgentUIECSTaskExecution-${var.environment}"
    Environment = var.environment
  }
}

# Attach AWS managed policy for ECS task execution
resource "aws_iam_role_policy_attachment" "ecs_task_execution" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# IAM Role for ECS Task (application permissions)
resource "aws_iam_role" "ecs_task" {
  name = "SAPAgentUIECSTask-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = "ecs-tasks.amazonaws.com"
      }
      Action = "sts:AssumeRole"
    }]
  })

  tags = {
    Name        = "SAPAgentUIECSTask-${var.environment}"
    Environment = var.environment
  }
}

# Policy for accessing AgentCore
resource "aws_iam_role_policy" "ecs_task_agentcore" {
  name = "AgentCoreAccess"
  role = aws_iam_role.ecs_task.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Action = [
          "bedrock-agentcore:*"
        ]
        Resource = "*"
      }
    ]
  })
}

# ECS Task Definition
resource "aws_ecs_task_definition" "sap_agent_ui" {
  family                   = "sap-agent-ui-${var.environment}"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"  # 1 vCPU
  memory                   = "2048"  # 2 GB
  execution_role_arn       = aws_iam_role.ecs_task_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn

  container_definitions = jsonencode([
    {
      name      = "sap-agent-ui"
      image     = "${aws_ecr_repository.sap_agent_ui.repository_url}:latest"
      essential = true

      portMappings = [
        {
          containerPort = 8080
          protocol      = "tcp"
        }
      ]

      environment = [
        {
          name  = "PORT"
          value = "8080"
        },
        {
          name  = "AGENT_ENV"
          value = upper(var.environment)
        },
        {
          name  = "PYTHONUNBUFFERED"
          value = "1"
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.sap_agent_ui.name
          "awslogs-region"        = "us-east-1"
          "awslogs-stream-prefix" = "ecs"
        }
      }

      healthCheck = {
        command     = ["CMD-SHELL", "curl -f http://localhost:8080/health || exit 1"]
        interval    = 30
        timeout     = 5
        retries     = 3
        startPeriod = 60
      }
    }
  ])

  tags = {
    Name        = "sap-agent-ui-${var.environment}"
    Environment = var.environment
  }
}

# Security Group for ALB
resource "aws_security_group" "alb" {
  name        = "sap-agent-ui-alb-${var.environment}"
  description = "Security group for SAP Agent UI ALB"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow HTTP from anywhere"
  }

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow HTTPS from anywhere"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name        = "sap-agent-ui-alb-${var.environment}"
    Environment = var.environment
  }
}

# Security Group for ECS Tasks
resource "aws_security_group" "ecs_tasks" {
  name        = "sap-agent-ui-ecs-tasks-${var.environment}"
  description = "Security group for SAP Agent UI ECS tasks"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port       = 8080
    to_port         = 8080
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
    description     = "Allow traffic from ALB"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
    description = "Allow all outbound"
  }

  tags = {
    Name        = "sap-agent-ui-ecs-tasks-${var.environment}"
    Environment = var.environment
  }
}

# Application Load Balancer
resource "aws_lb" "sap_agent_ui" {
  name               = "sap-agent-ui-${var.environment}"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [aws_security_group.alb.id]
  subnets            = data.aws_subnets.default.ids

  enable_deletion_protection = false

  tags = {
    Name        = "sap-agent-ui-${var.environment}"
    Environment = var.environment
  }
}

# ALB Target Group
resource "aws_lb_target_group" "sap_agent_ui" {
  name        = "sap-agent-ui-${var.environment}"
  port        = 8080
  protocol    = "HTTP"
  vpc_id      = data.aws_vpc.default.id
  target_type = "ip"

  health_check {
    enabled             = true
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    path                = "/health"
    protocol            = "HTTP"
    matcher             = "200"
  }

  deregistration_delay = 30

  tags = {
    Name        = "sap-agent-ui-${var.environment}"
    Environment = var.environment
  }
}

# ============================================================================
# SSL Certificate and DNS
# ============================================================================

# Get the Route 53 hosted zone (created when domain is registered)
data "aws_route53_zone" "main" {
  name         = "erp-assistant.com"
  private_zone = false
}

# ACM Certificate for HTTPS
resource "aws_acm_certificate" "sap_agent_ui" {
  domain_name       = "erp-assistant.com"
  validation_method = "DNS"

  subject_alternative_names = ["www.erp-assistant.com"]

  tags = {
    Name        = "sap-agent-ui-${var.environment}"
    Environment = var.environment
  }

  lifecycle {
    create_before_destroy = true
  }
}

# Route 53 records for ACM certificate validation
resource "aws_route53_record" "cert_validation" {
  for_each = {
    for dvo in aws_acm_certificate.sap_agent_ui.domain_validation_options : dvo.domain_name => {
      name   = dvo.resource_record_name
      record = dvo.resource_record_value
      type   = dvo.resource_record_type
    }
  }

  allow_overwrite = true
  name            = each.value.name
  records         = [each.value.record]
  ttl             = 60
  type            = each.value.type
  zone_id         = data.aws_route53_zone.main.zone_id
}

# Wait for certificate validation
resource "aws_acm_certificate_validation" "sap_agent_ui" {
  certificate_arn         = aws_acm_certificate.sap_agent_ui.arn
  validation_record_fqdns = [for record in aws_route53_record.cert_validation : record.fqdn]
}

# Route 53 A record pointing to ALB
resource "aws_route53_record" "sap_agent_ui" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "erp-assistant.com"
  type    = "A"

  alias {
    name                   = aws_lb.sap_agent_ui.dns_name
    zone_id                = aws_lb.sap_agent_ui.zone_id
    evaluate_target_health = true
  }
}

# Route 53 A record for www subdomain
resource "aws_route53_record" "sap_agent_ui_www" {
  zone_id = data.aws_route53_zone.main.zone_id
  name    = "www.erp-assistant.com"
  type    = "A"

  alias {
    name                   = aws_lb.sap_agent_ui.dns_name
    zone_id                = aws_lb.sap_agent_ui.zone_id
    evaluate_target_health = true
  }
}

# ============================================================================
# ALB Listeners
# ============================================================================

# ALB Listener (HTTP) - Redirect to HTTPS
resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.sap_agent_ui.arn
  port              = "80"
  protocol          = "HTTP"

  default_action {
    type = "redirect"

    redirect {
      port        = "443"
      protocol    = "HTTPS"
      status_code = "HTTP_301"
    }
  }
}

# ALB Listener (HTTPS)
resource "aws_lb_listener" "https" {
  load_balancer_arn = aws_lb.sap_agent_ui.arn
  port              = "443"
  protocol          = "HTTPS"
  ssl_policy        = "ELBSecurityPolicy-TLS13-1-2-2021-06"
  certificate_arn   = aws_acm_certificate_validation.sap_agent_ui.certificate_arn

  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.sap_agent_ui.arn
  }
}

# ECS Service
resource "aws_ecs_service" "sap_agent_ui" {
  name            = "sap-agent-ui-${var.environment}"
  cluster         = aws_ecs_cluster.sap_agent_ui.id
  task_definition = aws_ecs_task_definition.sap_agent_ui.arn
  desired_count   = 1
  launch_type     = "FARGATE"

  network_configuration {
    subnets          = data.aws_subnets.default.ids
    security_groups  = [aws_security_group.ecs_tasks.id]
    assign_public_ip = true
  }

  load_balancer {
    target_group_arn = aws_lb_target_group.sap_agent_ui.arn
    container_name   = "sap-agent-ui"
    container_port   = 8080
  }

  depends_on = [aws_lb_listener.http, aws_lb_listener.https]

  tags = {
    Name        = "sap-agent-ui-${var.environment}"
    Environment = var.environment
  }
}

# Outputs
output "application_url" {
  description = "HTTPS URL of the SAP Agent UI"
  value       = "https://erp-assistant.com"
}

output "alb_dns_name" {
  description = "DNS name of the Application Load Balancer (for reference)"
  value       = aws_lb.sap_agent_ui.dns_name
}

output "ecs_cluster_name" {
  description = "Name of the ECS cluster"
  value       = aws_ecs_cluster.sap_agent_ui.name
}

output "ecs_service_name" {
  description = "Name of the ECS service"
  value       = aws_ecs_service.sap_agent_ui.name
}
