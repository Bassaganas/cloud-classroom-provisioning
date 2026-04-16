#!/bin/bash

# Local testing script - starts both mock API and React dev server
# Usage: ./scripts/test_local.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
FRONTEND_DIR="$PROJECT_ROOT/frontend/ec2-manager"

echo "🚀 Starting Local Testing Environment"
echo ""

# Check if npm is installed
if ! command -v npm >/dev/null 2>&1; then
  echo "❌ Error: npm is not installed"
  echo "   Please install Node.js and npm first"
  exit 1
fi

# Check if Python is installed
if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ Error: python3 is not installed"
  echo "   Please install Python 3 first"
  exit 1
fi

# Install frontend dependencies if needed
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
  echo "📦 Installing npm dependencies..."
  cd "$FRONTEND_DIR"
  npm install
  cd "$PROJECT_ROOT"
fi

# Function to get Lambda URL from Terraform outputs
get_lambda_url() {
  local root_dir="$PROJECT_ROOT/iac/aws"
  
  if [ ! -d "$root_dir" ]; then
    return 1
  fi
  
  cd "$root_dir"
  
  # Initialize Terraform if needed
  if [ ! -d ".terraform" ]; then
    terraform init > /dev/null 2>&1 || return 1
  fi
  
  # Get Lambda URL from output
  terraform output -raw instance_manager_url 2>/dev/null || return 1
}

# Check if user wants to use real Lambda or mock
echo "Choose testing mode:"
echo "  1) Use mock API server (no AWS needed)"
echo "  2) Use real Lambda API (requires deployed infrastructure)"
read -p "Enter choice [1 or 2]: " choice

if [ "$choice" = "2" ]; then
  # Use real Lambda
  LAMBDA_URL=$(get_lambda_url)
  
  if [ -z "$LAMBDA_URL" ]; then
    echo "❌ Error: Could not get Lambda URL"
    echo "   Make sure infrastructure is deployed first:"
    echo "   ./scripts/setup_classroom.sh --name <classroom> --cloud aws --region <region>"
    echo "   Or choose option 1 to use mock API"
    exit 1
  fi
  
  echo ""
  echo "✅ Using real Lambda API: $LAMBDA_URL"
  echo ""
  echo "Starting React dev server..."
  echo "Open http://localhost:5173 in your browser"
  echo ""
  
  cd "$FRONTEND_DIR"
  LAMBDA_URL=$LAMBDA_URL npm run dev
else
  # Use mock API
  echo ""
  echo "✅ Using mock API server"
  echo ""
  echo "Starting mock API server on port 8000..."
  
  # Start mock API in background
  python3 "$PROJECT_ROOT/scripts/mock_api_server.py" --port 8000 &
  MOCK_PID=$!
  
  # Wait a moment for server to start
  sleep 2
  
  # Update Vite config temporarily to use mock server
  cd "$FRONTEND_DIR"
  
  # Create a temporary vite config for local testing
  cat > vite.config.local.js << 'EOF'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    outDir: 'dist',
    emptyOutDir: true
  },
  base: '/',
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        rewrite: (path) => path,
      }
    }
  }
})
EOF
  
  echo "Starting React dev server..."
  echo "Open http://localhost:5173 in your browser"
  echo ""
  echo "Press Ctrl+C to stop both servers"
  echo ""
  
  # Trap Ctrl+C to kill mock server
  trap "kill $MOCK_PID 2>/dev/null; rm -f vite.config.local.js; exit" INT TERM
  
  # Start React dev server with local config
  VITE_USER_CONFIG_FILE=vite.config.local.js npm run dev
  
  # Cleanup
  kill $MOCK_PID 2>/dev/null || true
  rm -f vite.config.local.js
fi
