#!/usr/bin/env python3
"""
Simple mock API server for local frontend testing.
Mimics the Lambda API endpoints for development.

Usage:
    python3 scripts/mock_api_server.py [--port 8000]

Then update vite.config.js to proxy to http://localhost:8000
"""

import json
import http.server
import socketserver
import sys
import urllib.parse
from datetime import datetime

PORT = 8000

class MockAPIHandler(http.server.SimpleHTTPRequestHandler):
    def do_OPTIONS(self):
        """Handle CORS preflight"""
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()
    
    def do_GET(self):
        """Handle GET requests"""
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        query_params = urllib.parse.parse_qs(parsed_path.query)
        
        if path == '/api/templates':
            self.send_json_response({
                'success': True,
                'templates': {
                    'testus_patronus': {
                        'workshop_name': 'testus_patronus',
                        'ami_id': 'ami-12345678',
                        'instance_type': 't3.medium',
                        'app_port': 80
                    },
                    'fellowship': {
                        'workshop_name': 'fellowship',
                        'ami_id': 'ami-87654321',
                        'instance_type': 't3.medium',
                        'app_port': 8080
                    }
                }
            })
        elif path == '/api/list':
            self.send_json_response({
                'success': True,
                'instances': [
                    {
                        'instance_id': 'i-mock123',
                        'workshop': 'testus_patronus',
                        'type': 'pool',
                        'state': 'running',
                        'public_ip': '1.2.3.4',
                        'assigned': None
                    }
                ],
                'summary': {
                    'total': 1,
                    'pool': {'total': 1, 'running': 1, 'stopped': 0, 'assigned': 0},
                    'admin': {'total': 0, 'running': 0, 'stopped': 0}
                }
            })
        elif path == '/api/timeout_settings':
            workshop = query_params.get('workshop', ['testus_patronus'])[0]
            self.send_json_response({
                'success': True,
                'settings': {
                    'stop_timeout': 4,
                    'terminate_timeout': 20,
                    'hard_terminate_timeout': 45,
                    'admin_cleanup_days': 7
                },
                'timeouts': {
                    'stop_timeout': 4,
                    'terminate_timeout': 20,
                    'hard_terminate_timeout': 45,
                    'admin_cleanup_days': 7
                }
            })
        else:
            self.send_error(404, 'Not found')
    
    def do_POST(self):
        """Handle POST requests"""
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            data = json.loads(body) if body else {}
        except:
            data = {}
        
        if path == '/api/login':
            # Mock login - accept any password or empty
            password = data.get('password', '')
            self.send_json_response({
                'success': True,
                'token': 'mock-token'
            })
        elif path == '/api/create':
            count = data.get('count', 1)
            instance_type = data.get('type', 'pool')
            self.send_json_response({
                'success': True,
                'count': count,
                'message': f'Mock: Created {count} {instance_type} instance(s)'
            })
        elif path == '/api/assign':
            self.send_json_response({
                'success': True,
                'message': f'Mock: Assigned instance {data.get("instance_id")} to {data.get("student_name")}'
            })
        elif path == '/api/delete':
            self.send_json_response({
                'success': True,
                'count': 1,
                'message': f'Mock: Deleted instance {data.get("instance_id")}'
            })
        elif path == '/api/bulk_delete':
            self.send_json_response({
                'success': True,
                'deleted_count': 5,
                'message': 'Mock: Bulk deleted instances'
            })
        elif path == '/api/update_timeout_settings':
            self.send_json_response({
                'success': True,
                'message': f'Mock: Updated timeout settings for {data.get("workshop")}'
            })
        elif path == '/api/update_cleanup_days':
            self.send_json_response({
                'success': True,
                'message': f'Mock: Updated cleanup days to {data.get("cleanup_days")}'
            })
        elif path == '/api/enable_https':
            self.send_json_response({
                'success': True,
                'domain': f'https://mock-{data.get("instance_id")}.testingfantasy.com'
            })
        elif path == '/api/delete_https':
            self.send_json_response({
                'success': True,
                'domain': 'https://mock-domain.testingfantasy.com'
            })
        else:
            self.send_error(404, 'Not found')
    
    def send_cors_headers(self):
        """Send CORS headers"""
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
    
    def send_json_response(self, data, status=200):
        """Send JSON response with CORS"""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_cors_headers()
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))
    
    def log_message(self, format, *args):
        """Override to reduce log noise"""
        pass

def main():
    if len(sys.argv) > 1 and sys.argv[1] == '--port':
        global PORT
        PORT = int(sys.argv[2])
    
    with socketserver.TCPServer(("", PORT), MockAPIHandler) as httpd:
        print(f"Mock API server running on http://localhost:{PORT}")
        print(f"Update vite.config.js to proxy /api to http://localhost:{PORT}")
        print("Press Ctrl+C to stop")
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nShutting down mock server...")
            httpd.shutdown()

if __name__ == '__main__':
    main()
