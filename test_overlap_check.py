#!/usr/bin/env python3
"""Check if there's actual overlap between inventory and open orders"""

import sys
sys.path.append('.')

from utils.agent import invoke_agent

AGENT_ARN = "arn:aws:bedrock-agentcore:us-east-1:654537381132:runtime/strands_s3_english_PRD-RQs0CCH1G4"

print("\n🔍 CHECKING FOR OVERLAP...\n")

# Test 1: Get materials in stock
print("1. Checking inventory...")
inv_response = invoke_agent(AGENT_ARN, "What materials do we have in stock? List the first 5 material numbers.")
print("📦 INVENTORY:")
print(inv_response.get('response', 'No response')[:500])
print()

# Test 2: Get open purchase orders
print("\n2. Checking open purchase orders...")
po_response = invoke_agent(AGENT_ARN, "What materials are in open purchase orders? List the first 5 material numbers.")
print("📋 OPEN ORDERS:")
print(po_response.get('response', 'No response')[:500])
print()

# Test 3: Get inventory with open orders
print("\n3. Checking overlap...")
overlap_response = invoke_agent(AGENT_ARN, "Which materials have both inventory and open orders?")
print("🔗 OVERLAP:")
print(overlap_response.get('response', 'No response'))
print()
