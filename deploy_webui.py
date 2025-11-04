#!/usr/bin/env python3
"""
Deploy SAP Agent Web UI to AWS App Runner
"""
import boto3
import json
import time
import os
import subprocess

# AWS Configuration
REGION = 'us-east-1'
SERVICE_NAME = 'sap-agent-webui'
ECR_REPOSITORY_NAME = 'sap-agent-webui'

def get_account_id():
    """Get AWS account ID"""
    sts = boto3.client('sts', region_name=REGION)
    return sts.get_caller_identity()['Account']

def create_ecr_repository():
    """Create ECR repository if it doesn't exist"""
    ecr = boto3.client('ecr', region_name=REGION)

    try:
        response = ecr.describe_repositories(repositoryNames=[ECR_REPOSITORY_NAME])
        print(f"✓ ECR repository '{ECR_REPOSITORY_NAME}' already exists")
        return response['repositories'][0]['repositoryUri']
    except ecr.exceptions.RepositoryNotFoundException:
        print(f"Creating ECR repository '{ECR_REPOSITORY_NAME}'...")
        response = ecr.create_repository(
            repositoryName=ECR_REPOSITORY_NAME,
            imageScanningConfiguration={'scanOnPush': True}
        )
        print(f"✓ ECR repository created: {response['repository']['repositoryUri']}")
        return response['repository']['repositoryUri']

def build_and_push_image(repository_uri):
    """Build and push Docker image to ECR"""
    account_id = get_account_id()

    print("\n" + "="*60)
    print("Building Docker image...")
    print("="*60)

    # Build the image
    build_cmd = [
        'docker', 'build',
        '-f', 'Dockerfile.webui',
        '-t', f'{ECR_REPOSITORY_NAME}:latest',
        '.'
    ]
    subprocess.run(build_cmd, check=True)

    # Tag for ECR
    tag_cmd = [
        'docker', 'tag',
        f'{ECR_REPOSITORY_NAME}:latest',
        f'{repository_uri}:latest'
    ]
    subprocess.run(tag_cmd, check=True)

    print("\n" + "="*60)
    print("Logging into ECR...")
    print("="*60)

    # Login to ECR using AWS CLI
    login_cmd = f'aws ecr get-login-password --region {REGION} | docker login --username AWS --password-stdin {account_id}.dkr.ecr.{REGION}.amazonaws.com'
    subprocess.run(login_cmd, shell=True, check=True)

    print("\n" + "="*60)
    print("Pushing image to ECR...")
    print("="*60)

    # Push to ECR
    push_cmd = ['docker', 'push', f'{repository_uri}:latest']
    subprocess.run(push_cmd, check=True)

    print(f"\n✓ Image pushed successfully: {repository_uri}:latest")
    return f'{repository_uri}:latest'

def create_app_runner_role():
    """Create IAM role for App Runner with necessary permissions"""
    iam = boto3.client('iam', region_name=REGION)
    role_name = 'AppRunnerECRAccessRole'

    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "build.apprunner.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }

    try:
        role = iam.get_role(RoleName=role_name)
        print(f"✓ IAM role '{role_name}' already exists")
        return role['Role']['Arn']
    except iam.exceptions.NoSuchEntityException:
        print(f"Creating IAM role '{role_name}'...")
        role = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description='Allows App Runner to access ECR'
        )

        # Attach ECR read policy
        iam.attach_role_policy(
            RoleName=role_name,
            PolicyArn='arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess'
        )

        print(f"✓ IAM role created: {role['Role']['Arn']}")
        return role['Role']['Arn']

def create_instance_role():
    """Create IAM role for App Runner instance with Bedrock access"""
    iam = boto3.client('iam', region_name=REGION)
    role_name = 'AppRunnerInstanceRole'

    trust_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Principal": {
                    "Service": "tasks.apprunner.amazonaws.com"
                },
                "Action": "sts:AssumeRole"
            }
        ]
    }

    bedrock_policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": [
                    "bedrock-agentcore:InvokeAgentRuntime",
                    "bedrock:InvokeModel",
                    "ssm:GetParameter"
                ],
                "Resource": "*"
            }
        ]
    }

    try:
        role = iam.get_role(RoleName=role_name)
        print(f"✓ Instance IAM role '{role_name}' already exists")
        return role['Role']['Arn']
    except iam.exceptions.NoSuchEntityException:
        print(f"Creating instance IAM role '{role_name}'...")
        role = iam.create_role(
            RoleName=role_name,
            AssumeRolePolicyDocument=json.dumps(trust_policy),
            Description='Allows App Runner instances to access Bedrock'
        )

        # Attach inline policy for Bedrock access
        iam.put_role_policy(
            RoleName=role_name,
            PolicyName='BedrockAccess',
            PolicyDocument=json.dumps(bedrock_policy)
        )

        print(f"✓ Instance IAM role created: {role['Role']['Arn']}")

        # Wait for role to be available
        time.sleep(10)

        return role['Role']['Arn']

def deploy_to_app_runner(image_uri, access_role_arn, instance_role_arn):
    """Deploy to AWS App Runner"""
    apprunner = boto3.client('apprunner', region_name=REGION)

    # Check if service exists
    try:
        services = apprunner.list_services()
        existing_service = None
        for service in services.get('ServiceSummaryList', []):
            if service['ServiceName'] == SERVICE_NAME:
                existing_service = service
                break

        if existing_service:
            print(f"\nUpdating existing App Runner service '{SERVICE_NAME}'...")
            response = apprunner.update_service(
                ServiceArn=existing_service['ServiceArn'],
                SourceConfiguration={
                    'ImageRepository': {
                        'ImageIdentifier': image_uri,
                        'ImageRepositoryType': 'ECR',
                        'ImageConfiguration': {
                            'Port': '8080',
                            'RuntimeEnvironmentVariables': {
                                'AGENT_ENV': 'PRD'
                            }
                        }
                    },
                    'AutoDeploymentsEnabled': True,
                    'AuthenticationConfiguration': {
                        'AccessRoleArn': access_role_arn
                    }
                },
                InstanceConfiguration={
                    'Cpu': '1 vCPU',
                    'Memory': '2 GB',
                    'InstanceRoleArn': instance_role_arn
                }
            )
            service_arn = existing_service['ServiceArn']
        else:
            print(f"\nCreating new App Runner service '{SERVICE_NAME}'...")
            response = apprunner.create_service(
                ServiceName=SERVICE_NAME,
                SourceConfiguration={
                    'ImageRepository': {
                        'ImageIdentifier': image_uri,
                        'ImageRepositoryType': 'ECR',
                        'ImageConfiguration': {
                            'Port': '8080',
                            'RuntimeEnvironmentVariables': {
                                'AGENT_ENV': 'PRD'
                            }
                        }
                    },
                    'AutoDeploymentsEnabled': True,
                    'AuthenticationConfiguration': {
                        'AccessRoleArn': access_role_arn
                    }
                },
                InstanceConfiguration={
                    'Cpu': '1 vCPU',
                    'Memory': '2 GB',
                    'InstanceRoleArn': instance_role_arn
                }
            )
            service_arn = response['Service']['ServiceArn']

        print(f"\n✓ App Runner service deployment initiated")
        print(f"  Service ARN: {service_arn}")

        # Wait for service to be running
        print("\nWaiting for service to be ready...")
        while True:
            service = apprunner.describe_service(ServiceArn=service_arn)
            status = service['Service']['Status']
            print(f"  Current status: {status}")

            if status == 'RUNNING':
                service_url = service['Service']['ServiceUrl']
                print(f"\n{'='*60}")
                print("🎉 DEPLOYMENT SUCCESSFUL!")
                print(f"{'='*60}")
                print(f"\nYour SAP Agent Web UI is now live at:")
                print(f"  https://{service_url}")
                print(f"\nYou can access it from any device!")
                print(f"{'='*60}\n")
                return service_url
            elif status in ['CREATE_FAILED', 'UPDATE_FAILED']:
                print(f"\n❌ Deployment failed with status: {status}")
                return None

            time.sleep(10)

    except Exception as e:
        print(f"❌ Error deploying to App Runner: {e}")
        return None

def main():
    print("\n" + "="*60)
    print("SAP Agent Web UI - AWS Deployment")
    print("="*60 + "\n")

    try:
        # Step 1: Create ECR repository
        print("Step 1: Setting up ECR repository...")
        repository_uri = create_ecr_repository()

        # Step 2: Build and push Docker image
        print("\nStep 2: Building and pushing Docker image...")
        image_uri = build_and_push_image(repository_uri)

        # Step 3: Create IAM roles
        print("\nStep 3: Setting up IAM roles...")
        access_role_arn = create_app_runner_role()
        instance_role_arn = create_instance_role()

        # Step 4: Deploy to App Runner
        print("\nStep 4: Deploying to AWS App Runner...")
        service_url = deploy_to_app_runner(image_uri, access_role_arn, instance_role_arn)

        if service_url:
            print("\n✅ Deployment completed successfully!")
        else:
            print("\n❌ Deployment failed. Check the logs above for details.")

    except Exception as e:
        print(f"\n❌ Deployment failed: {e}")
        raise

if __name__ == '__main__':
    main()
