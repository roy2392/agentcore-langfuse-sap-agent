#!/usr/bin/env python3
"""Test the fixed get_inventory_with_open_orders function"""

import sys
sys.path.append('.')

from utils.agent import invoke_agent

AGENT_ARN = "arn:aws:bedrock-agentcore:us-east-1:654537381132:runtime/strands_s3_english_PRD-RQs0CCH1G4"

print("\n🧪 Testing fixed get_inventory_with_open_orders function...\n")

response = invoke_agent(AGENT_ARN, "Which materials have both inventory and open orders?")

print("📝 AGENT RESPONSE:")
print("=" * 80)
print(response.get('response', 'No response'))
print("=" * 80)

# Check if it's actually returning data now
response_text = response.get('response', '')
if "no materials" in response_text.lower() or "not found" in response_text.lower():
    print("\n⚠️  Still no data - might be legitimate (no overlap in system)")
elif "error" in response_text.lower():
    print("\n❌ Error occurred")
else:
    print("\n✅ Function appears to be working!")
