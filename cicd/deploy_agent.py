#!/usr/bin/env python3
"""
Deploy agent script for CI/CD pipeline.
This script reads agent hyperparameters from hp_config.json and deploys an agent
using the deploy_agent function from utils.agent with specified environment (TST or PRD).
"""

import json
import sys
import os
import argparse
from pathlib import Path

# Add the parent directory to the Python path to import utils
sys.path.append(str(Path(__file__).parent.parent))

from utils.agent import deploy_agent


def load_hp_config(config_path="cicd/hp_config.json"):
    """Load hyperparameters from the configuration file."""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        return config
    except FileNotFoundError:
        print(f"Error: Configuration file {config_path} not found.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in {config_path}: {e}")
        sys.exit(1)


def main():
    """Main function to deploy the agent."""
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Deploy agent to specified environment')
    parser.add_argument('--environment', choices=['TST', 'PRD'],
                       help='Environment to deploy to (TST or PRD)', default='TST')
    parser.add_argument('--force-redeploy', action='store_true',
                       help='Force redeploy even if agent exists')
    args = parser.parse_args()
    
    environment = args.environment
    
    print("Loading agent hyperparameters...")
    config = load_hp_config()
    
    # Extract the model and system prompt from the config
    if not config.get("model") or not config.get("system_prompt"):
        print("Error: Configuration must contain 'model' and 'system_prompt' objects.")
        sys.exit(1)
    
    model = config["model"]
    system_prompt = config["system_prompt"]

    # Read gateway URL from terraform/gateway_output.json
    gateway_url = ""
    cognito_client_id = ""
    cognito_domain = ""
    cognito_client_secret = os.getenv("COGNITO_CLIENT_SECRET", "")

    try:
        with open("terraform/gateway_output.json", 'r') as f:
            gateway_output = json.load(f)
            gateway_url = gateway_output.get("gatewayUrl", "")

            authorizer_config = gateway_output.get("authorizerConfiguration", {}).get("customJWTAuthorizer", {})
            cognito_client_id = authorizer_config.get("allowedClients", [""])[0]

            # Get Cognito domain - the Gateway is always created with "prd" environment
            # regardless of which agent environment (TST/PRD) we're deploying
            # Format: sap-gateway-prd-{account_id}
            import boto3
            account_id = boto3.client('sts').get_caller_identity()['Account']
            cognito_domain = f"sap-gateway-prd-{account_id}"

            if not gateway_url:
                print("Error: gatewayUrl not found in terraform/gateway_output.json")
                sys.exit(1)
            if not cognito_client_id:
                print("Error: Cognito Client ID not found in terraform/gateway_output.json")
                sys.exit(1)
            if not cognito_client_secret:
                print("Error: COGNITO_CLIENT_SECRET environment variable not set.")
                sys.exit(1)

    except FileNotFoundError:
        print("Error: terraform/gateway_output.json not found. Please run terraform apply first.")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in terraform/gateway_output.json: {e}")
        sys.exit(1)
    
    print(f"Deploying agent with:")
    print(f"  Model: {model['name']} ({model['model_id']})")
    print(f"  System Prompt: {system_prompt['name']}")
    print(f"  Environment: {environment}")
    print(f"  Gateway URL: {gateway_url}")
    print(f"  Cognito Client ID: {cognito_client_id}")
    print(f"  Cognito Domain: {cognito_domain}")
    print(f"  Cognito Client Secret: {'*' * len(cognito_client_secret) if cognito_client_secret else 'Not Set'}") # Mask secret
    
    try:
        # Deploy the agent with specified environment
        result = deploy_agent(
            model=model,
            system_prompt=system_prompt,
            force_redeploy=args.force_redeploy,
            environment=environment,
            gateway_url=gateway_url,
            cognito_client_id=cognito_client_id,
            cognito_client_secret=cognito_client_secret,
            cognito_domain=cognito_domain
        )
        
        print(f"Agent deployment successful!")
        print(f"Agent Name: {result['agent_name']}")
        print(f"Agent ARN: {result['launch_result'].agent_arn}")
        print(f"Agent ID: {result['launch_result'].agent_id}")
        
        # Add agent ARN to the existing hp_config.json for use by subsequent pipeline steps
        # Use environment-specific keys to avoid conflicts between TST and PRD deployments
        # Create the environment key if it doesn't exist
        if environment.lower() not in config:
            config[environment.lower()] = {}
        
        config[environment.lower()][f'agent_arn'] = result['launch_result'].agent_arn
        config[environment.lower()][f'agent_name'] = result['agent_name']
        config[environment.lower()][f'agent_id'] = result['launch_result'].agent_id
        
        with open("cicd/hp_config.json", 'w') as f:
            json.dump(config, f, indent=2)
        print(f"Agent ARN added to hp_config.json with {environment} environment key")
        
        # Wait for agent to be ready
        print("Waiting for agent to be ready...")
        import time
        time.sleep(60)        
        # status_response = result['launch_result'].status()
        # status = status_response.endpoint['status']
        # end_status = ['READY', 'CREATE_FAILED', 'DELETE_FAILED', 'UPDATE_FAILED']
        # while status not in end_status:
        #     time.sleep(10)
        #     status_response = result['launch_result'].status()
        #     status = status_response.endpoint['status']
        #     print(f"Agent status: {status}")
        
        # if status == 'READY':
        #     print("Agent is ready!")
        # else:
        #     print(f"Agent deployment failed with status: {status}")
        #     sys.exit(1)
        
        return result
        
    except Exception as e:
        print(f"Error deploying agent: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()
