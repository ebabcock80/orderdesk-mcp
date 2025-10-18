#!/bin/bash

# Test all MCP endpoints
BASE_URL="http://localhost:8080"
MASTER_KEY="dev-admin-master-key-change-in-production-VNS09qKDdt"

TESTS_PASSED=0
TESTS_FAILED=0

log_test() {
    local name="$1"
    local passed="$2"
    local details="$3"
    
    if [ "$passed" = "true" ]; then
        echo "✅ PASS: $name"
        ((TESTS_PASSED++))
    else
        echo "❌ FAIL: $name"
        ((TESTS_FAILED++))
    fi
    
    if [ -n "$details" ]; then
        echo "  $details"
    fi
}

echo "============================================================"
echo "Testing MCP Endpoints"
echo "============================================================"
echo

# Test initialize
echo "📋 Core MCP Protocol:"
RESPONSE=$(curl -s -X POST "${BASE_URL}/mcp?token=${MASTER_KEY}" \
    -H "Content-Type: application/json" \
    -d '{
        "jsonrpc": "2.0",
        "id": 0,
        "method": "initialize",
        "params": {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {"name": "test-client", "version": "1.0.0"}
        }
    }')

if echo "$RESPONSE" | grep -q '"capabilities"'; then
    log_test "initialize" "true" "Server capabilities returned"
else
    log_test "initialize" "false" "Missing capabilities in response"
fi

# Test tools/list
RESPONSE=$(curl -s -X POST "${BASE_URL}/mcp?token=${MASTER_KEY}" \
    -H "Content-Type: application/json" \
    -d '{
        "jsonrpc": "2.0",
        "id": 1,
        "method": "tools/list",
        "params": {}
    }')

TOOL_COUNT=$(echo "$RESPONSE" | grep -o '"name"' | wc -l | tr -d ' ')
if [ "$TOOL_COUNT" -ge 10 ]; then
    log_test "tools/list" "true" "Found $TOOL_COUNT tools"
else
    log_test "tools/list" "false" "Found only $TOOL_COUNT tools, expected >= 10"
fi

# Test prompts/list
RESPONSE=$(curl -s -X POST "${BASE_URL}/mcp?token=${MASTER_KEY}" \
    -H "Content-Type: application/json" \
    -d '{
        "jsonrpc": "2.0",
        "id": 2,
        "method": "prompts/list",
        "params": {}
    }')

if echo "$RESPONSE" | grep -q '"prompts"'; then
    log_test "prompts/list" "true" "Prompts list returned"
else
    log_test "prompts/list" "false" "Missing prompts in response"
fi

# Test resources/list
RESPONSE=$(curl -s -X POST "${BASE_URL}/mcp?token=${MASTER_KEY}" \
    -H "Content-Type: application/json" \
    -d '{
        "jsonrpc": "2.0",
        "id": 3,
        "method": "resources/list",
        "params": {}
    }')

if echo "$RESPONSE" | grep -q '"resources"'; then
    log_test "resources/list" "true" "Resources list returned"
else
    log_test "resources/list" "false" "Missing resources in response"
fi

echo

# Test store tools
echo "🏪 Store Tools:"
RESPONSE=$(curl -s -X POST "${BASE_URL}/mcp?token=${MASTER_KEY}" \
    -H "Content-Type: application/json" \
    -d '{
        "jsonrpc": "2.0",
        "id": 4,
        "method": "tools/call",
        "params": {
            "name": "stores_list",
            "arguments": {}
        }
    }')

if echo "$RESPONSE" | grep -q '"content"'; then
    log_test "stores_list" "true" "Content returned"
else
    log_test "stores_list" "false" "Missing content: $RESPONSE"
fi

echo

# Test order tools
echo "📦 Order Tools:"
RESPONSE=$(curl -s -X POST "${BASE_URL}/mcp?token=${MASTER_KEY}" \
    -H "Content-Type: application/json" \
    -d '{
        "jsonrpc": "2.0",
        "id": 5,
        "method": "tools/call",
        "params": {
            "name": "orders_list",
            "arguments": {
                "store_identifier": "DR",
                "limit": 5
            }
        }
    }')

if echo "$RESPONSE" | grep -q '"content"' && ! echo "$RESPONSE" | grep -q '"error"'; then
    log_test "orders_list" "true" "Orders retrieved"
else
    ERROR=$(echo "$RESPONSE" | grep -o '"message":"[^"]*"' | head -1)
    log_test "orders_list" "false" "Error: $ERROR"
fi

RESPONSE=$(curl -s -X POST "${BASE_URL}/mcp?token=${MASTER_KEY}" \
    -H "Content-Type: application/json" \
    -d '{
        "jsonrpc": "2.0",
        "id": 6,
        "method": "tools/call",
        "params": {
            "name": "orders_get",
            "arguments": {
                "order_id": "342635621",
                "store_identifier": "DR"
            }
        }
    }')

if echo "$RESPONSE" | grep -q '"content"' && ! echo "$RESPONSE" | grep -q '"error"'; then
    log_test "orders_get" "true" "Order retrieved"
else
    ERROR=$(echo "$RESPONSE" | grep -o '"message":"[^"]*"' | head -1)
    log_test "orders_get" "false" "Error: $ERROR"
fi

RESPONSE=$(curl -s -X POST "${BASE_URL}/mcp?token=${MASTER_KEY}" \
    -H "Content-Type: application/json" \
    -d '{
        "jsonrpc": "2.0",
        "id": 7,
        "method": "tools/call",
        "params": {
            "name": "orders_update",
            "arguments": {
                "order_id": "342635621",
                "store_identifier": "DR",
                "changes": {
                    "order_notes": [{
                        "content": "Test note from automated testing",
                        "username": "Test Script"
                    }]
                }
            }
        }
    }')

if echo "$RESPONSE" | grep -q "updated successfully" && ! echo "$RESPONSE" | grep -q '"error"'; then
    log_test "orders_update" "true" "Order updated"
else
    ERROR=$(echo "$RESPONSE" | grep -o '"message":"[^"]*"' | head -1)
    log_test "orders_update" "false" "Error or unexpected response: $ERROR"
fi

echo

# Test product tools
echo "📦 Product Tools:"
RESPONSE=$(curl -s -X POST "${BASE_URL}/mcp?token=${MASTER_KEY}" \
    -H "Content-Type: application/json" \
    -d '{
        "jsonrpc": "2.0",
        "id": 8,
        "method": "tools/call",
        "params": {
            "name": "products_list",
            "arguments": {
                "store_identifier": "DR",
                "limit": 5
            }
        }
    }')

if echo "$RESPONSE" | grep -q '"content"' && ! echo "$RESPONSE" | grep -q '"error"'; then
    log_test "products_list" "true" "Products retrieved"
else
    ERROR=$(echo "$RESPONSE" | grep -o '"message":"[^"]*"' | head -1)
    log_test "products_list" "false" "Error: $ERROR"
fi

echo
echo "============================================================"
echo "Tests Passed: $TESTS_PASSED"
echo "Tests Failed: $TESTS_FAILED"
echo "Total Tests: $((TESTS_PASSED + TESTS_FAILED))"
echo "============================================================"

if [ $TESTS_FAILED -gt 0 ]; then
    echo
    echo "❌ Some tests failed!"
    exit 1
else
    echo
    echo "✅ All tests passed!"
    exit 0
fi
