terraform {
  required_version = ">= 1.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

# Variables
variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment name"
  type        = string
  default     = "prd"
}

variable "sap_host" {
  description = "SAP OData API host"
  type        = string
  sensitive   = true
}

variable "sap_user" {
  description = "SAP username"
  type        = string
  sensitive   = true
}

variable "sap_password" {
  description = "SAP password"
  type        = string
  sensitive   = true
}

# Outputs - defined in gateway.tf to use the null_resource outputs
