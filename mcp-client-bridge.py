#!/usr/bin/env python3
"""
MCP Client Bridge for OrderDesk MCP Server

This script acts as a bridge between stdio-based MCP clients (like Claude Desktop)
and HTTP-based MCP servers. It reads MCP requests from stdin, forwards them to
the HTTP server, and writes responses back to stdout.

Usage:
    python3 mcp-client-bridge.py <server_url> <master_key>

Example:
    python3 mcp-client-bridge.py http://localhost:8080/mcp your-master-key-here
"""

import sys
import json
import requests
from typing import Any, Dict


def main():
    if len(sys.argv) < 3:
        print("Usage: python3 mcp-client-bridge.py <server_url> <master_key>", file=sys.stderr)
        sys.exit(1)
    
    server_url = sys.argv[1]
    master_key = sys.argv[2]
    
    # Read from stdin, send to server, write to stdout
    for line in sys.stdin:
        try:
            # Parse MCP request from stdin
            request_data = json.loads(line.strip())
            
            # Forward to HTTP server
            response = requests.post(
                server_url,
                json=request_data,
                headers={
                    "Authorization": f"Bearer {master_key}",
                    "Content-Type": "application/json"
                },
                timeout=30
            )
            
            response.raise_for_status()
            
            # Write response to stdout
            print(json.dumps(response.json()), flush=True)
            
        except json.JSONDecodeError as e:
            error_response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32700,
                    "message": f"Parse error: {str(e)}"
                },
                "id": None
            }
            print(json.dumps(error_response), flush=True)
        except requests.RequestException as e:
            error_response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Server error: {str(e)}"
                },
                "id": request_data.get("id") if 'request_data' in locals() else None
            }
            print(json.dumps(error_response), flush=True)
        except Exception as e:
            error_response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Internal error: {str(e)}"
                },
                "id": request_data.get("id") if 'request_data' in locals() else None
            }
            print(json.dumps(error_response), flush=True)


if __name__ == "__main__":
    main()

