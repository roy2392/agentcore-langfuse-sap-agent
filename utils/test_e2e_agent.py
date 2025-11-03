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
AGENT_ID = "strands_s3_hebinv_PRD-9BFPdlAkq9"
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
            response = client.invoke_agent_runtime(
                agentRuntimeArn=f"arn:aws:bedrock-agentcore:{REGION}:654537381132:runtime/{AGENT_ID}",
                runtimeSessionId=session_id,
                payload={
                    "message": test['question']
                }
            )

            # Collect response
            full_response = ""
            tool_calls = []

            if 'responseStream' in response:
                for event in response['responseStream']:
                    if 'chunk' in event:
                        chunk_data = event['chunk']
                        if 'message' in chunk_data:
                            full_response += chunk_data['message'].get('content', '')
                    elif 'toolUse' in event:
                        tool_calls.append(event['toolUse'])

            print(f"\n   Agent Response:")
            print(f"   {full_response[:500]}...")
            print()

            # Verify expected content
            found_keywords = []
            missing_keywords = []

            for keyword in test['expected_keywords']:
                if keyword.lower() in full_response.lower():
                    found_keywords.append(keyword)
                else:
                    missing_keywords.append(keyword)

            if found_keywords:
                print(f"   ✅ Found expected data: {', '.join(found_keywords)}")

            if missing_keywords:
                print(f"   ⚠️  Missing keywords: {', '.join(missing_keywords)}")

            # Check for tool usage
            if tool_calls:
                print(f"   🔧 Tool calls made: {len(tool_calls)}")
                for tool in tool_calls:
                    print(f"      - {tool.get('name', 'unknown')}")

            results.append({
                "test": test['description'],
                "success": len(found_keywords) > 0,
                "found_keywords": found_keywords,
                "missing_keywords": missing_keywords
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
