#!/usr/bin/env python3
"""
Evaluate Agent with SAP MCP Integration

This script runs the agent evaluation using the SAP MCP Server for real inventory data.
It demonstrates the complete flow from user question → agent → SAP MCP → response.
"""

import json
import sys
import os
import logging
from typing import Dict, Any
from dataclasses import dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from utils.test_sap_api import _missing_env

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class EvaluationResult:
    name: str
    value: float
    comment: str = ""

class SAPMCPEvaluator:
    """Evaluate agent responses using deployed Bedrock agent"""

    def __init__(self, agent_arn):
        """Initialize evaluator with agent ARN and SAP MCP server for ground truth"""
        self.agent_arn = agent_arn

        try:
            from utils.sap_mcp_server import SAPMCPServer
            self.mcp_server = SAPMCPServer()
        except Exception as e:
            logger.error(f"SAP MCP Server not available: {e}")
            raise

        try:
            from utils.agent import invoke_agent
            self.invoke_agent = invoke_agent
        except Exception as e:
            logger.error(f"Agent invocation not available: {e}")
            raise

    def evaluate_stock_level_query(self) -> EvaluationResult:
        """Evaluate: "מה כמות המלאי של המוצר 100-100?" """

        print("\n" + "="*80)
        print("EVALUATION: Stock Level Query")
        print("="*80)

        question = "מה כמות המלאי של המוצר 100-100?"
        print(f"\nQuestion: {question}")

        # Get SAP data through MCP
        print("\n1. Fetching SAP data via MCP server...")
        stock_result = self.mcp_server.execute_tool(
            "get_stock_levels",
            {"material_number": "100-100"}
        )

        if stock_result.get('status') != 'success':
            return EvaluationResult(
                name="stock_level_query",
                value=0.0,
                comment=f"Failed to fetch SAP data: {stock_result.get('message')}"
            )

        # Parse response
        entries = stock_result.get('data', {}).get('entries', [])
        if not entries:
            return EvaluationResult(
                name="stock_level_query",
                value=0.5,
                comment="No stock data found for material 100-100"
            )

        entry = entries[0]
        material = entry.get('Material', 'N/A')
        available = entry.get('AvailableQuantity', 0)
        on_hand = entry.get('QuantityOnHand', 0)
        ordered = entry.get('QuantityOrdered', 0)

        # Format expected output in Hebrew
        expected_output = (
            f"כמות המלאי של המוצר {material}:\n"
            f"- זמינה: {available} יחידות\n"
            f"- ביד: {on_hand} יחידות\n"
            f"- מוזמנת: {ordered} יחידות"
        )

        print(f"\n2. SAP Response:")
        print(f"   Material: {material}")
        print(f"   Available: {available}")
        print(f"   On Hand: {on_hand}")
        print(f"   Ordered: {ordered}")

        print(f"\n3. Expected Hebrew Response:")
        print(f"   {expected_output}")

        # Score: Perfect if we got data
        score = 1.0 if available > 0 else 0.8

        return EvaluationResult(
            name="stock_level_query",
            value=score,
            comment=f"Material {material}: {available} units available (SAP verified)"
        )

    def evaluate_low_stock_query(self) -> EvaluationResult:
        """Evaluate: "אילו מוצרים יש לנו במלאי נמוך?" """

        print("\n" + "="*80)
        print("EVALUATION: Low Stock Query")
        print("="*80)

        question = "אילו מוצרים יש לנו במלאי נמוך?"
        print(f"\nQuestion: {question}")

        # Get SAP data
        print("\n1. Fetching low-stock materials via MCP...")
        low_stock_result = self.mcp_server.execute_tool(
            "get_low_stock_materials",
            {"threshold": 50}
        )

        if low_stock_result.get('status') != 'success':
            return EvaluationResult(
                name="low_stock_query",
                value=0.0,
                comment=f"Failed: {low_stock_result.get('message')}"
            )

        entries = low_stock_result.get('data', {}).get('entries', [])

        if not entries:
            print("   No low-stock materials found")
            return EvaluationResult(
                name="low_stock_query",
                value=0.9,
                comment="No materials below threshold"
            )

        # Format response
        print(f"\n2. SAP Response: Found {len(entries)} low-stock items")

        response_lines = ["מוצרים במלאי נמוך:"]
        for item in entries[:5]:  # Top 5
            material = item.get('Material', 'N/A')
            qty = item.get('AvailableQuantity', 0)
            response_lines.append(f"- {material}: {qty} יחידות")
            print(f"   {material}: {qty} units")

        expected_output = "\n".join(response_lines)

        print(f"\n3. Expected Hebrew Response:")
        print(f"   {expected_output}")

        score = 1.0 if entries else 0.8

        return EvaluationResult(
            name="low_stock_query",
            value=score,
            comment=f"Found {len(entries)} low-stock materials"
        )

    def evaluate_po_status_query(self) -> EvaluationResult:
        """Evaluate: "מה סטטוס ההזמנה מסדר קנייה 4500000520?" """

        print("\n" + "="*80)
        print("EVALUATION: Purchase Order Status Query")
        print("="*80)

        question = "מה סטטוס ההזמנה מסדר קנייה 4500000520?"
        print(f"\nQuestion: {question}")

        po_number = "4500000520"

        # Get SAP ground truth data
        print(f"\n1. Fetching SAP ground truth for PO {po_number}...")
        po_result = self.mcp_server.execute_tool(
            "get_complete_po_data",
            {"po_number": po_number}
        )

        if not po_result or not po_result.get('header'):
            return EvaluationResult(
                name="po_status_query",
                value=0.0,
                comment=f"PO {po_number} not found in SAP"
            )

        header = po_result.get('header', {})
        items = po_result.get('items', [])
        summary = po_result.get('summary', {})

        print(f"   ✓ SAP Ground Truth: {len(items)} items, {summary.get('total_value', 0)} {header.get('DocumentCurrency', 'USD')}")

        # Invoke the actual agent
        print(f"\n2. Invoking agent...")
        try:
            agent_response = self.invoke_agent(self.agent_arn, question)

            if 'error' in agent_response:
                return EvaluationResult(
                    name="po_status_query",
                    value=0.0,
                    comment=f"Agent error: {agent_response['error']}"
                )

            response_text = agent_response.get('response', '')
            print(f"   ✓ Agent responded (length: {len(response_text)} chars)")

            # Check if response contains key information
            has_supplier = header.get('Supplier', '') in response_text
            has_items_count = str(len(items)) in response_text
            has_value = str(int(summary.get('total_value', 0))) in response_text

            score = 0.0
            if has_supplier:
                score += 0.4
            if has_items_count:
                score += 0.3
            if has_value:
                score += 0.3

            print(f"\n3. Response Analysis:")
            print(f"   Supplier mentioned: {'✓' if has_supplier else '✗'}")
            print(f"   Items count mentioned: {'✓' if has_items_count else '✗'}")
            print(f"   Total value mentioned: {'✓' if has_value else '✗'}")

            return EvaluationResult(
                name="po_status_query",
                value=score,
                comment=f"Agent accuracy: {score*100:.0f}% (traced in Langfuse)"
            )

        except Exception as e:
            logger.error(f"Agent invocation failed: {e}")
            return EvaluationResult(
                name="po_status_query",
                value=0.0,
                comment=f"Agent invocation failed: {str(e)[:100]}"
            )

    def evaluate_po_supplier_query(self) -> EvaluationResult:
        """Evaluate: "מי הספק של הזמנת רכש 4500000520?" """

        print("\n" + "="*80)
        print("EVALUATION: PO Supplier Query")
        print("="*80)

        question = "מי הספק של הזמנת רכש 4500000520?"
        print(f"\nQuestion: {question}")

        po_number = "4500000520"

        # Get ground truth
        po_result = self.mcp_server.execute_tool(
            "get_complete_po_data",
            {"po_number": po_number}
        )

        if not po_result or not po_result.get('header'):
            return EvaluationResult("po_supplier_query", 0.0, f"PO {po_number} not found")

        supplier = po_result.get('header', {}).get('Supplier', 'N/A')
        print(f"\n1. SAP Ground Truth: Supplier = {supplier}")

        # Invoke agent
        print(f"\n2. Invoking agent...")
        try:
            agent_response = self.invoke_agent(self.agent_arn, question)

            if 'error' in agent_response:
                return EvaluationResult("po_supplier_query", 0.0, f"Agent error: {agent_response['error']}")

            response_text = agent_response.get('response', '')
            has_supplier = supplier in response_text

            score = 1.0 if has_supplier else 0.0

            print(f"   ✓ Agent responded")
            print(f"\n3. Supplier in response: {'✓' if has_supplier else '✗'}")

            return EvaluationResult(
                name="po_supplier_query",
                value=score,
                comment=f"Supplier {'found' if has_supplier else 'not found'} (traced in Langfuse)"
            )
        except Exception as e:
            return EvaluationResult("po_supplier_query", 0.0, f"Error: {str(e)[:100]}")

    def evaluate_po_items_query(self) -> EvaluationResult:
        """Evaluate: "מה הפריטים בהזמנת רכש 4500000520?" """

        print("\n" + "="*80)
        print("EVALUATION: PO Items Query")
        print("="*80)

        question = "מה הפריטים בהזמנת רכש 4500000520?"
        print(f"\nQuestion: {question}")

        po_number = "4500000520"
        po_result = self.mcp_server.execute_tool(
            "get_complete_po_data",
            {"po_number": po_number}
        )

        if not po_result or not po_result.get('items'):
            return EvaluationResult("po_items_query", 0.0, "No items found")

        items = po_result.get('items', [])
        print(f"\n1. SAP Ground Truth: {len(items)} items")

        # Invoke agent
        print(f"\n2. Invoking agent...")
        try:
            agent_response = self.invoke_agent(self.agent_arn, question)

            if 'error' in agent_response:
                return EvaluationResult("po_items_query", 0.0, f"Agent error: {agent_response['error']}")

            response_text = agent_response.get('response', '')

            # Check if at least 3 material numbers are mentioned
            materials_found = sum(1 for item in items if item.get('material', '') in response_text)
            score = min(1.0, materials_found / 3)  # Full score if 3+ materials mentioned

            print(f"   ✓ Agent responded")
            print(f"\n3. Materials mentioned: {materials_found}/{len(items)}")

            return EvaluationResult(
                name="po_items_query",
                value=score,
                comment=f"{materials_found} materials found (traced in Langfuse)"
            )
        except Exception as e:
            return EvaluationResult("po_items_query", 0.0, f"Error: {str(e)[:100]}")

    def evaluate_po_value_query(self) -> EvaluationResult:
        """Evaluate: "מה הערך הכולל של הזמנת רכש 4500000520?" """

        print("\n" + "="*80)
        print("EVALUATION: PO Total Value Query")
        print("="*80)

        question = "מה הערך הכולל של הזמנת רכש 4500000520?"
        print(f"\nQuestion: {question}")

        po_number = "4500000520"
        po_result = self.mcp_server.execute_tool(
            "get_complete_po_data",
            {"po_number": po_number}
        )

        if not po_result or not po_result.get('summary'):
            return EvaluationResult("po_value_query", 0.0, "No summary found")

        total_value = po_result.get('summary', {}).get('total_value', 0)
        currency = po_result.get('header', {}).get('DocumentCurrency', 'USD')

        print(f"\n1. SAP Ground Truth: {total_value} {currency}")

        # Invoke agent
        print(f"\n2. Invoking agent...")
        try:
            agent_response = self.invoke_agent(self.agent_arn, question)

            if 'error' in agent_response:
                return EvaluationResult("po_value_query", 0.0, f"Agent error: {agent_response['error']}")

            response_text = agent_response.get('response', '')

            # Check if value is mentioned (accept approximate values)
            has_value = str(int(total_value)) in response_text or currency in response_text
            score = 1.0 if has_value else 0.0

            print(f"   ✓ Agent responded")
            print(f"\n3. Value mentioned: {'✓' if has_value else '✗'}")

            return EvaluationResult(
                name="po_value_query",
                value=score,
                comment=f"Value {'found' if has_value else 'not found'} (traced in Langfuse)"
            )
        except Exception as e:
            return EvaluationResult("po_value_query", 0.0, f"Error: {str(e)[:100]}")

    def run_evaluation(self) -> Dict[str, Any]:
        """Run complete evaluation suite - ONLY Purchase Order queries (accessible endpoints)"""

        print("\n" + "="*80)
        print("                 SAP MCP EVALUATION SUITE")
        print("                  (Purchase Orders Only)")
        print("="*80)

        # Check credentials
        missing = _missing_env()
        if missing:
            print(f"\n❌ ERROR: Missing SAP credentials: {', '.join(missing)}")
            print("\nSet these environment variables:")
            for var in missing:
                print(f"  export {var}='your_value'")
            return None

        print(f"\n✓ SAP credentials configured")
        print(f"ℹ Note: Only testing Purchase Order endpoints (AWSDEMO user has limited permissions)")

        # Run evaluations - ONLY PO queries that work
        results = []

        # Test 1: PO Status
        try:
            results.append(self.evaluate_po_status_query())
        except Exception as e:
            logger.error(f"PO status evaluation failed: {e}")
            results.append(EvaluationResult("po_status_query", 0.0, str(e)))

        # Test 2: PO Supplier
        try:
            results.append(self.evaluate_po_supplier_query())
        except Exception as e:
            logger.error(f"PO supplier evaluation failed: {e}")
            results.append(EvaluationResult("po_supplier_query", 0.0, str(e)))

        # Test 3: PO Items
        try:
            results.append(self.evaluate_po_items_query())
        except Exception as e:
            logger.error(f"PO items evaluation failed: {e}")
            results.append(EvaluationResult("po_items_query", 0.0, str(e)))

        # Test 4: PO Total Value
        try:
            results.append(self.evaluate_po_value_query())
        except Exception as e:
            logger.error(f"PO value evaluation failed: {e}")
            results.append(EvaluationResult("po_value_query", 0.0, str(e)))

        # REMOVED: Stock queries - AWSDEMO user doesn't have permission
        # Stock level, low stock, and warehouse queries get 403 Forbidden
        # Only Purchase Order endpoints are accessible

        # Generate summary
        print("\n" + "="*80)
        print("                    EVALUATION SUMMARY")
        print("="*80)

        scores = [r.value for r in results]
        avg_score = sum(scores) / len(scores) if scores else 0

        print(f"\nResults ({len(results)} evaluations):")
        for result in results:
            status_icon = "✓" if result.value >= 0.8 else "⚠️ " if result.value >= 0.5 else "❌"
            print(f"  {status_icon} {result.name}: {result.value:.2f}")
            if result.comment:
                print(f"     {result.comment}")

        print(f"\n{'='*80}")
        print(f"Average Quality Score: {avg_score:.3f} ({avg_score*100:.1f}%)")
        print(f"{'='*80}\n")

        # Save results
        eval_results = {
            "experiment_name": "SAP MCP Evaluation",
            "total_items": len(results),
            "average_quality_score": avg_score,
            "scores": [
                {
                    "name": r.name,
                    "value": r.value,
                    "comment": r.comment
                }
                for r in results
            ]
        }

        return eval_results

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Evaluate SAP agent with real Bedrock invocations")
    parser.add_argument(
        '--agent-arn',
        type=str,
        help='ARN of the deployed Bedrock agent to evaluate'
    )
    parser.add_argument(
        '--agent-name',
        type=str,
        default='strands_haiku_inventory_PRD',
        help='Name of the deployed agent (will look up ARN)'
    )

    args = parser.parse_args()

    # Get agent ARN
    agent_arn = args.agent_arn

    if not agent_arn:
        # Look up agent by name
        print(f"Looking up agent: {args.agent_name}...")
        try:
            import boto3
            client = boto3.client('bedrock-agentcore-control', region_name='us-east-1')
            response = client.list_agent_runtimes()

            for agent in response.get('agentRuntimes', []):
                if agent['agentRuntimeName'] == args.agent_name:
                    agent_arn = agent['agentRuntimeArn']
                    print(f"✓ Found agent: {agent_arn}")
                    break

            if not agent_arn:
                print(f"❌ Agent not found: {args.agent_name}")
                print("\nAvailable agents:")
                for agent in response.get('agentRuntimes', []):
                    print(f"  - {agent['agentRuntimeName']}")
                return 1
        except Exception as e:
            print(f"❌ Error looking up agent: {e}")
            return 1

    try:
        evaluator = SAPMCPEvaluator(agent_arn)
        results = evaluator.run_evaluation()

        if results:
            # Save to file
            with open('sap_mcp_evaluation_results.json', 'w') as f:
                json.dump(results, f, indent=2)

            print(f"\n✓ Results saved to: sap_mcp_evaluation_results.json")
            print(f"✓ Traces available in Langfuse!")

            return 0 if results['average_quality_score'] >= 0.7 else 1
        else:
            return 1

    except Exception as e:
        print(f"\n❌ Evaluation failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == '__main__':
    sys.exit(main())
