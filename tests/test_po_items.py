#!/usr/bin/env python3
"""Test PO items query directly"""
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
from sap_tools import make_sap_request, _build_url, parse_json_entries

print("Testing PO items query...\n")

# Test without orderby
url = _build_url(
    "/sap/opu/odata/sap/C_PURCHASEORDER_FS_SRV/I_PurchaseOrderItem",
    filters=None,
    select=["PurchaseOrder", "PurchaseOrderItem", "Material"],
    orderby=None,
    top=5
)

print(f"URL: {url}\n")
res = make_sap_request(url)
print(f"Status: {res['status']}")

if res['status'] == 'success':
    print("✅ Query successful!")
    parsed = parse_json_entries(res['data'])
    print(f"Found {len(parsed.get('entries', []))} items")
    for entry in parsed.get('entries', [])[:3]:
        print(f"  PO: {entry.get('PurchaseOrder')}, Item: {entry.get('PurchaseOrderItem')}, Material: {entry.get('Material')}")
else:
    print(f"❌ Error: {res.get('message')}")
    if 'details' in res:
        print(f"Details: {res['details'][:500]}")
