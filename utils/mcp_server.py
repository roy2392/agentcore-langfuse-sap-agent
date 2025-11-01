#!/usr/bin/env python3
"""
SAP MCP Server using Python MCP SDK

Implements the Model Context Protocol using the official MCP SDK to properly
expose SAP functions as tools to Bedrock AgentCore.
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

try:
    from mcp.server import Server
    from mcp.types import Tool, TextContent
except ImportError:
    logger.warning("MCP SDK not available, using fallback mode")
    Server = None


def create_sap_tools() -> List[Tool]:
    """Create Tool definitions for SAP functions using MCP SDK"""

    if Server is None:
        logger.warning("MCP SDK not available")
        return []

    return [
        Tool(
            name="get_stock_levels",
            description="Get current stock levels for a specific material",
            inputSchema={
                "type": "object",
                "properties": {
                    "material_number": {
                        "type": "string",
                        "description": "The material/product number (e.g., '100-100')"
                    }
                },
                "required": ["material_number"]
            }
        ),
        Tool(
            name="get_low_stock_materials",
            description="Get list of materials with low stock levels",
            inputSchema={
                "type": "object",
                "properties": {
                    "threshold": {
                        "type": "number",
                        "description": "Stock threshold value (optional)"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_material_info",
            description="Get detailed information about a specific material",
            inputSchema={
                "type": "object",
                "properties": {
                    "material_number": {
                        "type": "string",
                        "description": "The material/product number"
                    }
                },
                "required": ["material_number"]
            }
        ),
        Tool(
            name="get_warehouse_stock",
            description="Get warehouse stock summary for a plant and/or storage location",
            inputSchema={
                "type": "object",
                "properties": {
                    "plant": {
                        "type": "string",
                        "description": "Plant code (optional, e.g., '1000')"
                    },
                    "storage_location": {
                        "type": "string",
                        "description": "Storage location code (optional, e.g., '01')"
                    }
                },
                "required": []
            }
        ),
        Tool(
            name="get_purchase_orders_for_material",
            description="Get pending purchase orders for a specific material",
            inputSchema={
                "type": "object",
                "properties": {
                    "material_number": {
                        "type": "string",
                        "description": "The material/product number"
                    }
                },
                "required": ["material_number"]
            }
        ),
        Tool(
            name="get_goods_receipt",
            description="Get goods receipt information for a purchase order",
            inputSchema={
                "type": "object",
                "properties": {
                    "po_number": {
                        "type": "string",
                        "description": "The purchase order number (e.g., '4500000520')"
                    }
                },
                "required": ["po_number"]
            }
        ),
        Tool(
            name="forecast_material_demand",
            description="Get demand forecast for a material",
            inputSchema={
                "type": "object",
                "properties": {
                    "material_number": {
                        "type": "string",
                        "description": "The material/product number"
                    },
                    "days_ahead": {
                        "type": "number",
                        "description": "Number of days to forecast (default: 30)"
                    }
                },
                "required": ["material_number"]
            }
        ),
        Tool(
            name="get_complete_po_data",
            description="Get complete purchase order data including line items and status",
            inputSchema={
                "type": "object",
                "properties": {
                    "po_number": {
                        "type": "string",
                        "description": "The purchase order number"
                    }
                },
                "required": ["po_number"]
            }
        ),
    ]


def execute_sap_tool(tool_name: str, tool_input: Dict[str, Any]) -> Dict[str, Any]:
    """Execute a SAP tool and return results"""

    try:
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


async def run_server():
    """Run the MCP server"""

    if Server is None:
        logger.error("MCP SDK not available")
        sys.exit(1)

    server = Server("sap-mcp-server")

    # Register tools
    @server.list_tools()
    async def list_tools():
        """Return list of available tools"""
        return create_sap_tools()

    @server.call_tool()
    async def call_tool(name: str, arguments: Dict[str, Any]) -> List[TextContent]:
        """Execute a tool"""
        logger.info(f"Executing tool: {name} with arguments: {arguments}")

        result = execute_sap_tool(name, arguments)

        logger.info(f"Tool result: {json.dumps(result, indent=2)[:500]}")

        return [TextContent(type="text", text=json.dumps(result))]

    async with server:
        logger.info("SAP MCP Server started")
        await server.wait()


if __name__ == "__main__":
    import asyncio

    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server stopped")
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)
