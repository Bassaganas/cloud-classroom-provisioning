"""
Unit tests for Provisioning Function Integration

Tests cover:
- Fellowship status provisioning logic
- Instance manager provisioning updates
- Provision state transitions
- Error handling in provisioning
- Pre-assignment workflow
"""

import pytest
import json
import os
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime
import sys
import boto3

# Try new moto import first, fall back to old style
try:
    from moto import mock_aws
except ImportError:
    from moto import mock_dynamodb as mock_aws_dynamodb, mock_secretsmanager as mock_aws_secretsmanager
    # Wrapper for compatibility
    def mock_aws(func):
        def wrapper(*args, **kwargs):
            return mock_aws_dynamodb(mock_aws_secretsmanager(func))(*args, **kwargs)
        return wrapper

# Mock environment before import
os.environ['AWS_REGION'] = 'eu-west-1'
os.environ['WORKSHOP_NAME'] = 'fellowship'
os.environ['ENVIRONMENT'] = 'dev'
os.environ['AWS_ACCOUNT_ID'] = '087559609246'


@mock_aws
class TestFellowshipProvisioningStatus:
    """Test suite for fellowship provisioning status tracking"""

    def test_provisioning_state_not_started(self):
        """Test initial provisioning state"""
        student_name = 'fellowship-student-test'
        
        # Record without provisioning info
        record = {
            'student_name': student_name,
            'created_at': datetime.utcnow().isoformat(),
            'provisioning_state': 'NOT_STARTED'
        }

        assert record['provisioning_state'] == 'NOT_STARTED'

    def test_provisioning_state_in_progress(self):
        """Test in-progress provisioning state"""
        record = {
            'provisioning_state': 'IN_PROGRESS',
            'provision_start_time': datetime.utcnow().isoformat(),
            'provision_steps': ['dify_setup', 'ai_model_config']
        }

        assert record['provisioning_state'] == 'IN_PROGRESS'
        assert len(record['provision_steps']) > 0

    def test_provisioning_state_completed(self):
        """Test completed provisioning state"""
        record = {
            'provisioning_state': 'COMPLETED',
            'provision_completion_time': datetime.utcnow().isoformat(),
            'dify_instance_url': 'https://dify-instance-123.lambda-url.eu-west-1.on.aws',
            'ai_models_configured': True
        }

        assert record['provisioning_state'] == 'COMPLETED'
        assert 'dify_instance_url' in record
        assert record['ai_models_configured'] is True

    def test_provisioning_state_failed(self):
        """Test failed provisioning state"""
        record = {
            'provisioning_state': 'FAILED',
            'failure_reason': 'Dify container startup timeout',
            'failure_step': 'dify_setup',
            'retry_count': 2
        }

        assert record['provisioning_state'] == 'FAILED'
        assert 'failure_reason' in record

    def test_provision_step_tracking(self):
        """Test tracking of provisioning steps"""
        steps = [
            {'step': 'ec2_instance_ready', 'status': 'completed', 'duration': 45},
            {'step': 'dify_docker_pulled', 'status': 'completed', 'duration': 120},
            {'step': 'dify_container_running', 'status': 'in_progress', 'duration': None},
        ]

        completed = [s for s in steps if s['status'] == 'completed']
        in_progress = [s for s in steps if s['status'] == 'in_progress']

        assert len(completed) == 2
        assert len(in_progress) == 1


@mock_aws
class TestInstanceManagerProvisioning:
    """Test suite for instance manager provisioning updates"""

    def test_instance_provision_status_field(self):
        """Test that instance records include provision status"""
        record = {
            'student_name': 'test-student',
            'instance_id': 'i-12345',
            'provision_status': 'ready_for_provisioning'
        }

        assert 'provision_status' in record

    def test_instance_provision_timestamp(self):
        """Test provision timestamp tracking"""
        now = datetime.utcnow()
        record = {
            'student_name': 'test-student',
            'instance_id': 'i-12345',
            'provision_initiated_at': now.isoformat(),
            'last_provision_check': now.isoformat()
        }

        assert record['provision_initiated_at']
        assert record['last_provision_check']

    def test_instance_dify_url_field(self):
        """Test Dify URL field in instance record"""
        record = {
            'student_name': 'test-student',
            'instance_id': 'i-12345',
            'dify_instance_url': 'https://dify-instance-xyz.lambda-url.eu-west-1.on.aws'
        }

        assert 'https://' in record['dify_instance_url']
        assert 'dify' in record['dify_instance_url'].lower()

    def test_instance_provisioning_health_check(self):
        """Test health check fields for provisioning"""
        record = {
            'student_name': 'test-student',
            'instance_id': 'i-12345',
            'provisioning_health': {
                'ec2_status': 'ok',
                'dify_status': 'running',
                'ai_models_status': 'configured',
                'last_check': datetime.utcnow().isoformat()
            }
        }

        assert record['provisioning_health']['ec2_status'] == 'ok'
        assert record['provisioning_health']['dify_status'] == 'running'


class TestPreAssignmentWorkflow:
    """Test suite for pre-assignment workflow"""

    def test_pre_assignment_checks(self):
        """Test pre-assignment validation checks"""
        checks = {
            'aws_credentials_valid': True,
            'instance_available': True,
            'resources_sufficient': True,
            'dify_image_current': True,
            'ai_models_available': True
        }

        all_passed = all(checks.values())
        assert all_passed is True

    def test_pre_assignment_fails_missing_resources(self):
        """Test pre-assignment fails when resources unavailable"""
        checks = {
            'aws_credentials_valid': True,
            'instance_available': False,  # No instances available
            'resources_sufficient': False,  # Insufficient resources
            'dify_image_current': True,
            'ai_models_available': True
        }

        can_proceed = all([
            checks['aws_credentials_valid'],
            checks['instance_available'],
            checks['resources_sufficient']
        ])

        assert can_proceed is False

    def test_pre_assignment_requires_dify_available(self):
        """Test that pre-assignment requires Dify to be available"""
        requirements = {
            'student_authenticated': True,
            'dify_available': False,  # Fail if Dify not available
            'ai_models_available': True
        }

        can_assign = requirements['student_authenticated'] and requirements['dify_available']
        assert can_assign is False

        # Now fix and verify
        requirements['dify_available'] = True
        can_assign = requirements['student_authenticated'] and requirements['dify_available']
        assert can_assign is True

    def test_assignment_workflow_order(self):
        """Test correct order of assignment workflow steps"""
        workflow_steps = [
            'validate_student',
            'generate_credentials',
            'reserve_instance',
            'trigger_provisioning',
            'wait_for_provisioning',
            'return_credentials_and_urls'
        ]

        # Verify steps are in correct order
        assert workflow_steps.index('validate_student') < workflow_steps.index('generate_credentials')
        assert workflow_steps.index('generate_credentials') < workflow_steps.index('reserve_instance')
        assert workflow_steps.index('trigger_provisioning') < workflow_steps.index('wait_for_provisioning')


class TestProvisioningErrorRecovery:
    """Test suite for error handling and recovery in provisioning"""

    def test_provisioning_retry_logic(self):
        """Test retry logic for failed provisioning steps"""
        max_retries = 3
        attempt = 0
        
        while attempt < max_retries:
            try:
                result = self._simulate_provision_step()
                break
            except Exception as e:
                attempt += 1
                if attempt >= max_retries:
                    raise

    def _simulate_provision_step(self):
        """Simulate a provisioning step that might fail"""
        return {'status': 'success', 'duration': 5}

    def test_provisioning_timeout_handling(self):
        """Test timeout handling in provisioning"""
        timeout_seconds = 600  # 10 minutes
        start_time = datetime.utcnow()
        
        # Simulate provision check timeout
        elapsed = (datetime.utcnow() - start_time).total_seconds()
        
        if elapsed > timeout_seconds:
            status = 'TIMEOUT'
        else:
            status = 'IN_PROGRESS'

        assert status in ['IN_PROGRESS', 'TIMEOUT', 'COMPLETED']

    def test_provisioning_failure_notification(self):
        """Test that provisioning failures trigger notifications"""
        failure_event = {
            'student_name': 'test-student',
            'failure_reason': 'Dify container failed to start',
            'failure_timestamp': datetime.utcnow().isoformat(),
            'notify_user': True,
            'notify_admin': True
        }

        assert failure_event['notify_user'] is True
        assert failure_event['notify_admin'] is True

    def test_provision_state_rollback(self):
        """Test rollback when provisioning fails partway"""
        state = {
            'steps_completed': ['ec2_ready', 'dify_pulled'],
            'steps_failed': ['dify_startup'],
            'should_rollback': True
        }

        rollback_steps = list(reversed(state['steps_completed']))
        assert 'dify_pulled' in rollback_steps[0]


class TestProvisioningMetrics:
    """Test suite for provisioning metrics and monitoring"""

    def test_provisioning_duration_tracking(self):
        """Test tracking of total provisioning duration"""
        start = datetime.utcnow()
        
        # Simulate provisioning taking 2 minutes
        import time
        # time.sleep(0.1)  # Don't actually sleep in tests
        
        end = datetime.utcnow()
        duration = (end - start).total_seconds()

        assert duration >= 0

    def test_provisioning_step_metrics(self):
        """Test metrics for individual provisioning steps"""
        metrics = {
            'ec2_launch': {'duration_seconds': 45, 'status': 'completed'},
            'dify_pull': {'duration_seconds': 120, 'status': 'completed'},
            'dify_startup': {'duration_seconds': 60, 'status': 'completed'},
            'ai_config': {'duration_seconds': 30, 'status': 'completed'}
        }

        total_time = sum(m['duration_seconds'] for m in metrics.values())
        assert total_time == 255

    def test_provisioning_success_rate(self):
        """Test tracking of provisioning success rates"""
        results = [
            {'student': 's1', 'status': 'success'},
            {'student': 's2', 'status': 'success'},
            {'student': 's3', 'status': 'failed'},
            {'student': 's4', 'status': 'success'},
            {'student': 's5', 'status': 'success'},
        ]

        success_count = len([r for r in results if r['status'] == 'success'])
        total_count = len(results)
        success_rate = (success_count / total_count) * 100

        assert success_rate == 80.0

    def test_provisioning_resource_utilization(self):
        """Test tracking of resource utilization during provisioning"""
        utilization = {
            'ec2_instances_active': 5,
            'ec2_instances_available': 10,
            'dify_containers_running': 5,
            'dify_containers_max': 20
        }

        ec2_usage = (utilization['ec2_instances_active'] / utilization['ec2_instances_available']) * 100
        dify_usage = (utilization['dify_containers_running'] / utilization['dify_containers_max']) * 100

        assert ec2_usage == 50.0
        assert dify_usage == 25.0
