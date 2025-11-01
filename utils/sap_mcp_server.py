#!/usr/bin/env python3
"""
SAP MCP Server

Implements the Model Context Protocol (MCP) for exposing SAP OData API functions
as tools that can be used by Bedrock AgentCore.

This server provides inventory management capabilities through SAP integration.
"""

import json
import sys
import os
import logging
from typing import Any, Dict, List

# Fix import path - handle both module and direct execution
if __name__ != '__main__':
    from .test_sap_api import (
        get_stock_levels,
        get_low_stock_materials,
        get_material_info,
        get_warehouse_stock,
        get_purchase_orders_for_material,
        get_goods_receipt,
        forecast_material_demand,
        get_complete_po_data,
        _missing_env
    )
else:
    from test_sap_api import (
        get_stock_levels,
        get_low_stock_materials,
        get_material_info,
        get_warehouse_stock,
        get_purchase_orders_for_material,
        get_goods_receipt,
        forecast_material_demand,
        get_complete_po_data,
        _missing_env
    )

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# MCP Server Implementation
class SAPMCPServer:
    """SAP MCP Server that exposes inventory functions as tools"""

    def __init__(self):
        self.tools = self._define_tools()

    def _define_tools(self) -> List[Dict[str, Any]]:
        """Define all available SAP tools"""
        return [
            {
                "name": "get_stock_levels",
                "description": "Get current stock levels for a specific material",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "material_number": {
                            "type": "string",
                            "description": "The material/product number (e.g., '100-100')"
                        }
                    },
                    "required": ["material_number"]
                }
            },
            {
                "name": "get_low_stock_materials",
                "description": "Get list of materials with low stock levels",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "threshold": {
                            "type": "number",
                            "description": "Stock threshold value (optional)",
                            "default": None
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "get_material_info",
                "description": "Get detailed information about a specific material",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "material_number": {
                            "type": "string",
                            "description": "The material/product number"
                        }
                    },
                    "required": ["material_number"]
                }
            },
            {
                "name": "get_warehouse_stock",
                "description": "Get warehouse stock summary for a plant and/or storage location",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "plant": {
                            "type": "string",
                            "description": "Plant code (optional, e.g., '1000')",
                            "default": None
                        },
                        "storage_location": {
                            "type": "string",
                            "description": "Storage location code (optional, e.g., '01')",
                            "default": None
                        }
                    },
                    "required": []
                }
            },
            {
                "name": "get_purchase_orders_for_material",
                "description": "Get pending purchase orders for a specific material",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "material_number": {
                            "type": "string",
                            "description": "The material/product number"
                        }
                    },
                    "required": ["material_number"]
                }
            },
            {
                "name": "get_goods_receipt",
                "description": "Get goods receipt information for a purchase order",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "po_number": {
                            "type": "string",
                            "description": "The purchase order number (e.g., '4500000520')"
                        }
                    },
                    "required": ["po_number"]
                }
            },
            {
                "name": "forecast_material_demand",
                "description": "Get demand forecast for a material",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "material_number": {
                            "type": "string",
                            "description": "The material/product number"
                        },
                        "days_ahead": {
                            "type": "integer",
                            "description": "Number of days to forecast ahead (default: 30)",
                            "default": 30
                        }
                    },
                    "required": ["material_number"]
                }
            },
            {
                "name": "get_complete_po_data",
                "description": "Get complete purchase order data including header and items",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "po_number": {
                            "type": "string",
                            "description": "The purchase order number"
                        }
                    },
                    "required": ["po_number"]
                }
            }
        ]

    def execute_tool(self, tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a SAP tool"""
        try:
            # Check if SAP credentials are available
            missing = _missing_env()
            if missing:
                return {
                    "status": "error",
                    "message": f"Missing SAP credentials: {', '.join(missing)}",
                    "tool": tool_name
                }

            if tool_name == "get_stock_levels":
                return get_stock_levels(tool_input["material_number"])
            elif tool_name == "get_low_stock_materials":
                threshold = tool_input.get("threshold")
                return get_low_stock_materials(threshold)
            elif tool_name == "get_material_info":
                return get_material_info(tool_input["material_number"])
            elif tool_name == "get_warehouse_stock":
                plant = tool_input.get("plant")
                storage_location = tool_input.get("storage_location")
                return get_warehouse_stock(plant, storage_location)
            elif tool_name == "get_purchase_orders_for_material":
                return get_purchase_orders_for_material(tool_input["material_number"])
            elif tool_name == "get_goods_receipt":
                return get_goods_receipt(tool_input["po_number"])
            elif tool_name == "forecast_material_demand":
                material_number = tool_input["material_number"]
                days_ahead = tool_input.get("days_ahead", 30)
                return forecast_material_demand(material_number, days_ahead)
            elif tool_name == "get_complete_po_data":
                return get_complete_po_data(tool_input["po_number"])
            else:
                return {
                    "status": "error",
                    "message": f"Unknown tool: {tool_name}"
                }
        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {str(e)}")
            return {
                "status": "error",
                "message": str(e),
                "tool": tool_name
            }

def handle_tool_call(request: Dict[str, Any]) -> Dict[str, Any]:
    """Handle MCP tool call request"""
    server = SAPMCPServer()
    tool_name = request.get("tool")
    tool_input = request.get("input", {})

    logger.info(f"Executing tool: {tool_name} with input: {tool_input}")
    result = server.execute_tool(tool_name, tool_input)
    logger.info(f"Tool result: {json.dumps(result, indent=2)[:500]}")

    return {
        "tool": tool_name,
        "result": result
    }

def list_tools() -> Dict[str, Any]:
    """Return list of available tools"""
    server = SAPMCPServer()
    return {
        "tools": server.tools
    }

if __name__ == "__main__":
    # Simple test/debug mode
    import argparse

    parser = argparse.ArgumentParser(description="SAP MCP Server")
    parser.add_argument("--list-tools", action="store_true", help="List available tools")
    parser.add_argument("--test-tool", type=str, help="Test a specific tool")
    parser.add_argument("--input", type=str, help="JSON input for the tool")

    args = parser.parse_args()

    if args.list_tools:
        print(json.dumps(list_tools(), indent=2))
    elif args.test_tool:
        if not args.input:
            print("Error: --input is required when using --test-tool")
            sys.exit(1)
        try:
            tool_input = json.loads(args.input)
            result = handle_tool_call({"tool": args.test_tool, "input": tool_input})
            print(json.dumps(result, indent=2))
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON input: {e}")
            sys.exit(1)
    else:
        print("SAP MCP Server - Usage:")
        print("  --list-tools              List all available tools")
        print("  --test-tool NAME          Test a specific tool")
        print("  --input JSON              Provide input as JSON")
        print("\nExample:")
        print("  python sap_mcp_server.py --test-tool get_stock_levels --input '{\"material_number\": \"100-100\"}'")
