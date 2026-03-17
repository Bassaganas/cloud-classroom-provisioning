#!/bin/bash
# Test runner script that sets up mocked AWS environment and runs Playwright tests

set -e

PROJECT_ROOT="$( cd "$( dirname "${BASH_SOURCE[0]}" )/.." && pwd )"
TESTS_DIR="$PROJECT_ROOT/frontend/ec2-manager"

echo "=========================================="
echo "Playwright E2E Tests (with Mocked AWS)"
echo "=========================================="
echo ""

# Configuration
TEST_MODE="true"
API_PORT=8000
API_URL="http://localhost:$API_PORT/api"
INSTALL_MOTO=false

# Parse arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        --install-moto)
            INSTALL_MOTO=true
            shift
            ;;
        --help)
            echo "Usage: $0 [OPTIONS]"
            echo ""
            echo "Options:"
            echo "  --install-moto   Install moto dependency before running tests"
            echo "  --help           Show this help message"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# Install moto if requested
if [ "$INSTALL_MOTO" = true ]; then
    echo "[SETUP] Installing moto for AWS mocking..."
    pip3 install 'moto[ec2,dynamodb,secretsmanager,ssm]>=5.0.0' -q
    echo "[SETUP] ✓ moto installed"
    echo ""
fi

# Start mock API server in background
echo "[SETUP] Starting mock API server (TEST_MODE=true)..."
export TEST_MODE="$TEST_MODE"
export AWS_ACCESS_KEY_ID="testing"
export AWS_SECRET_ACCESS_KEY="testing"
export AWS_DEFAULT_REGION="eu-west-1"

# Kill any existing server on the port
if lsof -Pi :$API_PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    kill $(lsof -Pi :$API_PORT -sTCP:LISTEN -t) 2>/dev/null || true
    sleep 1
fi

# Start mock server
python3 "$PROJECT_ROOT/scripts/mock_api_server_test_mode.py" --port $API_PORT > /tmp/mock_api_server.log 2>&1 &
MOCK_SERVER_PID=$!
echo "[SETUP] ✓ Mock API server started (PID: $MOCK_SERVER_PID)"

# Wait for server to be ready
echo "[SETUP] Waiting for API server to be ready..."
max_retries=30
retry_count=0
while ! curl -s "$API_URL/templates" > /dev/null 2>&1; do
    ((retry_count++))
    if [ $retry_count -ge $max_retries ]; then
        echo "[SETUP] ✗ Server failed to start. Check /tmp/mock_api_server.log"
        cat /tmp/mock_api_server.log
        exit 1
    fi
    sleep 0.5
done
echo "[SETUP] ✓ API server ready at $API_URL"
echo ""

# Cleanup function
cleanup() {
    echo ""
    echo "[CLEANUP] Stopping mock API server..."
    kill $MOCK_SERVER_PID 2>/dev/null || true
    sleep 1
    echo "[CLEANUP] ✓ Mock API server stopped"
}

# Register cleanup on exit
trap cleanup EXIT

# Run Playwright tests against the mock API
echo "[TESTS] Starting Playwright test suite..."
echo "[TESTS] API URL: $API_URL"
echo ""

cd "$TESTS_DIR"

# Set API URL for frontend tests if using environment variable
export VITE_API_URL="$API_URL"

# Ensure CI-friendly report locations
export PLAYWRIGHT_HTML_OPEN="never"

# Run tests
npx playwright test tests/e2e/tutorial-instance-manager.spec.js --reporter=list,html --output=test-results

echo ""
echo "=========================================="
echo "✓ All tests completed!"
echo "=========================================="
