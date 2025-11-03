#!/usr/bin/env python3
"""
SAP MCP HTTP Server - AgentCore Gateway Compatible

Implements streamable-HTTP MCP server for AWS Bedrock AgentCore Gateway.
Follows AWS best practices:
- Stateless streamable-HTTP protocol
- Available at 0.0.0.0:8000/mcp
- Supports Mcp-Session-Id header for session continuity
- Compatible with AgentCore Gateway MCP targets

The server exposes:
- POST /mcp - MCP protocol endpoint (tools list, tool execution)
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
        """Handle POST requests - MCP Protocol"""
        parsed_path = urlparse(self.path)
        path = parsed_path.path

        # Extract session ID from headers (AgentCore Gateway adds this)
        session_id = self.headers.get('Mcp-Session-Id', 'default')
        logger.info(f"POST {path} [session: {session_id}]")

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

        # MCP Protocol endpoint - handles both list tools and call tool
        if path == '/mcp' or path == '/mcp/':
            try:
                method = request_data.get('method')

                if method == 'tools/list':
                    # List available tools
                    tools_data = list_tools()
                    response = {
                        'tools': tools_data.get('tools', [])
                    }

                elif method == 'tools/call':
                    # Execute a tool
                    params = request_data.get('params', {})
                    tool_name = params.get('name')
                    tool_input = params.get('arguments', {})

                    result = handle_tool_call({
                        'tool': tool_name,
                        'input': tool_input
                    })

                    response = {
                        'content': [
                            {
                                'type': 'text',
                                'text': json.dumps(result.get('result', {}), ensure_ascii=False)
                            }
                        ]
                    }
                else:
                    self.send_response(400)
                    self.send_header('Content-type', 'application/json')
                    self.end_headers()
                    error_response = {'error': f'Unknown method: {method}'}
                    self.wfile.write(json.dumps(error_response).encode())
                    return

                self.send_response(200)
                self.send_header('Content-type', 'application/json')
                self.send_header('Mcp-Session-Id', session_id)
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())

            except Exception as e:
                logger.error(f"Error handling MCP request: {str(e)}")
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
