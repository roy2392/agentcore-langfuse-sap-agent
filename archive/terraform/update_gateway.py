#!/usr/bin/env python3
"""
Update Gateway configuration by recreating it with new settings
"""

import json
import boto3
import time

def update_gateway():
    client = boto3.client('bedrock-agentcore', region_name='us-east-1')

    # Load current gateway info
    with open('gateway_output.json', 'r') as f:
        gateway_info = json.load(f)

    gateway_id = gateway_info['gatewayId']

    # Load new configuration
    with open('gateway_create_config.json', 'r') as f:
        new_config = json.load(f)

    print(f"Deleting existing Gateway: {gateway_id}")
    try:
        client.delete_gateway(gatewayId=gateway_id)
        print("Gateway deleted successfully")
    except Exception as e:
        print(f"Error deleting gateway: {e}")
        return False

    # Wait for deletion to complete
    print("Waiting for gateway deletion to complete...")
    time.sleep(10)

    # Create gateway with new configuration
    print("Creating gateway with updated configuration...")
    response = client.create_gateway(**new_config)

    # Save new gateway info
    with open('gateway_output.json', 'w') as f:
        json.dump(response, f, indent=4, default=str)

    print(f"\nGateway created successfully!")
    print(f"Gateway ID: {response['gatewayId']}")
    print(f"Gateway URL: {response['gatewayUrl']}")
    print(f"Status: {response['status']}")

    # Wait for gateway to be active
    print("\nWaiting for gateway to become active...")
    max_attempts = 30
    for attempt in range(max_attempts):
        try:
            gateway = client.get_gateway(gatewayId=response['gatewayId'])
            status = gateway['status']
            print(f"Attempt {attempt + 1}/{max_attempts}: Status = {status}")

            if status == 'ACTIVE':
                print("\n✅ Gateway is now ACTIVE!")
                return True
            elif status in ['FAILED', 'DELETING']:
                print(f"\n❌ Gateway is in {status} state!")
                return False

            time.sleep(10)
        except Exception as e:
            print(f"Error checking gateway status: {e}")
            time.sleep(10)

    print("\n⚠️  Gateway creation timeout - check AWS console for status")
    return False

if __name__ == "__main__":
    update_gateway()
