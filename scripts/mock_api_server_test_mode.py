#!/usr/bin/env python3
"""
Test-mode mock API server for Playwright E2E testing.

This server uses moto to mock all AWS services, allowing tests to run
without creating real AWS infrastructure.

Usage:
    export TEST_MODE=true
    python3 scripts/mock_api_server_test_mode.py [--port 8000]

Then update frontend tests to connect to http://localhost:8000/api
"""

import json
import http.server
import socketserver
import sys
import urllib.parse
import os
from datetime import datetime
from pathlib import Path

# Enable test mode FIRST (before any AWS imports)
os.environ['TEST_MODE'] = 'true'
os.environ.setdefault('AWS_ACCESS_KEY_ID', 'testing')
os.environ.setdefault('AWS_SECRET_ACCESS_KEY', 'testing')
os.environ.setdefault('AWS_DEFAULT_REGION', 'eu-west-1')

# Now import the Lambda module with moto mocks active
repo_root = Path(__file__).resolve().parents[1]
functions_root = repo_root / 'functions'

sys.path.insert(0, str(functions_root))
sys.path.insert(0, str(functions_root / 'aws'))
sys.path.insert(0, str(functions_root / 'common'))

# Import after TEST_MODE is set
from common import classroom_instance_manager

PORT = 8000

class TestModeAPIHandler(http.server.SimpleHTTPRequestHandler):
    """Handle API requests and delegate to real Lambda module with mocked AWS"""
    
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()
    
    def send_cors_headers(self):
        """Add CORS headers to response"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    
    def send_json_response(self, data, status_code=200):
        """Send JSON response with CORS headers"""
        self.send_response(status_code)
        self.send_cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def do_GET(self):
        """Handle GET requests - delegate to Lambda module"""
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        query_params = urllib.parse.parse_qs(parsed_path.query)
        
        # Remove /api prefix
        api_path = path.replace('/api', '', 1) if path.startswith('/api') else path
        
        print(f"[TEST MODE] GET {api_path}")
        
        # Construct event for Lambda handler
        event = {
            'requestContext': {'http': {'method': 'GET'}},
            'rawPath': api_path,
            'rawQueryString': parsed_path.query or '',
            'queryStringParameters': {k: v[0] for k, v in query_params.items()} if query_params else None,
        }
        
        try:
            response = classroom_instance_manager.lambda_handler(event, None)
            status_code = response.get('statusCode', 500)
            body = json.loads(response.get('body', '{}'))
            self.send_json_response(body, status_code)
        except Exception as e:
            print(f"[TEST MODE] Error: {str(e)}")
            self.send_json_response({'success': False, 'error': str(e)}, 500)
    
    def do_POST(self):
        """Handle POST requests - delegate to Lambda module"""
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        query_params = urllib.parse.parse_qs(parsed_path.query)
        
        # Remove /api prefix
        api_path = path.replace('/api', '', 1) if path.startswith('/api') else path
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        print(f"[TEST MODE] POST {api_path}")
        
        try:
            body_dict = json.loads(body) if body else {}
        except json.JSONDecodeError:
            body_dict = {}
        
        # Construct event for Lambda handler
        event = {
            'requestContext': {'http': {'method': 'POST'}},
            'rawPath': api_path,
            'rawQueryString': parsed_path.query or '',
            'queryStringParameters': {k: v[0] for k, v in query_params.items()} if query_params else None,
            'body': body or '{}',
        }
        
        try:
            response = classroom_instance_manager.lambda_handler(event, None)
            status_code = response.get('statusCode', 500)
            body_response = json.loads(response.get('body', '{}'))
            self.send_json_response(body_response, status_code)
        except Exception as e:
            print(f"[TEST MODE] Error: {str(e)}")
            self.send_json_response({'success': False, 'error': str(e)}, 500)

def run_server(port=PORT):
    """Start the test mode API server"""
    handler = TestModeAPIHandler
    
    with socketserver.TCPServer(("", port), handler) as httpd:
        print(f"[TEST MODE] Mock API server running at http://localhost:{port}")
        print("[TEST MODE] All AWS services are mocked via moto")
        print("[TEST MODE] Press Ctrl+C to stop")
        httpd.serve_forever()

if __name__ == '__main__':
    port = PORT
    
    if len(sys.argv) > 1:
        if sys.argv[1] == '--port' and len(sys.argv) > 2:
            port = int(sys.argv[2])
    
    run_server(port)
