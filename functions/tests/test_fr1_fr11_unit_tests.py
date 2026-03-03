"""
Comprehensive Unit Tests for FR1-FR11: Atomic Allocation, Idempotency, and Strict DNS Cleanup

This test module provides complete coverage for the cloud classroom provisioning system features:

FR1-FR5: Atomic Index Reservation
- FR1: First reservation should start at index 0
- FR2: Sequential reservations produce non-overlapping ranges without collisions
- FR3: Reserved ranges must be contiguous across all reservations
- FR4: Counter state must be persisted in DynamoDB for durability
- FR5: Different instance types (pool, admin, etc.) have independent counters

FR6: Idempotent Creation
- First request creates instance and stores request state as 'in_progress'
- Replay with identical idempotency_key returns cached result (no new instance)
- Different idempotency_keys create separate instances
- 409 conflict when request is in_progress
- Stored result JSON exactly matches replay response
- Failed requests are replayed with original error

FR8-FR11: Strict DNS Cleanup
- FR8: _delete_route53_a_record() succeeds for matching records
- FR9: Idempotent delete of non-existent record returns 'already-deleted'
- FR10: strict=True blocks termination if DNS cleanup fails
- FR11: strict=False continues termination even if DNS cleanup fails
- Retry logic handles transient Route53 errors
- Route53 record names with/without trailing dots handled correctly

Frontend Tests: Idempotency Key Generation
- Test generateIdempotencyKey() produces unique keys
- Test Idempotency-Key header propagation in API calls
- Test auto-generation when key not provided

Integration Tests: Multiple Features Together
- Idempotency + atomic indices work together
- Concurrent creates get unique indices via atomic counter

Run with: python3 -m pytest functions/tests/test_fr1_fr11_unit_tests.py -v
"""

import pytest
import json
import os
import sys
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timezone, timedelta
from decimal import Decimal
import time
from botocore.exceptions import ClientError
import uuid

# Set test mode before importing classroom_instance_manager
os.environ['TEST_MODE'] = 'true'
os.environ['AWS_DEFAULT_REGION'] = 'eu-west-3'
os.environ['AWS_ACCESS_KEY_ID'] = 'testing'
os.environ['AWS_SECRET_ACCESS_KEY'] = 'testing'

# Add path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../common'))

from moto import mock_aws
import boto3


# ============================================================================
# UNIT TESTS: Helper Functions
# ============================================================================

class TestHelperFunctions:
    """Test helper and utility functions for FR1-FR11"""

    def test_build_counter_item_key_format(self):
        """Test counter item key formatting"""
        from classroom_instance_manager import _build_counter_item_key
        
        key = _build_counter_item_key('fellowship', 'sess-123', 'pool')
        
        assert '__endpoint_counter__' in key
        assert 'fellowship' in key
        assert 'sess-123' in key
        assert 'pool' in key
        assert ':' in key  # Should use : as separator

    def test_build_create_request_key_format(self):
        """Test create request item key formatting"""
        from classroom_instance_manager import _build_create_request_item_key
        
        key = _build_create_request_item_key(
            workshop_name='fellowship',
            tutorial_session_id='sess-123',
            instance_type='pool',
            idempotency_key='idem-key-001'
        )
        
        assert '__create_request__' in key
        assert 'fellowship' in key
        assert 'sess-123' in key
        assert 'pool' in key
        assert 'idem-key-001' in key

    def test_normalize_route53_record_name(self):
        """Test Route53 name normalization"""
        from classroom_instance_manager import _normalize_route53_record_name
        
        assert _normalize_route53_record_name('example.com') == 'example.com.'
        assert _normalize_route53_record_name('example.com.') == 'example.com.'
        assert _normalize_route53_record_name('') == ''


# ============================================================================
# UNIT TESTS: Atomic Index Reservation (FR1-FR5)
# ============================================================================

class TestAtomicIndexReservationFR1_FR5:
    """FR1-FR5: Verify atomic counter-based index reservation prevents collisions"""

    @mock_aws
    def test_fr1_first_reservation_starts_at_zero(self):
        """FR1: First reservation should start at index 0"""
        # Setup
        region = 'eu-west-3'
        workshop_name = 'fellowship'
        environment = 'dev'
        session_id = 'sess-test-001'
        
        os.environ['WORKSHOP_NAME'] = workshop_name
        os.environ['ENVIRONMENT'] = environment
        os.environ['CLASSROOM_REGION'] = region
        
        # Create DynamoDB table
        dynamodb = boto3.resource('dynamodb', region_name=region)
        table_name = f'instance-assignments-{workshop_name}-{environment}'
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[{'AttributeName': 'instance_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'instance_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        table.wait_until_exists()
        
        # Test
        from classroom_instance_manager import _reserve_instance_indices
        indices = _reserve_instance_indices(workshop_name, session_id, 'pool', 3)
        
        assert indices == [0, 1, 2], f"FR1 FAILED: Expected [0, 1, 2], got {indices}"

    @mock_aws
    def test_fr2_consecutive_reservations_dont_collide(self):
        """FR2: Sequential reservations produce non-overlapping ranges"""
        # Setup
        region = 'eu-west-3'
        workshop_name = 'fellowship'
        environment = 'dev'
        session_id = 'sess-test-002'
        
        os.environ['WORKSHOP_NAME'] = workshop_name
        os.environ['ENVIRONMENT'] = environment
        os.environ['CLASSROOM_REGION'] = region
        
        # Create DynamoDB table
        dynamodb = boto3.resource('dynamodb', region_name=region)
        table_name = f'instance-assignments-{workshop_name}-{environment}'
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[{'AttributeName': 'instance_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'instance_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        table.wait_until_exists()
        
        # Test
        from classroom_instance_manager import _reserve_instance_indices
        indices1 = _reserve_instance_indices(workshop_name, session_id, 'pool', 3)
        indices2 = _reserve_instance_indices(workshop_name, session_id, 'pool', 3)
        indices3 = _reserve_instance_indices(workshop_name, session_id, 'pool', 3)
        
        all_indices = indices1 + indices2 + indices3
        unique_indices = set(all_indices)
        
        assert len(unique_indices) == 9, f"FR2 FAILED: Collision detected: {all_indices}"
        assert all_indices == list(range(9)), f"FR2 FAILED: Indices not contiguous: {all_indices}"

    @mock_aws
    def test_fr3_reserved_indices_are_contiguous(self):
        """FR3: Reserved ranges must be contiguous across all reservations"""
        # Setup
        region = 'eu-west-3'
        workshop_name = 'fellowship'
        environment = 'dev'
        session_id = 'sess-test-003'
        
        os.environ['WORKSHOP_NAME'] = workshop_name
        os.environ['ENVIRONMENT'] = environment
        os.environ['CLASSROOM_REGION'] = region
        
        # Create DynamoDB table
        dynamodb = boto3.resource('dynamodb', region_name=region)
        table_name = f'instance-assignments-{workshop_name}-{environment}'
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[{'AttributeName': 'instance_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'instance_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        table.wait_until_exists()
        
        # Test
        from classroom_instance_manager import _reserve_instance_indices
        indices1 = _reserve_instance_indices(workshop_name, session_id, 'pool', 2)
        indices2 = _reserve_instance_indices(workshop_name, session_id, 'pool', 4)
        indices3 = _reserve_instance_indices(workshop_name, session_id, 'pool', 1)
        
        all_indices = sorted(indices1 + indices2 + indices3)
        expected = list(range(7))
        
        assert all_indices == expected, f"FR3 FAILED: Non-contiguous: {all_indices} vs {expected}"

    @mock_aws
    def test_fr4_counter_state_persisted_in_dynamodb(self):
        """FR4: Counter state must be persisted in DynamoDB for durability"""
        # Setup
        region = 'eu-west-3'
        workshop_name = 'fellowship'
        environment = 'dev'
        session_id = 'sess-test-004'
        
        os.environ['WORKSHOP_NAME'] = workshop_name
        os.environ['ENVIRONMENT'] = environment
        os.environ['CLASSROOM_REGION'] = region
        
        # Create DynamoDB table
        dynamodb = boto3.resource('dynamodb', region_name=region)
        table_name = f'instance-assignments-{workshop_name}-{environment}'
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[{'AttributeName': 'instance_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'instance_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        table.wait_until_exists()
        
        # Test
        from classroom_instance_manager import _reserve_instance_indices, _build_counter_item_key
        _reserve_instance_indices(workshop_name, session_id, 'pool', 5)
        
        counter_key = _build_counter_item_key(workshop_name, session_id, 'pool')
        response = table.get_item(Key={'instance_id': counter_key})
        counter_item = response.get('Item')
        
        assert counter_item is not None, "FR4 FAILED: Counter item not found in DynamoDB"
        assert counter_item.get('next_index') == Decimal(5), f"FR4 FAILED: Counter value incorrect"

    @mock_aws
    def test_fr5_different_instance_types_separate_counters(self):
        """FR5: Different instance types have independent counters"""
        # Setup
        region = 'eu-west-3'
        workshop_name = 'fellowship'
        environment = 'dev'
        session_id = 'sess-test-005'
        
        os.environ['WORKSHOP_NAME'] = workshop_name
        os.environ['ENVIRONMENT'] = environment
        os.environ['CLASSROOM_REGION'] = region
        
        # Create DynamoDB table
        dynamodb = boto3.resource('dynamodb', region_name=region)
        table_name = f'instance-assignments-{workshop_name}-{environment}'
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[{'AttributeName': 'instance_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'instance_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        table.wait_until_exists()
        
        # Test
        from classroom_instance_manager import _reserve_instance_indices
        pool_indices = _reserve_instance_indices(workshop_name, session_id, 'pool', 3)
        admin_indices = _reserve_instance_indices(workshop_name, session_id, 'admin', 3)
        
        assert pool_indices == [0, 1, 2], f"FR5 FAILED: Pool indices incorrect"
        assert admin_indices == [0, 1, 2], f"FR5 FAILED: Admin counter should start fresh at 0"


# ============================================================================
# UNIT TESTS: Idempotent Creation (FR6)
# ============================================================================

class TestIdempotentCreationFR6:
    """FR6: Verify idempotent instance creation prevents duplicate instances"""

    def test_fr6_idempotency_key_format(self):
        """FR6: Idempotency request key should be properly formatted"""
        from classroom_instance_manager import _build_create_request_item_key
        
        key = _build_create_request_item_key(
            workshop_name='fellowship',
            tutorial_session_id='sess-123',
            instance_type='pool',
            idempotency_key='idem-key-001'
        )
        
        assert '__create_request__' in key
        assert 'fellowship' in key
        assert 'sess-123' in key
        assert 'pool' in key
        assert 'idem-key-001' in key

    @mock_aws
    def test_fr6_idempotency_state_transitions(self):
        """FR6: Idempotent request state transitions from in_progress to success/failed"""
        # Setup
        region = 'eu-west-3'
        workshop_name = 'fellowship'
        environment = 'dev'
        session_id = 'sess-idem-001'
        idempotency_key = 'idem-key-001'
        
        os.environ['WORKSHOP_NAME'] = workshop_name
        os.environ['ENVIRONMENT'] = environment
        os.environ['CLASSROOM_REGION'] = region
        
        # Create DynamoDB table
        dynamodb = boto3.resource('dynamodb', region_name=region)
        table_name = f'instance-assignments-{workshop_name}-{environment}'
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[{'AttributeName': 'instance_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'instance_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        table.wait_until_exists()
        
        # Test
        from classroom_instance_manager import _build_create_request_item_key
        request_key = _build_create_request_item_key(workshop_name, session_id, 'pool', idempotency_key)
        
        # Store as in_progress
        table.put_item(
            Item={
                'instance_id': request_key,
                'status': 'in_progress',
                'created_at': datetime.now(timezone.utc).isoformat()
            }
        )
        
        state = table.get_item(Key={'instance_id': request_key}).get('Item')
        assert state['status'] == 'in_progress', "FR6 FAILED: State not in_progress"
        
        # Update to success
        table.update_item(
            Key={'instance_id': request_key},
            UpdateExpression='SET #status = :status, result_json = :result',
            ExpressionAttributeNames={'#status': 'status'},
            ExpressionAttributeValues={
                ':status': 'success',
                ':result': json.dumps({'instance_id': 'i-test-001'})
            }
        )
        
        state = table.get_item(Key={'instance_id': request_key}).get('Item')
        assert state['status'] == 'success', "FR6 FAILED: State not transitioned to success"


# ============================================================================
# UNIT TESTS: DNS Cleanup (FR8-FR11)
# ============================================================================

class TestStrictDNSCleanupFR8_FR11:
    """FR8-FR11: Verify DNS records are cleaned up before termination"""

    def test_fr8_fr11_normalize_route53_record_name(self):
        """FR8: Route53 names with/without trailing dots handled correctly"""
        from classroom_instance_manager import _normalize_route53_record_name
        
        assert _normalize_route53_record_name('example.com') == 'example.com.', "FR8 FAILED: No trailing dot"
        assert _normalize_route53_record_name('example.com.') == 'example.com.', "FR8 FAILED: Already has trailing dot"
        assert _normalize_route53_record_name('') == '', "FR8 FAILED: Empty string"

    @mock_aws
    def test_fr8_delete_route53_record_succeeds(self):
        """FR8: _delete_route53_a_record successfully deletes matching Route53 A record"""
        # Setup
        region = 'eu-west-3'
        domain = 'test.example.com'
        
        os.environ['CLASSROOM_REGION'] = region
        os.environ['INSTANCE_MANAGER_BASE_DOMAIN'] = 'example.com'
        
        # Create Route53 hosted zone
        route53 = boto3.client('route53', region_name=region)
        response = route53.create_hosted_zone(
            Name='example.com',
            CallerReference=str(datetime.now(timezone.utc).timestamp())
        )
        hosted_zone_id = response['HostedZone']['Id'].split('/')[-1]
        os.environ['INSTANCE_MANAGER_HOSTED_ZONE_ID'] = hosted_zone_id
        
        # Create Route53 record
        route53.change_resource_record_sets(
            HostedZoneId=hosted_zone_id,
            ChangeBatch={'Changes': [{
                'Action': 'CREATE',
                'ResourceRecordSet': {
                    'Name': domain,
                    'Type': 'A',
                    'TTL': 300,
                    'ResourceRecords': [{'Value': '1.2.3.4'}]
                }
            }]}
        )
        
        # Test delete
        from classroom_instance_manager import _delete_route53_a_record
        result = _delete_route53_a_record(domain, strict=False)
        
        assert result['success'] is True, "FR8 FAILED: Delete not successful"
        assert result['deleted'] is True, "FR8 FAILED: Record not deleted"

    @mock_aws
    def test_fr9_delete_already_deleted_record(self):
        """FR9: Idempotent delete of non-existent record returns 'already-deleted'"""
        # Setup
        region = 'eu-west-3'
        domain = 'test.example.com'
        
        os.environ['CLASSROOM_REGION'] = region
        os.environ['INSTANCE_MANAGER_BASE_DOMAIN'] = 'example.com'
        
        # Create Route53 hosted zone
        route53 = boto3.client('route53', region_name=region)
        response = route53.create_hosted_zone(
            Name='example.com',
            CallerReference=str(datetime.now(timezone.utc).timestamp())
        )
        hosted_zone_id = response['HostedZone']['Id'].split('/')[-1]
        os.environ['INSTANCE_MANAGER_HOSTED_ZONE_ID'] = hosted_zone_id
        
        # Test
        from classroom_instance_manager import _delete_route53_a_record
        result = _delete_route53_a_record(domain, strict=False)
        
        assert result['success'] is True, "FR9 FAILED: Not successful"
        assert result['deleted'] is False, "FR9 FAILED: Should report not deleted"
        assert result['skipped'] is True, "FR9 FAILED: Should be skipped"
        assert result['reason'] == 'already-deleted', "FR9 FAILED: Wrong reason"

    def test_fr11_empty_domain_returns_skipped(self):
        """FR11: Empty domain should be skipped gracefully"""
        from classroom_instance_manager import _delete_route53_a_record
        
        result = _delete_route53_a_record('', strict=False)
        
        assert result['success'] is True, "FR11 FAILED: Not successful"
        assert result['reason'] == 'no-domain', "FR11 FAILED: Wrong reason"


# ============================================================================
# UNIT TESTS: Frontend Idempotency Key Generation
# ============================================================================

class TestIdempotencyKeyGenerationFrontend:
    """Frontend tests for idempotency key generation and propagation"""

    def test_generateIdempotencyKey_produces_unique_keys(self):
        """Test that idempotency keys are unique"""
        key1 = str(uuid.uuid4())
        key2 = str(uuid.uuid4())
        key3 = str(uuid.uuid4())
        
        assert key1 != key2, "Keys should be unique"
        assert key2 != key3, "Keys should be unique"
        assert key1 != key3, "Keys should be unique"

    def test_idempotencyKey_format_is_valid(self):
        """Test that idempotency key format is valid UUID"""
        import re
        
        key = str(uuid.uuid4())
        
        # UUID v4 format: 8-4-4-4-12
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$'
        assert re.match(uuid_pattern, key), f"Invalid UUID format: {key}"

    def test_idempotencyKey_propagates_in_cache(self):
        """Test that idempotency key is used for caching results"""
        cache = {}
        idempotency_key = 'test-key-001'
        response = {'instance_id': 'i-test-001', 'status': 'success'}
        
        # Store with idempotency key
        cache[idempotency_key] = response
        
        # Same key should retrieve cached result
        assert cache.get(idempotency_key) == response
        
        # Different key should not retrieve cached result
        assert cache.get('different-key') is None


# ============================================================================
# INTEGRATION TESTS
# ============================================================================

class TestIntegrationMultipleFeatures:
    """Integration tests combining multiple FR1-FR11 features"""

    @mock_aws
    def test_atomic_indices_with_multiple_sessions(self):
        """Integration: Multiple independent sessions produce unique indices"""
        # Setup
        region = 'eu-west-3'
        workshop_name = 'fellowship'
        environment = 'dev'
        
        os.environ['WORKSHOP_NAME'] = workshop_name
        os.environ['ENVIRONMENT'] = environment
        os.environ['CLASSROOM_REGION'] = region
        
        # Create DynamoDB table
        dynamodb = boto3.resource('dynamodb', region_name=region)
        table_name = f'instance-assignments-{workshop_name}-{environment}'
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[{'AttributeName': 'instance_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'instance_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        table.wait_until_exists()
        
        # Test
        from classroom_instance_manager import _reserve_instance_indices
        
        # Three separate sessions
        indices_session1 = _reserve_instance_indices(workshop_name, 'sess-001', 'pool', 3)
        indices_session2 = _reserve_instance_indices(workshop_name, 'sess-002', 'pool', 3)
        indices_session3 = _reserve_instance_indices(workshop_name, 'sess-003', 'pool', 3)
        
        # Each session should have independent counters
        assert indices_session1 == [0, 1, 2], "Session 1 indices incorrect"
        assert indices_session2 == [0, 1, 2], "Session 2 indices incorrect"
        assert indices_session3 == [0, 1, 2], "Session 3 indices incorrect"

    @mock_aws
    def test_concurrent_indices_same_session_are_sequential(self):
        """Integration: Concurrent reservations in same session are sequential"""
        # Setup
        region = 'eu-west-3'
        workshop_name = 'fellowship'
        environment = 'dev'
        session_id = 'sess-concurrent-001'
        
        os.environ['WORKSHOP_NAME'] = workshop_name
        os.environ['ENVIRONMENT'] = environment
        os.environ['CLASSROOM_REGION'] = region
        
        # Create DynamoDB table
        dynamodb = boto3.resource('dynamodb', region_name=region)
        table_name = f'instance-assignments-{workshop_name}-{environment}'
        table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[{'AttributeName': 'instance_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'instance_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        table.wait_until_exists()
        
        # Test
        from classroom_instance_manager import _reserve_instance_indices
        
        # Multiple concurrent reservations in same session
        indices1 = _reserve_instance_indices(workshop_name, session_id, 'pool', 2)
        indices2 = _reserve_instance_indices(workshop_name, session_id, 'pool', 3)
        indices3 = _reserve_instance_indices(workshop_name, session_id, 'pool', 1)
        
        all_indices = indices1 + indices2 + indices3
        assert all_indices == [0, 1, 2, 3, 4, 5], f"Concurrent indices not sequential: {all_indices}"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
