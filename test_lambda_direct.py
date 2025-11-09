#!/usr/bin/env python3
"""Test Lambda function directly to see raw response"""

import boto3
import json

# Invoke the Lambda directly
client = boto3.client('lambda', region_name='us-east-1')

# Test get_inventory_with_open_orders
print("\n🧪 Testing get_inventory_with_open_orders directly...\n")

event = {
    "bedrockAgentCoreToolName": "sap-tools-target___get_inventory_with_open_orders",
    "threshold": 10
}

response = client.invoke(
    FunctionName='sap-tools-prd',
    InvocationType='RequestResponse',
    Payload=json.dumps(event)
)

payload = json.loads(response['Payload'].read())
print("RAW RESPONSE:")
print(json.dumps(payload, indent=2))

# Check if it's actually empty or has data
if 'result' in payload:
    result = json.loads(payload['result'])
    print("\n\nPARSED RESULT:")
    print(json.dumps(result, indent=2)[:1000])

    if 'inventory_with_open_orders' in result:
        count = len(result['inventory_with_open_orders'])
        print(f"\n✅ Found {count} materials with both inventory and open orders")

        if count > 0:
            print("\nFirst material:")
            print(json.dumps(result['inventory_with_open_orders'][0], indent=2))
    else:
        print("\n⚠️ No inventory_with_open_orders in result")
