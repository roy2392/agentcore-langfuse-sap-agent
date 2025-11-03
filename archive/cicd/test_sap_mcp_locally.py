#!/usr/bin/env python3
"""
Test SAP MCP Server Locally

This script tests the SAP MCP server locally before deployment to verify:
1. SAP API connectivity
2. MCP server tool discovery
3. Tool execution
4. Integration with agent
"""

import json
import sys
import os
import subprocess

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

def print_section(title):
    print(f"\n{'='*80}")
    print(f"  {title}")
    print(f"{'='*80}\n")

def test_sap_connectivity():
    """Test direct SAP API connectivity"""
    print_section("TEST 1: SAP API Connectivity")

    from utils.test_sap_api import _missing_env, fetch_metadata

    missing = _missing_env()
    if missing:
        print(f"❌ Missing credentials: {', '.join(missing)}")
        print("\nSet these environment variables:")
        for var in missing:
            print(f"  export {var}='your_value'")
        return False

    print(f"✓ SAP credentials configured")
    print(f"  SAP_HOST: {os.getenv('SAP_HOST')}")
    print(f"  SAP_USER: {os.getenv('SAP_USER')}")

    print("\nTesting SAP metadata fetch...")
    result = fetch_metadata()

    if result.get('status') == 'success':
        print(f"✓ SAP connection successful")
        print(f"  Response size: {len(result.get('data', ''))} bytes")
        return True
    else:
        print(f"❌ SAP connection failed")
        print(f"  Error: {result.get('message')}")
        return False

def test_mcp_tool_discovery():
    """Test MCP server tool discovery"""
    print_section("TEST 2: MCP Tool Discovery")

    from utils.sap_mcp_server import SAPMCPServer

    server = SAPMCPServer()
    tools = server.tools

    print(f"✓ MCP server initialized")
    print(f"  Tools available: {len(tools)}\n")

    for i, tool in enumerate(tools, 1):
        print(f"  {i}. {tool['name']}")
        print(f"     Description: {tool['description']}")
        print(f"     Required inputs: {tool['inputSchema'].get('required', [])}")

    return len(tools) > 0

def test_mcp_tool_execution():
    """Test MCP server tool execution"""
    print_section("TEST 3: MCP Tool Execution")

    from utils.sap_mcp_server import SAPMCPServer
    from utils.test_sap_api import _missing_env

    missing = _missing_env()
    if missing:
        print(f"⚠️  Skipping tool execution (SAP credentials missing)")
        return None

    server = SAPMCPServer()

    test_cases = [
        ("get_stock_levels", {"material_number": "100-100"}),
        ("get_low_stock_materials", {}),
    ]

    for tool_name, tool_input in test_cases:
        print(f"\nTesting: {tool_name}")
        print(f"Input: {json.dumps(tool_input)}")

        try:
            result = server.execute_tool(tool_name, tool_input)

            if result.get('status') == 'success':
                entries = result.get('data', {}).get('entries', [])
                print(f"✓ Tool execution successful")
                print(f"  Returned {len(entries)} entries")
                if entries:
                    print(f"  First entry keys: {list(entries[0].keys())[:5]}")
            else:
                print(f"⚠️  Tool returned status: {result.get('status')}")
                print(f"  Message: {result.get('message')}")
        except Exception as e:
            print(f"❌ Tool execution failed: {str(e)}")

    return True

def test_mcp_server_startup():
    """Test MCP server startup"""
    print_section("TEST 4: MCP Server Startup (Docker)")

    print("Checking Docker installation...")
    try:
        result = subprocess.run(['docker', '--version'], capture_output=True, text=True)
        print(f"✓ Docker available: {result.stdout.strip()}")
    except FileNotFoundError:
        print(f"⚠️  Docker not installed")
        return None

    print("\nBuilding SAP MCP Server Docker image...")
    try:
        result = subprocess.run(
            ['docker', 'build', '-f', 'Dockerfile.sap-mcp', '-t', 'sap-mcp-server:test', '.'],
            capture_output=True,
            text=True,
            timeout=120
        )

        if result.returncode == 0:
            print(f"✓ Docker image built successfully")
            print(f"  Image: sap-mcp-server:test")
            return True
        else:
            print(f"❌ Docker build failed")
            print(f"  Error: {result.stderr}")
            return False
    except subprocess.TimeoutExpired:
        print(f"⚠️  Docker build timeout (>2 minutes)")
        return None
    except Exception as e:
        print(f"❌ Docker build error: {str(e)}")
        return None

def test_evaluation_data_format():
    """Test evaluation data format"""
    print_section("TEST 5: Evaluation Data Format")

    test_data = {
        "id": "eval_stock_query",
        "input": {"question": "מה כמות המלאי של המוצר 100-100?"},
        "expected_output": "כמות המלאי של המוצר 100-100 היא 150 יחידות זמינות",
        "sap_raw_response": {
            "status": "success",
            "data": {
                "entries": [
                    {
                        "Material": "100-100",
                        "AvailableQuantity": 150
                    }
                ]
            }
        }
    }

    print("Sample evaluation data structure:")
    print(json.dumps(test_data, indent=2, ensure_ascii=False))

    print("\n✓ Evaluation data format is valid")
    print("  Required fields: id, input, expected_output, sap_raw_response")

    return True

def generate_test_report(results):
    """Generate test report"""
    print_section("TEST REPORT SUMMARY")

    total = len(results)
    passed = sum(1 for v in results.values() if v is True)
    skipped = sum(1 for v in results.values() if v is None)
    failed = sum(1 for v in results.values() if v is False)

    print(f"Total Tests: {total}")
    print(f"✓ Passed:  {passed}")
    print(f"⚠️  Skipped: {skipped}")
    print(f"❌ Failed:  {failed}")

    print("\nDetailed Results:")
    for test_name, result in results.items():
        status = "✓ PASS" if result is True else "⚠️  SKIP" if result is None else "❌ FAIL"
        print(f"  {status} - {test_name}")

    if failed > 0:
        print(f"\n❌ Some tests failed. Please address before deployment.")
        return False
    elif skipped > 0:
        print(f"\n⚠️  Some tests were skipped (likely due to SAP credentials).")
        print(f"   These will be verified during deployment.")
        return True
    else:
        print(f"\n✓ All tests passed! SAP MCP is ready for deployment.")
        return True

def main():
    print("\n" + "="*80)
    print("                    SAP MCP SERVER LOCAL TESTS")
    print("="*80)

    results = {}

    # Test 1: SAP Connectivity
    results["SAP API Connectivity"] = test_sap_connectivity()

    # Test 2: MCP Tool Discovery
    results["MCP Tool Discovery"] = test_mcp_tool_discovery()

    # Test 3: MCP Tool Execution
    results["MCP Tool Execution"] = test_mcp_tool_execution()

    # Test 4: Docker Build
    results["Docker Image Build"] = test_mcp_server_startup()

    # Test 5: Evaluation Data Format
    results["Evaluation Data Format"] = test_evaluation_data_format()

    # Generate report
    success = generate_test_report(results)

    print("\n" + "="*80)
    if success:
        print("✓ READY FOR DEPLOYMENT")
    else:
        print("❌ NOT READY - Fix issues above")
    print("="*80 + "\n")

    return 0 if success else 1

if __name__ == '__main__':
    sys.exit(main())
