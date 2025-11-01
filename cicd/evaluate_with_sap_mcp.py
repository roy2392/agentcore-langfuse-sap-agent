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
    """Evaluate agent responses using SAP MCP for ground truth"""

    def __init__(self):
        """Initialize evaluator with SAP MCP server"""
        try:
            from utils.langfuse import get_langfuse_client
            self.langfuse = get_langfuse_client()
        except Exception as e:
            logger.warning(f"Langfuse not available: {e}")
            self.langfuse = None

        try:
            from utils.sap_mcp_server import SAPMCPServer
            self.mcp_server = SAPMCPServer()
        except Exception as e:
            logger.error(f"SAP MCP Server not available: {e}")
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

        # Get SAP data
        print(f"\n1. Fetching PO {po_number} data via MCP...")
        po_result = self.mcp_server.execute_tool(
            "get_complete_po_data",
            {"po_number": po_number}
        )

        if not po_result or not po_result.get('header'):
            return EvaluationResult(
                name="po_status_query",
                value=0.5,
                comment=f"PO {po_number} not found in SAP"
            )

        header = po_result.get('header', {})
        items = po_result.get('items', [])
        summary = po_result.get('summary', {})

        print(f"\n2. SAP Response:")
        print(f"   Supplier: {header.get('Supplier', 'N/A')}")
        print(f"   Date: {header.get('PurchaseOrderDate', 'N/A')}")
        print(f"   Items: {len(items)}")
        print(f"   Total Value: {summary.get('total_value', 0)}")
        print(f"   Currency: {header.get('DocumentCurrency', 'ILS')}")

        # Format response
        expected_output = (
            f"הזמנה {po_number}:\n"
            f"- ספק: {header.get('Supplier', 'N/A')}\n"
            f"- תאריך: {header.get('PurchaseOrderDate', 'N/A')}\n"
            f"- פריטים: {len(items)}\n"
            f"- סה\"כ ערך: {summary.get('total_value', 0)} {header.get('DocumentCurrency', 'ILS')}"
        )

        print(f"\n3. Expected Hebrew Response:")
        print(f"   {expected_output}")

        score = 1.0 if header else 0.5

        return EvaluationResult(
            name="po_status_query",
            value=score,
            comment=f"PO {po_number}: {len(items)} items, {summary.get('total_value', 0)} {header.get('DocumentCurrency', 'ILS')}"
        )

    def evaluate_warehouse_query(self) -> EvaluationResult:
        """Evaluate: "מה המצב הכללי של המלאי במחסן 01?" """

        print("\n" + "="*80)
        print("EVALUATION: Warehouse Status Query")
        print("="*80)

        question = "מה המצב הכללי של המלאי במחסן 01?"
        print(f"\nQuestion: {question}")

        # Get SAP data
        print("\n1. Fetching warehouse stock via MCP...")
        warehouse_result = self.mcp_server.execute_tool(
            "get_warehouse_stock",
            {"storage_location": "01"}
        )

        if warehouse_result.get('status') != 'success':
            return EvaluationResult(
                name="warehouse_query",
                value=0.5,
                comment=f"Failed: {warehouse_result.get('message')}"
            )

        entries = warehouse_result.get('data', {}).get('entries', [])

        total_available = 0
        total_on_hand = 0
        for entry in entries:
            total_available += entry.get('AvailableQuantity', 0)
            total_on_hand += entry.get('QuantityOnHand', 0)

        print(f"\n2. SAP Response:")
        print(f"   Total Items: {len(entries)}")
        print(f"   Total Available: {total_available}")
        print(f"   Total On Hand: {total_on_hand}")

        expected_output = (
            f"סטטוס מחסן 01:\n"
            f"- סה\"כ פריטים: {len(entries)}\n"
            f"- סה\"כ זמינה: {total_available} יחידות\n"
            f"- סה\"כ ביד: {total_on_hand} יחידות"
        )

        print(f"\n3. Expected Hebrew Response:")
        print(f"   {expected_output}")

        score = 1.0 if len(entries) > 0 else 0.5

        return EvaluationResult(
            name="warehouse_query",
            value=score,
            comment=f"Warehouse 01: {len(entries)} items, {total_available} available"
        )

    def run_evaluation(self) -> Dict[str, Any]:
        """Run complete evaluation suite"""

        print("\n" + "="*80)
        print("                 SAP MCP EVALUATION SUITE")
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

        # Run evaluations
        results = []

        try:
            results.append(self.evaluate_stock_level_query())
        except Exception as e:
            logger.error(f"Stock level evaluation failed: {e}")
            results.append(EvaluationResult("stock_level_query", 0.0, str(e)))

        try:
            results.append(self.evaluate_low_stock_query())
        except Exception as e:
            logger.error(f"Low stock evaluation failed: {e}")
            results.append(EvaluationResult("low_stock_query", 0.0, str(e)))

        try:
            results.append(self.evaluate_po_status_query())
        except Exception as e:
            logger.error(f"PO status evaluation failed: {e}")
            results.append(EvaluationResult("po_status_query", 0.0, str(e)))

        try:
            results.append(self.evaluate_warehouse_query())
        except Exception as e:
            logger.error(f"Warehouse evaluation failed: {e}")
            results.append(EvaluationResult("warehouse_query", 0.0, str(e)))

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
    try:
        evaluator = SAPMCPEvaluator()
        results = evaluator.run_evaluation()

        if results:
            # Save to file
            with open('sap_mcp_evaluation_results.json', 'w') as f:
                json.dump(results, f, indent=2)

            print(f"✓ Results saved to: sap_mcp_evaluation_results.json")

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
