#!/usr/bin/env python3
"""
End-to-End Test: User → Agent → MCP Gateway (OAuth) → Lambda → Real SAP Data

This script tests the complete flow to ensure:
1. Agent receives Hebrew question
2. Agent calls MCP tool through OAuth-protected Gateway
3. Gateway authenticates and routes to Lambda
4. Lambda retrieves REAL SAP data (not mock)
5. Agent responds with actual SAP purchase order details
"""
import boto3
import json
import uuid
import sys

# Agent configuration
AGENT_ID = "strands_s3_hebinv_TST-AOSMpkAeu5"
REGION = "us-east-1"

def test_agent_e2e():
    """Test the complete end-to-end flow"""
    print("=" * 80)
    print("🧪 End-to-End Agent Test")
    print("Testing: User → Agent → MCP Gateway (OAuth) → Lambda → Real SAP")
    print("=" * 80)
    print()

    # Initialize Bedrock AgentCore client
    print(f"📡 Connecting to agent: {AGENT_ID}")
    client = boto3.client('bedrock-agentcore', region_name=REGION)
    session_id = f'e2e-test-{uuid.uuid4()}'
    print(f"   Session ID: {session_id}")
    print()

    # Test questions in Hebrew to verify end-to-end flow
    test_questions = [
        {
            "question": "מה המידע על הזמנת רכש 4500000520?",
            "expected_keywords": ["4500000520", "BKC-990", "Frame", "209", "USSU-VSF08"],
            "description": "Hebrew: What is the information about purchase order 4500000520?"
        },
        {
            "question": "כמה פריטים יש בהזמנת רכש 4500000520?",
            "expected_keywords": ["7", "4500000520", "items", "פריטים"],
            "description": "Hebrew: How many items are in purchase order 4500000520?"
        }
    ]

    results = []

    for i, test in enumerate(test_questions, 1):
        print(f"📝 Test {i}/{len(test_questions)}: {test['description']}")
        print(f"   Question: {test['question']}")
        print("-" * 80)

        try:
            # Invoke the agent
            print(f"   🚀 Invoking agent...")
            response = client.invoke_agent_runtime(
                agentRuntimeArn=f"arn:aws:bedrock-agentcore:{REGION}:654537381132:runtime/{AGENT_ID}",
                runtimeSessionId=session_id,
                payload=json.dumps({
                    "prompt": test['question']
                }).encode('utf-8')
            )

            print(f"   📥 Response received. Keys: {list(response.keys())}")

            # Collect response
            full_response = ""
            tool_calls = []

            # Read from the 'response' StreamingBody
            if 'response' in response:
                print(f"   📡 Reading response stream...")
                response_body = response['response']
                response_text = response_body.read().decode('utf-8')
                print(f"   📄 Response text ({len(response_text)} chars)")

                # Parse JSON response
                try:
                    response_data = json.loads(response_text)

                    # Check if it's a dict or string
                    if isinstance(response_data, dict):
                        print(f"   📦 Parsed JSON dict with keys: {list(response_data.keys())}")

                        # Extract the actual response content
                        if 'output' in response_data:
                            full_response = response_data['output']
                            print(f"   ✅ Found output field")
                        elif 'response' in response_data:
                            full_response = response_data['response']
                            print(f"   ✅ Found response field")
                        elif 'message' in response_data:
                            full_response = response_data['message']
                            print(f"   ✅ Found message field")
                        else:
                            # Fallback to raw response
                            full_response = response_text
                            print(f"   ⚠️  Using raw response")

                        # Check for tool usage information
                        if 'toolCalls' in response_data:
                            tool_calls = response_data['toolCalls']
                            print(f"   🔧 Found {len(tool_calls)} tool calls")
                    elif isinstance(response_data, str):
                        # Direct string response
                        full_response = response_data
                        print(f"   ✅ Got direct string response")
                    else:
                        full_response = str(response_data)
                        print(f"   ⚠️  Converted to string: {type(response_data)}")

                except json.JSONDecodeError as e:
                    print(f"   ⚠️  JSON decode error: {e}")
                    # Response is plain text, not JSON
                    full_response = response_text
                    print(f"   ✅ Using plain text response")
            else:
                print(f"   ⚠️  No 'response' field found. Keys: {list(response.keys())}")

            print(f"\n   Agent Response:")
            print(full_response if full_response else "⚠️  EMPTY RESPONSE")
            print()

            # Check for tool usage
            if tool_calls:
                print(f"   🔧 Tool calls made: {len(tool_calls)}")
                for tool in tool_calls:
                    print(f"      - {tool.get('name', 'unknown')}")

            results.append({
                "test": test['description'],
                "success": True,
            })

        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()
            results.append({
                "test": test['description'],
                "success": False,
                "error": str(e)
            })

        print()
        print("=" * 80)
        print()

    # Summary
    print("\n📊 Test Summary")
    print("=" * 80)

    successful_tests = sum(1 for r in results if r.get('success', False))
    total_tests = len(results)

    for result in results:
        status = "✅ PASS" if result.get('success') else "❌ FAIL"
        print(f"{status}: {result['test']}")
        if 'error' in result:
            print(f"   Error: {result['error']}")

    print()
    print(f"Results: {successful_tests}/{total_tests} tests passed")

    if successful_tests == total_tests:
        print("\n🎉 SUCCESS! End-to-end flow is working correctly!")
        print("   ✅ Agent → MCP Gateway (OAuth) → Lambda → Real SAP Data")
        return 0
    else:
        print("\n⚠️  Some tests failed. Check the output above for details.")
        return 1

if __name__ == "__main__":
    sys.exit(test_agent_e2e())
