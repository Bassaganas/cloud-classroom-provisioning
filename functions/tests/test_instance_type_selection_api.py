import json
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../common'))
from test_mode import init_test_mode

init_test_mode()

import classroom_instance_manager as cim


def _event_for_create(body):
    return {
        'requestContext': {'http': {'method': 'POST', 'path': '/api/create'}},
        'rawPath': '/api/create',
        'queryStringParameters': {},
        'headers': {},
        'body': json.dumps(body),
    }


@pytest.fixture(autouse=True)
def _patch_auth(monkeypatch):
    monkeypatch.setattr(cim, 'check_password_auth', lambda *_: True)


@pytest.fixture
def _capture_create_call(monkeypatch):
    captured = {}

    def _fake_create_instance(**kwargs):
        captured.update(kwargs)
        return {'success': True, 'count': kwargs.get('count', 0), 'instances': []}

    monkeypatch.setattr(cim, 'create_instance', _fake_create_instance)
    monkeypatch.setattr(cim, 'get_template_map', lambda: {'fellowship': {}})
    return captured


def test_create_uses_default_t3_medium_when_not_provided(_capture_create_call):
    response = cim.lambda_handler(_event_for_create({
        'count': 1,
        'type': 'pool',
        'workshop': 'fellowship',
    }), None)

    assert response['statusCode'] == 200
    assert _capture_create_call['ec2_instance_type'] is None


def test_create_accepts_allowed_instance_type(_capture_create_call):
    response = cim.lambda_handler(_event_for_create({
        'count': 1,
        'type': 'pool',
        'workshop': 'fellowship',
        'ec2_instance_type': 't3.large',
    }), None)

    assert response['statusCode'] == 200
    assert _capture_create_call['ec2_instance_type'] == 't3.large'


def test_create_rejects_disallowed_instance_type(_capture_create_call):
    response = cim.lambda_handler(_event_for_create({
        'count': 1,
        'type': 'pool',
        'workshop': 'fellowship',
        'ec2_instance_type': 'm5.2xlarge',
    }), None)

    assert response['statusCode'] == 400
    payload = json.loads(response['body'])
    assert payload['success'] is False
    assert 'ec2_instance_type' in payload['error']
