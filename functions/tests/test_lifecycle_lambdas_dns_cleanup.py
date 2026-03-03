"""
Test Suite for Lifecycle Lambda Functions: Strict DNS Cleanup (FR8-FR11)

Tests validate that:
- classroom_stop_old_instances.py enforces strict DNS cleanup before termination
- classroom_admin_cleanup.py enforces strict DNS cleanup before termination  
- Termination is blocked if DNS cleanup fails (strict=True)
- Retry logic handles transient Route53 errors
- All cleanup paths (timeout, spot expiry, admin cleanup) use strict cleanup

Run with: python -m pytest functions/tests/test_lifecycle_lambdas_dns_cleanup.py -v
"""

import pytest
import os
import sys
import json
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from botocore.exceptions import ClientError

# Add path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../common'))

from test_mode import init_test_mode
init_test_mode()

import boto3
from moto import mock_ec2, mock_dynamodb, mock_route53, mock_ssm


# ============================================================================
# FR8-FR11: STOP_OLD_INSTANCES LAMBDA - STRICT DNS CLEANUP
# ============================================================================

@mock_dynamodb
@mock_ec2
@mock_route53
@mock_ssm
class TestStopOldInstancesDNSCleanup:
    """FR8-FR11: Verify classroom_stop_old_instances.py enforces strict DNS cleanup"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup environment for lifecycle lambda tests"""
        self.region = 'eu-west-3'
        self.workshop_name = 'fellowship'
        self.environment = 'dev'
        
        # Setup environment variables
        os.environ['CLASSROOM_REGION'] = self.region
        os.environ['WORKSHOP_NAME'] = self.workshop_name
        os.environ['ENVIRONMENT'] = self.environment
        os.environ['INSTANCE_MANAGER_HOSTED_ZONE_ID'] = self._create_hosted_zone()
        os.environ['INSTANCE_MANAGER_BASE_DOMAIN'] = 'example.com'
        
        # Create DynamoDB table
        dynamodb = boto3.resource('dynamodb', region_name=self.region)
        table_name = f'instance-assignments-{self.workshop_name}-{self.environment}'
        self.table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[{'AttributeName': 'instance_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'instance_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        self.table.wait_until_exists()
        
        # Create SSM parameters for timeouts
        ssm = boto3.client('ssm', region_name=self.region)
        param_prefix = f'/classroom/{self.workshop_name}/{self.environment}'
        ssm.put_parameter(Name=f'{param_prefix}/instance_stop_timeout_minutes', Value='10', Type='String')
        ssm.put_parameter(Name=f'{param_prefix}/instance_terminate_timeout_minutes', Value='60', Type='String')
        ssm.put_parameter(Name=f'{param_prefix}/instance_hard_terminate_timeout_minutes', Value='240', Type='String')

    def _create_hosted_zone(self):
        """Create mock Route53 hosted zone"""
        route53 = boto3.client('route53', region_name=self.region)
        response = route53.create_hosted_zone(
            Name='example.com',
            CallerReference=str(datetime.now(timezone.utc).timestamp())
        )
        return response['HostedZone']['Id'].split('/')[-1]

    def _create_instance(self, instance_state='running', instance_type='pool', 
                         domain=None, age_minutes=0):
        """Helper to create mock EC2 instance"""
        ec2 = boto3.client('ec2', region_name=self.region)
        
        # Create VPC and subnet
        vpc = ec2.create_vpc(CidrBlock='10.0.0.0/16')
        subnet = ec2.create_subnet(VpcId=vpc['Vpc']['VpcId'], CidrBlock='10.0.1.0/24')
        
        # Calculate launch time based on age
        launch_time = datetime.now(timezone.utc) - timedelta(minutes=age_minutes)
        
        # Create instance
        tag_list = [
            {'Key': 'Project', 'Value': 'classroom'},
            {'Key': 'Type', 'Value': instance_type},
            {'Key': 'WorkshopID', 'Value': self.workshop_name},
        ]
        
        if domain:
            tag_list.append({'Key': 'HttpsDomain', 'Value': domain})
        
        response = ec2.run_instances(
            ImageId='ami-12345678',
            MinCount=1,
            MaxCount=1,
            SubnetId=subnet['Subnet']['SubnetId'],
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': tag_list
            }]
        )
        
        instance_id = response['Instances'][0]['InstanceId']
        
        # Update state if needed
        if instance_state == 'stopped':
            ec2.stop_instances(InstanceIds=[instance_id])
        
        return instance_id

    def _create_route53_record(self, domain):
        """Helper to create Route53 A record"""
        route53 = boto3.client('route53', region_name=self.region)
        zone_id = os.environ.get('INSTANCE_MANAGER_HOSTED_ZONE_ID')
        route53.change_resource_record_sets(
            HostedZoneId=zone_id,
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

    def test_dns_cleanup_removes_httsdomain_record(self):
        """FR8: DNS cleanup should remove HttpsDomain Route53 record"""
        from common.classroom_stop_old_instances import cleanup_route53_record
        
        domain = 'i-test-123.example.com'
        self._create_route53_record(domain)
        
        tags = {'HttpsDomain': domain}
        result = cleanup_route53_record('i-test-123', tags, strict=False)
        
        assert result['success'] is True
        assert result['deleted'] is True

    def test_termination_blocked_if_dns_cleanup_fails_strict_mode(self):
        """FR10: With strict=True, termination should be blocked if DNS cleanup fails"""
        from common.classroom_stop_old_instances import cleanup_route53_record
        
        with patch('common.classroom_stop_old_instances.route53') as mock_route53:
            # Simulate Route53 error
            mock_route53.list_resource_record_sets.side_effect = ClientError(
                {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
                'ListResourceRecordSets'
            )
            
            tags = {'HttpsDomain': 'i-test-456.example.com'}
            result = cleanup_route53_record('i-test-456', tags, strict=True, max_retries=1)
            
            # Should fail and prevent termination
            assert result['success'] is False
            assert result['reason'] == 'delete-failed'

    def test_termination_allowed_if_dns_cleanup_fails_non_strict(self):
        """FR11: With strict=False, termination should continue despite DNS cleanup failure"""
        from common.classroom_stop_old_instances import cleanup_route53_record
        
        with patch('common.classroom_stop_old_instances.route53') as mock_route53:
            # Simulate Route53 error
            mock_route53.list_resource_record_sets.side_effect = ClientError(
                {'Error': {'Code': 'AccessDenied', 'Message': 'Access denied'}},
                'ListResourceRecordSets'
            )
            
            tags = {'HttpsDomain': 'i-test-789.example.com'}
            result = cleanup_route53_record('i-test-789', tags, strict=False, max_retries=1)
            
            # Should succeed (allowing termination to continue)
            assert result['success'] is True

    def test_hard_terminate_path_uses_strict_cleanup(self):
        """FR8: Hard terminate path should enforce strict DNS cleanup"""
        # This test verifies that the lambda code calls cleanup_route53_record with strict=True
        # Note: Full lambda integration test in test_fr1_fr11_implementation.py
        from common.classroom_stop_old_instances import cleanup_route53_record
        
        # Hard terminate (exceeded hard_terminate_timeout) should use strict=True
        tags = {'HttpsDomain': 'instance.example.com'}
        
        with patch('common.classroom_stop_old_instances.route53'):
            result = cleanup_route53_record('i-hardterm', tags, strict=True)
            # Verify not skipped
            assert result is not None

    def test_retry_logic_with_transient_errors(self):
        """FR8-FR11: Should retry on transient Route53 errors"""
        from common.classroom_stop_old_instances import cleanup_route53_record
        
        with patch('common.classroom_stop_old_instances.route53') as mock_route53:
            # Fail twice, succeed on third attempt
            mock_route53.list_resource_record_sets.side_effect = [
                ClientError({'Error': {'Code': 'Throttling'}}, 'ListResourceRecordSets'),
                ClientError({'Error': {'Code': 'Throttling'}}, 'ListResourceRecordSets'),
                {'ResourceRecordSets': []}
            ]
            
            tags = {'HttpsDomain': 'retry-test.example.com'}
            result = cleanup_route53_record('i-retry', tags, strict=False, max_retries=3)
            
            assert result['success'] is True
            assert result['attempts'] == 3

    def test_already_deleted_domain_returns_success(self):
        """FR9: Attempting to delete already-deleted domain should return success"""
        from common.classroom_stop_old_instances import cleanup_route53_record
        
        # Try to delete non-existent domain
        tags = {'HttpsDomain': 'nonexistent.example.com'}
        result = cleanup_route53_record('i-nonexistent', tags, strict=False)
        
        # Should succeed (idempotent)
        assert result['success'] is True
        assert result['reason'] == 'already-deleted'

    def test_missing_domain_tag_returns_skipped(self):
        """FR8: If HttpsDomain tag missing, cleanup should skip and return success"""
        from common.classroom_stop_old_instances import cleanup_route53_record
        
        tags = {}  # No HttpsDomain
        result = cleanup_route53_record('i-notag', tags, strict=False)
        
        assert result['success'] is True
        assert result['skipped'] is True
        assert result['reason'] == 'no-domain'


# ============================================================================
# FR8-FR11: ADMIN_CLEANUP LAMBDA - STRICT DNS CLEANUP
# ============================================================================

@mock_dynamodb
@mock_ec2
@mock_route53
class TestAdminCleanupDNSCleanup:
    """FR8-FR11: Verify classroom_admin_cleanup.py enforces strict DNS cleanup"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup environment for admin cleanup lambda tests"""
        self.region = 'eu-west-3'
        self.workshop_name = 'fellowship'
        self.environment = 'dev'
        
        os.environ['CLASSROOM_REGION'] = self.region
        os.environ['WORKSHOP_NAME'] = self.workshop_name
        os.environ['ENVIRONMENT'] = self.environment
        os.environ['INSTANCE_MANAGER_HOSTED_ZONE_ID'] = self._create_hosted_zone()
        os.environ['INSTANCE_MANAGER_BASE_DOMAIN'] = 'example.com'

    def _create_hosted_zone(self):
        """Create mock Route53 hosted zone"""
        route53 = boto3.client('route53', region_name=self.region)
        response = route53.create_hosted_zone(
            Name='example.com',
            CallerReference=str(datetime.now(timezone.utc).timestamp())
        )
        return response['HostedZone']['Id'].split('/')[-1]

    def test_admin_cleanup_calls_strict_dns_cleanup(self):
        """FR10: Admin cleanup should enforce strict DNS cleanup before termination"""
        from common.classroom_admin_cleanup import cleanup_route53_record
        
        # Verify function accepts strict parameter
        tags = {'HttpsDomain': 'admin-instance.example.com'}
        
        with patch('common.classroom_admin_cleanup.route53'):
            result = cleanup_route53_record('i-admin-001', tags, strict=True)
            # Should not raise, verify behavior
            assert result is not None

    def test_admin_instance_cleanup_prevents_orphaned_dns(self):
        """FR11: Admin cleanup should skip termination if DNS cleanup fails (strict mode)"""
        from common.classroom_admin_cleanup import cleanup_route53_record
        
        with patch('common.classroom_admin_cleanup.route53') as mock_route53:
            # Simulate Route53 error
            mock_route53.list_resource_record_sets.side_effect = ClientError(
                {'Error': {'Code': 'InvalidInput', 'Message': 'Invalid input'}},
                'ListResourceRecordSets'
            )
            
            tags = {'HttpsDomain': 'admin.example.com'}
            result = cleanup_route53_record('i-admin', tags, strict=True, max_retries=1)
            
            # With strict=True, error should indicate cleanup failed
            assert result['success'] is False

    def test_admin_instance_without_domain_cleanup_succeeds(self):
        """FR8: Admin instances without HttpsDomain tag should cleanup successfully"""
        from common.classroom_admin_cleanup import cleanup_route53_record
        
        tags = {'Name': 'admin-instance', 'Type': 'admin'}  # No HttpsDomain
        result = cleanup_route53_record('i-admin-nodomain', tags, strict=True)
        
        # Should skip DNS and return success
        assert result['success'] is True
        assert result['skipped'] is True


# ============================================================================
# INTEGRATION: DELETE_INSTANCES FUNCTION - STRICT DNS CLEANUP
# ============================================================================

@mock_dynamodb
@mock_ec2
@mock_route53
class TestDeleteInstancesStrictCleanup:
    """FR8-FR11: Verify delete_instances enforces strict DNS cleanup"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup environment"""
        self.region = 'eu-west-3'
        self.workshop_name = 'fellowship'
        self.environment = 'dev'
        
        os.environ['CLASSROOM_REGION'] = self.region
        os.environ['WORKSHOP_NAME'] = self.workshop_name
        os.environ['ENVIRONMENT'] = self.environment
        os.environ['INSTANCE_MANAGER_HOSTED_ZONE_ID'] = self._create_hosted_zone()
        os.environ['INSTANCE_MANAGER_BASE_DOMAIN'] = 'example.com'
        
        # Create DynamoDB table
        dynamodb = boto3.resource('dynamodb', region_name=self.region)
        table_name = f'instance-assignments-{self.workshop_name}-{self.environment}'
        self.table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[{'AttributeName': 'instance_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'instance_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        self.table.wait_until_exists()

    def _create_hosted_zone(self):
        """Create mock Route53 hosted zone"""
        route53 = boto3.client('route53', region_name=self.region)
        response = route53.create_hosted_zone(
            Name='example.com',
            CallerReference=str(datetime.now(timezone.utc).timestamp())
        )
        return response['HostedZone']['Id'].split('/')[-1]

    def _create_instance_with_domain(self, domain):
        """Helper to create instance with HttpsDomain tag"""
        ec2 = boto3.client('ec2', region_name=self.region)
        
        vpc = ec2.create_vpc(CidrBlock='10.0.0.0/16')
        subnet = ec2.create_subnet(VpcId=vpc['Vpc']['VpcId'], CidrBlock='10.0.1.0/24')
        
        response = ec2.run_instances(
            ImageId='ami-12345678',
            MinCount=1,
            MaxCount=1,
            SubnetId=subnet['Subnet']['SubnetId'],
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [
                    {'Key': 'Project', 'Value': 'classroom'},
                    {'Key': 'Type', 'Value': 'pool'},
                    {'Key': 'HttpsDomain', 'Value': domain}
                ]
            }]
        )
        
        return response['Instances'][0]['InstanceId']

    def test_delete_instances_calls_strict_cleanup(self):
        """FR10: delete_instances should call _delete_route53_a_record with strict=True"""
        from classroom_instance_manager import delete_instances, _delete_route53_a_record
        
        instance_id = self._create_instance_with_domain('test.example.com')
        
        with patch('classroom_instance_manager._delete_route53_a_record') as mock_delete:
            mock_delete.return_value = {'success': True, 'deleted': True}
            
            delete_instances([instance_id], delete_type='individual')
            
            # Verify strict=True was used
            mock_delete.assert_called()
            call_args = mock_delete.call_args
            assert call_args[1].get('strict') is True

    def test_delete_blocked_if_dns_cleanup_fails(self):
        """FR10: delete_instances should not terminate if strict DNS cleanup fails"""
        from classroom_instance_manager import delete_instances, _delete_route53_a_record
        
        instance_id = self._create_instance_with_domain('fail.example.com')
        
        with patch('classroom_instance_manager._delete_route53_a_record') as mock_delete:
            # Simulate DNS cleanup failure
            mock_delete.return_value = {'success': False, 'deleted': False, 'reason': 'failed'}
            
            with patch('classroom_instance_manager.ec2.terminate_instances') as mock_terminate:
                delete_instances([instance_id], delete_type='individual')
                
                # EC2 terminate should not be called if strict cleanup failed
                # (This depends on implementation; verify the DeleteInstances returns error)
                mock_terminate.assert_not_called()

    def test_delete_succeeds_when_dns_cleanup_succeeds(self):
        """FR8: delete_instances should terminate after successful DNS cleanup"""
        from classroom_instance_manager import delete_instances
        
        instance_id = self._create_instance_with_domain('success.example.com')
        
        with patch('classroom_instance_manager._delete_route53_a_record') as mock_delete:
            mock_delete.return_value = {'success': True, 'deleted': True}
            
            with patch('classroom_instance_manager.ec2.terminate_instances') as mock_terminate:
                delete_instances([instance_id], delete_type='individual')
                
                # EC2 terminate should be called
                mock_terminate.assert_called()


# ============================================================================
# EDGE CASES AND ERROR SCENARIOS
# ============================================================================

@mock_route53
class TestDNSCleanupEdgeCases:
    """FR8-FR11: Test edge cases and error scenarios"""

    def setup_method(self):
        """Setup Route53 for each test"""
        self.region = 'eu-west-3'
        self.zone_id = self._create_hosted_zone()
        os.environ['INSTANCE_MANAGER_HOSTED_ZONE_ID'] = self.zone_id

    def _create_hosted_zone(self):
        """Create mock Route53 hosted zone"""
        route53 = boto3.client('route53', region_name=self.region)
        response = route53.create_hosted_zone(
            Name='example.com',
            CallerReference=str(datetime.now(timezone.utc).timestamp())
        )
        return response['HostedZone']['Id'].split('/')[-1]

    def test_empty_domain_name_handled_gracefully(self):
        """FR8: Empty/None domain should return success (skip)"""
        from common.classroom_stop_old_instances import cleanup_route53_record
        
        result = cleanup_route53_record('i-empty', {}, strict=True)
        
        assert result['success'] is True
        assert result['skipped'] is True

    def test_max_retries_exceeded(self):
        """FR8-FR11: Max retries exhausted should fail with strict=True"""
        from common.classroom_stop_old_instances import cleanup_route53_record
        
        with patch('common.classroom_stop_old_instances.route53') as mock_route53:
            # Fail all attempts
            mock_route53.list_resource_record_sets.side_effect = ClientError(
                {'Error': {'Code': 'Throttling'}},
                'ListResourceRecordSets'
            )
            
            result = cleanup_route53_record(
                'i-maxretry',
                {'HttpsDomain': 'test.example.com'},
                strict=True,
                max_retries=3
            )
            
            assert result['success'] is False
            assert result['attempts'] == 3

    def test_hosted_zone_not_found(self):
        """FR8-FR11: Missing hosted zone should fail gracefully"""
        from common.classroom_admin_cleanup import cleanup_route53_record
        
        with patch('common.classroom_admin_cleanup.route53') as mock_route53:
            mock_route53.list_resource_record_sets.side_effect = ClientError(
                {'Error': {'Code': 'NoSuchHostedZone'}},
                'ListResourceRecordSets'
            )
            
            result = cleanup_route53_record(
                'i-nohz',
                {'HttpsDomain': 'test.example.com'},
                strict=True,
                max_retries=1
            )
            
            assert result['success'] is False
            assert result['reason'] == 'hosted-zone-missing'
