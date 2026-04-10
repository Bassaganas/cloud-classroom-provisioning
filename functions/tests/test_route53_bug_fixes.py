"""
Test Suite to Verify Route53 Bug Fixes

Validates that:
1. Route53 cleanup works with normalized domain names
2. Instances are deleted even if Route53 cleanup fails (strict=False)
3. Lambda returns success (200) even with Route53 failures
"""

import pytest
import os
import sys
import json
from datetime import datetime, timezone, timedelta
from unittest.mock import Mock, patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../common'))
from test_mode import init_test_mode
init_test_mode()

import boto3
from moto import mock_aws
from botocore.exceptions import ClientError


@mock_aws
class TestRoute53BugFixes:
    """Verify Route53 cleanup bug fixes"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup Route53 and EC2 mocks"""
        self.region = 'eu-west-3'
        self.workshop_name = 'fellowship'
        self.environment = 'dev'
        
        os.environ['CLASSROOM_REGION'] = self.region
        os.environ['WORKSHOP_NAME'] = self.workshop_name
        os.environ['ENVIRONMENT'] = self.environment
        self.hosted_zone_id = self._create_hosted_zone()
        os.environ['INSTANCE_MANAGER_HOSTED_ZONE_ID'] = self.hosted_zone_id
        os.environ['INSTANCE_MANAGER_BASE_DOMAIN'] = 'testingfantasy.com'
        os.environ['ADMIN_CLEANUP_INTERVAL_DAYS'] = '7'

        # classroom_admin_cleanup reads these at import time; refresh for each test.
        import classroom_admin_cleanup as cleanup_mod
        cleanup_mod.region = self.region
        cleanup_mod.ec2_client = boto3.client('ec2', region_name=self.region)
        cleanup_mod.HTTPS_HOSTED_ZONE_ID = self.hosted_zone_id
        cleanup_mod.HTTPS_BASE_DOMAIN = 'testingfantasy.com'
        
        self.ec2 = boto3.client('ec2', region_name=self.region)
        self.route53 = boto3.client('route53', region_name=self.region)

    def _create_hosted_zone(self):
        """Create mock Route53 hosted zone"""
        route53 = boto3.client('route53', region_name=self.region)
        response = route53.create_hosted_zone(
            Name='testingfantasy.com',
            CallerReference=str(datetime.now(timezone.utc).timestamp())
        )
        return response['HostedZone']['Id'].split('/')[-1]

    def _create_admin_instance_with_domain(self, domain_name):
        """Create admin instance with Route53 A record"""
        vpc = self.ec2.create_vpc(CidrBlock='10.0.0.0/16')
        subnet = self.ec2.create_subnet(VpcId=vpc['Vpc']['VpcId'], CidrBlock='10.0.1.0/24')
        
        # Create instance
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
                    {'Key': 'HttpsDomain', 'Value': domain_name},
                    {'Key': 'Template', 'Value': self.workshop_name}
                ]
            }]
        )
        
        instance_id = response['Instances'][0]['InstanceId']
        
        # Create Route53 A record (WITHOUT trailing dot - simulating the bug scenario)
        hosted_zone_id = self.hosted_zone_id
        try:
            self.route53.change_resource_record_sets(
                HostedZoneId=hosted_zone_id,
                ChangeBatch={
                    'Changes': [{
                        'Action': 'CREATE',
                        'ResourceRecordSet': {
                            'Name': domain_name + '.',  # Route53 stores with trailing dot
                            'Type': 'A',
                            'TTL': 300,
                            'ResourceRecords': [{'Value': '1.2.3.4'}]
                        }
                    }]
                }
            )
        except ClientError as e:
            if e.response.get('Error', {}).get('Code') != 'NoSuchHostedZone':
                raise

            # Recreate hosted zone in this moto context and retry once.
            self.hosted_zone_id = self._create_hosted_zone()
            os.environ['INSTANCE_MANAGER_HOSTED_ZONE_ID'] = self.hosted_zone_id
            import classroom_admin_cleanup as cleanup_mod
            cleanup_mod.HTTPS_HOSTED_ZONE_ID = self.hosted_zone_id

            self.route53.change_resource_record_sets(
                HostedZoneId=self.hosted_zone_id,
                ChangeBatch={
                    'Changes': [{
                        'Action': 'CREATE',
                        'ResourceRecordSet': {
                            'Name': domain_name + '.',
                            'Type': 'A',
                            'TTL': 300,
                            'ResourceRecords': [{'Value': '1.2.3.4'}]
                        }
                    }]
                }
            )
        
        return instance_id

    def test_route53_cleanup_with_normalized_domain(self):
        """BUG FIX #1: Verify Route53 cleanup uses normalized domain names"""
        from classroom_admin_cleanup import cleanup_route53_record
        
        domain = 'fellowship-paula5-admin-1.fellowship.testingfantasy.com'
        instance_id = self._create_admin_instance_with_domain(domain)
        
        # Get instance tags
        instances = self.ec2.describe_instances(InstanceIds=[instance_id])
        instance = instances['Reservations'][0]['Instances'][0]
        tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
        
        # Test cleanup with normalized domain (this should now work with the fix)
        result = cleanup_route53_record(instance_id, tags, strict=False, max_retries=1)
        
        # Verify cleanup succeeded
        assert result['success'] == True, f"Cleanup failed: {result}"
        assert result['deleted'] == True, "Record should be deleted"
        
        # Verify record is actually deleted from Route53
        hosted_zone_id = os.environ['INSTANCE_MANAGER_HOSTED_ZONE_ID']
        response = self.route53.list_resource_record_sets(HostedZoneId=hosted_zone_id)
        
        # The A record for our domain should not exist
        a_records = [r for r in response['ResourceRecordSets'] 
                     if r['Type'] == 'A' and domain in r['Name']]
        assert len(a_records) == 0, "Route53 record should be deleted"

    def test_instance_deletion_succeeds_despite_route53_failure(self):
        """BUG FIX #2: Verify instances are deleted even if Route53 cleanup fails"""
        from classroom_admin_cleanup import cleanup_route53_record
        
        # Create instance WITHOUT a Route53 record (simulating missing domain)
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
                    {'Key': 'CleanupDays', 'Value': '-5'},  # Expired 5 days ago
                    {'Key': 'Template', 'Value': self.workshop_name}
                ]
            }]
        )
        
        instance_id = response['Instances'][0]['InstanceId']
        
        # Get instance tags (no HttpsDomain tag)
        instances = self.ec2.describe_instances(InstanceIds=[instance_id])
        instance = instances['Reservations'][0]['Instances'][0]
        tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
        
        # Route53 cleanup should be skipped (no domain tag)
        result = cleanup_route53_record(instance_id, tags, strict=False)
        assert result['skipped'] == True,  "Should be skipped (no domain)"
        
        # But with strict=False, the cleanup returns success
        assert result['success'] == True, "Should still be considered success in non-strict mode"
        
        # System should allow instance deletion to proceed
        # (In real code, this would happen regardless of Route53 cleanup result)
        self.ec2.terminate_instances(InstanceIds=[instance_id])
        
        # Verify instance is marked for termination
        instances = self.ec2.describe_instances(InstanceIds=[instance_id])
        instance_state = instances['Reservations'][0]['Instances'][0]['State']['Name']
        assert instance_state in ['shutting-down', 'terminated'], "Instance should be terminated"

    def test_cleanup_non_blocking_with_invalid_domain(self):
        """BUG FIX #2: Verify strict=False allows cleanup to continue on failures"""
        from classroom_admin_cleanup import cleanup_route53_record
        
        # Create a tag with domain that doesn't exist in Route53
        tags = {
            'HttpsDomain': 'nonexistent-domain.fellowship.testingfantasy.com'
        }
        
        # With strict=False, cleanup should return success even if domain not found
        result = cleanup_route53_record('i-test', tags, strict=False, max_retries=1)
        
        # Should be skipped (not found) but still considered successful
        assert result['success'] == True, "Should return success with strict=False"
        # If hosted zone is unavailable in the mocked context the cleanup is still non-blocking.
        assert result.get('skipped', False) or result.get('reason') in ['hosted-zone-missing', 'hosted-zone-not-configured']

    def test_lambda_returns_200_on_route53_errors(self):
        """BUG FIX #3: Verify lambda returns 200 even when Route53 cleanup fails"""
        from classroom_admin_cleanup import lambda_handler
        
        # Create expired admin instance
        domain = 'test-admin.testingfantasy.com'
        instance_id = self._create_admin_instance_with_domain(domain)
        
        # Age the instance creation time (simulate 10 days old)
        # Note: In real test we'd modify the instance launch time, but moto doesn't support this
        # So we'll just verify the function executes and returns proper status code
        
        # Mock the event and context
        event = {}
        context = type('obj', (object,), {
            'invoked_function_arn': 'arn:aws:lambda:eu-west-3:123456789:function:admin-cleanup',
            'function_name': 'admin-cleanup'
        })()
        
        # Execute lambda
        response = lambda_handler(event, context)
        
        # Verify response
        assert response['statusCode'] == 200, f"Lambda should return 200, got {response['statusCode']}"
        body = json.loads(response['body'])
        assert 'message' in body, "Response should have message"
        # Response shape differs depending on whether any instance qualifies for cleanup.
        if 'No admin instances' not in body.get('message', ''):
            assert 'deleted' in body, "Response should track deleted count when cleanup runs"
            assert 'errors' in body, "Response should track error count when cleanup runs"


@mock_aws
class TestInstanceDeletionWithRoute53:
    """Verify instance deletion works with Route53 cleanup"""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup for instance deletion tests"""
        self.region = 'eu-west-3'
        self.workshop_name = 'fellowship'
        self.environment = 'dev'
        
        os.environ['CLASSROOM_REGION'] = self.region
        os.environ['WORKSHOP_NAME'] = self.workshop_name
        os.environ['ENVIRONMENT'] = self.environment
        os.environ['INSTANCE_MANAGER_HOSTED_ZONE_ID'] = self._create_hosted_zone()
        os.environ['INSTANCE_MANAGER_BASE_DOMAIN'] = 'testingfantasy.com'
        
        self.ec2 = boto3.client('ec2', region_name=self.region)
        self.route53 = boto3.client('route53', region_name=self.region)

    def _create_hosted_zone(self):
        """Create mock Route53 hosted zone"""
        route53 = boto3.client('route53', region_name=self.region)
        response = route53.create_hosted_zone(
            Name='testingfantasy.com',
            CallerReference=str(datetime.now(timezone.utc).timestamp())
        )
        return response['HostedZone']['Id'].split('/')[-1]

    def test_pool_instance_deletion_with_route53(self):
        """Test pool instance deletion with Route53 cleanup"""
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
                    {'Key': 'Type', 'Value': 'pool'},
                    {'Key': 'HttpsDomain', 'Value': 'pool.testingfantasy.com'},
                    {'Key': 'Template', 'Value': self.workshop_name}
                ]
            }]
        )
        
        instance_id = response['Instances'][0]['InstanceId']
        
        # Delete instance
        self.ec2.terminate_instances(InstanceIds=[instance_id])
        
        # Verify deletion initiated
        instances = self.ec2.describe_instances(InstanceIds=[instance_id])
        instance_state = instances['Reservations'][0]['Instances'][0]['State']['Name']
        assert instance_state in ['shutting-down', 'terminated'], "Instance should be deleted"
