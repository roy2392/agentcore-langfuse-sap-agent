#!/usr/bin/env python3
"""
Generate Purchase Order Evaluation Data

This script creates evaluation data using ONLY the accessible SAP Purchase Order endpoints.
The AWSDEMO user has limited permissions and can only access PO data.
"""

import json
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from utils.test_sap_api import (
    get_complete_po_data,
    get_purchase_order,
    get_purchase_order_items,
    _missing_env
)

def format_po_response(po_data):
    """Format purchase order response as Hebrew text"""
    if not po_data or not po_data.get('header'):
        return "לא נמצאו פרטי הזמנת רכש"

    summary = po_data.get('summary', {})
    header = po_data.get('header', {})
    items = po_data.get('items', [])

    response_lines = [f"פרטי הזמנת רכש {po_data.get('purchase_order', 'N/A')}:"]
    response_lines.append(f"ספק: {header.get('Supplier', 'N/A')}")
    response_lines.append(f"תאריך יצירה: {header.get('CreationDate', 'N/A')}")
    response_lines.append(f"תאריך הזמנה: {header.get('PurchaseOrderDate', 'N/A')}")
    response_lines.append(f"סה\"כ פריטים: {summary.get('items_count', 0)}")
    response_lines.append(f"סה\"כ ערך: {summary.get('total_value', 0):.2f} {header.get('DocumentCurrency', 'USD')}")
    response_lines.append(f"סה\"כ כמות: {summary.get('total_quantity', 0):.0f}")
    response_lines.append(f"קוד חברה: {header.get('CompanyCode', 'N/A')}")
    response_lines.append(f"ארגון רכש: {header.get('PurchasingOrganization', 'N/A')}")

    if items:
        response_lines.append("\nפריטים בהזמנה:")
        for item in items[:5]:  # Show first 5 items
            item_num = item.get('item', 'N/A')
            material = item.get('material', 'N/A')
            name = item.get('name', 'N/A')
            qty = item.get('qty', 0)
            uom = item.get('uom', 'PC')
            price = item.get('price', 0)
            net = item.get('net', 0)
            response_lines.append(f"  {item_num}. {material} ({name})")
            response_lines.append(f"     כמות: {qty:.0f} {uom}, מחיר יחידה: ${price:.2f}, סה\"כ: ${net:.2f}")

    return "\n".join(response_lines)

def format_po_items_response(po_data):
    """Format purchase order items as Hebrew text"""
    if not po_data or not po_data.get('items'):
        return "לא נמצאו פריטים בהזמנה"

    items = po_data.get('items', [])
    response_lines = [f"רשימת פריטים בהזמנת רכש {po_data.get('purchase_order')}:"]

    for item in items:
        material = item.get('material', 'N/A')
        name = item.get('name', 'N/A')
        qty = item.get('qty', 0)
        uom = item.get('uom', 'PC')
        response_lines.append(f"- {material}: {name} (כמות: {qty:.0f} {uom})")

    return "\n".join(response_lines)

def format_po_summary(po_data):
    """Format purchase order summary as Hebrew text"""
    if not po_data or not po_data.get('summary'):
        return "לא נמצא סיכום הזמנה"

    summary = po_data.get('summary', {})
    header = po_data.get('header', {})

    return (
        f"הזמנת רכש {po_data.get('purchase_order')} כוללת "
        f"{summary.get('items_count', 0)} פריטים "
        f"בשווי כולל של {summary.get('total_value', 0):.2f} {header.get('DocumentCurrency', 'USD')}. "
        f"הספק הוא {header.get('Supplier', 'N/A')} "
        f"והכמות הכוללת היא {summary.get('total_quantity', 0):.0f} יחידות."
    )

def generate_evaluation_data():
    """Generate evaluation data using accessible Purchase Order endpoints"""

    # Check credentials
    missing = _missing_env()
    if missing:
        print(f"Error: Missing SAP credentials: {', '.join(missing)}")
        print("Please set SAP_HOST, SAP_USER, and SAP_PASSWORD environment variables")
        return None

    print(f"\n{'='*80}")
    print("Querying SAP Purchase Order Data for Evaluation")
    print(f"{'='*80}\n")

    evaluation_data = []

    # We'll use PO 4500000520 which we know works
    po_number = "4500000520"

    # Test Case 1: Complete PO details
    print(f"1. Querying complete PO data for {po_number}...")
    po_result = get_complete_po_data(po_number)
    if po_result.get('header'):
        po_response = format_po_response(po_result)
        evaluation_data.append({
            "id": "eval_po_details",
            "input": {"question": f"מה הפרטים המלאים של הזמנת רכש {po_number}?"},
            "expected_output": po_response,
            "sap_raw_response": po_result
        })
        print(f"   ✓ Successfully retrieved PO data")
        print(f"   Items: {po_result.get('summary', {}).get('items_count', 0)}")
        print(f"   Value: ${po_result.get('summary', {}).get('total_value', 0):,.2f}\n")
    else:
        print(f"   ✗ Failed to retrieve PO data\n")
        return None

    # Test Case 2: PO summary
    print(f"2. Creating PO summary query...")
    po_summary_response = format_po_summary(po_result)
    evaluation_data.append({
        "id": "eval_po_summary",
        "input": {"question": f"תן לי סיכום של הזמנת רכש {po_number}"},
        "expected_output": po_summary_response,
        "sap_raw_response": po_result
    })
    print(f"   ✓ Summary created\n")

    # Test Case 3: Items in PO
    print(f"3. Creating PO items query...")
    po_items_response = format_po_items_response(po_result)
    evaluation_data.append({
        "id": "eval_po_items",
        "input": {"question": f"מה הפריטים בהזמנת רכש {po_number}?"},
        "expected_output": po_items_response,
        "sap_raw_response": po_result
    })
    print(f"   ✓ Items list created\n")

    # Test Case 4: Specific item question
    if po_result.get('items') and len(po_result['items']) > 0:
        first_item = po_result['items'][0]
        material = first_item.get('material')
        name = first_item.get('name')
        qty = first_item.get('qty', 0)

        print(f"4. Creating specific item query for {material}...")
        item_response = f"בהזמנת רכש {po_number}, מוצר {material} ({name}) מוזמן בכמות של {qty:.0f} יחידות."
        evaluation_data.append({
            "id": "eval_po_specific_item",
            "input": {"question": f"כמה יחידות של מוצר {material} מוזמנות בהזמנת רכש {po_number}?"},
            "expected_output": item_response,
            "sap_raw_response": po_result
        })
        print(f"   ✓ Specific item query created\n")

    # Test Case 5: Supplier information
    supplier = po_result.get('header', {}).get('Supplier', 'N/A')
    print(f"5. Creating supplier query...")
    supplier_response = f"הספק של הזמנת רכש {po_number} הוא {supplier}."
    evaluation_data.append({
        "id": "eval_po_supplier",
        "input": {"question": f"מי הספק של הזמנת רכש {po_number}?"},
        "expected_output": supplier_response,
        "sap_raw_response": po_result
    })
    print(f"   ✓ Supplier query created\n")

    return evaluation_data

def save_evaluation_data(eval_data, output_file="sap_po_evaluation_data.json"):
    """Save evaluation data to file"""
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(eval_data, f, indent=2, ensure_ascii=False)
    print(f"✓ Evaluation data saved to: {output_file}")
    return output_file

def create_langfuse_dataset(eval_data, dataset_name="sap-po-evaluation"):
    """Create Langfuse dataset with evaluation data"""
    try:
        from utils.langfuse import get_langfuse_client

        print(f"\nCreating Langfuse dataset: {dataset_name}")
        langfuse = get_langfuse_client()

        # Create or get dataset
        try:
            dataset = langfuse.create_dataset(name=dataset_name)
        except Exception as e:
            if "already exists" in str(e).lower():
                print(f"  Dataset already exists, will add items to existing dataset")
                # Get existing dataset
                datasets = langfuse.get_dataset(name=dataset_name)
                dataset = datasets
            else:
                raise

        # Create dataset items
        for item in eval_data:
            try:
                dataset.create_item(
                    input=item["input"],
                    expected_output=item["expected_output"],
                    id=item["id"]
                )
                print(f"  ✓ Added item: {item['id']}")
            except Exception as e:
                print(f"  ⚠ Warning for {item['id']}: {e}")

        print(f"✓ Langfuse dataset updated with {len(eval_data)} items")
        return dataset
    except Exception as e:
        print(f"Warning: Could not create Langfuse dataset: {e}")
        import traceback
        traceback.print_exc()
        return None

def main():
    print("\n" + "="*80)
    print("SAP Purchase Order Evaluation Data Generator")
    print("="*80)

    # Generate evaluation data
    eval_data = generate_evaluation_data()

    if not eval_data:
        print("Failed to generate evaluation data")
        sys.exit(1)

    # Save to JSON file
    output_file = save_evaluation_data(eval_data)

    print(f"\n{'='*80}")
    print(f"Generated {len(eval_data)} Purchase Order test cases")
    print(f"Output file: {output_file}")

    # Create Langfuse dataset
    try:
        dataset = create_langfuse_dataset(eval_data, "sap-po-evaluation")
        if dataset:
            print(f"✓ Langfuse dataset 'sap-po-evaluation' is ready")
    except Exception as e:
        print(f"⚠ Skipping Langfuse dataset creation: {e}")

    print(f"{'='*80}\n")

    print("Next steps:")
    print("1. Review the evaluation data in:", output_file)
    print("2. Run evaluations with: python cicd/evaluate_with_sap_mcp.py")
    print("3. View results in Langfuse dashboard")

if __name__ == '__main__':
    main()
