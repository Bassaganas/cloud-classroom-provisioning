"""Shared pytest fixtures for API tests"""

import pytest
from datetime import datetime, timezone
from decimal import Decimal

@pytest.fixture
def mock_instance():
    """Standard mock EC2 instance"""
    return {
        'InstanceId': 'i-test-123',
        'State': {'Name': 'running'},
        'InstanceType': 't2.micro',
        'LaunchTime': datetime.now(timezone.utc),
        'PublicIpAddress': '1.2.3.4',
        'PrivateIpAddress': '10.0.0.1',
        'Tags': [
            {'Key': 'Project', 'Value': 'classroom'},
            {'Key': 'Type', 'Value': 'pool'},
            {'Key': 'TutorialSessionID', 'Value': 'sess-abc'},
            {'Key': 'WorkshopID', 'Value': 'fellowship'}
        ]
    }

@pytest.fixture
def mock_session():
    """Standard mock tutorial session"""
    return {
        'session_id': 'sess-123',
        'workshop_name': 'fellowship',
        'created_at': '2026-03-01T10:00:00+00:00',
        'pool_count': Decimal('3'),
        'admin_count': Decimal('1'),
        'productive_tutorial': False,
        'purchase_type': 'spot',
        'spot_max_price': Decimal('0.50'),
        'status': 'active'
    }

@pytest.fixture
def session_with_instances():
    """Session with aggregated instance costs"""
    return {
        'session_id': 'sess-123',
        'workshop_name': 'fellowship',
        'aggregated_estimated_cost_usd': 25.50,
        'aggregated_hourly_cost_usd': 2.55,
        'aggregated_estimated_24h_cost_usd': 30.60,
        'actual_instance_count': 3
    }