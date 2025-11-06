#!/usr/bin/env python3
"""
Comprehensive SAP Inventory Management Test Script

This script tests all SAP inventory-related APIs to provide a complete picture:
- Material stock levels (low stock alerts)
- Purchase orders status (open/closed, goods receipt status)
- Unclosed orders and pending deliveries
- Supplier performance
- Inventory forecasting and recommendations

Not focused on specific PO numbers - provides holistic inventory view.
"""
import json
import os
import sys
from datetime import datetime, timedelta

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
    list_purchase_orders,
    search_purchase_orders,
    get_material_stock,
    get_orders_in_transit,
    get_goods_receipts,
    get_open_purchase_orders,
    get_inventory_with_open_orders
)

# Check for missing environment variables
def _missing_env():
    """Check for missing required environment variables"""
    required = ["SAP_HOST", "SAP_USER", "SAP_PASSWORD"]
    missing = [var for var in required if not os.getenv(var)]
    return missing


class InventoryHealthCheck:
    """Comprehensive inventory health check and reporting"""

    def __init__(self):
        self.results = {
            "timestamp": datetime.now().isoformat(),
            "checks": {}
        }

    def check_low_stock_materials(self, threshold=10):
        """Check for materials with low stock levels"""
        print(f"\n{'='*80}")
        print(f"CHECK 1: Low Stock Materials (threshold < {threshold} units)")
        print(f"{'='*80}")

        try:
            result = get_material_stock(low_stock_only=True, threshold=threshold)

            if result.get("status") == "success":
                stock_info = result.get("stock_info", [])
                print(f"✅ Found {len(stock_info)} materials with low stock")

                if stock_info:
                    print("\n⚠️  LOW STOCK ALERTS:")
                    for item in stock_info[:10]:  # Show first 10
                        material = item.get("Material", "N/A")
                        desc = item.get("MaterialDescription", "No description")
                        qty = item.get("AvailableQuantity", 0)
                        plant = item.get("Plant", "N/A")
                        print(f"  - {material}: {qty} units @ Plant {plant}")
                        print(f"    {desc}")
                else:
                    print("✓ All materials have sufficient stock")

                self.results["checks"]["low_stock"] = {
                    "status": "pass",
                    "low_stock_count": len(stock_info),
                    "threshold": threshold
                }
            else:
                print(f"❌ Failed: {result.get('message')}")
                self.results["checks"]["low_stock"] = {
                    "status": "fail",
                    "error": result.get("message")
                }

        except Exception as e:
            print(f"❌ Exception: {e}")
            self.results["checks"]["low_stock"] = {
                "status": "error",
                "error": str(e)
            }

    def check_material_stock_overview(self):
        """Get general material stock overview"""
        print(f"\n{'='*80}")
        print("CHECK 2: Material Stock Overview")
        print(f"{'='*80}")

        try:
            result = get_material_stock()

            if result.get("status") == "success":
                stock_info = result.get("stock_info", [])
                total_qty = result.get("total_available_quantity", 0)

                print(f"✅ Found {len(stock_info)} materials in inventory")
                print(f"📊 Total available quantity: {total_qty}")

                if stock_info:
                    print("\n📦 Top 5 Materials by Quantity:")
                    sorted_stock = sorted(stock_info, key=lambda x: x.get("AvailableQuantity", 0), reverse=True)
                    for item in sorted_stock[:5]:
                        material = item.get("Material", "N/A")
                        desc = item.get("MaterialDescription", "No description")
                        qty = item.get("AvailableQuantity", 0)
                        plant = item.get("Plant", "N/A")
                        print(f"  {material}: {qty} units @ Plant {plant}")
                        print(f"    {desc[:60]}...")

                self.results["checks"]["stock_overview"] = {
                    "status": "pass",
                    "total_materials": len(stock_info),
                    "total_quantity": total_qty
                }
            else:
                print(f"⚠️  Note: {result.get('message')}")
                self.results["checks"]["stock_overview"] = {
                    "status": "partial",
                    "message": result.get("message")
                }

        except Exception as e:
            print(f"❌ Exception: {e}")
            self.results["checks"]["stock_overview"] = {
                "status": "error",
                "error": str(e)
            }

    def check_orders_in_transit(self):
        """Check purchase orders currently in transit"""
        print(f"\n{'='*80}")
        print("CHECK 3: Orders In Transit / Pending Deliveries")
        print(f"{'='*80}")

        try:
            result = get_orders_in_transit(limit=50)

            if result.get("status") == "success":
                orders = result.get("orders_in_transit", [])
                print(f"✅ Found {len(orders)} recent orders (last 90 days)")

                if orders:
                    print("\n🚚 Recent Purchase Orders:")
                    for order in orders[:10]:  # Show first 10
                        po = order.get("PurchaseOrder", "N/A")
                        supplier = order.get("Supplier", "N/A")
                        date = order.get("PurchaseOrderDate", "N/A")
                        currency = order.get("DocumentCurrency", "N/A")
                        print(f"  PO {po} | Supplier: {supplier} | Date: {date} | Currency: {currency}")

                self.results["checks"]["orders_in_transit"] = {
                    "status": "pass",
                    "orders_count": len(orders)
                }
            else:
                print(f"❌ Failed: {result.get('message')}")
                self.results["checks"]["orders_in_transit"] = {
                    "status": "fail",
                    "error": result.get("message")
                }

        except Exception as e:
            print(f"❌ Exception: {e}")
            self.results["checks"]["orders_in_transit"] = {
                "status": "error",
                "error": str(e)
            }

    def check_supplier_orders(self, limit=30):
        """Get orders grouped by supplier"""
        print(f"\n{'='*80}")
        print("CHECK 4: Orders by Supplier")
        print(f"{'='*80}")

        try:
            result = list_purchase_orders(limit=limit)

            if result.get("status") == "success":
                orders = result.get("purchase_orders", [])

                # Group by supplier
                supplier_summary = {}
                for order in orders:
                    supplier = order.get("Supplier", "Unknown")
                    if supplier not in supplier_summary:
                        supplier_summary[supplier] = {
                            "count": 0,
                            "orders": []
                        }
                    supplier_summary[supplier]["count"] += 1
                    supplier_summary[supplier]["orders"].append(order.get("PurchaseOrder"))

                print(f"✅ Analyzed {len(orders)} orders from {len(supplier_summary)} suppliers")
                print("\n🏢 Top Suppliers by Order Count:")
                sorted_suppliers = sorted(supplier_summary.items(), key=lambda x: x[1]["count"], reverse=True)
                for supplier, data in sorted_suppliers[:5]:
                    print(f"  {supplier}: {data['count']} orders")

                self.results["checks"]["supplier_orders"] = {
                    "status": "pass",
                    "total_orders": len(orders),
                    "unique_suppliers": len(supplier_summary),
                    "top_suppliers": [s[0] for s in sorted_suppliers[:5]]
                }
            else:
                print(f"❌ Failed: {result.get('message')}")
                self.results["checks"]["supplier_orders"] = {
                    "status": "fail",
                    "error": result.get("message")
                }

        except Exception as e:
            print(f"❌ Exception: {e}")
            self.results["checks"]["supplier_orders"] = {
                "status": "error",
                "error": str(e)
            }

    def check_recent_orders_by_date(self, days_back=30):
        """Check purchase orders from recent period"""
        print(f"\n{'='*80}")
        print(f"CHECK 5: Purchase Orders from Last {days_back} Days")
        print(f"{'='*80}")

        try:
            date_from = (datetime.now() - timedelta(days=days_back)).strftime("%Y-%m-%d")
            result = list_purchase_orders(limit=100, date_from=date_from)

            if result.get("status") == "success":
                orders = result.get("purchase_orders", [])
                print(f"✅ Found {len(orders)} orders since {date_from}")

                if orders:
                    # Analyze by date
                    by_date = {}
                    for order in orders:
                        date = order.get("PurchaseOrderDate", "Unknown")
                        if date not in by_date:
                            by_date[date] = 0
                        by_date[date] += 1

                    print(f"\n📅 Orders by Date (last {min(7, len(by_date))} days):")
                    sorted_dates = sorted(by_date.items(), reverse=True)
                    for date, count in sorted_dates[:7]:
                        print(f"  {date}: {count} orders")

                self.results["checks"]["recent_orders"] = {
                    "status": "pass",
                    "orders_count": len(orders),
                    "days_back": days_back,
                    "date_from": date_from
                }
            else:
                print(f"❌ Failed: {result.get('message')}")
                self.results["checks"]["recent_orders"] = {
                    "status": "fail",
                    "error": result.get("message")
                }

        except Exception as e:
            print(f"❌ Exception: {e}")
            self.results["checks"]["recent_orders"] = {
                "status": "error",
                "error": str(e)
            }

    def check_goods_receipts(self, limit=20):
        """Check goods receipts from Material Documents API"""
        print(f"\n{'='*80}")
        print("CHECK 6: Goods Receipts (Material Documents)")
        print(f"{'='*80}")

        try:
            result = get_goods_receipts(limit=limit)

            if result.get("status") == "success":
                receipts = result.get("goods_receipts", [])
                total_qty = result.get("total_quantity_received", 0)

                print(f"✅ Found {len(receipts)} goods receipts")
                print(f"📦 Total quantity received: {total_qty}")

                if receipts:
                    print("\n📥 Recent Goods Receipts:")
                    for gr in receipts[:10]:  # Show first 10
                        material = gr.get("Material", "N/A")
                        po = gr.get("PurchaseOrder", "N/A")
                        qty = gr.get("QuantityInEntryUnit", 0)
                        date = gr.get("PostingDate", "N/A")
                        print(f"  Material: {material} | PO: {po} | Qty: {qty} | Date: {date}")

                self.results["checks"]["goods_receipts"] = {
                    "status": "pass",
                    "receipts_count": len(receipts),
                    "total_quantity": total_qty
                }
            else:
                print(f"⚠️  Note: {result.get('message')}")
                self.results["checks"]["goods_receipts"] = {
                    "status": "partial",
                    "message": result.get("message")
                }

        except Exception as e:
            print(f"❌ Exception: {e}")
            self.results["checks"]["goods_receipts"] = {
                "status": "error",
                "error": str(e)
            }

    def check_open_purchase_orders(self, limit=30):
        """Check open purchase orders (ordered > received)"""
        print(f"\n{'='*80}")
        print("CHECK 7: Open Purchase Orders (Ordered vs Received)")
        print(f"{'='*80}")

        try:
            result = get_open_purchase_orders(limit=limit)

            if result.get("status") == "success":
                open_orders = result.get("open_purchase_orders", [])
                total_open_items = result.get("total_open_items", 0)

                print(f"✅ Found {len(open_orders)} open purchase orders")
                print(f"📋 Total open items: {total_open_items}")

                if open_orders:
                    print("\n🔓 Open Purchase Orders:")
                    for order in open_orders[:10]:  # Show first 10
                        po = order.get("purchase_order", "N/A")
                        supplier = order.get("supplier", "N/A")
                        date = order.get("order_date", "N/A")
                        items_count = order.get("total_open_items", 0)
                        print(f"  PO: {po} | Supplier: {supplier} | Date: {date} | Open Items: {items_count}")

                        # Show first 3 items
                        for item in order.get("items", [])[:3]:
                            material = item.get("material", "N/A")
                            ordered = item.get("ordered_quantity", 0)
                            received = item.get("received_quantity", 0)
                            open_qty = item.get("open_quantity", 0)
                            print(f"    - {material}: Ordered={ordered}, Received={received}, Open={open_qty}")
                else:
                    print("✓ No open purchase orders found (all orders fully received)")

                self.results["checks"]["open_orders"] = {
                    "status": "pass",
                    "open_orders_count": len(open_orders),
                    "total_open_items": total_open_items
                }
            else:
                print(f"❌ Failed: {result.get('message')}")
                self.results["checks"]["open_orders"] = {
                    "status": "fail",
                    "error": result.get("message")
                }

        except Exception as e:
            print(f"❌ Exception: {e}")
            self.results["checks"]["open_orders"] = {
                "status": "error",
                "error": str(e)
            }

    def check_inventory_with_open_orders(self):
        """Check materials that have stock AND open purchase orders"""
        print(f"\n{'='*80}")
        print("CHECK 8: Inventory with Open Orders (Cross-Reference)")
        print(f"{'='*80}")

        try:
            result = get_inventory_with_open_orders()

            if result.get("status") == "success":
                inventory_items = result.get("inventory_with_open_orders", [])

                print(f"✅ Found {len(inventory_items)} materials with both stock and open orders")

                if inventory_items:
                    print("\n📦🔓 Materials with Stock AND Open Orders:")
                    for item in inventory_items[:10]:  # Show first 10
                        material = item.get("material", "N/A")
                        desc = item.get("description", "No description")
                        available = item.get("available_quantity", 0)
                        open_qty = item.get("total_open_quantity", 0)
                        orders_count = item.get("open_orders_count", 0)

                        print(f"  {material}: {desc[:40]}")
                        print(f"    Available Stock: {available}, Incoming: {open_qty} ({orders_count} orders)")
                else:
                    print("ℹ️  No materials found with both stock and open orders")

                self.results["checks"]["inventory_with_open_orders"] = {
                    "status": "pass",
                    "materials_count": len(inventory_items)
                }
            else:
                print(f"⚠️  Note: {result.get('message')}")
                self.results["checks"]["inventory_with_open_orders"] = {
                    "status": "partial",
                    "message": result.get("message")
                }

        except Exception as e:
            print(f"❌ Exception: {e}")
            self.results["checks"]["inventory_with_open_orders"] = {
                "status": "error",
                "error": str(e)
            }

    def generate_inventory_recommendations(self):
        """Generate inventory management recommendations based on checks"""
        print(f"\n{'='*80}")
        print("📋 INVENTORY MANAGEMENT RECOMMENDATIONS")
        print(f"{'='*80}\n")

        recommendations = []

        # Low stock check
        low_stock_check = self.results["checks"].get("low_stock", {})
        if low_stock_check.get("status") == "pass":
            count = low_stock_check.get("low_stock_count", 0)
            if count > 0:
                recommendations.append({
                    "priority": "HIGH",
                    "category": "Stock Replenishment",
                    "message": f"⚠️  {count} materials have low stock levels. Review and create purchase requisitions."
                })

        # Open orders check
        open_orders_check = self.results["checks"].get("open_orders", {})
        if open_orders_check.get("status") == "pass":
            count = open_orders_check.get("open_orders_count", 0)
            if count > 10:
                recommendations.append({
                    "priority": "MEDIUM",
                    "category": "Open Orders",
                    "message": f"ℹ️  {count} purchase orders are still open. Follow up with suppliers for delivery status."
                })

        # Recent orders trend
        recent_orders_check = self.results["checks"].get("recent_orders", {})
        if recent_orders_check.get("status") == "pass":
            count = recent_orders_check.get("orders_count", 0)
            days = recent_orders_check.get("days_back", 30)
            if count == 0:
                recommendations.append({
                    "priority": "MEDIUM",
                    "category": "Procurement Activity",
                    "message": f"⚠️  No purchase orders in last {days} days. Verify procurement plans."
                })

        # Supplier diversity
        supplier_check = self.results["checks"].get("supplier_orders", {})
        if supplier_check.get("status") == "pass":
            supplier_count = supplier_check.get("unique_suppliers", 0)
            if supplier_count < 3:
                recommendations.append({
                    "priority": "LOW",
                    "category": "Supplier Diversity",
                    "message": f"ℹ️  Only {supplier_count} active suppliers. Consider diversifying supplier base."
                })

        # Display recommendations
        if recommendations:
            for i, rec in enumerate(recommendations, 1):
                print(f"{i}. [{rec['priority']}] {rec['category']}")
                print(f"   {rec['message']}\n")
        else:
            print("✅ No critical recommendations at this time. Inventory health looks good!\n")

        self.results["recommendations"] = recommendations

    def print_summary(self):
        """Print final summary"""
        print(f"\n{'='*80}")
        print("📊 INVENTORY HEALTH CHECK SUMMARY")
        print(f"{'='*80}\n")

        total_checks = len(self.results["checks"])
        passed = sum(1 for c in self.results["checks"].values() if c.get("status") == "pass")
        failed = sum(1 for c in self.results["checks"].values() if c.get("status") == "fail")
        errors = sum(1 for c in self.results["checks"].values() if c.get("status") == "error")

        print(f"Total Checks: {total_checks}")
        print(f"✅ Passed: {passed}")
        print(f"❌ Failed: {failed}")
        print(f"⚠️  Errors: {errors}")
        print(f"\nTimestamp: {self.results['timestamp']}")

        # Save results to file
        output_file = "inventory_health_report.json"
        with open(output_file, 'w') as f:
            json.dump(self.results, f, indent=2)
        print(f"\n📄 Detailed report saved to: {output_file}")


def main():
    """Run comprehensive inventory health check"""
    print("\n" + "="*80)
    print("🏥 SAP INVENTORY HEALTH CHECK")
    print("="*80)
    print("\nComprehensive inventory management analysis")
    print("This check provides a complete picture of your SAP inventory:")
    print("  • Material stock levels and low stock alerts")
    print("  • Purchase orders status and trends")
    print("  • Orders in transit and pending deliveries")
    print("  • Supplier performance and diversity")
    print("  • Inventory management recommendations")

    # Check environment
    missing = _missing_env()
    if missing:
        print(f"\n❌ Missing environment variables: {', '.join(missing)}")
        print("Please set SAP_HOST, SAP_USER, and SAP_PASSWORD in .env file")
        return 1

    print(f"\n✅ Environment configured")
    print(f"SAP Host: {os.getenv('SAP_HOST')}")
    print(f"SAP User: {os.getenv('SAP_USER')}")

    # Run health check
    checker = InventoryHealthCheck()

    try:
        checker.check_low_stock_materials(threshold=10)
        checker.check_material_stock_overview()
        checker.check_orders_in_transit()
        checker.check_supplier_orders(limit=50)
        checker.check_recent_orders_by_date(days_back=30)
        checker.check_goods_receipts(limit=20)
        checker.check_open_purchase_orders(limit=30)
        checker.check_inventory_with_open_orders()
        checker.generate_inventory_recommendations()
        checker.print_summary()

        print("\n" + "="*80)
        print("✅ INVENTORY HEALTH CHECK COMPLETE")
        print("="*80 + "\n")

        return 0

    except Exception as e:
        print(f"\n❌ Fatal error during health check: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
