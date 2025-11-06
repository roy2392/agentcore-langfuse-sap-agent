#!/usr/bin/env python3
"""
Test script for new Material Document API tools
Tests the three new tools:
1. get_goods_receipts - Get goods receipt data
2. get_open_purchase_orders - Find orders where ordered > received
3. get_inventory_with_open_orders - Cross-reference stock with open orders
"""
import json
import os
import sys

# Add parent directory to path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# Import from lambda_functions
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lambda_functions'))
from sap_tools import (
    get_goods_receipts,
    get_open_purchase_orders,
    get_inventory_with_open_orders
)


def test_goods_receipts():
    """Test goods receipts API"""
    print("\n" + "="*80)
    print("TEST 1: Goods Receipts (Material Documents)")
    print("="*80)

    print("\n1.1 Get all recent goods receipts:")
    result = get_goods_receipts(limit=10)
    print(f"Status: {result.get('status')}")

    if result.get("status") == "success":
        receipts = result.get("goods_receipts", [])
        print(f"Found {len(receipts)} goods receipts")
        print(f"Total quantity received: {result.get('total_quantity_received', 0)}")

        if receipts:
            print("\nSample receipts:")
            for gr in receipts[:3]:
                print(f"  Material: {gr.get('Material')} | PO: {gr.get('PurchaseOrder')} | Qty: {gr.get('QuantityInEntryUnit')} | Date: {gr.get('PostingDate')}")
    else:
        print(f"Note: {result.get('message')}")

    print("\n1.2 Get goods receipts for specific PO (4500000520):")
    result = get_goods_receipts(po_number="4500000520", limit=20)
    print(f"Status: {result.get('status')}")

    if result.get("status") == "success":
        receipts = result.get("goods_receipts", [])
        print(f"Found {len(receipts)} goods receipts for PO 4500000520")

        if receipts:
            for gr in receipts:
                print(f"  Material: {gr.get('Material')} | Item: {gr.get('PurchaseOrderItem')} | Qty: {gr.get('QuantityInEntryUnit')} | Date: {gr.get('PostingDate')}")


def test_open_purchase_orders():
    """Test open purchase orders"""
    print("\n" + "="*80)
    print("TEST 2: Open Purchase Orders (Ordered vs Received)")
    print("="*80)

    result = get_open_purchase_orders(limit=20)
    print(f"Status: {result.get('status')}")

    if result.get("status") == "success":
        open_orders = result.get("open_purchase_orders", [])
        total_open_items = result.get("total_open_items", 0)

        print(f"Found {len(open_orders)} open purchase orders")
        print(f"Total open items: {total_open_items}")

        if open_orders:
            print("\nOpen purchase orders:")
            for order in open_orders[:5]:
                po = order.get("purchase_order")
                supplier = order.get("supplier")
                date = order.get("order_date")
                items_count = order.get("total_open_items")

                print(f"\n  PO: {po} | Supplier: {supplier} | Date: {date} | Open Items: {items_count}")

                for item in order.get("items", [])[:3]:
                    material = item.get("material")
                    ordered = item.get("ordered_quantity")
                    received = item.get("received_quantity")
                    open_qty = item.get("open_quantity")
                    print(f"    - {material}: Ordered={ordered}, Received={received}, Open={open_qty}")
        else:
            print("No open purchase orders found (all orders fully received)")
    else:
        print(f"Error: {result.get('message')}")


def test_inventory_with_open_orders():
    """Test inventory cross-reference with open orders"""
    print("\n" + "="*80)
    print("TEST 3: Inventory with Open Orders (Cross-Reference)")
    print("="*80)

    result = get_inventory_with_open_orders()
    print(f"Status: {result.get('status')}")

    if result.get("status") == "success":
        inventory_items = result.get("inventory_with_open_orders", [])

        print(f"Found {len(inventory_items)} materials with both stock and open orders")

        if inventory_items:
            print("\nMaterials with stock AND open orders:")
            for item in inventory_items[:10]:
                material = item.get("material")
                desc = item.get("description", "No description")
                available = item.get("available_quantity")
                open_qty = item.get("total_open_quantity")
                orders_count = item.get("open_orders_count")

                print(f"\n  {material}: {desc[:50]}")
                print(f"    Available Stock: {available}, Incoming: {open_qty} ({orders_count} orders)")

                # Show open orders for this material
                for order in item.get("open_orders", [])[:2]:
                    po = order.get("purchase_order")
                    supplier = order.get("supplier")
                    qty = order.get("open_quantity")
                    print(f"      PO {po} ({supplier}): {qty} units")
        else:
            print("No materials found with both stock and open orders")
    else:
        print(f"Note: {result.get('message')}")


def main():
    """Run all tests"""
    print("\n" + "="*80)
    print("🧪 Testing New Material Document API Tools")
    print("="*80)
    print("\nThis script tests three new tools:")
    print("1. get_goods_receipts - Track what has been received")
    print("2. get_open_purchase_orders - Find orders with pending deliveries")
    print("3. get_inventory_with_open_orders - Cross-reference stock with open POs")

    # Check environment
    required = ["SAP_HOST", "SAP_USER", "SAP_PASSWORD"]
    missing = [var for var in required if not os.getenv(var)]
    if missing:
        print(f"\n❌ Missing environment variables: {', '.join(missing)}")
        print("Please set SAP_HOST, SAP_USER, and SAP_PASSWORD in .env file")
        return 1

    print(f"\n✅ Environment configured")
    print(f"SAP Host: {os.getenv('SAP_HOST')}")
    print(f"SAP User: {os.getenv('SAP_USER')}")

    try:
        test_goods_receipts()
        test_open_purchase_orders()
        test_inventory_with_open_orders()

        print("\n" + "="*80)
        print("✅ ALL TESTS COMPLETE")
        print("="*80)
        print("\nThese tools now enable answering the Hebrew questions:")
        print("  כמה במלאי? (How much in stock?) - Use get_material_stock")
        print("  מה פתוח בהזמנות? (What's open in orders?) - Use get_open_purchase_orders")
        print("  מה יש לו מלאי שיש בהזמנת רכש פתוחה? - Use get_inventory_with_open_orders")
        print()

        return 0

    except Exception as e:
        print(f"\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
