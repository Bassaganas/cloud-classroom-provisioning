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
            # Return mock instances with Jenkins/Gitea URLs for assigned instances
            tutorial_session_id = query_params.get('tutorial_session_id', [None])[0]
            self.send_json_response({
                'success': True,
                'instances': [
                    {
                        'instance_id': 'i-mock-assigned-1',
                        'workshop': 'fellowship',
                        'tutorial_session_id': 'tutorial1',
                        'type': 'pool',
                        'state': 'running',
                        'public_ip': '1.2.3.4',
                        'private_ip': '10.0.0.5',
                        'instance_type': 't3.medium',
                        'assigned_to': 'student1',
                        'assignment_status': 'active',
                        'https_url': 'https://student1-fellowship.testingfantasy.com',
                        'jenkins_job_url': 'https://jenkins.fellowship.testingfantasy.com/job/student1/job/fellowship-pipeline/',
                        'gitea_repo_url': 'https://gitea.fellowship.testingfantasy.com/fellowship-org/fellowship-sut-student1',
                        'hourly_rate_estimate_usd': 0.0416,
                        'estimated_cost_usd': 1.0,
                        'purchase_type': 'on-demand'
                    },
                    {
                        'instance_id': 'i-mock-unassigned-1',
                        'workshop': 'fellowship',
                        'tutorial_session_id': 'tutorial1',
                        'type': 'pool',
                        'state': 'running',
                        'public_ip': '1.2.3.5',
                        'private_ip': '10.0.0.6',
                        'instance_type': 't3.medium',
                        'assigned_to': None,
                        'https_url': None,
                        'hourly_rate_estimate_usd': 0.0416,
                        'estimated_cost_usd': 1.0,
                        'purchase_type': 'on-demand'
                    }
                ],
                'count': 2,
                'summary': {
                    'total': 2,
                    'pool': {'total': 2, 'running': 2, 'stopped': 0, 'assigned': 1, 'available': 1},
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
        elif path == '/api/shared_core_settings':
            workshop = query_params.get('workshop', ['fellowship'])[0]
            self.send_json_response({
                'success': True,
                'settings': {
                    'shared_core_mode': True,
                    'shared_jenkins_url': 'https://jenkins.fellowship.testingfantasy.com',
                    'shared_gitea_url': 'https://gitea.fellowship.testingfantasy.com'
                }
            })
        elif path == '/api/tutorial_sessions':
            workshop = query_params.get('workshop', ['fellowship'])[0]
            self.send_json_response({
                'success': True,
                'sessions': [
                    {
                        'session_id': 'tutorial1',
                        'workshop': workshop,
                        'name': 'Tutorial Session 1',
                        'created_at': datetime.now().isoformat(),
                        'description': 'Mock tutorial session for testing'
                    }
                ]
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
        elif path == '/api/update_shared_core_settings':
            workshop = data.get('workshop', 'fellowship')
            shared_core_mode = data.get('shared_core_mode', False)
            self.send_json_response({
                'success': True,
                'message': f'Mock: Updated shared-core mode to {shared_core_mode} for {workshop}'
            })
        elif path == '/api/delete_shared_core_resources':
            resource_type = data.get('resource_type', 'jenkins_folders')
            workshop = data.get('workshop', 'fellowship')
            deleted_count = 3 if resource_type == 'jenkins_folders' else 5
            deleted_items = [f'item{i}' for i in range(1, deleted_count + 1)]
            self.send_json_response({
                'success': True,
                'deleted': deleted_items,
                'deleted_count': deleted_count,
                'errors': [],
                'message': f'Mock: Deleted {deleted_count} {resource_type} from {workshop}'
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
