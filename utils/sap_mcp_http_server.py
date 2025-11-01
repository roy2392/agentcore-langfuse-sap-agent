#!/usr/bin/env python3
"""
SAP MCP HTTP Server

Provides HTTP server interface for SAP MCP Server to expose Model Context Protocol endpoints.
This allows the Strands agent to connect to the SAP MCP server via HTTP.

The server exposes:
- GET /mcp/tools - List available tools
- POST /mcp/tool/execute - Execute a tool call
- GET /health - Health check endpoint
"""

import json
import sys
import os
import logging
from typing import Any, Dict
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import threading

# Fix import path - handle both module and direct execution
if __name__ != '__main__':
    from .sap_mcp_server import SAPMCPServer, list_tools, handle_tool_call
else:
    from sap_mcp_server import SAPMCPServer, list_tools, handle_tool_call

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class SAPMCPHTTPHandler(BaseHTTPRequestHandler):
    """HTTP Request handler for SAP MCP Server"""

    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        logger.info(f"GET {path}")

        if path == '/health' or path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'status': 'healthy', 'service': 'SAP MCP Server'}
            self.wfile.write(json.dumps(response).encode())

        elif path == '/mcp' or path == '/mcp/':
            # MCP server info endpoint
            try:
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                response = {
                    'name': 'SAP MCP Server',
                    'version': '1.0',
                    'capabilities': {
                        'tools': True
                    }
                }
                self.wfile.write(json.dumps(response).encode())
            except Exception as e:
                logger.error(f"Error: {str(e)}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_response = {'error': str(e)}
                self.wfile.write(json.dumps(error_response).encode())

        elif path == '/mcp/tools':
            try:
                tools_data = list_tools()
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(tools_data).encode())
            except Exception as e:
                logger.error(f"Error listing tools: {str(e)}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_response = {'error': str(e)}
                self.wfile.write(json.dumps(error_response).encode())

        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'error': 'Not found'}
            self.wfile.write(json.dumps(response).encode())

    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        logger.info(f"POST {path}")

        # Read request body
        content_length = int(self.headers.get('Content-Length', 0))
        request_body = self.rfile.read(content_length)

        try:
            request_data = json.loads(request_body.decode('utf-8'))
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in request: {str(e)}")
            self.send_response(400)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            error_response = {'error': 'Invalid JSON'}
            self.wfile.write(json.dumps(error_response).encode())
            return

        if path == '/mcp/tool/execute':
            try:
                result = handle_tool_call(request_data)
                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(result).encode())
            except Exception as e:
                logger.error(f"Error executing tool: {str(e)}")
                self.send_response(500)
                self.send_header('Content-type', 'application/json')
                self.end_headers()
                error_response = {'error': str(e)}
                self.wfile.write(json.dumps(error_response).encode())

        else:
            self.send_response(404)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            response = {'error': 'Not found'}
            self.wfile.write(json.dumps(response).encode())

    def log_message(self, format, *args):
        """Override logging to use our logger"""
        logger.info("%s - - [%s] %s\n" % (self.client_address[0], self.log_date_time_string(), format % args))


class SAPMCPHTTPServer:
    """SAP MCP HTTP Server wrapper"""

    def __init__(self, host: str = '0.0.0.0', port: int = 8000):
        """Initialize the HTTP server

        Args:
            host: Host to listen on (default: 0.0.0.0)
            port: Port to listen on (default: 8000)
        """
        self.host = host
        self.port = port
        self.server = None
        self.thread = None

    def start(self):
        """Start the HTTP server"""
        logger.info(f"Starting SAP MCP HTTP Server on {self.host}:{self.port}")

        self.server = HTTPServer((self.host, self.port), SAPMCPHTTPHandler)

        # Run server in background thread
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

        logger.info("SAP MCP HTTP Server started successfully")

    def stop(self):
        """Stop the HTTP server"""
        if self.server:
            logger.info("Stopping SAP MCP HTTP Server")
            self.server.shutdown()
            self.server.server_close()

    def wait(self):
        """Wait for server thread to finish"""
        if self.thread:
            self.thread.join()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="SAP MCP HTTP Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to listen on (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Port to listen on (default: 8000)")

    args = parser.parse_args()

    server = SAPMCPHTTPServer(host=args.host, port=args.port)

    try:
        server.start()
        logger.info(f"Server is running on http://{args.host}:{args.port}")
        logger.info("Press Ctrl+C to stop the server")
        server.wait()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.stop()
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        sys.exit(1)
