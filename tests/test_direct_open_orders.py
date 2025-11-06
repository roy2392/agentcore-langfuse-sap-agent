#!/usr/bin/env python3
"""Test get_open_purchase_orders directly"""
import json
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'lambda_functions'))
from sap_tools import get_open_purchase_orders

print("Testing get_open_purchase_orders directly...\n")

result = get_open_purchase_orders(limit=10)

print(f"Status: {result.get('status')}")
print(f"Message: {result.get('message', 'N/A')}")
print(f"Details: {result.get('details', 'N/A')}")
print(f"Note: {result.get('note', 'N/A')}")

if result.get('status') == 'success':
    print(f"\nTotal open orders: {result.get('total_open_orders')}")
    print(f"Total open items: {result.get('total_open_items')}")

    orders = result.get('open_purchase_orders', [])
    if orders:
        print(f"\nFirst 3 open orders:")
        for order in orders[:3]:
            print(f"  PO: {order.get('purchase_order')} | Supplier: {order.get('supplier')} | Items: {order.get('total_open_items')}")
