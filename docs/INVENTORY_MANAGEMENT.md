# SAP Inventory Management - Complete Guide

This document describes the comprehensive inventory management capabilities of the SAP Agent, going beyond single purchase order queries to provide a holistic view of your SAP inventory.

---

## 🎯 Overview

The SAP Agent provides **complete inventory visibility** across multiple dimensions:

1. **Material Stock Levels** - Real-time inventory quantities and alerts
2. **Purchase Orders** - Open orders, pending deliveries, order history
3. **Supplier Performance** - Order patterns and supplier diversity
4. **Inventory Health** - Low stock alerts and replenishment recommendations
5. **Forecasting & Planning** - Demand patterns and procurement insights

---

## 📊 Key Capabilities

### 1. Material Stock Management

#### Check All Material Stock Levels
```
Hebrew: מה מצב המלאי של כל החומרים?
English: What is the stock status of all materials?
```

**Returns:**
- Complete list of materials in inventory
- Available quantities per material
- Plant and storage location information
- Total inventory value

#### Low Stock Alerts
```
Hebrew: אילו פריטים יש להם מלאי נמוך?
English: Which items have low stock?

Hebrew: תראה לי חומרים עם פחות מ-10 יחידות
English: Show me materials with less than 10 units
```

**Returns:**
- Materials below stock threshold
- Current quantities and locations
- Recommended reorder quantities

#### Specific Material Stock
```
Hebrew: כמה יחידות יש במלאי של חומר MZ-RM-C990-01?
English: How many units are in stock for material MZ-RM-C990-01?
```

**Returns:**
- Specific material quantities
- Distribution across plants/warehouses
- On-hand vs. available quantities

---

### 2. Purchase Order Management

#### Recent Purchase Orders
```
Hebrew: הצג את כל ההזמנות מ-30 הימים האחרונים
English: Show all orders from the last 30 days

Hebrew: מה ההזמנות מחודש מרץ 2024?
English: What orders are from March 2024?
```

**Returns:**
- Orders within date range
- Order dates and values
- Supplier information
- Order trends and patterns

#### Orders by Supplier
```
Hebrew: מה ההזמנות מהספק USSU-VSF08?
English: What orders are from supplier USSU-VSF08?

Hebrew: תן לי סיכום של כל הספקים שלנו
English: Give me a summary of all our suppliers
```

**Returns:**
- Orders grouped by supplier
- Supplier order frequency
- Total spend per supplier
- Supplier diversity metrics

#### Orders In Transit
```
Hebrew: אילו הזמנות בדרך?
English: Which orders are in transit?

Hebrew: מה המשלוחים שממתינים?
English: What shipments are pending?
```

**Returns:**
- Recent orders (last 90 days)
- Expected delivery dates
- Order status and tracking
- Pending deliveries

---

### 3. Inventory Health Analysis

#### Comprehensive Health Check
```
Hebrew: תן לי דוח מלא על מצב המלאי
English: Give me a complete inventory status report

Hebrew: בדוק את בריאות המלאי שלנו
English: Check our inventory health
```

**Analyzes:**
- Low stock materials requiring attention
- Recent procurement activity trends
- Supplier diversity and concentration
- Order fulfillment patterns
- Inventory turnover metrics

#### Reorder Recommendations
```
Hebrew: מה צריך להזמין מחדש?
English: What needs to be reordered?

Hebrew: תן לי המלצות לניהול המלאי
English: Give me inventory management recommendations
```

**Provides:**
- Materials requiring immediate reorder
- Recommended order quantities
- Supplier suggestions
- Priority rankings (HIGH/MEDIUM/LOW)

---

## 🔧 Testing & Validation

### Inventory Health Check Script

Run comprehensive inventory analysis:

```bash
python utils/test_sap_inventory.py
```

**This script performs:**

1. **Low Stock Materials Check**
   - Identifies materials below threshold
   - Shows quantities and locations
   - Generates reorder alerts

2. **Material Stock Overview**
   - Lists all materials in inventory
   - Calculates total available quantities
   - Shows top materials by quantity

3. **Orders In Transit**
   - Recent purchase orders (last 90 days)
   - Pending deliveries
   - Supplier breakdown

4. **Supplier Analysis**
   - Orders grouped by supplier
   - Top suppliers by order count
   - Supplier concentration metrics

5. **Recent Orders Trend**
   - Orders from last 30 days
   - Daily order patterns
   - Procurement activity trends

6. **Inventory Recommendations**
   - Automated analysis of health checks
   - Prioritized action items
   - Stock replenishment suggestions

**Output:**
- Console summary with visual indicators (✅ ❌ ⚠️)
- Detailed JSON report: `inventory_health_report.json`
- Recommendations with priority levels

---

## 📋 SAP API Endpoints Used

The agent integrates with multiple SAP OData APIs:

### Material Stock Service
- **Service:** `API_MATERIAL_STOCK_SRV`
- **Entity:** `A_MaterialStock`
- **Purpose:** Real-time inventory quantities

**Key Fields:**
- `Material` - Material number
- `Plant` - Plant code
- `StorageLocation` - Storage location
- `AvailableQuantity` - Available quantity
- `QuantityOnHand` - Physical quantity
- `BaseUnit` - Unit of measure
- `MaterialDescription` - Material description

### Purchase Order Service
- **Service:** `C_PURCHASEORDER_FS_SRV`
- **Entities:** `I_PurchaseOrder`, `I_PurchaseOrderItem`
- **Purpose:** Purchase order header and line items

**Key Fields (Header):**
- `PurchaseOrder` - PO number
- `Supplier` - Supplier code
- `PurchasingOrganization` - Purchasing org
- `PurchaseOrderDate` - Order date
- `DocumentCurrency` - Currency

**Key Fields (Items):**
- `PurchaseOrderItem` - Line item number
- `Material` - Material number
- `OrderQuantity` - Ordered quantity
- `NetAmount` - Net value
- `PurchaseOrderItemText` - Item description

---

## 🎯 Use Cases

### 1. Daily Inventory Review
**Scenario:** Start-of-day inventory check

**Questions:**
```
Hebrew: תן לי דוח יומי על המלאי
English: Give me a daily inventory report
```

**Includes:**
- Low stock alerts
- Yesterday's receipts
- Today's expected deliveries
- Critical shortages

### 2. Procurement Planning
**Scenario:** Weekly procurement review

**Questions:**
```
Hebrew: מה הזמנו בשבוע האחרון?
English: What did we order last week?

Hebrew: אילו חומרים צריך להזמין?
English: Which materials need to be ordered?
```

**Provides:**
- Recent order history
- Materials below reorder point
- Supplier recommendations
- Budget impact

### 3. Supplier Performance Review
**Scenario:** Monthly supplier analysis

**Questions:**
```
Hebrew: מי הספקים המובילים שלנו?
English: Who are our top suppliers?

Hebrew: כמה הזמנו מכל ספק?
English: How much did we order from each supplier?
```

**Shows:**
- Orders per supplier
- Total spend by supplier
- Delivery performance
- Supplier diversity metrics

### 4. Stock Shortage Response
**Scenario:** Production planning needs material availability

**Questions:**
```
Hebrew: האם יש מלאי של חומר X?
English: Is there stock of material X?

Hebrew: מתי אפשר לקבל עוד יחידות?
English: When can we get more units?
```

**Answers:**
- Current availability
- Pending PO quantities
- Expected delivery dates
- Alternative materials

### 5. Financial Reporting
**Scenario:** Month-end inventory valuation

**Questions:**
```
Hebrew: מה ערך המלאי הכולל?
English: What is the total inventory value?

Hebrew: כמה הוצאנו על רכש החודש?
English: How much did we spend on procurement this month?
```

**Calculates:**
- Total inventory value
- Monthly procurement spend
- Inventory turnover
- Carrying costs

---

## 🔐 Security & Access

### Required SAP Permissions

To use inventory management features, users need:

**Read Access:**
- Material Master (`MM01`)
- Material Stock (`MB52`, `MB53`)
- Purchase Orders (`ME23N`)
- Goods Receipt (`MIGO`)

**OData Services:**
- `API_MATERIAL_STOCK_SRV`
- `C_PURCHASEORDER_FS_SRV`
- `API_SUPPLIERINVOICE_PROCESS_SRV` (optional)

### Environment Configuration

Set in `.env` file:
```bash
SAP_HOST=your-sap-system.com
SAP_USER=your_username
SAP_PASSWORD=your_password
```

**Security Best Practices:**
- Use service accounts with minimal required permissions
- Rotate passwords regularly
- Store credentials in AWS Secrets Manager (production)
- Enable audit logging for all queries

---

## 📈 Performance Optimization

### Query Optimization

1. **Use Filters:** Always specify filters when possible
   ```
   Good: "Show materials with low stock"
   Less efficient: "Show all materials" (then filter manually)
   ```

2. **Limit Results:** Use reasonable limits for large datasets
   ```
   Good: "Show top 50 orders"
   Less efficient: "Show all orders" (thousands of records)
   ```

3. **Date Ranges:** Specify date ranges to reduce data volume
   ```
   Good: "Orders from last 30 days"
   Less efficient: "All historical orders"
   ```

### Caching Strategy

- **Material Master:** Cache for 1 hour (static data)
- **Stock Levels:** Cache for 5 minutes (changes frequently)
- **Purchase Orders:** Cache for 15 minutes (moderate changes)
- **Supplier Data:** Cache for 24 hours (rarely changes)

---

## 🚀 Advanced Features

### Multi-Plant Inventory

Query stock across multiple plants:
```
Hebrew: מה המלאי של חומר X בכל המפעלים?
English: What is the stock of material X across all plants?
```

### Material Substitution

Find alternative materials:
```
Hebrew: מה החומרים החלופיים ל-Y?
English: What are the alternative materials for Y?
```

### Batch Tracking

Track material batches:
```
Hebrew: מה הסטטוס של אצווה Z?
English: What is the status of batch Z?
```

### Forecast & Planning

Future demand analysis:
```
Hebrew: מה הביקוש הצפוי לחודש הבא?
English: What is the expected demand for next month?
```

---

## 📚 Related Documentation

- [Example Questions](EXAMPLE_QUESTIONS.md) - Sample queries for each tool
- [Architecture](ARCHITECTURE.md) - System design and data flow
- [API Reference](../lambda_functions/sap_tools.py) - Tool implementations
- [Testing Guide](E2E_TEST_GUIDE.md) - End-to-end testing procedures

---

## 🐛 Troubleshooting

### Common Issues

**Issue:** "No stock data returned"
**Solution:** Check SAP_MATERIAL_STOCK_SRV is enabled in your SAP system

**Issue:** "Permission denied for material queries"
**Solution:** Ensure user has `S_TCODE` authorization for `MB52`, `MB53`

**Issue:** "Slow query performance"
**Solution:** Add date filters and reduce result limits

**Issue:** "Low stock threshold not working"
**Solution:** Verify threshold parameter is numeric, not string

---

## 📞 Support

For issues or questions:
1. Check [Troubleshooting](#troubleshooting) section
2. Review SAP API documentation
3. Test with `utils/test_sap_inventory.py`
4. Check CloudWatch logs for detailed errors

---

**Last Updated:** 2025-01-05
**Version:** 1.0.0
