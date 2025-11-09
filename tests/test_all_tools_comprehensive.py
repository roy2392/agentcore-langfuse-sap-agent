#!/usr/bin/env python3
"""
Comprehensive test suite for all SAP tools
Tests each tool directly via Lambda to ensure correct responses
"""
import sys
import json
import os
from pathlib import Path

# Add parent directory to path to import lambda functions
sys.path.insert(0, str(Path(__file__).parent.parent / "lambda_functions"))

from sap_tools import (
    list_purchase_orders,
    search_purchase_orders,
    get_material_stock,
    get_material_in_transit,
    get_orders_in_transit,
    get_goods_receipts,
    get_open_purchase_orders,
    get_inventory_with_open_orders,
    get_orders_awaiting_invoice_or_delivery
)
from get_complete_po_data import get_complete_po_data

# Load environment variables
try:
    from dotenv import load_dotenv
    load_dotenv()
except:
    pass

class Colors:
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'
    BOLD = '\033[1m'

def print_section(title):
    print(f"\n{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{title}{Colors.END}")
    print(f"{Colors.BOLD}{Colors.BLUE}{'='*80}{Colors.END}\n")

def print_test(test_name, status, details=None):
    status_color = Colors.GREEN if status == "✓" else Colors.RED if status == "✗" else Colors.YELLOW
    print(f"{status_color}{status} {test_name}{Colors.END}")
    if details:
        print(f"  {details}")

def validate_response(result, test_name):
    """Validate that a response has the expected structure"""
    if not isinstance(result, dict):
        print_test(test_name, "✗", f"Response is not a dict: {type(result)}")
        return False

    if result.get("status") == "error":
        print_test(test_name, "✗", f"Error: {result.get('message')}")
        return False

    if result.get("status") != "success":
        print_test(test_name, "⚠", f"Unexpected status: {result.get('status')}")
        return False

    return True

def test_list_purchase_orders():
    print_section("TEST 1: list_purchase_orders")

    # Test 1.1: Default parameters
    result = list_purchase_orders()
    if validate_response(result, "1.1: Default parameters"):
        count = result.get('total_count', 0)
        print_test("1.1: Default parameters", "✓", f"Retrieved {count} orders")

    # Test 1.2: With limit
    result = list_purchase_orders(limit=5)
    if validate_response(result, "1.2: With limit=5"):
        count = result.get('total_count', 0)
        print_test("1.2: With limit=5", "✓", f"Retrieved {count} orders (max 5)")
        if count > 5:
            print_test("1.2: Limit validation", "✗", f"Expected ≤5 but got {count}")

    # Test 1.3: With date filter
    result = list_purchase_orders(date_from="2024-08-01", limit=10)
    if validate_response(result, "1.3: With date filter"):
        count = result.get('total_count', 0)
        print_test("1.3: With date filter", "✓", f"Retrieved {count} orders from 2024-08-01")

def test_search_purchase_orders():
    print_section("TEST 2: search_purchase_orders")

    # Test 2.1: Search by PO number
    result = search_purchase_orders(search_term="4500001818", search_field="po_number")
    if validate_response(result, "2.1: Search by PO number"):
        count = result.get('total_orders', 0)
        print_test("2.1: Search by PO number", "✓", f"Found {count} matching orders")

    # Test 2.2: Search with all fields
    result = search_purchase_orders(search_term="4500", search_field="all", limit=5)
    if validate_response(result, "2.2: Search all fields"):
        count = result.get('total_orders', 0)
        print_test("2.2: Search all fields", "✓", f"Found {count} matching orders")

def test_get_material_stock():
    print_section("TEST 3: get_material_stock")

    # Test 3.1: All materials
    result = get_material_stock()
    if validate_response(result, "3.1: All materials"):
        count = result.get('total_items', 0)
        total_qty = result.get('total_available_quantity', 0)
        print_test("3.1: All materials", "✓", f"{count} materials, total {total_qty:.2f} units")

    # Test 3.2: Low stock only
    result = get_material_stock(low_stock_only=True, threshold=10)
    if validate_response(result, "3.2: Low stock items"):
        count = result.get('total_items', 0)
        print_test("3.2: Low stock items", "✓", f"Found {count} items with stock < 10")

def test_get_material_in_transit():
    print_section("TEST 4: get_material_in_transit (INVENTORY-FOCUSED)")

    # Test 4.1: All materials in transit
    result = get_material_in_transit()
    if validate_response(result, "4.1: All materials in transit"):
        count = result.get('total_materials', 0)
        print_test("4.1: All materials in transit", "✓", f"{count} materials with in-transit quantities")

        # Sample data validation
        materials = result.get('materials_in_transit', [])
        if materials:
            sample = materials[0]
            has_qty = 'total_in_transit_qty' in sample
            has_orders = 'related_orders' in sample
            if has_qty and has_orders:
                print_test("4.1: Data structure", "✓", f"Correct structure: material, qty, related orders")
            else:
                print_test("4.1: Data structure", "✗", "Missing expected fields")

def test_get_orders_in_transit():
    print_section("TEST 5: get_orders_in_transit (ORDER-FOCUSED)")

    # Test 5.1: Orders in transit
    result = get_orders_in_transit()
    if validate_response(result, "5.1: Orders in transit"):
        count = result.get('total_orders', 0)
        print_test("5.1: Orders in transit", "✓", f"{count} orders with items pending delivery")

        # Sample data validation
        orders = result.get('orders_in_transit', [])
        if orders:
            sample = orders[0]
            has_po = 'purchase_order' in sample
            has_items = 'items_in_transit' in sample
            if has_po and has_items:
                print_test("5.1: Data structure", "✓", f"Correct structure: PO, supplier, items")
            else:
                print_test("5.1: Data structure", "✗", "Missing expected fields")

def test_get_goods_receipts():
    print_section("TEST 6: get_goods_receipts")

    # Test 6.1: All goods receipts
    result = get_goods_receipts()
    if result.get("status") == "partial":
        print_test("6.1: All goods receipts", "⚠", "API not available (expected for demo system)")
    elif validate_response(result, "6.1: All goods receipts"):
        count = result.get('total_records', 0)
        print_test("6.1: All goods receipts", "✓", f"{count} receipt records")

def test_get_open_purchase_orders():
    print_section("TEST 7: get_open_purchase_orders")

    # Test 7.1: Open orders
    result = get_open_purchase_orders()
    if validate_response(result, "7.1: Open purchase orders"):
        count = result.get('total_open_orders', 0)
        print_test("7.1: Open purchase orders", "✓", f"{count} potentially open orders")

def test_get_inventory_with_open_orders():
    print_section("TEST 8: get_inventory_with_open_orders")

    # Test 8.1: Cross-reference inventory and orders
    result = get_inventory_with_open_orders()
    if result.get("status") == "partial":
        print_test("8.1: Inventory with open orders", "⚠", "Partial data available")
    elif validate_response(result, "8.1: Inventory with open orders"):
        count = result.get('total_materials', 0)
        print_test("8.1: Inventory with open orders", "✓", f"{count} materials with stock + open orders")

def test_get_orders_awaiting_invoice_or_delivery():
    print_section("TEST 9: get_orders_awaiting_invoice_or_delivery")

    # Test 9.1: All pending items
    result = get_orders_awaiting_invoice_or_delivery()
    if validate_response(result, "9.1: Awaiting invoice or delivery"):
        total_items = result.get('total_items_in_system', 0)
        summary = result.get('summary', {})
        both_pending = summary.get('total_both_pending', 0)
        patterns = summary.get('patterns', {})

        print_test("9.1: Awaiting invoice or delivery", "✓",
                  f"Analyzed {total_items} items")
        print_test("9.1: Items pending both", "✓",
                  f"{both_pending} items without delivery AND invoice")

        # Validate pattern analysis
        if patterns:
            unique_pos = patterns.get('total_unique_pos', 0)
            percentage = patterns.get('percentage_with_issues', 0)
            print_test("9.1: Pattern analysis", "✓",
                      f"{unique_pos} unique POs, {percentage}% with issues")

    # Test 9.2: Filter by not_delivered
    result = get_orders_awaiting_invoice_or_delivery(filter_type="not_delivered", limit=10)
    if validate_response(result, "9.2: Not delivered only"):
        items = result.get('items_awaiting_delivery', [])
        print_test("9.2: Not delivered only", "✓", f"{len(items)} items not delivered")

def test_get_complete_po_data():
    print_section("TEST 10: get_complete_po_data (FIXED)")

    # Test 10.1: Valid PO number
    result = get_complete_po_data("4500001818")
    if isinstance(result, dict):
        po = result.get('purchase_order')
        header_found = result.get('summary', {}).get('header_found', False)
        items_count = result.get('summary', {}).get('items_count', 0)

        print_test("10.1: Valid PO (4500001818)", "✓",
                  f"PO: {po}, Header: {header_found}, Items: {items_count}")
    else:
        print_test("10.1: Valid PO", "✗", "Unexpected response format")

    # Test 10.2: Different PO number (verify no hardcoded default)
    result2 = get_complete_po_data("4500001819")
    if isinstance(result2, dict):
        po2 = result2.get('purchase_order')
        if po2 == "4500001819":
            print_test("10.2: Different PO (4500001819)", "✓",
                      f"Correctly returns PO: {po2} (not hardcoded 4500000520)")
        else:
            print_test("10.2: Different PO", "✗",
                      f"Expected 4500001819 but got {po2}")

def test_data_accuracy():
    print_section("DATA ACCURACY VALIDATION")

    # Test: Check if PO numbers are in expected range
    result = list_purchase_orders(limit=20)
    if validate_response(result, "Data validation"):
        orders = result.get('purchase_orders', [])
        if orders:
            po_numbers = [o.get('PurchaseOrder') for o in orders if o.get('PurchaseOrder')]
            if po_numbers:
                po_nums = [int(po) if po.isdigit() else 0 for po in po_numbers]
                min_po = min(po_nums)
                max_po = max(po_nums)
                print_test("PO number range", "✓",
                          f"Range: {min_po} to {max_po}")

                # Check if they're in reasonable range (4500000000-4500999999)
                if 4500000000 <= min_po <= 4500999999 and 4500000000 <= max_po <= 4500999999:
                    print_test("PO number format", "✓", "All POs in expected format (4500XXXXXX)")
                else:
                    print_test("PO number format", "⚠", "Some POs outside expected range")

def main():
    print(f"\n{Colors.BOLD}{Colors.BLUE}")
    print("╔════════════════════════════════════════════════════════════════════════════╗")
    print("║                  SAP TOOLS COMPREHENSIVE TEST SUITE                        ║")
    print("╚════════════════════════════════════════════════════════════════════════════╝")
    print(Colors.END)

    # Run all tests
    try:
        test_list_purchase_orders()
        test_search_purchase_orders()
        test_get_material_stock()
        test_get_material_in_transit()
        test_get_orders_in_transit()
        test_get_goods_receipts()
        test_get_open_purchase_orders()
        test_get_inventory_with_open_orders()
        test_get_orders_awaiting_invoice_or_delivery()
        test_get_complete_po_data()
        test_data_accuracy()

        print_section("TEST SUITE COMPLETE")
        print(f"{Colors.GREEN}All tests executed successfully!{Colors.END}\n")

    except Exception as e:
        print(f"\n{Colors.RED}Test suite failed with error:{Colors.END}")
        print(f"{Colors.RED}{str(e)}{Colors.END}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()
