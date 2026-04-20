"""
Unit tests for Fellowship Student Assignment Lambda

Tests cover:
- Student creation
- URL generation
- HTML response generation
- Cookie creation
- Error handling
"""

import pytest
import json
import os
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime
import sys
import boto3
from moto import mock_iam, mock_dynamodb, mock_secretsmanager

# Add functions to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock environment before import
os.environ['AWS_REGION'] = 'eu-west-1'
os.environ['WORKSHOP_NAME'] = 'fellowship'
os.environ['ENVIRONMENT'] = 'dev'
os.environ['STATUS_LAMBDA_URL'] = 'https://test.lambda-url.eu-west-1.on.aws/'
os.environ['SKIP_IAM_USER_CREATION'] = 'false'


@mock_iam
@mock_dynamodb
@mock_secretsmanager
class TestFellowshipStudentAssignment:
    """Test suite for fellowship student assignment"""

    def setup_method(self):
        """Setup test environment"""
        # Initialize DynamoDB table
        dynamodb = boto3.resource('dynamodb', region_name='eu-west-1')
        self.table = dynamodb.create_table(
            TableName='instance-assignments-fellowship-dev',
            KeySchema=[
                {'AttributeName': 'student_name', 'KeyType': 'HASH'}
            ],
            AttributeDefinitions=[
                {'AttributeName': 'student_name', 'AttributeType': 'S'}
            ],
            BillingMode='PAY_PER_REQUEST'
        )

        # Create secrets manager secret
        secrets_client = boto3.client('secretsmanager', region_name='eu-west-1')
        secrets_client.create_secret(
            Name='azure/llm/configs',
            SecretString=json.dumps([
                {
                    'config_name': 'GPT-4',
                    'deployment_name': 'gpt-4-deployment',
                    'api_key': 'test-key-1',
                    'endpoint': 'https://test.openai.azure.com/',
                    'api_version': '2024-02-15-preview'
                },
                {
                    'config_name': 'GPT-3.5',
                    'deployment_name': 'gpt-3.5-deployment',
                    'api_key': 'test-key-2',
                    'endpoint': 'https://test.openai.azure.com/',
                    'api_version': '2024-02-15-preview'
                }
            ])
        )

    def test_generate_student_name(self):
        """Test student name generation"""
        from aws.fellowship.fellowship_student_assignment import generate_student_name

        name = generate_student_name()
        assert name.startswith('fellowship-student-')
        assert len(name) > len('fellowship-student-')

    def test_generate_random_password(self):
        """Test password generation"""
        from aws.fellowship.fellowship_student_assignment import generate_random_password

        password = generate_random_password()
        assert len(password) >= 12
        assert any(c.islower() for c in password)
        assert any(c.isupper() for c in password)
        assert any(c.isdigit() for c in password)

    def test_generate_fellowship_urls(self):
        """Test URL generation"""
        from aws.fellowship.fellowship_student_assignment import generate_fellowship_urls

        urls = generate_fellowship_urls(
            'fellowship-student-test123',
            'https://sut.example.com/test'
        )

        assert urls['sut_url'] == 'https://sut.example.com/test'
        assert 'jenkins.fellowship.testingfantasy.com/job/fellowship-student-test123' in urls['jenkins_url']
        assert 'gitea.fellowship.testingfantasy.com/fellowship-org' in urls['gitea_url']
        assert urls['gitea_url'].endswith('fellowship-sut-fellowship-student-test123')

    def test_create_cookie_headers(self):
        """Test cookie creation"""
        from aws.fellowship.fellowship_student_assignment import create_cookie_headers

        user_info = {
            'student_name': 'fellowship-student-test',
            'instance_id': 'i-12345',
            'sut_url': 'https://example.com/sut',
        }

        cookies = create_cookie_headers(user_info)

        assert len(cookies) == 3
        assert any('fellowship_student=' in c for c in cookies)
        assert any('fellowship_instance_id=' in c for c in cookies)
        assert any('fellowship_sut_url=' in c for c in cookies)

    def test_html_response_generation(self):
        """Test HTML response generation"""
        from aws.fellowship.fellowship_student_assignment import generate_html_response

        user_info = {
            'student_name': 'fellowship-student-test',
            'password': 'Test123!',
            'instance_id': 'i-12345',
            'sut_url': 'https://sut.example.com/test',
            'jenkins_url': 'https://jenkins.example.com/job/test/',
            'gitea_url': 'https://gitea.example.com/org/repo',
            'llm_configs': [
                {
                    'config_name': 'Test Config',
                    'deployment_name': 'test-deployment',
                    'api_key': 'test-key',
                    'endpoint': 'https://test.openai.azure.com/'
                }
            ]
        }

        html = generate_html_response(user_info)

        assert '<html' in html.lower()
        assert 'fellowship-student-test' in html
        assert 'jenkins.example.com' in html
        assert 'gitea.example.com' in html
        assert 'Test Config' in html

    def test_html_error_response(self):
        """Test error response generation"""
        from aws.fellowship.fellowship_student_assignment import generate_html_response

        html = generate_html_response({}, error_message="Test error message")

        assert '<html' in html.lower()
        assert 'Test error message' in html
        assert 'The Road is Dark' in html

    @patch('aws.fellowship.fellowship_student_assignment.assign_ec2_instance_to_student')
    def test_create_student_user(self, mock_assign):
        """Test student user creation"""
        from aws.fellowship.fellowship_student_assignment import create_student_user

        # Mock the EC2 assignment
        mock_assign.return_value = {
            'instance_id': 'i-12345',
            'status': 'starting'
        }

        user_info = create_student_user('fellowship-student-test')

        assert user_info['student_name'] == 'fellowship-student-test'
        assert 'password' in user_info
        assert len(user_info['password']) >= 12

    def test_create_student_record(self):
        """Test student record creation in DynamoDB"""
        from aws.fellowship.fellowship_student_assignment import create_student_record

        result = create_student_record(
            'test-student',
            'i-12345',
            'https://sut.example.com',
            {'config_name': 'Test', 'api_key': 'key123'}
        )

        assert result is True

        # Verify record was created
        response = self.table.get_item(Key={'student_name': 'test-student'})
        assert 'Item' in response
        assert response['Item']['student_name'] == 'test-student'
        assert response['Item']['instance_id'] == 'i-12345'

    @patch('aws.fellowship.fellowship_student_assignment.assign_ec2_instance_to_student')
    def test_lambda_handler_new_student(self, mock_assign):
        """Test lambda handler for new student"""
        from aws.fellowship.fellowship_student_assignment import lambda_handler

        mock_assign.return_value = {
            'instance_id': 'i-12345',
            'status': 'starting'
        }

        event = {
            'requestContext': {
                'http': {
                    'method': 'GET',
                    'path': '/'
                }
            },
            'headers': {},
            'cookies': []
        }

        response = lambda_handler(event, None)

        assert response['statusCode'] == 200
        assert response['headers']['Content-Type'] == 'text/html'
        assert 'fellowship' in response['body'].lower()
        assert 'cookies' in response

    def test_lambda_handler_method_not_allowed(self):
        """Test lambda handler with invalid method"""
        from aws.fellowship.fellowship_student_assignment import lambda_handler

        event = {
            'requestContext': {
                'http': {
                    'method': 'POST',
                    'path': '/'
                }
            },
            'headers': {},
        }

        response = lambda_handler(event, None)

        assert response['statusCode'] == 405

    @patch('aws.fellowship.fellowship_student_assignment.cleanup_expired_sessions')
    def test_lambda_handler_destroy(self, mock_cleanup):
        """Test lambda handler destroy endpoint"""
        from aws.fellowship.fellowship_student_assignment import lambda_handler

        event = {
            'requestContext': {
                'http': {
                    'method': 'GET',
                    'path': '/destroy'
                }
            },
            'headers': {},
            'queryStringParameters': {
                'key': 'default_destroy_key'
            }
        }

        response = lambda_handler(event, None)

        assert response['statusCode'] == 200
        mock_cleanup.assert_called_once()

    def test_lambda_handler_destroy_invalid_key(self):
        """Test destroy endpoint with invalid key"""
        from aws.fellowship.fellowship_student_assignment import lambda_handler

        event = {
            'requestContext': {
                'http': {
                    'method': 'GET',
                    'path': '/destroy'
                }
            },
            'headers': {},
            'queryStringParameters': {
                'key': 'wrong_key'
            }
        }

        response = lambda_handler(event, None)

        assert response['statusCode'] == 403


class TestUrlGeneration:
    """Test URL generation logic"""

    def test_sut_url_format(self):
        """Test SUT URL format"""
        from aws.fellowship.fellowship_student_assignment import generate_fellowship_urls

        urls = generate_fellowship_urls('test-student', 'https://sut.example.com/test')
        assert urls['sut_url'].startswith('https://')

    def test_jenkins_url_format(self):
        """Test Jenkins URL format"""
        from aws.fellowship.fellowship_student_assignment import generate_fellowship_urls

        urls = generate_fellowship_urls('test-student', 'https://sut.example.com')
        assert '/job/test-student/' in urls['jenkins_url']

    def test_gitea_url_format(self):
        """Test Gitea URL format"""
        from aws.fellowship.fellowship_student_assignment import generate_fellowship_urls

        urls = generate_fellowship_urls('test-student', 'https://sut.example.com')
        assert 'fellowship-sut-test-student' in urls['gitea_url']


class TestHTMLGeneration:
    """Test HTML response generation"""

    def test_html_contains_required_sections(self):
        """Test HTML contains all required sections"""
        from aws.fellowship.fellowship_student_assignment import generate_html_response

        user_info = {
            'student_name': 'test',
            'password': 'pass123',
            'instance_id': 'i-123',
            'sut_url': 'https://sut.com',
            'jenkins_url': 'https://jenkins.com',
            'gitea_url': 'https://gitea.com',
            'llm_configs': []
        }

        html = generate_html_response(user_info)

        assert '🧝 Fellowship Quest' in html
        assert 'test' in html
        assert 'Your Credentials' in html
        assert 'Fellowship Resources' in html

    def test_html_responsive_design(self):
        """Test HTML includes responsive CSS"""
        from aws.fellowship.fellowship_student_assignment import generate_html_response

        user_info = {
            'student_name': 'test',
            'password': 'pass123',
        }

        html = generate_html_response(user_info)

        assert '@media (max-width: 768px)' in html

    def test_html_copy_to_clipboard(self):
        """Test HTML includes copy functionality"""
        from aws.fellowship.fellowship_student_assignment import generate_html_response

        user_info = {
            'student_name': 'test',
            'password': 'pass123',
        }

        html = generate_html_response(user_info)

        assert 'copyToClipboard' in html
        assert 'navigator.clipboard.writeText' in html


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
