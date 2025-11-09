#!/usr/bin/env python3
"""
Test the PRD agent with various questions to assess what data is available
and prepare demo questions
"""

import sys
import json
from utils.agent import invoke_agent

# Agent ARN from hp_config.json
AGENT_ARN = "arn:aws:bedrock-agentcore:us-east-1:654537381132:runtime/strands_s3_english_PRD-RQs0CCH1G4"

# Test questions to assess what data is available
test_questions = [
    # 1. Test get_complete_po_data (known to work with PO 4500000520)
    {
        "question": "What are the details of purchase order 4500000520?",
        "expected_tool": "get_complete_po_data",
        "description": "Test specific PO lookup - known good PO"
    },

    # 2. Test get_material_stock
    {
        "question": "How much inventory do we have in stock?",
        "expected_tool": "get_material_stock",
        "description": "Test material stock levels"
    },

    # 3. Test get_open_purchase_orders
    {
        "question": "What purchase orders are currently open?",
        "expected_tool": "get_open_purchase_orders",
        "description": "Test open POs"
    },

    # 4. Test get_orders_awaiting_invoice_or_delivery
    {
        "question": "Which orders haven't been invoiced yet?",
        "expected_tool": "get_orders_awaiting_invoice_or_delivery",
        "description": "Test uninvoiced orders"
    },

    # 5. Test get_material_in_transit
    {
        "question": "What materials are currently in transit?",
        "expected_tool": "get_material_in_transit",
        "description": "Test materials in transit"
    },

    # 6. Test list_purchase_orders
    {
        "question": "Show me all purchase orders",
        "expected_tool": "list_purchase_orders",
        "description": "Test list all POs"
    },

    # 7. Test get_goods_receipts (known to have issues)
    {
        "question": "What goods have been received recently?",
        "expected_tool": "get_goods_receipts",
        "description": "Test goods receipts - may have no data"
    },

    # 8. Test get_inventory_with_open_orders (known to have issues)
    {
        "question": "Which materials have both inventory and open orders?",
        "expected_tool": "get_inventory_with_open_orders",
        "description": "Test combined inventory + orders - may have no data"
    },
]

def test_question(question_data):
    """Test a single question and analyze the response"""
    print("\n" + "="*80)
    print(f"TEST: {question_data['description']}")
    print(f"QUESTION: {question_data['question']}")
    print(f"EXPECTED TOOL: {question_data['expected_tool']}")
    print("="*80)

    try:
        response = invoke_agent(AGENT_ARN, question_data['question'])

        print("\n📝 AGENT RESPONSE:")
        print(response.get('response', 'No response'))

        # Check if tool was used
        tool_used = response.get('tool_used', 'Unknown')
        print(f"\n🔧 TOOL USED: {tool_used}")

        # Assess data quality
        response_text = response.get('response', '')

        if "No data" in response_text or "not found" in response_text.lower():
            print("⚠️  STATUS: No data returned")
            return "NO_DATA"
        elif "error" in response_text.lower() or "failed" in response_text.lower():
            print("❌ STATUS: Error occurred")
            return "ERROR"
        else:
            print("✅ STATUS: Success - has data")
            return "SUCCESS"

    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        return "EXCEPTION"

def main():
    """Run all tests and compile results"""
    print("\n🚀 TESTING SAP INVENTORY AGENT - PRD ENVIRONMENT")
    print(f"Agent ARN: {AGENT_ARN}")

    results = []

    for question_data in test_questions:
        status = test_question(question_data)
        results.append({
            "question": question_data['question'],
            "tool": question_data['expected_tool'],
            "status": status
        })

    # Summary
    print("\n\n" + "="*80)
    print("📊 TEST SUMMARY")
    print("="*80)

    success_count = sum(1 for r in results if r['status'] == 'SUCCESS')
    no_data_count = sum(1 for r in results if r['status'] == 'NO_DATA')
    error_count = sum(1 for r in results if r['status'] == 'ERROR')

    print(f"\n✅ Success: {success_count}/{len(results)}")
    print(f"⚠️  No Data: {no_data_count}/{len(results)}")
    print(f"❌ Errors: {error_count}/{len(results)}")

    print("\n📋 DETAILED RESULTS:")
    for r in results:
        status_icon = "✅" if r['status'] == 'SUCCESS' else "⚠️" if r['status'] == 'NO_DATA' else "❌"
        print(f"{status_icon} {r['tool']}: {r['status']}")

    # Recommend demo questions
    print("\n\n" + "="*80)
    print("💡 RECOMMENDED DEMO QUESTIONS")
    print("="*80)

    print("\nBased on what works, use these questions for your demo:\n")

    for i, r in enumerate(results, 1):
        if r['status'] == 'SUCCESS':
            print(f"{i}. {r['question']}")

    print("\n⚠️  Avoid these (no data or errors):\n")
    for i, r in enumerate(results, 1):
        if r['status'] != 'SUCCESS':
            print(f"{i}. {r['question']} - {r['status']}")

if __name__ == "__main__":
    main()
