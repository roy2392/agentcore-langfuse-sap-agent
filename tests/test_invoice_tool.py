#!/usr/bin/env python3
"""Test the new invoice/delivery tool"""
import sys
sys.path.insert(0, '.')
from utils.agent import invoke_agent
import uuid
import json

agent_arn = 'arn:aws:bedrock-agentcore:us-east-1:654537381132:runtime/strands_s3_hebinv_TST-5534QT9g4p'
session_id = f'test-invoice-{uuid.uuid4()}'

print('=' * 80)
print('Testing: Which orders have not received an invoice?')
print('=' * 80)
print()

response = invoke_agent(
    agent_arn=agent_arn,
    prompt='איזה הזמנות פתוחות יש שלא התקבלה עליהם חשבונית?',
    session_id=session_id
)

response_text = str(response.get('response', ''))

# Extract final text
if '{"event":' in response_text:
    lines = response_text.split('\n')
    final_text = []
    for line in lines:
        if '"text":' in line:
            try:
                data = json.loads(line)
                text = data.get('event', {}).get('contentBlockDelta', {}).get('delta', {}).get('text', '')
                if text:
                    final_text.append(text)
            except:
                pass

    if final_text:
        answer = ''.join(final_text)
        print(answer[:3000])
    else:
        print(response_text[-2000:])
else:
    print(response_text)
