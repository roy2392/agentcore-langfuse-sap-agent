# Material Document API Implementation

## Overview

This document describes the implementation of three new tools that integrate with SAP's Material Document API (`API_MATERIAL_DOCUMENT_SRV`) to track goods receipts and determine open vs closed purchase orders.

**Implementation Date:** 2025-01-05
**Purpose:** Answer critical inventory questions in Hebrew and English

---

## Problem Statement

The original implementation could list purchase orders but couldn't answer:

1. **כמה במלאי?** (How much in stock?)
   ✅ Already solved with `get_material_stock`

2. **מה פתוח בהזמנות?** (What's open in orders?)
   ❌ Missing - couldn't determine which orders were fully received vs partially received

3. **מה יש לו מלאי שיש בהזמנת רכש פתוחה?** (What has stock with open PO?)
   ❌ Missing - couldn't cross-reference stock with open orders

---

## Solution

Added three new tools to `lambda_functions/sap_tools.py`:

### 1. `get_goods_receipts(po_number=None, material_number=None, limit=50)`

**Purpose:** Query Material Document API to get goods receipt data

**How it works:**
- Queries `API_MATERIAL_DOCUMENT_SRV/A_MaterialDocumentItem`
- Filters for movement type 101 (goods receipts)
- Can filter by PO number or material number
- Returns received quantities with dates and locations

**Returns:**
```json
{
  "status": "success",
  "goods_receipts": [
    {
      "MaterialDocument": "5000012345",
      "Material": "MZ-RM-C990-01",
      "PurchaseOrder": "4500000520",
      "PurchaseOrderItem": "00010",
      "QuantityInEntryUnit": 100,
      "PostingDate": "2024-03-15",
      "Plant": "1710"
    }
  ],
  "total_quantity_received": 500
}
```

**Usage:**
```python
# Get all recent goods receipts
result = get_goods_receipts(limit=20)

# Get goods receipts for specific PO
result = get_goods_receipts(po_number="4500000520")

# Get goods receipts for specific material
result = get_goods_receipts(material_number="MZ-RM-C990-01")
```

---

### 2. `get_open_purchase_orders(limit=50)`

**Purpose:** Find purchase orders where ordered quantity > received quantity

**How it works:**
1. Gets recent PO items (last 180 days)
2. For each PO, calls `get_goods_receipts` to get received quantities
3. Compares ordered vs received quantities
4. Returns only items where open quantity > 0

**Returns:**
```json
{
  "status": "success",
  "open_purchase_orders": [
    {
      "purchase_order": "4500000520",
      "supplier": "USSU-VSF08",
      "order_date": "2024-03-01",
      "total_open_items": 3,
      "items": [
        {
          "material": "MZ-RM-C990-01",
          "ordered_quantity": 500,
          "received_quantity": 300,
          "open_quantity": 200
        }
      ]
    }
  ],
  "total_open_orders": 5,
  "total_open_items": 12
}
```

**Usage:**
```python
# Get all open purchase orders
result = get_open_purchase_orders(limit=30)

# Check which orders still need delivery
for order in result.get("open_purchase_orders", []):
    print(f"PO {order['purchase_order']} has {order['total_open_items']} open items")
```

**Answers:** מה פתוח בהזמנות? (What's open in orders?)

---

### 3. `get_inventory_with_open_orders(threshold=10)`

**Purpose:** Cross-reference materials that have BOTH stock AND open purchase orders

**How it works:**
1. Gets current stock from `get_material_stock`
2. Gets open orders from `get_open_purchase_orders`
3. Cross-references materials that appear in both
4. Returns materials with stock + incoming quantities

**Returns:**
```json
{
  "status": "success",
  "inventory_with_open_orders": [
    {
      "material": "MZ-RM-C990-01",
      "description": "Raw Material C990-01",
      "plant": "1710",
      "available_quantity": 150,
      "total_open_quantity": 200,
      "open_orders_count": 2,
      "open_orders": [
        {
          "purchase_order": "4500000520",
          "supplier": "USSU-VSF08",
          "open_quantity": 100
        },
        {
          "purchase_order": "4500000525",
          "supplier": "17300001",
          "open_quantity": 100
        }
      ]
    }
  ],
  "total_materials": 8
}
```

**Usage:**
```python
# Find materials with stock + open orders
result = get_inventory_with_open_orders()

# Check for potential overstocking
for item in result.get("inventory_with_open_orders", []):
    available = item["available_quantity"]
    incoming = item["total_open_quantity"]
    print(f"{item['material']}: {available} in stock, {incoming} incoming")
```

**Answers:** מה יש לו מלאי שיש בהזמנת רכש פתוחה? (What has stock with open PO?)

---

## Technical Implementation

### File Changes

1. **lambda_functions/sap_tools.py**
   - Added 3 new tool functions (TOOL 5, 6, 7)
   - Updated `lambda_handler` to route to new tools
   - Added to available_tools list

2. **utils/test_sap_inventory.py**
   - Added 3 new check methods
   - Updated recommendations to include open orders
   - Updated main() to run 8 checks (was 5)

3. **utils/test_new_tools.py** (NEW)
   - Standalone test script for new tools
   - Focused testing of Material Document API integration
   - Shows how to use each new function

4. **docs/INVENTORY_MANAGEMENT.md**
   - Added documentation for new capabilities
   - Updated SAP API endpoints section
   - Added Material Document Service description
   - Updated testing section with new checks

---

## API Integration Details

### Material Document API Endpoint

**Service:** `API_MATERIAL_DOCUMENT_SRV`
**Entity:** `A_MaterialDocumentItem`
**URL Pattern:**
```
https://{SAP_HOST}/sap/opu/odata/sap/API_MATERIAL_DOCUMENT_SRV/A_MaterialDocumentItem
```

### Key OData Filters Used

```
# Goods receipts only (movement type 101)
$filter=GoodsMovementType eq '101'

# For specific PO
$filter=GoodsMovementType eq '101' and PurchaseOrder eq '4500000520'

# For specific material
$filter=GoodsMovementType eq '101' and Material eq 'MZ-RM-C990-01'
```

### Fields Retrieved

```python
select = [
    "MaterialDocument",      # Receipt document number
    "MaterialDocumentYear",  # Fiscal year
    "MaterialDocumentItem",  # Item number
    "Material",              # Material number
    "Plant",                 # Plant code
    "StorageLocation",       # Storage location
    "GoodsMovementType",     # 101 = goods receipt
    "QuantityInEntryUnit",   # Received quantity
    "EntryUnit",             # Unit of measure
    "PurchaseOrder",         # Reference PO
    "PurchaseOrderItem",     # Reference PO item
    "PostingDate",           # Receipt date
    "DocumentDate",          # Document date
    "MaterialDocumentHeaderText"  # Header text
]
```

---

## Testing

### Test All New Features

```bash
# Comprehensive inventory health check (8 checks)
python utils/test_sap_inventory.py

# Quick test of new tools only
python utils/test_new_tools.py
```

### Expected Results

If Material Document API is available:
- ✅ Goods receipts data returned
- ✅ Open orders calculated correctly
- ✅ Cross-reference shows materials with stock + open orders

If Material Document API is NOT available:
- ⚠️  "Material Document API may not be available in this SAP system"
- ✅ Other tools still work (PO listing, stock queries)
- ℹ️  User notified to contact SAP admin to enable API

---

## Lambda Handler Integration

The three new tools are registered in the lambda_handler:

```python
elif tool_name == "get_goods_receipts":
    result = get_goods_receipts(
        po_number=params.get("po_number"),
        material_number=params.get("material_number"),
        limit=int(params.get("limit", 50))
    )
elif tool_name == "get_open_purchase_orders":
    result = get_open_purchase_orders(
        limit=int(params.get("limit", 50))
    )
elif tool_name == "get_inventory_with_open_orders":
    result = get_inventory_with_open_orders(
        threshold=int(params.get("threshold", 10))
    )
```

---

## Use Cases

### 1. Daily Delivery Tracking
**Question:** "What orders are still waiting for delivery?"
**Tool:** `get_open_purchase_orders`
**Result:** List of POs with pending quantities

### 2. Warehouse Space Planning
**Question:** "What materials have stock and more coming?"
**Tool:** `get_inventory_with_open_orders`
**Result:** Materials with current stock + incoming quantities

### 3. Supplier Follow-up
**Question:** "Which suppliers have delayed deliveries?"
**Tool:** `get_open_purchase_orders` (filter by order date)
**Result:** Old open orders requiring supplier follow-up

### 4. Inventory Optimization
**Question:** "Are we overstocking any materials?"
**Tool:** `get_inventory_with_open_orders`
**Result:** Materials with high stock + large incoming orders

### 5. Goods Receipt Verification
**Question:** "What was received this week?"
**Tool:** `get_goods_receipts`
**Result:** Recent receipt documents with quantities

---

## Performance Considerations

### Optimizations Implemented

1. **Limited PO Checking:** `get_open_purchase_orders` only checks first 20 POs to avoid timeout
2. **Date Filtering:** Queries limited to last 180 days
3. **Result Limits:** Default limits prevent huge data transfers
4. **Graceful Degradation:** Falls back if Material Document API not available

### Performance Tuning

```python
# Adjust these parameters based on system performance:

# Number of POs to check for open status (default 50)
get_open_purchase_orders(limit=30)  # Faster

# Number of POs to query goods receipts for (hardcoded to 20)
# Increase in line 524 of sap_tools.py if needed:
for po in po_numbers[:20]:  # Change to [:50] for more thorough check
```

---

## Error Handling

All three tools include graceful error handling:

```python
# If Material Document API not available
if res["status"] != "success":
    return {
        "status": "partial",
        "message": "Material Document API may not be available",
        "goods_receipts": [],
        "note": "Contact SAP administrator to enable Material Document APIs"
    }
```

This ensures:
- No crashes if API unavailable
- User gets helpful error message
- Other tools continue to work

---

## Future Enhancements

### Potential Improvements

1. **Caching:** Cache goods receipt data for 15 minutes to reduce API calls
2. **Batch Processing:** Process multiple POs in parallel for faster open order checks
3. **Advanced Analytics:**
   - Supplier delivery performance (on-time delivery rate)
   - Average time from order to receipt
   - Materials with frequent shortages
4. **Alerts:** Proactive notifications for:
   - Orders open > 90 days
   - Materials with no receipts in 30 days
   - Overstocking situations

### Additional Questions to Answer

- "Which orders are overdue?" (compare order date + lead time with current date)
- "What's the average delivery time per supplier?"
- "Which materials have the highest order-to-receipt time?"

---

## Summary

The Material Document API integration successfully enables answering the three critical Hebrew questions:

1. ✅ **כמה במלאי?** → `get_material_stock`
2. ✅ **מה פתוח בהזמנות?** → `get_open_purchase_orders`
3. ✅ **מה יש לו מלאי שיש בהזמנת רכש פתוחה?** → `get_inventory_with_open_orders`

The implementation:
- Adds 3 new tools to the SAP agent
- Integrates with Material Document API for goods receipts
- Compares ordered vs received quantities
- Cross-references stock with open orders
- Provides comprehensive inventory visibility

**Next Steps:**
1. Deploy updated lambda function
2. Test with SAP demo system
3. Update AgentCore tool definitions
4. Create presentation questions using actual data

---

**Document Version:** 1.0.0
**Last Updated:** 2025-01-05
