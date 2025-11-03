#!/usr/bin/env python3
"""
Test script to query the Bedrock AgentCore agent
Usage: python test_agent_query.py "your question in Hebrew"
"""

import sys
import json
import boto3
import time

def query_agent(question):
    """Query the agent with a question"""

    # Agent configuration
    agent_runtime_arn = "arn:aws:bedrock-agentcore:us-east-1:654537381132:runtime/strands_s3_hebinv_PRD-9BFPdlAkq9"
    qualifier = "DEFAULT"
    region = "us-east-1"

    print(f"Querying agent...")
    print(f"Question: {question}")
    print("=" * 80)

    # Create boto3 client for bedrock-agentcore
    client = boto3.client('bedrock-agentcore', region_name=region)

    try:
        # Prepare payload with the question
        payload = json.dumps({"prompt": question})

        # Generate a session ID (must be 33+ characters)
        session_id = f"test-session-{abs(hash(question))}-{int(time.time())}"

        print(f"Session ID: {session_id}")
        print(f"Payload: {payload}\n")

        # Invoke agent using invoke_agent_runtime
        response = client.invoke_agent_runtime(
            agentRuntimeArn=agent_runtime_arn,
            runtimeSessionId=session_id,
            payload=payload,
            qualifier=qualifier
        )

        print("\nAgent Response:")
        print("-" * 80)

        # Read the response
        response_body = response['response'].read()
        response_data = json.loads(response_body)

        print(json.dumps(response_data, indent=2, ensure_ascii=False))
        print("-" * 80)
        print("\n✅ Agent invocation completed successfully!")

        return response_data

    except Exception as e:
        print(f"\n❌ Error invoking agent: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        # Default Hebrew question about inventory
        question = "מה המלאי הנוכחי של מוצרים?"
        print(f"No question provided, using default: {question}\n")
    else:
        question = " ".join(sys.argv[1:])

    query_agent(question)
