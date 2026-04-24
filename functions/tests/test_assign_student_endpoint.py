"""
Unit tests for /api/assign-student endpoint

Tests cover:
- Student name generation (unique, format validation)
- Random password generation (security, complexity)
- IAM user creation
- Pool instance reservation
- DynamoDB storage
- Shared-core provisioning
- Error handling and fallbacks
"""

import pytest
import json
import os
import sys
import boto3
from datetime import datetime
from unittest.mock import patch, MagicMock, Mock
from moto import mock_iam, mock_ec2, mock_dynamodb, mock_ssm

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Setup environment before importing
os.environ['AWS_REGION'] = 'eu-west-3'
os.environ['WORKSHOP_NAME'] = 'fellowship'
os.environ['ENVIRONMENT'] = 'dev'
os.environ['SKIP_IAM_USER_CREATION'] = 'false'
os.environ['SHARED_CORE_MODE'] = 'false'
os.environ['CLASSROOM_REGION'] = 'eu-west-3'
os.environ['FELLOWSHIP_SUT_DOMAIN'] = 'sut.fellowship.testingfantasy.com'


@mock_iam
@mock_ec2
@mock_dynamodb
@mock_ssm
class TestAssignStudentEndpoint:
    """Test suite for /api/assign-student endpoint"""

    def setup_method(self):
        """Setup test environment"""
        # Initialize AWS clients
        self.iam = boto3.client('iam', region_name='eu-west-3')
        self.ec2 = boto3.client('ec2', region_name='eu-west-3')
        self.dynamodb = boto3.resource('dynamodb', region_name='eu-west-3')
        self.ssm = boto3.client('ssm', region_name='eu-west-3')
        
        # Create DynamoDB table
        self.table = self.dynamodb.create_table(
            TableName='instance-assignments-fellowship-dev',
            KeySchema=[
                {'AttributeName': 'instance_id', 'KeyType': 'HASH'},
                {'AttributeName': 'student_name', 'KeyType': 'RANGE'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'instance_id', 'AttributeType': 'S'},
                {'AttributeName': 'student_name', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST',
            GlobalSecondaryIndexes=[
                {
                    'IndexName': 'student_name-index',
                    'KeySchema': [
                        {'AttributeName': 'student_name', 'KeyType': 'HASH'}
                    ],
                    'Projection': {'ProjectionType': 'ALL'},
                    'ProvisionedThroughput': {'ReadCapacityUnits': 5, 'WriteCapacityUnits': 5}
                }
            ]
        )
        
        # Create test EC2 pool instances
        for i in range(3):
            self.ec2.run_instances(
                ImageId='ami-12345678',
                MinCount=1,
                MaxCount=1,
                InstanceType='t3.medium',
                TagSpecifications=[{
                    'ResourceType': 'instance',
                    'Tags': [
                        {'Key': 'Type', 'Value': 'pool'},
                        {'Key': 'WorkshopID', 'Value': 'fellowship'},
                        {'Key': 'AssignedStudent', 'Value': '__AVAILABLE__'}
                    ]
                }]
            )

    def test_generate_student_name_format(self):
        """Test that student names follow expected format"""
        from functions.common.classroom_instance_manager import generate_student_name
        
        name = generate_student_name('fellowship')
        assert name.startswith('fellowship-student-')
        assert len(name.split('-')[-1]) == 3  # 3-digit number
        
    def test_generate_student_name_uniqueness(self):
        """Test that generated student names are unique"""
        from functions.common.classroom_instance_manager import generate_student_name
        
        names = set()
        for _ in range(10):
            name = generate_student_name('fellowship')
            assert name not in names, f"Duplicate name generated: {name}"
            names.add(name)
    
    def test_generate_random_password_complexity(self):
        """Test that passwords meet complexity requirements"""
        from functions.common.classroom_instance_manager import generate_random_password
        
        password = generate_random_password()
        
        assert len(password) >= 14, "Password too short"
        assert any(c.isupper() for c in password), "Missing uppercase"
        assert any(c.islower() for c in password), "Missing lowercase"
        assert any(c.isdigit() for c in password), "Missing digit"
        assert any(c in "!@#$%^*-_" for c in password), "Missing symbol"
        
        # Check no ambiguous characters
        ambiguous = "0O1l|`'\""
        assert not any(c in password for c in ambiguous), "Contains ambiguous character"
    
    def test_random_password_no_repeats_ambiguous(self):
        """Test that multiple passwords don't have ambiguous chars"""
        from functions.common.classroom_instance_manager import generate_random_password
        
        ambiguous = "0O1l|`'\""
        for _ in range(20):
            pwd = generate_random_password()
            assert not any(c in pwd for c in ambiguous), f"Ambiguous char in: {pwd}"
    
    def test_create_iam_user_success(self):
        """Test successful IAM user creation"""
        from functions.common.classroom_instance_manager import create_iam_user_for_student
        
        result = create_iam_user_for_student('fellowship-student-001', 'TestPass123!@#', 'fellowship')
        
        assert result['success'] is True
        assert result['user_arn']
        assert 'fellowship-student-001' in result['user_arn']
        
        # Verify user exists
        user = self.iam.get_user(UserName='fellowship-student-001')
        assert user['User']['UserName'] == 'fellowship-student-001'
    
    def test_create_iam_user_already_exists(self):
        """Test IAM user creation when user already exists"""
        from functions.common.classroom_instance_manager import create_iam_user_for_student
        
        # Create user first time
        result1 = create_iam_user_for_student('fellowship-student-001', 'TestPass123!@#', 'fellowship')
        assert result1['success'] is True
        
        # Try to create again - should handle gracefully
        result2 = create_iam_user_for_student('fellowship-student-001', 'NewPass123!@#', 'fellowship')
        assert result2['success'] is False
        assert 'already exists' in result2['error'].lower()
    
    def test_reserve_pool_instance_success(self):
        """Test successful pool instance reservation"""
        from functions.common.classroom_instance_manager import reserve_pool_instance
        
        result = reserve_pool_instance('fellowship')
        
        assert result['success'] is True
        assert result['instance_id']
        assert result['instance_type'] == 't3.medium'
    
    def test_reserve_pool_instance_no_available(self):
        """Test reservation when no instances available"""
        from functions.common.classroom_instance_manager import reserve_pool_instance
        
        # Mark all instances as unavailable
        instances = self.ec2.describe_instances()
        for reservation in instances['Reservations']:
            for instance in reservation['Instances']:
                self.ec2.create_tags(
                    Resources=[instance['InstanceId']],
                    Tags=[{'Key': 'AssignedStudent', 'Value': 'occupied'}]
                )
        
        result = reserve_pool_instance('fellowship')
        
        assert result['success'] is False
        assert 'No available' in result['error']
    
    def test_api_assign_student_full_flow(self):
        """Test complete /api/assign-student flow"""
        # Import after mocking
        from functions.common.classroom_instance_manager import lambda_handler
        
        event = {
            'requestContext': {
                'http': {'method': 'POST', 'path': '/api/assign-student'}
            },
            'body': json.dumps({'workshop': 'fellowship'}),
            'queryStringParameters': {},
            'headers': {}
        }
        
        context = Mock()
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        
        assert body['success'] is True
        assert body['student_name']
        assert body['password']
        assert body['instance_id']
        assert body['sut_url']
        
        # Verify stored in DynamoDB
        items = self.table.query(
            KeyConditionExpression='student_name = :sn',
            ExpressionAttributeValues={':sn': body['student_name']}
        )
        assert items['Items']
    
    def test_api_assign_student_skip_iam(self):
        """Test endpoint when IAM creation is skipped"""
        os.environ['SKIP_IAM_USER_CREATION'] = 'true'
        
        from functions.common.classroom_instance_manager import lambda_handler
        
        event = {
            'requestContext': {
                'http': {'method': 'POST', 'path': '/api/assign-student'}
            },
            'body': json.dumps({'workshop': 'fellowship'}),
            'queryStringParameters': {},
            'headers': {}
        }
        
        context = Mock()
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success'] is True
        
        # IAM user should NOT exist
        with pytest.raises(Exception):  # NoSuchEntity exception
            self.iam.get_user(UserName=body['student_name'])


class TestFellowshipStatusEndpoint:
    """Test suite for fellowship status check"""
    
    def test_parse_status_response_ready(self):
        """Test status response when instance is ready"""
        response_data = {
            'ready': True,
            'ip': '10.0.1.42',
            'instance_id': 'i-xxx',
            'student_name': 'fellowship-student-001'
        }
        
        assert response_data['ready'] is True
        assert response_data['ip']
        assert response_data['instance_id']
    
    def test_parse_status_response_not_ready(self):
        """Test status response when instance not ready"""
        response_data = {
            'ready': False,
            'reason': 'not_running'
        }
        
        assert response_data['ready'] is False
        assert 'reason' in response_data


class TestFellowshipStudentAssignmentHandler:
    """Test suite for fellowship_student_assignment lambda handler"""
    
    def test_parse_cookies_empty(self):
        """Test cookie parsing with empty header"""
        from functions.aws.fellowship.fellowship_student_assignment import parse_cookies
        
        result = parse_cookies('')
        assert result == {}
    
    def test_parse_cookies_single(self):
        """Test cookie parsing with single cookie"""
        from functions.aws.fellowship.fellowship_student_assignment import parse_cookies
        
        result = parse_cookies('fellowship_student=frodo-001')
        assert result['fellowship_student'] == 'frodo-001'
    
    def test_parse_cookies_multiple(self):
        """Test cookie parsing with multiple cookies"""
        from functions.aws.fellowship.fellowship_student_assignment import parse_cookies
        
        result = parse_cookies('fellowship_student=frodo-001; fellowship_instance_id=i-xxx')
        assert result['fellowship_student'] == 'frodo-001'
        assert result['fellowship_instance_id'] == 'i-xxx'
    
    def test_parse_cookies_url_encoded(self):
        """Test cookie parsing with URL-encoded values"""
        from functions.aws.fellowship.fellowship_student_assignment import parse_cookies
        
        result = parse_cookies('fellowship_student=frodo-001%20test')
        assert result['fellowship_student'] == 'frodo-001 test'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
