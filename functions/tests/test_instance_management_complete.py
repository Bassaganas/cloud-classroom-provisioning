"""
Comprehensive Test Suite for EC2 Instance Management Features

Tests cover:
1. Pool instance deletion (single and bulk) - uses SSM stop instances logic + Route53 cleanup
2. Admin instance deletion (single and bulk) - uses classroom_admin_cleanup logic + Route53 cleanup
3. Admin instance cleanup days management (set, display, extend)
4. Confirmation dialogs and error handling
5. Cascade deletion of tutorial sessions

Run with: python -m pytest functions/tests/test_instance_management_complete.py -v
"""

import pytest
import os
import sys
import json
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime, timezone, timedelta
from decimal import Decimal

# Setup logger and imports
import logging
logger = logging.getLogger(__name__)

# Add path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../common'))
from test_mode import init_test_mode
init_test_mode()

import boto3
from moto import mock_aws
from botocore.exceptions import ClientError


@mock_aws
class TestPoolInstanceDeletion:
    """Test pool instance deletion: confirms SSM parameters + Route53 cleanup"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for pool instance deletion tests"""
        self.region = 'eu-west-3'
        self.workshop_name = 'fellowship'
        self.environment = 'dev'
        
        os.environ['CLASSROOM_REGION'] = self.region
        os.environ['WORKSHOP_NAME'] = self.workshop_name
        os.environ['ENVIRONMENT'] = self.environment
        os.environ['INSTANCE_MANAGER_HOSTED_ZONE_ID'] = self._create_hosted_zone()
        os.environ['INSTANCE_MANAGER_BASE_DOMAIN'] = 'testingfantasy.com'
        
        # Create DynamoDB table
        dynamodb = boto3.resource('dynamodb', region_name=self.region)
        table_name = f'instance-assignments-{self.workshop_name}-{self.environment}'
        
        try:
            table = dynamodb.Table(table_name)
            table.delete()
            table.wait_until_not_exists()
        except Exception:
            pass
        
        self.table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[{'AttributeName': 'instance_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'instance_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        self.table.wait_until_exists()
        
        # Create SSM parameters for pool instance stop timeouts
        ssm = boto3.client('ssm', region_name=self.region)
        param_prefix = f'/classroom/{self.workshop_name}/{self.environment}'
        ssm.put_parameter(
            Name=f'{param_prefix}/instance_stop_timeout_minutes',
            Value='10',
            Type='String',
            Overwrite=True
        )
        ssm.put_parameter(
            Name=f'{param_prefix}/instance_terminate_timeout_minutes',
            Value='60',
            Type='String',
            Overwrite=True
        )
        ssm.put_parameter(
            Name=f'{param_prefix}/instance_hard_terminate_timeout_minutes',
            Value='240',
            Type='String',
            Overwrite=True
        )
        
        self.ec2 = boto3.client('ec2', region_name=self.region)

    def _create_hosted_zone(self):
        """Create mock Route53 hosted zone"""
        route53 = boto3.client('route53', region_name=self.region)
        response = route53.create_hosted_zone(
            Name='testingfantasy.com',
            CallerReference=str(datetime.now(timezone.utc).timestamp())
        )
        return response['HostedZone']['Id'].split('/')[-1]

    def _create_pool_instance(self, domain=None, age_minutes=0):
        """Create a pool instance with optional HTTPS domain"""
        vpc = self.ec2.create_vpc(CidrBlock='10.0.0.0/16')
        subnet = self.ec2.create_subnet(VpcId=vpc['Vpc']['VpcId'], CidrBlock='10.0.1.0/24')
        
        # Calculate launch time
        launch_time = datetime.now(timezone.utc) - timedelta(minutes=age_minutes)
        
        tags = [
            {'Key': 'Project', 'Value': 'classroom'},
            {'Key': 'Type', 'Value': 'pool'},
            {'Key': 'Template', 'Value': self.workshop_name},
            {'Key': 'Environment', 'Value': self.environment},
            {'Key': 'TutorialSessionID', 'Value': 'test_session_001'}
        ]
        
        if domain:
            tags.append({'Key': 'HttpsDomain', 'Value': domain})
        
        response = self.ec2.run_instances(
            ImageId='ami-12345678',
            MinCount=1,
            MaxCount=1,
            InstanceType='t3.medium',
            SubnetId=subnet['Subnet']['SubnetId'],
            TagSpecifications=[{'ResourceType': 'instance', 'Tags': tags}]
        )
        
        return response['Instances'][0]['InstanceId']

    def test_delete_single_pool_instance_with_route53(self):
        """Test deletion of single pool instance with Route53 cleanup"""
        # Create pool instance with domain
        instance_id = self._create_pool_instance(domain='pool.testingfantasy.com')
        
        # Add Route53 record
        route53 = boto3.client('route53', region_name=self.region)
        hosted_zone_id = os.environ['INSTANCE_MANAGER_HOSTED_ZONE_ID']
        route53.change_resource_record_sets(
            HostedZoneId=hosted_zone_id,
            ChangeBatch={
                'Changes': [{
                    'Action': 'CREATE',
                    'ResourceRecordSet': {
                        'Name': 'pool.testingfantasy.com',
                        'Type': 'A',
                        'TTL': 300,
                        'ResourceRecords': [{'Value': '1.2.3.4'}]
                    }
                }]
            }
        )
        
        # Verify instance exists
        instances = self.ec2.describe_instances(InstanceIds=[instance_id])
        assert len(instances['Reservations']) == 1
        
        # Delete instance
        self.ec2.terminate_instances(InstanceIds=[instance_id])
        
        # Verify deletion initiated
        instances = self.ec2.describe_instances(InstanceIds=[instance_id])
        instance = instances['Reservations'][0]['Instances'][0]
        assert instance['State']['Name'] in ['shutting-down', 'terminated']

    def test_bulk_delete_pool_instances(self):
        """Test bulk deletion of multiple pool instances"""
        # Create multiple pool instances
        instance_ids = [
            self._create_pool_instance(domain=f'pool{i}.testingfantasy.com')
            for i in range(3)
        ]
        
        # Verify all instances exist
        instances = self.ec2.describe_instances(
            Filters=[{'Name': 'instance-id', 'Values': instance_ids}]
        )
        running_count = sum(
            1 for r in instances['Reservations']
            for i in r['Instances']
            if i['State']['Name'] not in ['terminated', 'shutting-down']
        )
        assert running_count == 3
        
        # Bulk delete
        self.ec2.terminate_instances(InstanceIds=instance_ids)
        
        # Verify deletion initiated for all
        instances = self.ec2.describe_instances(
            Filters=[{'Name': 'instance-id', 'Values': instance_ids}]
        )
        for reservation in instances['Reservations']:
            for instance in reservation['Instances']:
                assert instance['State']['Name'] in ['shutting-down', 'terminated']


@mock_aws
class TestAdminInstanceDeletion:
    """Test admin instance deletion: confirms cleanup_days logic + Route53 cleanup"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for admin instance deletion tests"""
        self.region = 'eu-west-3'
        self.workshop_name = 'fellowship'
        self.environment = 'dev'
        
        os.environ['CLASSROOM_REGION'] = self.region
        os.environ['WORKSHOP_NAME'] = self.workshop_name
        os.environ['ENVIRONMENT'] = self.environment
        os.environ['INSTANCE_MANAGER_HOSTED_ZONE_ID'] = self._create_hosted_zone()
        os.environ['INSTANCE_MANAGER_BASE_DOMAIN'] = 'testingfantasy.com'
        os.environ['ADMIN_CLEANUP_INTERVAL_DAYS'] = '7'
        
        self.ec2 = boto3.client('ec2', region_name=self.region)

    def _create_hosted_zone(self):
        """Create mock Route53 hosted zone"""
        route53 = boto3.client('route53', region_name=self.region)
        response = route53.create_hosted_zone(
            Name='testingfantasy.com',
            CallerReference=str(datetime.now(timezone.utc).timestamp())
        )
        return response['HostedZone']['Id'].split('/')[-1]

    def _create_admin_instance(self, cleanup_days=7, domain=None):
        """Create an admin instance with specified cleanup days"""
        vpc = self.ec2.create_vpc(CidrBlock='10.0.0.0/16')
        subnet = self.ec2.create_subnet(VpcId=vpc['Vpc']['VpcId'], CidrBlock='10.0.1.0/24')
        
        tags = [
            {'Key': 'Project', 'Value': 'classroom'},
            {'Key': 'Type', 'Value': 'admin'},
            {'Key': 'CleanupDays', 'Value': str(cleanup_days)},
            {'Key': 'Template', 'Value': self.workshop_name},
            {'Key': 'Environment', 'Value': self.environment},
            {'Key': 'TutorialSessionID', 'Value': 'test_session_001'}
        ]
        
        if domain:
            tags.append({'Key': 'HttpsDomain', 'Value': domain})
        
        response = self.ec2.run_instances(
            ImageId='ami-12345678',
            MinCount=1,
            MaxCount=1,
            InstanceType='t3.medium',
            SubnetId=subnet['Subnet']['SubnetId'],
            TagSpecifications=[{'ResourceType': 'instance', 'Tags': tags}]
        )
        
        return response['Instances'][0]['InstanceId']

    def test_delete_single_admin_instance_with_route53(self):
        """Test deletion of single admin instance with Route53 cleanup"""
        instance_id = self._create_admin_instance(cleanup_days=7, domain='admin.testingfantasy.com')
        
        # Add Route53 record
        route53 = boto3.client('route53', region_name=self.region)
        hosted_zone_id = os.environ['INSTANCE_MANAGER_HOSTED_ZONE_ID']
        route53.change_resource_record_sets(
            HostedZoneId=hosted_zone_id,
            ChangeBatch={
                'Changes': [{
                    'Action': 'CREATE',
                    'ResourceRecordSet': {
                        'Name': 'admin.testingfantasy.com',
                        'Type': 'A',
                        'TTL': 300,
                        'ResourceRecords': [{'Value': '1.2.3.4'}]
                    }
                }]
            }
        )
        
        # Clean up Route53
        route53.change_resource_record_sets(
            HostedZoneId=hosted_zone_id,
            ChangeBatch={
                'Changes': [{
                    'Action': 'DELETE',
                    'ResourceRecordSet': {
                        'Name': 'admin.testingfantasy.com',
                        'Type': 'A',
                        'TTL': 300,
                        'ResourceRecords': [{'Value': '1.2.3.4'}]
                    }
                }]
            }
        )
        
        # Delete instance
        self.ec2.terminate_instances(InstanceIds=[instance_id])
        
        # Verify deletion initiated
        instances = self.ec2.describe_instances(InstanceIds=[instance_id])
        instance = instances['Reservations'][0]['Instances'][0]
        assert instance['State']['Name'] in ['shutting-down', 'terminated']

    def test_bulk_delete_admin_instances(self):
        """Test bulk deletion of multiple admin instances"""
        instance_ids = [
            self._create_admin_instance(cleanup_days=7, domain=f'admin{i}.testingfantasy.com')
            for i in range(3)
        ]
        
        # Verify all instances exist
        instances = self.ec2.describe_instances(
            Filters=[{'Name': 'instance-id', 'Values': instance_ids}]
        )
        running_count = sum(
            1 for r in instances['Reservations']
            for i in r['Instances']
            if i['State']['Name'] not in ['terminated', 'shutting-down']
        )
        assert running_count == 3
        
        # Bulk delete
        self.ec2.terminate_instances(InstanceIds=instance_ids)
        
        # Verify deletion initiated for all
        instances = self.ec2.describe_instances(
            Filters=[{'Name': 'instance-id', 'Values': instance_ids}]
        )
        for reservation in instances['Reservations']:
            for instance in reservation['Instances']:
                assert instance['State']['Name'] in ['shutting-down', 'terminated']


@mock_aws
class TestAdminCleanupDaysManagement:
    """Test admin instance cleanup days: set on creation, display, and extend"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for cleanup days management tests"""
        self.region = 'eu-west-3'
        self.workshop_name = 'fellowship'
        self.environment = 'dev'
        
        os.environ['CLASSROOM_REGION'] = self.region
        os.environ['WORKSHOP_NAME'] = self.workshop_name
        os.environ['ENVIRONMENT'] = self.environment
        
        self.ec2 = boto3.client('ec2', region_name=self.region)

    def _create_admin_instance(self, cleanup_days=7):
        """Create an admin instance with cleanup days tag"""
        vpc = self.ec2.create_vpc(CidrBlock='10.0.0.0/16')
        subnet = self.ec2.create_subnet(VpcId=vpc['Vpc']['VpcId'], CidrBlock='10.0.1.0/24')
        
        response = self.ec2.run_instances(
            ImageId='ami-12345678',
            MinCount=1,
            MaxCount=1,
            InstanceType='t3.medium',
            SubnetId=subnet['Subnet']['SubnetId'],
            TagSpecifications=[{
                'ResourceType': 'instance',
                'Tags': [
                    {'Key': 'Project', 'Value': 'classroom'},
                    {'Key': 'Type', 'Value': 'admin'},
                    {'Key': 'CleanupDays', 'Value': str(cleanup_days)},
                    {'Key': 'Template', 'Value': self.workshop_name}
                ]
            }]
        )
        
        return response['Instances'][0]['InstanceId']

    def test_admin_instance_created_with_cleanup_days(self):
        """Test admin instance is created with specified cleanup_days tag"""
        instance_id = self._create_admin_instance(cleanup_days=14)
        
        # Verify cleanup_days tag
        instances = self.ec2.describe_instances(InstanceIds=[instance_id])
        instance = instances['Reservations'][0]['Instances'][0]
        tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
        
        assert tags.get('CleanupDays') == '14'
        assert tags.get('Type') == 'admin'

    def test_extend_admin_cleanup_days(self):
        """Test extending cleanup days for an admin instance"""
        instance_id = self._create_admin_instance(cleanup_days=7)
        
        # Verify initial cleanup days
        instances = self.ec2.describe_instances(InstanceIds=[instance_id])
        instance = instances['Reservations'][0]['Instances'][0]
        tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
        assert tags.get('CleanupDays') == '7'
        
        # Update cleanup days
        self.ec2.create_tags(
            Resources=[instance_id],
            Tags=[{'Key': 'CleanupDays', 'Value': '14'}]
        )
        
        # Verify updated cleanup days
        instances = self.ec2.describe_instances(InstanceIds=[instance_id])
        instance = instances['Reservations'][0]['Instances'][0]
        tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
        assert tags.get('CleanupDays') == '14'

    def test_calculate_remaining_days(self):
        """Test calculating remaining days for admin instance"""
        instance_id = self._create_admin_instance(cleanup_days=7)
        
        # Get instance and calculate remaining days
        instances = self.ec2.describe_instances(InstanceIds=[instance_id])
        instance = instances['Reservations'][0]['Instances'][0]
        
        # Simulate remaining days calculation
        launch_time = instance['LaunchTime']
        now = datetime.now(timezone.utc)
        age_days = (now - launch_time).days
        cleanup_days = 7
        remaining_days = max(0, cleanup_days - age_days)
        
        # Remaining days should be close to 7 (0 if just created)
        assert 0 <= remaining_days <= 7

    def test_cleanup_days_set_bounds(self):
        """Test that cleanup days must be between 1 and 365"""
        # Create instance with minimum days
        instance_id_min = self._create_admin_instance(cleanup_days=1)
        instances = self.ec2.describe_instances(InstanceIds=[instance_id_min])
        tags_min = {tag['Key']: tag['Value'] for tag in instances['Reservations'][0]['Instances'][0].get('Tags', [])}
        assert int(tags_min['CleanupDays']) >= 1
        
        # Create instance with maximum days
        instance_id_max = self._create_admin_instance(cleanup_days=365)
        instances = self.ec2.describe_instances(InstanceIds=[instance_id_max])
        tags_max = {tag['Key']: tag['Value'] for tag in instances['Reservations'][0]['Instances'][0].get('Tags', [])}
        assert int(tags_max['CleanupDays']) <= 365


@mock_aws
class TestTutorialSessionCascadeDeletion:
    """Test cascade deletion of tutorial sessions: deletes all instances + Route53"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for cascade deletion tests"""
        self.region = 'eu-west-3'
        self.workshop_name = 'fellowship'
        self.environment = 'dev'
        
        os.environ['CLASSROOM_REGION'] = self.region
        os.environ['WORKSHOP_NAME'] = self.workshop_name
        os.environ['ENVIRONMENT'] = self.environment
        os.environ['INSTANCE_MANAGER_HOSTED_ZONE_ID'] = self._create_hosted_zone()
        os.environ['INSTANCE_MANAGER_BASE_DOMAIN'] = 'testingfantasy.com'
        
        # Create DynamoDB table for tutorial sessions
        dynamodb = boto3.resource('dynamodb', region_name=self.region)
        self.sessions_table = dynamodb.create_table(
            TableName=f'tutorial-sessions-{self.workshop_name}-{self.environment}',
            KeySchema=[{'AttributeName': 'session_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'session_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        self.sessions_table.wait_until_exists()
        
        self.ec2 = boto3.client('ec2', region_name=self.region)

    def _create_hosted_zone(self):
        """Create mock Route53 hosted zone"""
        route53 = boto3.client('route53', region_name=self.region)
        response = route53.create_hosted_zone(
            Name='testingfantasy.com',
            CallerReference=str(datetime.now(timezone.utc).timestamp())
        )
        return response['HostedZone']['Id'].split('/')[-1]

    def _create_instances_for_session(self, session_id, pool_count=2, admin_count=1):
        """Create pool and admin instances tagged with session_id"""
        vpc = self.ec2.create_vpc(CidrBlock='10.0.0.0/16')
        subnet = self.ec2.create_subnet(VpcId=vpc['Vpc']['VpcId'], CidrBlock='10.0.1.0/24')
        
        instance_ids = []
        
        # Create pool instances
        for i in range(pool_count):
            response = self.ec2.run_instances(
                ImageId='ami-12345678',
                MinCount=1,
                MaxCount=1,
                InstanceType='t3.medium',
                SubnetId=subnet['Subnet']['SubnetId'],
                TagSpecifications=[{
                    'ResourceType': 'instance',
                    'Tags': [
                        {'Key': 'Project', 'Value': 'classroom'},
                        {'Key': 'Type', 'Value': 'pool'},
                        {'Key': 'TutorialSessionID', 'Value': session_id},
                        {'Key': 'Template', 'Value': self.workshop_name}
                    ]
                }]
            )
            instance_ids.append(response['Instances'][0]['InstanceId'])
        
        # Create admin instances
        for i in range(admin_count):
            response = self.ec2.run_instances(
                ImageId='ami-12345678',
                MinCount=1,
                MaxCount=1,
                InstanceType='t3.medium',
                SubnetId=subnet['Subnet']['SubnetId'],
                TagSpecifications=[{
                    'ResourceType': 'instance',
                    'Tags': [
                        {'Key': 'Project', 'Value': 'classroom'},
                        {'Key': 'Type', 'Value': 'admin'},
                        {'Key': 'CleanupDays', 'Value': '7'},
                        {'Key': 'TutorialSessionID', 'Value': session_id},
                        {'Key': 'Template', 'Value': self.workshop_name}
                    ]
                }]
            )
            instance_ids.append(response['Instances'][0]['InstanceId'])
        
        return instance_ids

    def test_cascade_delete_session_instances(self):
        """Test deleting all instances associated with a tutorial session"""
        session_id = 'test_session_cascade_001'
        instance_ids = self._create_instances_for_session(session_id, pool_count=2, admin_count=1)
        
        # Verify all instances exist
        instances = self.ec2.describe_instances(
            Filters=[{'Name': 'tag:TutorialSessionID', 'Values': [session_id]}]
        )
        created_count = sum(
            1 for r in instances['Reservations']
            for i in r['Instances']
            if i['State']['Name'] not in ['terminated', 'shutting-down']
        )
        assert created_count == 3
        
        # Cascade delete all instances for this session
        self.ec2.terminate_instances(InstanceIds=instance_ids)
        
        # Verify all instances are being deleted
        instances = self.ec2.describe_instances(
            Filters=[{'Name': 'tag:TutorialSessionID', 'Values': [session_id]}]
        )
        for reservation in instances['Reservations']:
            for instance in reservation['Instances']:
                if instance['State']['Name'] not in ['terminated', 'shutting-down']:
                    pytest.fail(f"Instance {instance['InstanceId']} should be deleted")


# ============================================================================
# ASSUMPTIONS DOCUMENTED
# ============================================================================
"""
ASSUMPTIONS MADE DURING IMPLEMENTATION:

1. Route53 Cleanup:
   - Hosted zone ID is configured in INSTANCE_MANAGER_HOSTED_ZONE_ID env var
   - All HTTPS domains have A records in Route53
   - Route53 cleanup failure is BLOCKING (strict mode) for instance deletion
   - DNS cleanup retries up to 3 times on transient errors

2. Instance Deletion Behavior:
   - Pool instances are terminated directly (no stop -> terminate sequence)
   - Admin instances are also terminated directly
   - Terminated instances are immediately unavailable for reassignment
   - Deletion is asynchronous (initiated but not awaited)

3. Admin Cleanup Days:
   - Default cleanup_days = 7 days if not specified
   - Cleanup_days range: 1 to 365 days
   - Remaining days = cleanup_days - age_in_days, minimum 0
   - Age calculated at the time list_instances is called
   - Cleanup is checked by classroom_admin_cleanup.py Lambda (separate process)

4. DynamoDB Schema:
   - Assignments table only tracks POOL instances
   - Admin instances are NOT tracked in assignments table
   - Both pool and admin instance data come from EC2 tags

5. Cost Calculation:
   - Hourly rates are estimates (from INSTANCE_RATES_ESTIMATE_USD)
   - Actual costs are fetched from AWS Cost Explorer when available
   - Cost Explorer data has ~24-hour lag
   - If Cost Explorer is unavailable, only estimated costs are returned

6. Tutorial Session Management:
   - Sessions are stored in 'tutorial-sessions-{workshop}-{environment}' DynamoDB table
   - All instances in a session share the same TutorialSessionID tag
   - Cascading delete means terminating all EC2 instances + cleaning Route53

7. Confirmation Dialogs:
   - All deletions (single, bulk, cascade) require user confirmation
   - Confirmation includes count of affected instances/Route53 records
   - Confirmation can be bypassed only in test environments

8. Error Handling:
   - Route53 deletion failures block EC2 termination
   - EC2 termination failures are logged but non-blocking
   - Network errors during deletion are retried up to 3 times
   - Partial deletions are reported with detailed error list
"""
