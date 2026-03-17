#!/usr/bin/env python3
"""
Test-mode mock API server for Playwright E2E testing.

This server keeps an in-memory representation of tutorial sessions and
instances so the frontend E2E suite can run deterministically without
touching real AWS infrastructure.
"""

import http.server
import json
import os
import socketserver
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone

PORT = 8000

os.environ['TEST_MODE'] = 'true'
os.environ.setdefault('AWS_ACCESS_KEY_ID', 'testing')
os.environ.setdefault('AWS_SECRET_ACCESS_KEY', 'testing')
os.environ.setdefault('AWS_DEFAULT_REGION', 'eu-west-1')

WORKSHOP_TEMPLATES = {
    'fellowship': {
        'display_name': 'Fellowship',
        'description': 'Mock fellowship workshop for Playwright tests',
    },
    'testus_patronus': {
        'display_name': 'Testus Patronus',
        'description': 'Mock testus patronus workshop for Playwright tests',
    },
}

STATE = {
    'sessions': {},
    'instances': {},
    'next_instance_number': 1,
}


def utc_now_iso():
    return datetime.now(timezone.utc).isoformat()


def parse_bool(value):
    return str(value).lower() in {'1', 'true', 'yes', 'on'}


def make_ip(number):
    third = 10 + ((number - 1) // 250)
    fourth = 10 + ((number - 1) % 250)
    return f'203.0.{third}.{fourth}'


def build_instance(*, workshop_name, session_id, instance_type, purchase_type, cleanup_days=None, spot_max_price=None, force_http_only=False):
    number = STATE['next_instance_number']
    STATE['next_instance_number'] += 1

    instance_id = f'i-mock-{number:06d}'
    public_ip = make_ip(number)
    launch_time = utc_now_iso()
    tags = {
        'Workshop': workshop_name,
        'TutorialSessionId': session_id,
        'PurchaseType': purchase_type,
    }

    https_domain = None if force_http_only else f'{instance_id}.mock.testingfantasy.com'
    if https_domain:
        tags['HttpsDomain'] = https_domain
        tags['HttpsUrl'] = f'https://{https_domain}'

    instance = {
        'instance_id': instance_id,
        'tutorial_session_id': session_id,
        'workshop': workshop_name,
        'instance_type': 't3.medium',
        'type': instance_type,
        'state': 'running',
        'public_ip': public_ip,
        'https_domain': https_domain,
        'https_url': f'https://{https_domain}' if https_domain else None,
        'assigned_to': '',
        'cleanup_days': cleanup_days,
        'cleanup_days_remaining': cleanup_days,
        'launch_time': launch_time,
        'purchase_type': purchase_type,
        'spot_max_price': str(spot_max_price) if spot_max_price not in [None, ''] else None,
        'estimated_runtime_hours': 1.0,
        'hourly_rate_estimate_usd': 0.0125 if purchase_type == 'spot' else 0.0416,
        'estimated_cost_usd': 0.0125 if purchase_type == 'spot' else 0.0416,
        'estimated_cost_24h_usd': 0.3 if purchase_type == 'spot' else 1.0,
        'actual_cost_usd': 0.0,
        'health_status': 'healthy',
        'health_checked_at': launch_time,
        'health_error': '',
        'tags': tags,
    }

    STATE['instances'][instance_id] = instance
    return instance


def session_instances(session_id):
    return [instance for instance in STATE['instances'].values() if instance['tutorial_session_id'] == session_id]


def summarize_session(session):
    instances = session_instances(session['session_id'])
    return {
        **session,
        'actual_instance_count': len(instances),
        'aggregated_estimated_cost_usd': round(sum(float(instance.get('estimated_cost_usd') or 0) for instance in instances), 2),
    }


def build_stats(instances):
    return {
        'total_instances': len(instances),
        'running': sum(1 for instance in instances if instance.get('state') == 'running'),
        'stopped': sum(1 for instance in instances if instance.get('state') == 'stopped'),
        'pool_instances': sum(1 for instance in instances if instance.get('type') == 'pool'),
        'admin_instances': sum(1 for instance in instances if instance.get('type') == 'admin'),
    }


def build_costs(instances):
    estimated_hourly = sum(float(instance.get('hourly_rate_estimate_usd') or 0) for instance in instances)
    estimated_accrued = sum(float(instance.get('estimated_cost_usd') or 0) for instance in instances)
    estimated_24h = sum(float(instance.get('estimated_cost_24h_usd') or 0) for instance in instances)
    actual_total = sum(float(instance.get('actual_cost_usd') or 0) for instance in instances)
    return {
        'estimated_hourly': round(estimated_hourly, 4),
        'estimated_accrued': round(estimated_accrued, 2),
        'estimated_24h': round(estimated_24h, 2),
        'actual_total': round(actual_total, 2),
        'actual_data_source': 'mock',
    }


def create_session(session_id, workshop_name, pool_count, admin_count, admin_cleanup_days=7, productive_tutorial=False, spot_max_price=None, seed=False):
    purchase_type = 'on-demand' if productive_tutorial else 'spot'
    session = {
        'session_id': session_id,
        'workshop_name': workshop_name,
        'created_at': utc_now_iso(),
        'productive_tutorial': productive_tutorial,
        'purchase_type': purchase_type,
        'spot_max_price': None if productive_tutorial else (str(spot_max_price) if spot_max_price not in [None, ''] else None),
    }
    STATE['sessions'][session_id] = session

    force_http_only = workshop_name == 'testus_patronus'
    for _ in range(max(pool_count, 0)):
        build_instance(
            workshop_name=workshop_name,
            session_id=session_id,
            instance_type='pool',
            purchase_type=purchase_type,
            cleanup_days=None,
            spot_max_price=session['spot_max_price'],
            force_http_only=force_http_only,
        )
    for _ in range(max(admin_count, 0)):
        build_instance(
            workshop_name=workshop_name,
            session_id=session_id,
            instance_type='admin',
            purchase_type=purchase_type,
            cleanup_days=admin_cleanup_days,
            spot_max_price=session['spot_max_price'],
            force_http_only=force_http_only,
        )

    if seed:
        session['created_at'] = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()

    return summarize_session(session)


def reset_state():
    STATE['sessions'].clear()
    STATE['instances'].clear()
    STATE['next_instance_number'] = 1
    create_session('tut1', 'fellowship', pool_count=2, admin_count=0, productive_tutorial=True, seed=True)
    create_session('tutorial_wetest_athenes', 'testus_patronus', pool_count=2, admin_count=0, productive_tutorial=False, seed=True)


reset_state()


class TestModeAPIHandler(http.server.SimpleHTTPRequestHandler):
    """Handle API requests against an in-memory test backend."""

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_cors_headers()
        self.end_headers()

    def do_GET(self):
        self.handle_request('GET')

    def do_POST(self):
        self.handle_request('POST')

    def do_DELETE(self):
        self.handle_request('DELETE')

    def send_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, PUT, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')

    def send_json_response(self, data, status_code=200):
        self.send_response(status_code)
        self.send_cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def parse_request_payload(self):
        content_length = int(self.headers.get('Content-Length', 0))
        if content_length <= 0:
            return {}
        raw = self.rfile.read(content_length).decode('utf-8')
        if not raw:
            return {}
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return {}

    def handle_request(self, method):
        parsed_path = urllib.parse.urlparse(self.path)
        path = parsed_path.path
        query_params = urllib.parse.parse_qs(parsed_path.query)
        body = self.parse_request_payload() if method in {'POST', 'DELETE'} else {}

        if path.startswith('/api'):
            api_path = path.replace('/api', '', 1) or '/'
        else:
            api_path = path

        print(f'[TEST MODE] {method} {api_path}')

        try:
            response, status_code = self.route_request(method, api_path, query_params, body)
            self.send_json_response(response, status_code)
        except Exception as exc:
            print(f'[TEST MODE] Error: {exc}')
            self.send_json_response({'success': False, 'error': str(exc)}, 500)

    def route_request(self, method, api_path, query_params, body):
        if api_path in {'/templates', '/'} and method == 'GET':
            return {'success': True, 'templates': WORKSHOP_TEMPLATES}, 200

        if api_path == '/always-on-tutorials' and method == 'GET':
            return {'success': True, 'tutorials': []}, 200

        if api_path == '/login' and method in {'GET', 'POST'}:
            return {'success': True, 'message': 'Login successful'}, 200

        if api_path == '/tutorial_sessions' and method == 'GET':
            workshop = (query_params.get('workshop') or [''])[0]
            sessions = [
                summarize_session(session)
                for session in STATE['sessions'].values()
                if not workshop or session['workshop_name'] == workshop
            ]
            sessions.sort(key=lambda session: session['created_at'], reverse=True)
            return {'success': True, 'sessions': sessions}, 200

        if api_path == '/create_tutorial_session' and method == 'POST':
            session_id = str(body.get('session_id') or '').strip()
            workshop_name = str(body.get('workshop_name') or '').strip()
            if not session_id or not workshop_name:
                return {'success': False, 'error': 'session_id and workshop_name are required'}, 400
            if session_id in STATE['sessions']:
                return {'success': False, 'error': 'Tutorial session already exists'}, 409

            session = create_session(
                session_id,
                workshop_name,
                pool_count=int(body.get('pool_count', 0) or 0),
                admin_count=int(body.get('admin_count', 0) or 0),
                admin_cleanup_days=int(body.get('admin_cleanup_days', 7) or 7),
                productive_tutorial=bool(body.get('productive_tutorial', False)),
                spot_max_price=body.get('spot_max_price'),
            )
            return {'success': True, 'session': session}, 200

        if api_path.startswith('/tutorial_session/') and method == 'GET':
            session_id = api_path.split('/tutorial_session/', 1)[1]
            session = STATE['sessions'].get(session_id)
            if not session:
                return {'success': False, 'error': 'Session not found'}, 404

            instances = session_instances(session_id)
            return {
                'success': True,
                'session': summarize_session(session),
                'instances': instances,
                'stats': build_stats(instances),
                'costs': build_costs(instances),
            }, 200

        if api_path.startswith('/tutorial_session/') and method == 'DELETE':
            session_id = api_path.split('/tutorial_session/', 1)[1]
            session = STATE['sessions'].get(session_id)
            if not session:
                return {'success': False, 'error': 'Session not found'}, 404

            delete_instances = parse_bool((query_params.get('delete_instances') or ['false'])[0])
            if delete_instances:
                for instance in list(session_instances(session_id)):
                    STATE['instances'].pop(instance['instance_id'], None)
            else:
                for instance in session_instances(session_id):
                    instance['tutorial_session_id'] = ''
            STATE['sessions'].pop(session_id, None)
            return {'success': True, 'message': 'Session deleted'}, 200

        if api_path == '/list' and method == 'GET':
            tutorial_session_id = (query_params.get('tutorial_session_id') or [''])[0]
            instances = list(STATE['instances'].values())
            if tutorial_session_id:
                instances = [instance for instance in instances if instance['tutorial_session_id'] == tutorial_session_id]

            if parse_bool((query_params.get('include_health') or ['false'])[0]):
                for instance in instances:
                    instance['health_status'] = 'healthy'
                    instance['health_checked_at'] = utc_now_iso()
                    instance['health_error'] = ''

            return {
                'success': True,
                'instances': instances,
                'actual_total_usd': round(sum(float(instance.get('actual_cost_usd') or 0) for instance in instances), 2),
                'actual_data_source': 'mock',
            }, 200

        if api_path == '/create' and method == 'POST':
            session_id = str(body.get('tutorial_session_id') or '').strip()
            session = STATE['sessions'].get(session_id)
            if not session:
                return {'success': False, 'error': 'Session not found'}, 404

            count = int(body.get('count', 1) or 1)
            instance_type = body.get('type', 'pool')
            purchase_type = body.get('purchase_type') or session.get('purchase_type') or 'on-demand'
            cleanup_days = body.get('cleanup_days')
            force_http_only = session['workshop_name'] == 'testus_patronus'
            for _ in range(count):
                build_instance(
                    workshop_name=session['workshop_name'],
                    session_id=session_id,
                    instance_type=instance_type,
                    purchase_type=purchase_type,
                    cleanup_days=int(cleanup_days) if cleanup_days not in [None, ''] else None,
                    spot_max_price=body.get('spot_max_price') or session.get('spot_max_price'),
                    force_http_only=force_http_only,
                )
            return {'success': True, 'count': count}, 200

        if api_path == '/update_cleanup_days' and method == 'POST':
            instance_id = body.get('instance_id')
            cleanup_days = int(body.get('cleanup_days', 7) or 7)
            instance = STATE['instances'].get(instance_id)
            if not instance:
                return {'success': False, 'error': 'Instance not found'}, 404
            instance['cleanup_days'] = cleanup_days
            instance['cleanup_days_remaining'] = cleanup_days
            return {'success': True}, 200

        if api_path == '/delete' and method == 'POST':
            instance_ids = []
            if body.get('instance_id'):
                instance_ids.append(body['instance_id'])
            instance_ids.extend(body.get('instance_ids') or [])
            deleted = 0
            for instance_id in instance_ids:
                if STATE['instances'].pop(instance_id, None):
                    deleted += 1
            return {'success': True, 'count': deleted}, 200

        if api_path == '/enable_https' and method == 'POST':
            instance_id = body.get('instance_id')
            instance = STATE['instances'].get(instance_id)
            if not instance:
                return {'success': False, 'error': 'Instance not found'}, 404
            https_domain = f'{instance_id}.mock.testingfantasy.com'
            instance['https_domain'] = https_domain
            instance['https_url'] = f'https://{https_domain}'
            instance['tags']['HttpsDomain'] = https_domain
            instance['tags']['HttpsUrl'] = f'https://{https_domain}'
            return {'success': True}, 200

        return {'success': False, 'error': f'Unhandled endpoint: {method} {api_path}'}, 404


def run_server(port=PORT):
    handler = TestModeAPIHandler
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer(('', port), handler) as httpd:
        print(f'[TEST MODE] Mock API server running at http://localhost:{port}')
        print('[TEST MODE] Using in-memory tutorial/session data')
        print('[TEST MODE] Press Ctrl+C to stop')
        httpd.serve_forever()


if __name__ == '__main__':
    port = PORT
    if len(sys.argv) > 2 and sys.argv[1] == '--port':
        port = int(sys.argv[2])
    run_server(port)
