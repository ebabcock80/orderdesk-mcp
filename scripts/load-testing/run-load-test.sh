#!/bin/bash
#
# OrderDesk MCP Server - Load Testing Runner
# =============================================================================
# Runs k6 load tests against the server
#
# Usage:
#   ./scripts/load-testing/run-load-test.sh basic          # Basic load test
#   ./scripts/load-testing/run-load-test.sh stress         # Stress test
#   ./scripts/load-testing/run-load-test.sh --help         # Show help
#
# Prerequisites:
#   brew install k6  # macOS
#   # or: https://k6.io/docs/get-started/installation/
#
# =============================================================================

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BASE_URL="${BASE_URL:-http://localhost:8080}"
MASTER_KEY="${MASTER_KEY:-dev-admin-master-key-change-in-production-VNS09qKDdt}"
RESULTS_DIR="${RESULTS_DIR:-$SCRIPT_DIR/results}"

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

# Create results directory
mkdir -p "$RESULTS_DIR"

# Check if k6 is installed
if ! command -v k6 &> /dev/null; then
    echo -e "${RED}ERROR: k6 is not installed${NC}"
    echo ""
    echo "Install k6:"
    echo "  macOS:   brew install k6"
    echo "  Linux:   sudo gpg -k"
    echo "           sudo gpg --no-default-keyring --keyring /usr/share/keyrings/k6-archive-keyring.gpg --keyserver hkp://keyserver.ubuntu.com:80 --recv-keys C5AD17C747E3415A3642D57D77C6C491D6AC1D69"
    echo "           echo \"deb [signed-by=/usr/share/keyrings/k6-archive-keyring.gpg] https://dl.k6.io/deb stable main\" | sudo tee /etc/apt/sources.list.d/k6.list"
    echo "           sudo apt-get update"
    echo "           sudo apt-get install k6"
    echo "  Docker:  docker run --rm -i grafana/k6 run - <script.js"
    echo ""
    exit 1
fi

# Function to run a test
run_test() {
    local test_name="$1"
    local test_file="$2"
    local timestamp=$(date +%Y%m%d_%H%M%S)
    local result_file="$RESULTS_DIR/${test_name}-${timestamp}.json"
    
    echo -e "${GREEN}========================================${NC}"
    echo -e "${GREEN}Running: $test_name${NC}"
    echo -e "${GREEN}========================================${NC}"
    echo "Test file: $test_file"
    echo "Target: $BASE_URL"
    echo "Results: $result_file"
    echo ""
    
    # Check server health first
    echo "Checking server health..."
    if ! curl -sf "$BASE_URL/health" > /dev/null; then
        echo -e "${RED}ERROR: Server is not healthy${NC}"
        echo "Start the server first: docker-compose up -d"
        exit 1
    fi
    echo -e "${GREEN}✅ Server is healthy${NC}"
    echo ""
    
    # Run k6 test
    k6 run \
        --out json="$result_file" \
        --summary-export="$RESULTS_DIR/${test_name}-${timestamp}-summary.json" \
        -e BASE_URL="$BASE_URL" \
        -e MASTER_KEY="$MASTER_KEY" \
        "$test_file"
    
    local exit_code=$?
    
    echo ""
    echo -e "${GREEN}========================================${NC}"
    if [ $exit_code -eq 0 ]; then
        echo -e "${GREEN}✅ Test Passed: $test_name${NC}"
    else
        echo -e "${YELLOW}⚠️  Test Had Issues: $test_name${NC}"
    fi
    echo -e "${GREEN}========================================${NC}"
    echo "Results saved to: $result_file"
    echo ""
    
    return $exit_code
}

# Main
case "${1:-}" in
    basic)
        run_test "basic-load" "$SCRIPT_DIR/k6-basic-load.js"
        ;;
    stress)
        run_test "stress-test" "$SCRIPT_DIR/k6-stress-test.js"
        ;;
    --help|-h)
        echo "OrderDesk MCP Server - Load Testing"
        echo ""
        echo "Usage:"
        echo "  $0 basic          Run basic load test (10-20 users, 9 min)"
        echo "  $0 stress         Run stress test (up to 150 users, 26 min)"
        echo "  $0 --help         Show this help"
        echo ""
        echo "Environment Variables:"
        echo "  BASE_URL          Target server URL (default: http://localhost:8080)"
        echo "  MASTER_KEY        Master key for authentication"
        echo "  RESULTS_DIR       Results directory (default: ./results)"
        echo ""
        echo "Prerequisites:"
        echo "  - k6 installed (brew install k6)"
        echo "  - Server running (docker-compose up -d)"
        echo ""
        echo "Example:"
        echo "  export BASE_URL=https://staging.yourdomain.com"
        echo "  export MASTER_KEY=your-staging-master-key"
        echo "  $0 basic"
        echo ""
        exit 0
        ;;
    "")
        echo -e "${YELLOW}No test specified${NC}"
        echo "Usage: $0 {basic|stress|--help}"
        echo "Example: $0 basic"
        exit 1
        ;;
    *)
        echo -e "${RED}Unknown test: $1${NC}"
        echo "Available tests: basic, stress"
        echo "Use --help for more information"
        exit 1
        ;;
esac

