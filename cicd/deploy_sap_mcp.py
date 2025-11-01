#!/usr/bin/env python3
"""
Deploy SAP MCP Server to AWS ECR and optionally to ECS/Fargate

This script builds and pushes the SAP MCP Server Docker image to AWS ECR,
and can optionally deploy it to ECS.
"""

import os
import sys
import json
import subprocess
import argparse
import boto3
from typing import Optional

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.aws import get_ssm_parameter

def run_command(cmd, check=True):
    """Run a shell command"""
    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, check=check, capture_output=True, text=True)
    if result.stdout:
        print(result.stdout)
    if result.stderr:
        print(result.stderr, file=sys.stderr)
    return result

def get_or_create_ecr_repository(repo_name: str, region: str) -> str:
    """Get or create ECR repository and return URI"""
    ecr_client = boto3.client('ecr', region_name=region)

    try:
        # Try to get existing repository
        response = ecr_client.describe_repositories(repositoryNames=[repo_name])
        repo_uri = response['repositories'][0]['repositoryUri']
        print(f"✓ ECR repository exists: {repo_uri}")
        return repo_uri
    except ecr_client.exceptions.RepositoryNotFoundException:
        # Create new repository
        print(f"Creating ECR repository: {repo_name}")
        response = ecr_client.create_repository(repositoryName=repo_name)
        repo_uri = response['repository']['repositoryUri']
        print(f"✓ ECR repository created: {repo_uri}")
        return repo_uri

def get_ecr_login_token(region: str) -> tuple:
    """Get ECR login token and return (username, password, registry)"""
    ecr_client = boto3.client('ecr', region_name=region)
    response = ecr_client.get_authorization_token()

    auth_data = response['authorizationData'][0]
    import base64
    creds = base64.b64decode(auth_data['authorizationToken']).decode()
    username, password = creds.split(':')
    registry = auth_data['proxyEndpoint'].replace('https://', '')

    return username, password, registry

def build_and_push_image(
    dockerfile: str,
    repo_uri: str,
    tag: str,
    region: str,
    sap_host: Optional[str] = None,
    sap_user: Optional[str] = None,
    sap_password: Optional[str] = None
) -> str:
    """Build Docker image and push to ECR"""

    # Get ECR login credentials
    username, password, registry = get_ecr_login_token(region)

    # Docker login
    login_cmd = f"echo '{password}' | docker login -u {username} --password-stdin {registry}"
    run_command(["bash", "-c", login_cmd])
    print("✓ Docker logged in to ECR")

    # Build image
    image_tag = f"{repo_uri}:{tag}"
    build_cmd = ["docker", "build", "-f", dockerfile, "-t", image_tag, "."]
    run_command(build_cmd)
    print(f"✓ Docker image built: {image_tag}")

    # Push image
    push_cmd = ["docker", "push", image_tag]
    run_command(push_cmd)
    print(f"✓ Docker image pushed to ECR: {image_tag}")

    return image_tag

def create_ecs_task_definition(
    task_family: str,
    image_uri: str,
    region: str,
    sap_host: str,
    sap_user: str,
    sap_password: str,
    sap_client: Optional[str] = None
) -> dict:
    """Create ECS task definition for SAP MCP server"""

    ecs_client = boto3.client('ecs', region_name=region)

    # Build environment variables
    environment = [
        {"name": "SAP_HOST", "value": sap_host},
        {"name": "SAP_USER", "value": sap_user},
        {"name": "SAP_PASSWORD", "value": sap_password},
        {"name": "PYTHONUNBUFFERED", "value": "1"},
        {"name": "PORT", "value": "8000"}
    ]

    if sap_client:
        environment.append({"name": "SAP_CLIENT", "value": sap_client})

    # Task definition
    task_definition = {
        "family": task_family,
        "networkMode": "awsvpc",
        "requiresCompatibilities": ["FARGATE"],
        "cpu": "256",
        "memory": "512",
        "containerDefinitions": [
            {
                "name": "sap-mcp-server",
                "image": image_uri,
                "portMappings": [
                    {
                        "containerPort": 8000,
                        "hostPort": 8000,
                        "protocol": "tcp"
                    }
                ],
                "environment": environment,
                "logConfiguration": {
                    "logDriver": "awslogs",
                    "options": {
                        "awslogs-group": f"/ecs/{task_family}",
                        "awslogs-region": region,
                        "awslogs-stream-prefix": "ecs"
                    }
                },
                "healthCheck": {
                    "command": [
                        "CMD-SHELL",
                        "python -c 'import os; exit(0 if all([os.getenv(\"SAP_HOST\"), os.getenv(\"SAP_USER\"), os.getenv(\"SAP_PASSWORD\")]) else 1)'"
                    ],
                    "interval": 30,
                    "timeout": 10,
                    "retries": 3,
                    "startPeriod": 5
                }
            }
        ],
        "executionRoleArn": f"arn:aws:iam::{get_account_id()}:role/ecsTaskExecutionRole"
    }

    try:
        response = ecs_client.register_task_definition(**task_definition)
        task_def_arn = response['taskDefinition']['taskDefinitionArn']
        print(f"✓ ECS task definition registered: {task_def_arn}")
        return response['taskDefinition']
    except Exception as e:
        print(f"Error creating task definition: {e}")
        raise

def get_account_id() -> str:
    """Get AWS account ID"""
    sts_client = boto3.client('sts')
    return sts_client.get_caller_identity()['Account']

def save_deployment_config(config: dict, output_file: str = "sap_mcp_config.json"):
    """Save deployment configuration to file"""
    with open(output_file, 'w') as f:
        json.dump(config, f, indent=2)
    print(f"✓ Deployment config saved to: {output_file}")

def main():
    parser = argparse.ArgumentParser(description='Deploy SAP MCP Server')
    parser.add_argument('--region', default=os.getenv('AWS_REGION', 'us-east-1'),
                       help='AWS region (default: us-east-1)')
    parser.add_argument('--tag', default='latest',
                       help='Docker image tag (default: latest)')
    parser.add_argument('--deploy-ecs', action='store_true',
                       help='Deploy to ECS Fargate')
    parser.add_argument('--task-family', default='sap-mcp-server',
                       help='ECS task family name (default: sap-mcp-server)')
    parser.add_argument('--sap-host', help='SAP host (from SSM if not provided)')
    parser.add_argument('--sap-user', help='SAP user (from SSM if not provided)')
    parser.add_argument('--sap-password', help='SAP password (from SSM if not provided)')
    parser.add_argument('--sap-client', help='SAP client ID (optional)')

    args = parser.parse_args()

    print(f"\n{'='*80}")
    print("SAP MCP Server Deployment")
    print(f"{'='*80}\n")

    # Get SAP credentials
    sap_host = args.sap_host or get_ssm_parameter('/sap/SAP_HOST', region=args.region)
    sap_user = args.sap_user or get_ssm_parameter('/sap/SAP_USER', region=args.region)
    sap_password = args.sap_password or get_ssm_parameter('/sap/SAP_PASSWORD', region=args.region)

    if not all([sap_host, sap_user, sap_password]):
        print("Error: Missing SAP credentials")
        print("Please provide SAP_HOST, SAP_USER, and SAP_PASSWORD via:")
        print("  1. Command line arguments (--sap-host, --sap-user, --sap-password)")
        print("  2. AWS SSM Parameter Store (/sap/SAP_HOST, /sap/SAP_USER, /sap/SAP_PASSWORD)")
        sys.exit(1)

    print(f"Using SAP credentials from region: {args.region}")
    print(f"SAP Host: {sap_host}")
    print(f"SAP User: {sap_user}")

    # Get or create ECR repository
    repo_uri = get_or_create_ecr_repository('sap-mcp-server', args.region)

    # Build and push image
    print("\nBuilding and pushing Docker image...")
    image_uri = build_and_push_image(
        'Dockerfile.sap-mcp',
        repo_uri,
        args.tag,
        args.region,
        sap_host,
        sap_user,
        sap_password
    )

    # Save deployment config
    deployment_config = {
        "image_uri": image_uri,
        "ecr_repository": repo_uri,
        "region": args.region,
        "sap_host": sap_host,
        "sap_user": sap_user,
        "timestamp": __import__('datetime').datetime.now().isoformat()
    }

    save_deployment_config(deployment_config, 'cicd/sap_mcp_config.json')

    # Deploy to ECS if requested
    if args.deploy_ecs:
        print("\nDeploying to ECS Fargate...")
        try:
            task_def = create_ecs_task_definition(
                args.task_family,
                image_uri,
                args.region,
                sap_host,
                sap_user,
                sap_password,
                args.sap_client
            )
            print(f"✓ SAP MCP Server ECS task definition created")
            deployment_config['ecs_task_family'] = args.task_family
            deployment_config['ecs_task_arn'] = task_def['taskDefinitionArn']
            save_deployment_config(deployment_config, 'cicd/sap_mcp_config.json')
        except Exception as e:
            print(f"Error deploying to ECS: {e}")
            sys.exit(1)

    print(f"\n{'='*80}")
    print("SAP MCP Server deployment complete!")
    print(f"Image URI: {image_uri}")
    print(f"Config saved to: cicd/sap_mcp_config.json")
    print(f"{'='*80}\n")

if __name__ == '__main__':
    main()
