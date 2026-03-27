"""Regression tests for the classroom golden AMI launch contract."""

import json
import os
import sys
from datetime import datetime, timezone
from unittest.mock import patch

import boto3
import pytest
from moto import mock_aws

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../common'))
from test_mode import init_test_mode

init_test_mode()


class TestGoldenAmiLaunchContract:
    @pytest.fixture(autouse=True)
    def setup(self):
        """Each test gets its own isolated moto mock context."""
        self.region = 'eu-west-3'
        self.workshop_name = 'fellowship'
        self.environment = 'dev'
        self.base_domain = 'testingfantasy.com'

        self._mock = mock_aws()
        self._mock.start()

        os.environ['CLASSROOM_REGION'] = self.region
        os.environ['WORKSHOP_NAME'] = self.workshop_name
        os.environ['ENVIRONMENT'] = self.environment
        os.environ['EC2_INSTANCE_TYPE'] = 't3.medium'
        os.environ['EC2_SUBNET_ID'] = self._create_subnet()
        os.environ['EC2_IAM_INSTANCE_PROFILE'] = f'ec2-ssm-profile-{self.workshop_name}-{self.environment}'
        os.environ['INSTANCE_MANAGER_BASE_DOMAIN'] = self.base_domain
        os.environ['INSTANCE_MANAGER_HOSTED_ZONE_ID'] = self._create_hosted_zone()

        dynamodb = boto3.resource('dynamodb', region_name=self.region)
        table_name = f'instance-assignments-{self.workshop_name}-{self.environment}'
        self.table = dynamodb.create_table(
            TableName=table_name,
            KeySchema=[{'AttributeName': 'instance_id', 'KeyType': 'HASH'}],
            AttributeDefinitions=[{'AttributeName': 'instance_id', 'AttributeType': 'S'}],
            BillingMode='PAY_PER_REQUEST'
        )
        self.table.wait_until_exists()

        ssm = boto3.client('ssm', region_name=self.region)
        template_config = {
            'ami_id': 'ami-12c6146b',
            'instance_type': 't3.medium',
            'app_port': 5000
        }
        ssm.put_parameter(
            Name=f'/classroom/templates/{self.environment}/{self.workshop_name}',
            Value=json.dumps(template_config),
            Type='String',
            Overwrite=True
        )
        ssm.put_parameter(
            Name=f'/classroom/{self.workshop_name}/{self.environment}/instance_stop_timeout_minutes',
            Value='10', Type='String', Overwrite=True
        )
        ssm.put_parameter(
            Name=f'/classroom/{self.workshop_name}/{self.environment}/instance_terminate_timeout_minutes',
            Value='60', Type='String', Overwrite=True
        )
        ssm.put_parameter(
            Name=f'/classroom/{self.workshop_name}/{self.environment}/instance_hard_terminate_timeout_minutes',
            Value='240', Type='String', Overwrite=True
        )

        yield

        self._mock.stop()

    def _create_subnet(self):
        ec2 = boto3.client('ec2', region_name=self.region)
        # Moto always provides a default VPC; reuse an existing subnet within it if one exists
        vpcs = ec2.describe_vpcs(Filters=[{'Name': 'isDefault', 'Values': ['true']}]).get('Vpcs', [])
        if not vpcs:
            vpcs = ec2.describe_vpcs().get('Vpcs', [])
        vpc_id = vpcs[0]['VpcId'] if vpcs else ec2.create_vpc(CidrBlock='10.0.0.0/16')['Vpc']['VpcId']
        existing_subnets = ec2.describe_subnets(
            Filters=[{'Name': 'vpc-id', 'Values': [vpc_id]}]
        ).get('Subnets', [])
        if existing_subnets:
            return existing_subnets[0]['SubnetId']
        return ec2.create_subnet(VpcId=vpc_id, CidrBlock='10.0.1.0/24')['Subnet']['SubnetId']

    def _create_hosted_zone(self):
        route53 = boto3.client('route53', region_name=self.region)
        response = route53.create_hosted_zone(
            Name=self.base_domain,
            CallerReference=str(datetime.now(timezone.utc).timestamp())
        )
        return response['HostedZone']['Id'].split('/')[-1]

    def test_multi_instance_launch_injects_distinct_domains_without_accumulation(self):
        import classroom_instance_manager as manager

        manager.clear_template_cache()

        run_instances_calls = []

        def fake_run_instances(**kwargs):
            run_instances_calls.append(kwargs)
            idx = len(run_instances_calls) - 1
            return {
                'Instances': [{
                    'InstanceId': f'i-test-{idx}',
                    'State': {'Name': 'pending'},
                    'LaunchTime': datetime.now(timezone.utc),
                    'PrivateIpAddress': f'10.0.0.{idx + 10}'
                }]
            }

        with patch.object(manager.ec2, 'run_instances', side_effect=fake_run_instances), \
             patch.object(manager, 'setup_caddy_domain', side_effect=lambda instance_id, workshop_name, machine_name=None, domain=None: {
                 'https_url': f'https://{domain}',
                 'domain': domain,
                 'public_ip': '1.2.3.4'
             }), \
             patch.object(manager, 'get_latest_ami') as get_latest_ami:
            result = manager.create_instance(count=2, instance_type='pool', workshop_name=self.workshop_name)

        assert result['success'] is True
        assert len(run_instances_calls) == 2
        assert get_latest_ami.call_count == 0

        first_call = run_instances_calls[0]
        second_call = run_instances_calls[1]
        first_user_data = first_call['UserData']
        second_user_data = second_call['UserData']

        first_domain = 'fellowship-pool-0.fellowship.testingfantasy.com'
        second_domain = 'fellowship-pool-1.fellowship.testingfantasy.com'

        assert first_user_data.count('export CADDY_DOMAIN=') == 1
        assert second_user_data.count('export CADDY_DOMAIN=') == 1
        assert 'cd /opt/fellowship-sut' in first_user_data
        assert 'docker compose up -d' in first_user_data
        assert 'grep -v -E' in first_user_data
        assert 'mv .env.tmp .env' in first_user_data
        assert 'CADDY_DOMAIN=${CADDY_DOMAIN:-}' in first_user_data
        assert 'WORKSHOP_NAME=${WORKSHOP_NAME:-fellowship}' in first_user_data
        assert 'setup_fellowship.sh' not in first_user_data
        assert 'aws s3 cp' not in first_user_data
        assert f'export CADDY_DOMAIN={first_domain}' in first_user_data
        assert f'export CADDY_DOMAIN={second_domain}' in second_user_data
        assert first_domain not in second_user_data

        assert f'export JENKINS_DOMAIN=jenkins-{first_domain}' in first_user_data
        assert f'export IDE_DOMAIN=ide-{first_domain}' in first_user_data
        assert f'export JENKINS_DOMAIN=jenkins-{second_domain}' in second_user_data
        assert f'export IDE_DOMAIN=ide-{second_domain}' in second_user_data
        assert 'export ROUTE53_ZONE_ID=' in first_user_data

        first_tags = {tag['Key']: tag['Value'] for tag in first_call['TagSpecifications'][0]['Tags']}
        second_tags = {tag['Key']: tag['Value'] for tag in second_call['TagSpecifications'][0]['Tags']}

        assert first_tags['HttpsDomain'] == first_domain
        assert second_tags['HttpsDomain'] == second_domain
        assert first_tags['JenkinsDomain'] == f'jenkins-{first_domain}'
        assert first_tags['IdeDomain'] == f'ide-{first_domain}'
        assert second_tags['JenkinsDomain'] == f'jenkins-{second_domain}'
        assert second_tags['IdeDomain'] == f'ide-{second_domain}'

    def test_fellowship_template_only_needs_ami_contract_fields(self):
        import classroom_instance_manager as manager

        manager.clear_template_cache()

        user_data = manager.get_user_data_script(
            template_config={'ami_id': 'ami-12c6146b', 'instance_type': 't3.medium', 'app_port': 5000},
            workshop_name=self.workshop_name,
        )

        assert user_data.startswith('#!/bin/bash')
        assert 'cd /opt/fellowship-sut' in user_data
        assert 'docker compose up -d' in user_data
        assert 'grep -v -E' in user_data
        assert 'mv .env.tmp .env' in user_data
        assert 'CADDY_DOMAIN=${CADDY_DOMAIN:-}' in user_data
        assert 'WORKSHOP_NAME=${WORKSHOP_NAME:-fellowship}' in user_data
        assert 'export WORKSHOP_NAME=' not in user_data
        assert 'setup_fellowship.sh' not in user_data
        assert 'aws s3 cp' not in user_data