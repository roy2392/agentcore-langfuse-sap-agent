#!/usr/bin/env python3
"""
Generate Evaluation Data by Querying SAP

This script queries actual SAP data for the evaluation test questions
and generates expected outputs that can be used in the evaluation dataset.

The data is static and won't change between evaluation runs.
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.test_sap_api import (
    get_stock_levels,
    get_low_stock_materials,
    get_complete_po_data,
    get_warehouse_stock,
    get_purchase_orders_for_material,
    forecast_material_demand,
    _missing_env
)

def format_stock_response(result):
    """Format stock level response as Hebrew text"""
    if result.get('status') != 'success':
        return f"שגיאה בשליפת נתוני מלאי: {result.get('message', 'Unknown error')}"

    entries = result.get('data', {}).get('entries', [])
    if not entries:
        return "לא נמצאו פרטי מלאי עבור המוצר המבוקש"

    response_lines = ["פרטי המלאי עבור המוצר:"]
    for entry in entries:
        material = entry.get('Material', 'N/A')
        plant = entry.get('Plant', 'N/A')
        location = entry.get('StorageLocation', 'N/A')
        available = entry.get('AvailableQuantity', 0)
        on_hand = entry.get('QuantityOnHand', 0)
        ordered = entry.get('QuantityOrdered', 0)
        description = entry.get('MaterialDescription', 'N/A')

        response_lines.append(f"- מוצר: {material}")
        response_lines.append(f"  תיאור: {description}")
        response_lines.append(f"  מיקום: {plant}/{location}")
        response_lines.append(f"  כמות זמינה: {available}")
        response_lines.append(f"  כמות ביד: {on_hand}")
        response_lines.append(f"  כמות מוזמנת: {ordered}")

    return "\n".join(response_lines)

def format_low_stock_response(result):
    """Format low stock response as Hebrew text"""
    if result.get('status') != 'success':
        return f"שגיאה בשליפת נתונים: {result.get('message', 'Unknown error')}"

    entries = result.get('data', {}).get('entries', [])
    if not entries:
        return "לא נמצאו מוצרים במלאי נמוך"

    response_lines = ["מוצרים במלאי נמוך:"]
    for entry in entries[:5]:  # Return top 5
        material = entry.get('Material', 'N/A')
        available = entry.get('AvailableQuantity', 0)
        description = entry.get('MaterialDescription', 'N/A')

        response_lines.append(f"- {material}: {description} (כמות: {available})")

    return "\n".join(response_lines)

def format_po_response(po_data):
    """Format purchase order response as Hebrew text"""
    if not po_data:
        return "לא נמצאו פרטי הזמנה לפרסום עבור הזמנה זו"

    summary = po_data.get('summary', {})
    header = po_data.get('header', {})
    items = po_data.get('items', [])

    response_lines = [f"פרטי הזמנה {po_data.get('purchase_order', 'N/A')}:"]
    response_lines.append(f"ספק: {header.get('Supplier', 'N/A')}")
    response_lines.append(f"תאריך הזמנה: {header.get('PurchaseOrderDate', 'N/A')}")
    response_lines.append(f"סה\"כ פריטים: {summary.get('items_count', 0)}")
    response_lines.append(f"סה\"כ ערך: {summary.get('total_value', 0)} {header.get('DocumentCurrency', 'ILS')}")
    response_lines.append(f"סה\"כ כמות: {summary.get('total_quantity', 0)}")

    if items:
        response_lines.append("\nפריטים בהזמנה:")
        for item in items:
            item_num = item.get('item', 'N/A')
            material = item.get('material', 'N/A')
            qty = item.get('qty', 0)
            price = item.get('price', 0)
            response_lines.append(f"  פריט {item_num}: {material} - כמות: {qty}, מחיר: {price}")

    return "\n".join(response_lines)

def format_warehouse_response(result):
    """Format warehouse stock response as Hebrew text"""
    if result.get('status') != 'success':
        return f"שגיאה בשליפת נתוני מחסן: {result.get('message', 'Unknown error')}"

    entries = result.get('data', {}).get('entries', [])
    if not entries:
        return "לא נמצאו פרטי מחסן"

    response_lines = ["סיכום מלאי המחסן:"]
    total_available = 0
    total_on_hand = 0

    for entry in entries:
        available = entry.get('AvailableQuantity', 0)
        on_hand = entry.get('QuantityOnHand', 0)
        total_available += available
        total_on_hand += on_hand

    response_lines.append(f"סה\"כ כמות זמינה: {total_available}")
    response_lines.append(f"סה\"כ כמות ביד: {total_on_hand}")
    response_lines.append(f"מספר פריטים: {len(entries)}")

    return "\n".join(response_lines)

def generate_evaluation_data():
    """Generate evaluation data by querying SAP"""

    # Check credentials
    missing = _missing_env()
    if missing:
        print(f"Error: Missing SAP credentials: {', '.join(missing)}")
        print("Please set SAP_HOST, SAP_USER, and SAP_PASSWORD environment variables")
        return None

    print(f"\n{'='*80}")
    print("Querying SAP for Evaluation Data")
    print(f"{'='*80}\n")

    evaluation_data = []

    # Test Case 1: Stock levels for specific material
    print("1. Querying stock levels for material 100-100...")
    stock_result = get_stock_levels("100-100")
    stock_response = format_stock_response(stock_result)
    evaluation_data.append({
        "id": "eval_stock_query",
        "input": {"question": "מה כמות המלאי של המוצר 100-100?"},
        "expected_output": stock_response,
        "sap_raw_response": stock_result
    })
    print(f"   Expected output preview: {stock_response[:100]}...\n")

    # Test Case 2: Low stock materials
    print("2. Querying low stock materials...")
    low_stock_result = get_low_stock_materials()
    low_stock_response = format_low_stock_response(low_stock_result)
    evaluation_data.append({
        "id": "eval_low_stock",
        "input": {"question": "אילו מוצרים יש לנו במלאי נמוך?"},
        "expected_output": low_stock_response,
        "sap_raw_response": low_stock_result
    })
    print(f"   Expected output preview: {low_stock_response[:100]}...\n")

    # Test Case 3: Purchase order status
    print("3. Querying purchase order 4500000520...")
    po_result = get_complete_po_data("4500000520")
    po_response = format_po_response(po_result)
    evaluation_data.append({
        "id": "eval_po_status",
        "input": {"question": "מה סטטוס ההזמנה מסדר קנייה 4500000520?"},
        "expected_output": po_response,
        "sap_raw_response": po_result
    })
    print(f"   Expected output preview: {po_response[:100]}...\n")

    # Test Case 4: Warehouse summary
    print("4. Querying warehouse 01 stock...")
    warehouse_result = get_warehouse_stock(storage_location="01")
    warehouse_response = format_warehouse_response(warehouse_result)
    evaluation_data.append({
        "id": "eval_warehouse_status",
        "input": {"question": "מה המצב הכללי של המלאי במחסן 01?"},
        "expected_output": warehouse_response,
        "sap_raw_response": warehouse_result
    })
    print(f"   Expected output preview: {warehouse_response[:100]}...\n")

    # Test Case 5: Upcoming deliveries (POs with future dates)
    print("5. Querying material purchase orders...")
    po_items_result = get_purchase_orders_for_material("100-100")
    po_items_response = format_low_stock_response(po_items_result) if po_items_result.get('status') != 'success' else "מוצר 100-100 יש הזמנות קנייה קיימות"
    evaluation_data.append({
        "id": "eval_upcoming_deliveries",
        "input": {"question": "כמה מוצרים יישלחו בשבוע הקרוב?"},
        "expected_output": po_items_response,
        "sap_raw_response": po_items_result
    })
    print(f"   Expected output preview: {po_items_response[:100]}...\n")

    return evaluation_data

def save_evaluation_data(eval_data, output_file="sap_evaluation_data.json"):
    """Save evaluation data to file"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(eval_data, f, indent=2, ensure_ascii=False)
    print(f"✓ Evaluation data saved to: {output_file}")

def create_langfuse_dataset(eval_data, dataset_name="sap-inventory-evaluation"):
    """Create Langfuse dataset with evaluation data"""
    try:
        from utils.langfuse import get_langfuse_client

        print(f"\nCreating Langfuse dataset: {dataset_name}")
        langfuse = get_langfuse_client()

        # Create or get dataset
        dataset = langfuse.create_dataset(name=dataset_name)

        # Create dataset items
        for item in eval_data:
            dataset.create_item(
                input=item["input"],
                expected_output=item["expected_output"],
                id=item["id"]
            )
            print(f"  ✓ Added item: {item['id']}")

        print(f"✓ Langfuse dataset created with {len(eval_data)} items")
        return dataset
    except Exception as e:
        print(f"Warning: Could not create Langfuse dataset: {e}")
        return None

def main():
    print("\n" + "="*80)
    print("SAP Evaluation Data Generator")
    print("="*80)

    # Generate evaluation data
    eval_data = generate_evaluation_data()

    if not eval_data:
        print("Failed to generate evaluation data")
        sys.exit(1)

    # Save to JSON file
    save_evaluation_data(eval_data)

    # Create Langfuse dataset
    try:
        create_langfuse_dataset(eval_data, "strands-ai-mcp-agent-evaluation")
    except Exception as e:
        print(f"Skipping Langfuse dataset creation: {e}")

    print(f"\n{'='*80}")
    print("Evaluation data generation complete!")
    print(f"Generated {len(eval_data)} test cases")
    print(f"{'='*80}\n")

if __name__ == '__main__':
    main()
