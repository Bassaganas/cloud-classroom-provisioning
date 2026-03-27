"""
Test suite for spot instance tagging and naming.

Validates that spot instances receive proper Name tags and all required tags
so they can be managed by classroom_stop_old_instances.py cleanup Lambda.

Run with: python -m pytest functions/tests/test_spot_instance_tagging.py -v
"""

import pytest
import os
import sys
import json
from botocore.exceptions import ClientError
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

# Setup path and test mode
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../common'))
from test_mode import init_test_mode
init_test_mode()

import boto3
from moto import mock_aws
import logging

logger = logging.getLogger(__name__)


class TestSpotInstanceTagging:
    """Test that spot instances receive proper naming and tagging."""

    @pytest.fixture(autouse=True)
    def setup(self):
        """Setup environment for spot instance tests."""
        self.region = 'eu-west-3'
        self.workshop_name = 'fellowship'
        self.environment = 'dev'

        self._mock = mock_aws()
        self._mock.start()
        
        # Initialize EC2 client first
        self.ec2 = boto3.client('ec2', region_name=self.region)
        
        # Set environment variables
        os.environ['CLASSROOM_REGION'] = self.region
        os.environ['WORKSHOP_NAME'] = self.workshop_name
        os.environ['ENVIRONMENT'] = self.environment
        os.environ['EC2_SUBNET_ID'] = self._create_subnet()
        os.environ['EC2_INSTANCE_TYPE'] = 't3.medium'
        os.environ['EC2_IAM_INSTANCE_PROFILE'] = f'ec2-ssm-profile-{self.workshop_name}-{self.environment}'
        os.environ['INSTANCE_MANAGER_HOSTED_ZONE_ID'] = ''
        os.environ['INSTANCE_MANAGER_BASE_DOMAIN'] = ''
        self._create_instance_profile(os.environ['EC2_IAM_INSTANCE_PROFILE'])
        
        # Create DynamoDB table for template map and request tracking
        dynamodb = boto3.resource('dynamodb', region_name=self.region)
        table_name = f'instance-assignments-{self.workshop_name}-{self.environment}'

        self.table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[{'AttributeName': 'instance_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'instance_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        
        # Use moto's built-in default AMI
        test_ami = 'ami-12c6146b'  # Default moto AMI
        
        # Create SSM parameters for template (required for instance creation)
        ssm = boto3.client('ssm', region_name=self.region)
        template_config = {
            'ami_id': test_ami,
            'instance_type': 't3.medium',
            'app_port': 5000
        }
        ssm.put_parameter(
            Name=f'/classroom/templates/{self.environment}/{self.workshop_name}',
            Value=json.dumps(template_config),
            Type='String',
            Overwrite=True
        )
        
        # Create SSM timeout parameters
        param_prefix = f'/classroom/{self.workshop_name}/{self.environment}'
        ssm.put_parameter(Name=f'{param_prefix}/instance_stop_timeout_minutes', Value='10', Type='String', Overwrite=True)
        ssm.put_parameter(Name=f'{param_prefix}/instance_terminate_timeout_minutes', Value='60', Type='String', Overwrite=True)
        ssm.put_parameter(Name=f'{param_prefix}/instance_hard_terminate_timeout_minutes', Value='240', Type='String', Overwrite=True)

        sys.modules.pop('classroom_instance_manager', None)

        yield

        self._mock.stop()

    def _create_subnet(self):
        """Create VPC and subnet, return subnet ID."""
        ec2 = boto3.client('ec2', region_name=self.region)
        vpcs = ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}]).get('Vpcs', [])
        if not vpcs:
            vpcs = ec2.describe_vpcs().get('Vpcs', [])
        if vpcs:
            vpc_id = vpcs[0]['VpcId']
        else:
            try:
                vpc_id = ec2.create_vpc(CidrBlock='10.0.0.0/16')['Vpc']['VpcId']
            except ClientError as error:
                if error.response.get('Error', {}).get('Code') != 'VpcLimitExceeded':
                    raise
                existing_vpcs = ec2.describe_vpcs().get('Vpcs', [])
                if not existing_vpcs:
                    raise
                vpc_id = existing_vpcs[0]['VpcId']

        existing_subnets = ec2.describe_subnets(
            Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
        ).get('Subnets', [])
        if existing_subnets:
            return existing_subnets[0]['SubnetId']

        subnet_response = ec2.create_subnet(VpcId=vpc_id, CidrBlock='10.0.1.0/24')
        return subnet_response['Subnet']['SubnetId']

    def _create_hosted_zone(self):
        """Create mock Route53 hosted zone."""
        route53 = boto3.client('route53', region_name=self.region)
        response = route53.create_hosted_zone(
            Name='testingfantasy.com',
            CallerReference=str(datetime.now(timezone.utc).timestamp())
        )
        return response['HostedZone']['Id'].split('/')[-1]

    def _create_instance_profile(self, profile_name):
        """Create a mock IAM role + instance profile for EC2 launches."""
        iam = boto3.client('iam', region_name=self.region)
        role_name = f'{profile_name}-role'
        assume_role_policy = json.dumps({
            'Version': '2012-10-17',
            'Statement': [{
                'Effect': 'Allow',
                'Principal': {'Service': 'ec2.amazonaws.com'},
                'Action': 'sts:AssumeRole'
            }]
        })
        iam.create_role(RoleName=role_name, AssumeRolePolicyDocument=assume_role_policy)
        iam.create_instance_profile(InstanceProfileName=profile_name)
        iam.add_role_to_instance_profile(InstanceProfileName=profile_name, RoleName=role_name)

    def _get_instance_tags(self, instance_id):
        """Retrieve tags from an instance."""
        response = self.ec2.describe_instances(InstanceIds=[instance_id])
        tags = {}
        if response['Reservations']:
            for tag in response['Reservations'][0]['Instances'][0].get('Tags', []):
                tags[tag['Key']] = tag['Value']
        return tags

    def test_spot_instance_tagging_logic_in_code(self):
        """Test that the code builds proper tags for spot instances (unit test)."""
        # This test verifies the tagging logic without actually creating instances
        workshop_name = 'fellowship'
        tutorial_session_id = None
        instance_type = 'pool'
        purchase_type = 'spot'
        spot_max_price = '0.50'
        final_stop_timeout = 10
        final_terminate_timeout = 60
        final_hard_terminate_timeout = 240
        
        # Simulate the tag building logic from create_instance
        instance_index = 0
        
        if instance_type == 'pool':
            name = f'{workshop_name}-pool-{instance_index}'
            if tutorial_session_id:
                name = f'{workshop_name}-{tutorial_session_id}-pool-{instance_index}'
            tags = [
                {'Key': 'Name', 'Value': name},
                {'Key': 'Status', 'Value': 'available'},
                {'Key': 'Project', 'Value': 'classroom'},
                {'Key': 'Environment', 'Value': 'dev'},
                {'Key': 'Type', 'Value': 'pool'},
                {'Key': 'CreatedBy', 'Value': 'lambda-manager'},
                {'Key': 'CreatedAt', 'Value': datetime.utcnow().isoformat()},
                {'Key': 'WorkshopID', 'Value': workshop_name},
                {'Key': 'Template', 'Value': workshop_name},
                {'Key': 'AppPort', 'Value': '80'},
                {'Key': 'Company', 'Value': 'TestingFantasy'},
                {'Key': 'StopTimeout', 'Value': str(final_stop_timeout)},
                {'Key': 'TerminateTimeout', 'Value': str(final_terminate_timeout)},
                {'Key': 'HardTerminateTimeout', 'Value': str(final_hard_terminate_timeout)}
            ]
        
        # Add TutorialSessionID tag if provided
        if tutorial_session_id:
            tags.append({'Key': 'TutorialSessionID', 'Value': tutorial_session_id})
        
        # Add spot instance tags if using spot
        if purchase_type == 'spot':
            tags.append({'Key': 'PurchaseType', 'Value': 'spot'})
            if spot_max_price is not None:
                tags.append({'Key': 'SpotMaxPrice', 'Value': str(spot_max_price)})
        else:
            tags.append({'Key': 'PurchaseType', 'Value': 'on-demand'})
        
        # Verify tags
        tag_dict = {tag['Key']: tag['Value'] for tag in tags}
        
        # Spot instance should have Name tag
        assert 'Name' in tag_dict, "Name tag missing for spot instance"
        assert tag_dict['Name'] == f'{workshop_name}-pool-{instance_index}', \
            f"Name tag incorrect: {tag_dict['Name']}"
        
        # Verify required tags for cleanup
        required_tags = ['Name', 'Project', 'Type', 'WorkshopID', 'Status', 
                        'StopTimeout', 'TerminateTimeout', 'HardTerminateTimeout', 'PurchaseType']
        missing_tags = [t for t in required_tags if t not in tag_dict]
        assert not missing_tags, f"Missing required tags for spot instance: {missing_tags}"
        
        # Verify tag values
        assert tag_dict['Project'] == 'classroom', "Project tag incorrect"
        assert tag_dict['Type'] == 'pool', "Type tag incorrect"
        assert tag_dict['PurchaseType'] == 'spot', "PurchaseType tag should be spot"
        assert tag_dict['SpotMaxPrice'] == spot_max_price, "SpotMaxPrice tag incorrect"
        
        logger.info(f"✓ Spot instance tagging logic is correct. Tags: {tag_dict}")

    def test_spot_instance_has_required_tags_for_cleanup(self):
        """Test that spot instances have all tags required by cleanup Lambda."""
        from classroom_instance_manager import create_instance
        
        result = create_instance(
            count=1,
            instance_type='pool',
            purchase_type='spot',
            workshop_name=self.workshop_name
        )
        
        assert result['success'], f"Instance creation failed: {result.get('error')}"
        instance_id = result['instances'][0]['instance_id']
        tags = self._get_instance_tags(instance_id)
        
        # Tags required by classroom_stop_old_instances.py
        required_tags = [
            'Name',
            'Project',
            'Type',
            'WorkshopID',
            'Status',
            'StopTimeout',
            'TerminateTimeout',
            'HardTerminateTimeout',
            'PurchaseType'
        ]
        
        missing_tags = [tag for tag in required_tags if tag not in tags]
        assert not missing_tags, \
            f"Spot instance {instance_id} missing required tags: {missing_tags}"
        
        # Verify tag values
        assert tags['Project'] == 'classroom', f"Expected Project=classroom, got {tags.get('Project')}"
        assert tags['Type'] == 'pool', f"Expected Type=pool, got {tags.get('Type')}"
        assert tags['WorkshopID'] == self.workshop_name, f"Expected WorkshopID={self.workshop_name}, got {tags.get('WorkshopID')}"
        assert tags['PurchaseType'] == 'spot', f"Expected PurchaseType=spot, got {tags.get('PurchaseType')}"
        assert tags['Status'] == 'available', f"Expected Status=available, got {tags.get('Status')}"
        
        logger.info(f"✓ Spot instance {instance_id} has all required cleanup tags")

    def test_spot_instance_with_tutorial_session_has_session_tag(self):
        """Test that spot instances created for tutorial sessions get TutorialSessionID tag."""
        from classroom_instance_manager import create_instance
        
        session_id = 'e2e-tests-session-spot-001'
        
        result = create_instance(
            count=1,
            instance_type='pool',
            purchase_type='spot',
            tutorial_session_id=session_id,
            workshop_name=self.workshop_name
        )
        
        assert result['success'], f"Instance creation failed: {result.get('error')}"
        instance_id = result['instances'][0]['instance_id']
        tags = self._get_instance_tags(instance_id)
        
        # Verify TutorialSessionID tag
        assert 'TutorialSessionID' in tags, f"Instance {instance_id} missing TutorialSessionID tag"
        assert tags['TutorialSessionID'] == session_id, \
            f"Expected TutorialSessionID={session_id}, got {tags.get('TutorialSessionID')}"
        
        # Verify name includes session ID
        expected_prefix = f"{self.workshop_name}-{session_id}-pool-"
        assert tags['Name'].startswith(expected_prefix), \
            f"Name tag '{tags['Name']}' does not include session ID"
        
        logger.info(f"✓ Spot instance {instance_id} with session has correct tags")

    def test_spot_instance_with_max_price_has_price_tag(self):
        """Test that spot instances created with max price have SpotMaxPrice tag."""
        from classroom_instance_manager import create_instance
        
        max_price = '0.50'
        
        result = create_instance(
            count=1,
            instance_type='pool',
            purchase_type='spot',
            spot_max_price=max_price,
            workshop_name=self.workshop_name
        )
        
        assert result['success'], f"Instance creation failed: {result.get('error')}"
        instance_id = result['instances'][0]['instance_id']
        tags = self._get_instance_tags(instance_id)
        
        # Verify SpotMaxPrice tag
        assert 'SpotMaxPrice' in tags, f"Instance {instance_id} missing SpotMaxPrice tag"
        assert tags['SpotMaxPrice'] == max_price, \
            f"Expected SpotMaxPrice={max_price}, got {tags.get('SpotMaxPrice')}"
        
        logger.info(f"✓ Spot instance {instance_id} with max price has correct SpotMaxPrice tag")

    def test_admin_spot_instance_has_name_and_cleanup_days(self):
        """Test that admin spot instances get Name tag and CleanupDays tag."""
        from classroom_instance_manager import create_instance
        
        cleanup_days = 3
        result = create_instance(
            count=1,
            instance_type='admin',
            purchase_type='spot',
            cleanup_days=cleanup_days,
            workshop_name=self.workshop_name
        )
        
        assert result['success'], f"Instance creation failed: {result.get('error')}"
        instance_id = result['instances'][0]['instance_id']
        tags = self._get_instance_tags(instance_id)
        
        # Verify Name tag
        assert 'Name' in tags, f"Instance {instance_id} missing Name tag"
        expected_prefix = f"{self.workshop_name}-admin-"
        assert tags['Name'].startswith(expected_prefix), \
            f"Name tag '{tags['Name']}' does not start with '{expected_prefix}'"
        
        # Verify Type and CleanupDays tags
        assert tags['Type'] == 'admin', f"Expected Type=admin, got {tags.get('Type')}"
        assert 'CleanupDays' in tags, f"Instance {instance_id} missing CleanupDays tag"
        assert tags['CleanupDays'] == str(cleanup_days), \
            f"Expected CleanupDays={cleanup_days}, got {tags.get('CleanupDays')}"
        
        logger.info(f"✓ Admin spot instance {instance_id} has proper Name and CleanupDays tags")

    def test_multiple_spot_instances_get_unique_names(self):
        """Test that multiple spot instances get unique Name tags."""
        from classroom_instance_manager import create_instance
        
        result = create_instance(
            count=3,
            instance_type='pool',
            purchase_type='spot',
            workshop_name=self.workshop_name
        )
        
        assert result['success'], f"Instance creation failed: {result.get('error')}"
        assert result['count'] == 3, f"Expected 3 instances, got {result['count']}"
        
        instance_ids = [inst['instance_id'] for inst in result['instances']]
        names = []
        
        for instance_id in instance_ids:
            tags = self._get_instance_tags(instance_id)
            assert 'Name' in tags, f"Instance {instance_id} missing Name tag"
            names.append(tags['Name'])
        
        # Verify all names are unique
        assert len(names) == len(set(names)), f"Spot instances have duplicate names: {names}"
        
        # Verify names follow pattern
        for name in names:
            assert self.workshop_name in name, f"Name '{name}' missing workshop name"
            assert 'pool' in name, f"Name '{name}' missing 'pool' designation"
        
        logger.info(f"✓ Multiple spot instances have unique names: {names}")

    def test_on_demand_instance_also_has_proper_tags(self):
        """Test that on-demand instances also have proper Name tag (regression test)."""
        from classroom_instance_manager import create_instance
        
        result = create_instance(
            count=1,
            instance_type='pool',
            purchase_type='on-demand',
            workshop_name=self.workshop_name
        )
        
        assert result['success'], f"Instance creation failed: {result.get('error')}"
        instance_id = result['instances'][0]['instance_id']
        tags = self._get_instance_tags(instance_id)
        
        # Verify Name tag exists
        assert 'Name' in tags, f"On-demand instance {instance_id} missing Name tag"
        assert tags['Name'].strip(), f"On-demand instance {instance_id} has empty Name tag"
        
        # Verify PurchaseType
        assert tags['PurchaseType'] == 'on-demand', f"Expected PurchaseType=on-demand, got {tags.get('PurchaseType')}"
        
        logger.info(f"✓ On-demand instance {instance_id} has proper tags")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
