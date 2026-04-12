import json
import os
import sys

import boto3
from moto import mock_aws

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../aws'))

import leaderboard_api as api


def _event(path: str, method: str = 'GET'):
    return {
        'requestContext': {'http': {'method': method, 'path': path}},
        'rawPath': path,
        'headers': {},
        'queryStringParameters': {},
        'body': None,
    }


def _create_table(table_name: str, region: str):
    dynamodb = boto3.resource('dynamodb', region_name=region)
    try:
        return dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {'AttributeName': 'pk', 'KeyType': 'HASH'},
                {'AttributeName': 'sk', 'KeyType': 'RANGE'},
            ],
            AttributeDefinitions=[
                {'AttributeName': 'pk', 'AttributeType': 'S'},
                {'AttributeName': 'sk', 'AttributeType': 'S'},
            ],
            BillingMode='PAY_PER_REQUEST',
        )
    except dynamodb.meta.client.exceptions.ResourceInUseException:
        return dynamodb.Table(table_name)


@mock_aws
def test_health_endpoint_returns_ok(monkeypatch):
    monkeypatch.setenv('ENVIRONMENT', 'dev')

    response = api.lambda_handler(_event('/api/health'), None)

    assert response['statusCode'] == 200
    payload = json.loads(response['body'])
    assert payload['status'] == 'ok'


@mock_aws
def test_leaderboard_endpoint_returns_ranked_entries(monkeypatch):
    region = 'eu-west-1'
    table_name = 'leaderboard-test'
    monkeypatch.setenv('AWS_REGION', region)
    monkeypatch.setenv('LEADERBOARD_TABLE', table_name)
    monkeypatch.setenv('ENVIRONMENT', 'dev')

    table = _create_table(table_name, region)
    table.put_item(Item={
        'pk': 'STUDENT#frodo',
        'sk': 'profile',
        'student_id': 'frodo',
        'total_points': 55,
        'completed_exercises': ['ex1', 'ex2', 'ex3'],
        'last_updated': '2026-04-11T09:00:00Z',
    })
    table.put_item(Item={
        'pk': 'STUDENT#sam',
        'sk': 'profile',
        'student_id': 'sam',
        'total_points': 25,
        'completed_exercises': ['ex1', 'ex2'],
        'last_updated': '2026-04-11T08:00:00Z',
    })

    response = api.lambda_handler(_event('/api/leaderboard'), None)

    assert response['statusCode'] == 200
    payload = json.loads(response['body'])
    assert [entry['student_id'] for entry in payload['entries']] == ['frodo', 'sam']
    assert [entry['rank'] for entry in payload['entries']] == [1, 2]
    assert payload['entries'][0]['progress'] == '3/5'


@mock_aws
def test_leaderboard_entries_include_map_progress(monkeypatch):
    region = 'eu-west-1'
    table_name = 'leaderboard-test-map'
    monkeypatch.setenv('AWS_REGION', region)
    monkeypatch.setenv('LEADERBOARD_TABLE', table_name)
    monkeypatch.setenv('ENVIRONMENT', 'dev')

    table = _create_table(table_name, region)
    table.put_item(Item={
        'pk': 'STUDENT#aragorn',
        'sk': 'profile',
        'student_id': 'aragorn',
        'total_points': 10,
        'completed_exercises': ['ex1'],
        'last_updated': '2026-04-12T10:00:00Z',
    })

    response = api.lambda_handler(_event('/api/leaderboard'), None)

    assert response['statusCode'] == 200
    payload = json.loads(response['body'])
    assert len(payload['entries']) == 1
    entry = payload['entries'][0]
    assert entry['current_realm']
    assert entry['map_position']['x'] >= 0
    assert entry['map_position']['y'] >= 0


@mock_aws
def test_student_endpoint_includes_map_progress(monkeypatch):
    region = 'eu-west-1'
    table_name = 'leaderboard-test-student-map'
    monkeypatch.setenv('AWS_REGION', region)
    monkeypatch.setenv('LEADERBOARD_TABLE', table_name)
    monkeypatch.setenv('ENVIRONMENT', 'dev')

    table = _create_table(table_name, region)
    table.put_item(Item={
        'pk': 'STUDENT#legolas',
        'sk': 'profile',
        'student_id': 'legolas',
        'total_points': 45,
        'completed_exercises': ['ex1', 'ex2', 'ex3'],
        'last_updated': '2026-04-12T11:00:00Z',
    })

    response = api.lambda_handler(_event('/api/student/legolas'), None)

    assert response['statusCode'] == 200
    payload = json.loads(response['body'])
    assert payload['current_realm']
    assert payload['map_position']['x'] >= 0
    assert payload['map_position']['y'] >= 0


@mock_aws
def test_student_endpoint_returns_404_for_missing_student(monkeypatch):
    region = 'eu-west-1'
    table_name = 'leaderboard-test'
    monkeypatch.setenv('AWS_REGION', region)
    monkeypatch.setenv('LEADERBOARD_TABLE', table_name)
    monkeypatch.setenv('ENVIRONMENT', 'dev')

    _create_table(table_name, region)

    response = api.lambda_handler(_event('/api/student/gandalf'), None)

    assert response['statusCode'] == 404
    payload = json.loads(response['body'])
    assert payload['error'] == 'Student not found'