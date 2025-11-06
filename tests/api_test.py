#!/usr/bin/env python3
"""
Quick test of the deployed agent with inventory management questions
"""
import boto3
import json
import uuid
import time

# Agent configuration
AGENT_ID = "strands_s3_hebinv_TST-5534QT9g4p"
REGION = "us-east-1"

def test_inventory_questions():
    """Test agent with inventory management questions"""
    print("=" * 80)
    print("🧪 Testing Agent with Inventory Management Questions")
    print("=" * 80)
    print()

    client = boto3.client('bedrock-agentcore', region_name=REGION)
    session_id = f'inventory-test-{uuid.uuid4()}'

    # Test questions focused on inventory management
    test_questions = [
        {
            "question": "אילו פריטים יש להם מלאי נמוך?",
            "description": "Hebrew: Which items have low stock?",
            "expected_tool": "get_material_stock"
        },
        {
            "question": "כמה במלאי?",
            "description": "Hebrew: How much in stock?",
            "expected_tool": "get_material_stock"
        },
        {
            "question": "מה פתוח בהזמנות?",
            "description": "Hebrew: What orders are open?",
            "expected_tool": "get_open_purchase_orders"
        },
        {
            "question": "מה יש לו מלאי שיש בהזמנת רכש פתוחה?",
            "description": "Hebrew: What has stock with open orders?",
            "expected_tool": "get_inventory_with_open_orders"
        }
    ]

    for i, test in enumerate(test_questions, 1):
        print(f"\n📝 Test {i}/{len(test_questions)}: {test['description']}")
        print(f"   Question: {test['question']}")
        print(f"   Expected tool: {test['expected_tool']}")
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

            # Read response
            if 'response' in response:
                response_body = response['response']
                response_text = response_body.read().decode('utf-8')

                try:
                    response_data = json.loads(response_text)

                    # Pretty print the response
                    print(f"\n   📄 Response:")
                    print(json.dumps(response_data, indent=2, ensure_ascii=False))

                except json.JSONDecodeError:
                    print(f"\n   📄 Response (plain text):")
                    print(f"   {response_text}")

        except Exception as e:
            print(f"   ❌ Error: {e}")
            import traceback
            traceback.print_exc()

        print()
        # Brief pause between requests
        time.sleep(2)

    print("=" * 80)
    print("✅ Testing complete")
    print("=" * 80)

if __name__ == "__main__":
    test_inventory_questions()
