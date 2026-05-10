"""
Unit tests for Fellowship Classroom User Management Lambda

Tests cover:
- Credentials persistence across page reloads (bug fix)
- Maildog URL inclusion in responses
- HTML response generation with credentials
- extract_sut_urls_from_instance
- enrich_user_info_with_urls
"""

import pytest
import json
import os
import sys
from unittest.mock import patch, MagicMock
from datetime import datetime

# Add functions to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Mock environment before import
os.environ.setdefault('AWS_DEFAULT_REGION', 'eu-west-1')
os.environ.setdefault('AWS_REGION', 'eu-west-1')
os.environ.setdefault('WORKSHOP_NAME', 'fellowship')
os.environ.setdefault('ENVIRONMENT', 'dev')
os.environ.setdefault('STATUS_LAMBDA_URL', 'https://test.lambda-url.eu-west-1.on.aws/')
os.environ.setdefault('AWS_ACCOUNT_ID', '123456789012')

from aws.fellowship.fellowship_classroom_user_management import (
    generate_html_response,
    extract_sut_urls_from_instance,
    enrich_user_info_with_urls,
    generate_student_env_content,
    get_student_tokens_from_ssm,
    JENKINS_TOKEN_PLACEHOLDER,
    GITEA_TOKEN_PLACEHOLDER,
)


class TestCredentialsPersistence:
    """Test that Jenkins/Gitea credentials are shown correctly on reload."""

    def _make_user_info(self, with_credentials=True):
        """Helper to build a user_info dict like the lambda handler does."""
        user_info = {
            'user_name': 'legolas_ab12',
            'instance_id': 'i-0abc123def456',
            'sut_url': 'https://legolas-ab12.fellowship.testingfantasy.com',
            'jenkins_url': 'https://jenkins.fellowship.testingfantasy.com/job/legolas_ab12/',
            'gitea_url': 'https://gitea.fellowship.testingfantasy.com/user/login?redirect_to=%2ffellowship-org%2ffellowship-sut-legolas_ab12',
            'ide_url': 'https://ide.legolas-ab12.fellowship.testingfantasy.com',
            'maildog_url': 'https://maildog.fellowship.testingfantasy.com',
            'azure_configs': [],
        }
        if with_credentials:
            user_info['credentials'] = {
                'username': 'legolas_ab12',
                'password': 'legolas_ab12',
            }
        return user_info

    def test_html_contains_credentials_on_first_visit(self):
        """Credentials should be rendered in the HTML on first visit."""
        user_info = self._make_user_info(with_credentials=True)
        html = generate_html_response(user_info)

        # Username and password should appear in the credentials section
        assert 'legolas_ab12' in html
        # The credential-value span should contain the username
        assert '<span class="credential-value">legolas_ab12</span>' in html

    def test_html_credentials_empty_when_missing(self):
        """When credentials dict is absent, the HTML falls back to empty strings."""
        user_info = self._make_user_info(with_credentials=False)
        html = generate_html_response(user_info)

        # The page should still render without errors
        assert 'Fellowship Instance Information' in html
        # Empty credential values
        assert '<span class="credential-value"></span>' in html

    def test_html_credentials_present_with_password_from_dynamodb(self):
        """Simulate reload path: user_info from DynamoDB has 'password' but no 'credentials' key.
        The fix should populate credentials from user_name and password."""
        user_info = self._make_user_info(with_credentials=False)
        # Simulate what DynamoDB returns
        user_info['password'] = 'legolas_ab12'
        user_info['student_name'] = 'legolas_ab12'

        # Simulate the fix logic: populate credentials if missing
        if 'credentials' not in user_info:
            student = user_info.get('user_name', user_info.get('student_name', ''))
            user_info['credentials'] = {
                'username': student,
                'password': user_info.get('password', student),
            }

        html = generate_html_response(user_info)
        assert '<span class="credential-value">legolas_ab12</span>' in html


class TestMaildogUrl:
    """Test that maildog URL appears in the HTML response."""

    def test_html_contains_maildog_link(self):
        """Maildog card should be present in the instance info HTML."""
        user_info = {
            'user_name': 'gandalf_xy99',
            'instance_id': 'i-0abc123def456',
            'sut_url': 'https://gandalf-xy99.fellowship.testingfantasy.com',
            'jenkins_url': 'https://jenkins.fellowship.testingfantasy.com/job/gandalf_xy99/',
            'gitea_url': 'https://gitea.fellowship.testingfantasy.com/user/login',
            'ide_url': 'https://ide.gandalf-xy99.fellowship.testingfantasy.com',
            'maildog_url': 'https://maildog.fellowship.testingfantasy.com',
            'credentials': {'username': 'gandalf_xy99', 'password': 'gandalf_xy99'},
            'azure_configs': [],
        }
        html = generate_html_response(user_info)

        assert 'Maildog' in html
        assert 'https://maildog.fellowship.testingfantasy.com' in html
        assert 'Open Maildog' in html
        assert 'gandalf_xy99@fellowship.testingfantasy.com' in html

    def test_html_maildog_defaults_when_not_set(self):
        """If maildog_url is not in user_info, it should use the default."""
        user_info = {
            'user_name': 'aragorn_zz01',
            'instance_id': 'i-0abc123def456',
            'sut_url': '',
            'jenkins_url': '',
            'gitea_url': '',
            'ide_url': '',
            'credentials': {'username': 'aragorn_zz01', 'password': 'aragorn_zz01'},
            'azure_configs': [],
        }
        html = generate_html_response(user_info)

        # Default maildog URL should be used
        assert 'https://maildog.fellowship.testingfantasy.com' in html
        assert 'Maildog' in html

    def test_env_content_contains_maildog(self):
        """The .env file content should contain MAILDOG_URL."""
        user_info = {
            'user_name': 'frodo_aa11',
            'sut_url': 'https://frodo.fellowship.testingfantasy.com',
            'jenkins_url': 'https://jenkins.fellowship.testingfantasy.com/job/frodo_aa11/',
            'gitea_url': 'https://gitea.fellowship.testingfantasy.com/fellowship-org/fellowship-sut-frodo_aa11',
        }
        env_content = generate_student_env_content(user_info)
        assert 'MAILDOG_URL=https://maildog.fellowship.testingfantasy.com' in env_content
        assert 'frodo_aa11@fellowship.testingfantasy.com' in env_content

    def test_env_content_azure_openai_from_secret(self):
        """Azure OpenAI values from azure/llm/configs secret must appear in .env."""
        azure_configs = [
            {
                'config_name': 'GPT 3.5 Turbo',
                'api_key': 'key-3.5',
                'endpoint': 'https://my-resource.openai.azure.com/openai/deployments/gpt-35/chat/completions?api-version=2025-01-01',
                'deployment_name': 'gpt-35-turbo-16k',
                'api_version': '2024-12-01-preview',
            },
            {
                'config_name': 'GPT 4-o',
                'api_key': 'key-4o',
                'endpoint': 'https://my-resource.openai.azure.com/openai/deployments/gpt-4o/chat/completions?api-version=2025-01-01',
                'deployment_name': 'gpt-4o',
                'api_version': '2024-12-01-preview',
            },
        ]
        user_info = {
            'user_name': 'frodo_aa11',
            'sut_url': 'https://frodo.fellowship.testingfantasy.com',
            'jenkins_url': 'https://jenkins.fellowship.testingfantasy.com/job/frodo_aa11/',
            'gitea_url': 'https://gitea.fellowship.testingfantasy.com/fellowship-org/fellowship-sut-frodo_aa11',
        }
        env_content = generate_student_env_content(user_info, azure_configs)

        # Should prefer GPT-4o config
        assert 'AZURE_OPENAI_DEPLOYMENT=gpt-4o' in env_content
        assert 'AZURE_OPENAI_API_KEY=key-4o' in env_content
        # Endpoint must be normalized to base URL (no /openai/... path or query string)
        assert 'AZURE_OPENAI_ENDPOINT=https://my-resource.openai.azure.com' in env_content
        assert 'AZURE_OPENAI_API_VERSION=2024-12-01-preview' in env_content
        assert 'AZURE_OPENAI_MAX_TOKENS=500' in env_content
        assert 'AZURE_OPENAI_TEMPERATURE=0.7' in env_content

    def test_env_content_azure_fallback_when_no_gpt4o(self):
        """When no GPT-4o config exists, pick any GPT model."""
        azure_configs = [
            {
                'config_name': 'Embeddings',
                'api_key': 'key-embed',
                'endpoint': 'https://res.openai.azure.com',
                'deployment_name': 'text-embedding',
                'api_version': '2023-05-15',
            },
            {
                'config_name': 'GPT 3.5 Turbo',
                'api_key': 'key-35',
                'endpoint': 'https://res.openai.azure.com',
                'deployment_name': 'gpt-35',
                'api_version': '2024-12-01-preview',
            },
        ]
        user_info = {'user_name': 'sam_bb22', 'sut_url': '', 'jenkins_url': '', 'gitea_url': ''}
        env_content = generate_student_env_content(user_info, azure_configs)
        assert 'AZURE_OPENAI_DEPLOYMENT=gpt-35' in env_content
        assert 'AZURE_OPENAI_API_KEY=key-35' in env_content


class TestStudentTokensFromSsm:
    """Test get_student_tokens_from_ssm retrieves tokens correctly."""

    @patch('aws.fellowship.fellowship_classroom_user_management.boto3.client')
    def test_returns_tokens_when_present(self, mock_boto3_client):
        """Tokens found in SSM should be returned in the dict."""
        mock_ssm = MagicMock()
        mock_boto3_client.return_value = mock_ssm
        mock_ssm.get_parameters.return_value = {
            'Parameters': [
                {'Name': '/classroom/fellowship/dev/student-tokens/legolas_ab12/gitea-token', 'Value': 'gitea-tok-abc123'},
                {'Name': '/classroom/fellowship/dev/student-tokens/legolas_ab12/jenkins-token', 'Value': 'jenkins-tok-xyz789'},
            ],
            'InvalidParameters': [],
        }

        result = get_student_tokens_from_ssm('legolas_ab12')

        assert result['gitea_token'] == 'gitea-tok-abc123'
        assert result['jenkins_token'] == 'jenkins-tok-xyz789'

    @patch('aws.fellowship.fellowship_classroom_user_management.boto3.client')
    def test_returns_empty_strings_when_not_found(self, mock_boto3_client):
        """Missing SSM parameters (not yet provisioned) should return empty strings."""
        mock_ssm = MagicMock()
        mock_boto3_client.return_value = mock_ssm
        mock_ssm.get_parameters.return_value = {
            'Parameters': [],
            'InvalidParameters': [
                '/classroom/fellowship/dev/student-tokens/gandalf_xy99/gitea-token',
                '/classroom/fellowship/dev/student-tokens/gandalf_xy99/jenkins-token',
            ],
        }

        result = get_student_tokens_from_ssm('gandalf_xy99')

        assert result['gitea_token'] == ''
        assert result['jenkins_token'] == ''

    @patch('aws.fellowship.fellowship_classroom_user_management.boto3.client')
    def test_returns_empty_strings_on_error(self, mock_boto3_client):
        """SSM errors (e.g., permission denied) should return empty strings gracefully."""
        from botocore.exceptions import ClientError
        mock_ssm = MagicMock()
        mock_boto3_client.return_value = mock_ssm
        mock_ssm.get_parameters.side_effect = ClientError(
            {'Error': {'Code': 'AccessDeniedException', 'Message': 'Access denied'}},
            'GetParameters'
        )

        result = get_student_tokens_from_ssm('aragorn_zz01')

        assert result['gitea_token'] == ''
        assert result['jenkins_token'] == ''

    def test_returns_empty_strings_for_empty_student_name(self):
        """Empty student name should return empty strings without calling SSM."""
        result = get_student_tokens_from_ssm('')
        assert result['gitea_token'] == ''
        assert result['jenkins_token'] == ''


class TestEnvContentWithTokens:
    """Test that generate_student_env_content uses auto-generated tokens from SSM."""

    @patch('aws.fellowship.fellowship_classroom_user_management.get_student_tokens_from_ssm')
    def test_env_uses_auto_generated_tokens_when_available(self, mock_get_tokens):
        """When SSM returns tokens, they should appear in the .env content."""
        mock_get_tokens.return_value = {
            'gitea_token': 'gitea-real-token-abc',
            'jenkins_token': 'jenkins-real-token-xyz',
        }
        user_info = {
            'user_name': 'frodo_aa11',
            'sut_url': 'https://frodo.fellowship.testingfantasy.com',
            'jenkins_url': 'https://jenkins.fellowship.testingfantasy.com/job/frodo_aa11/',
            'gitea_url': 'https://gitea.fellowship.testingfantasy.com/fellowship-org/fellowship-sut-frodo_aa11',
        }
        env_content = generate_student_env_content(user_info)

        assert 'JENKINS_TOKEN=jenkins-real-token-xyz' in env_content
        assert 'GITEA_TOKEN=gitea-real-token-abc' in env_content
        # Should NOT have placeholder values
        assert '<your-jenkins-api-token>' not in env_content
        assert '<your-gitea-api-token>' not in env_content

    @patch('aws.fellowship.fellowship_classroom_user_management.get_student_tokens_from_ssm')
    def test_env_uses_placeholder_when_tokens_not_available(self, mock_get_tokens):
        """When SSM tokens are missing, placeholder values should appear in the .env."""
        mock_get_tokens.return_value = {
            'gitea_token': '',
            'jenkins_token': '',
        }
        user_info = {
            'user_name': 'sam_bb22',
            'sut_url': '',
            'jenkins_url': '',
            'gitea_url': '',
        }
        env_content = generate_student_env_content(user_info)

        assert f'JENKINS_TOKEN={JENKINS_TOKEN_PLACEHOLDER}' in env_content
        assert f'GITEA_TOKEN={GITEA_TOKEN_PLACEHOLDER}' in env_content

    @patch('aws.fellowship.fellowship_classroom_user_management.get_student_tokens_from_ssm')
    def test_env_note_mentions_auto_generated_tokens(self, mock_get_tokens):
        """The HTML note should indicate tokens are auto-generated."""
        mock_get_tokens.return_value = {'gitea_token': 'tok', 'jenkins_token': 'tok'}
        user_info = {
            'user_name': 'legolas_ab12',
            'instance_id': 'i-0abc123def456',
            'sut_url': 'https://legolas-ab12.fellowship.testingfantasy.com',
            'jenkins_url': 'https://jenkins.fellowship.testingfantasy.com/job/legolas_ab12/',
            'gitea_url': 'https://gitea.fellowship.testingfantasy.com/user/login?redirect_to=%2ffellowship-org%2ffellowship-sut-legolas_ab12',
            'ide_url': 'https://ide.legolas-ab12.fellowship.testingfantasy.com',
            'maildog_url': 'https://maildog.fellowship.testingfantasy.com',
            'credentials': {'username': 'legolas_ab12', 'password': 'legolas_ab12'},
            'azure_configs': [],
        }
        html = generate_html_response(user_info)

        assert 'auto-generated' in html
        # Confirm the updated note text is present and the old manual-instruction text is gone
        assert 'JENKINS_TOKEN</code> and <code>GITEA_TOKEN</code> are auto-generated' in html
        assert 'must be generated from your Jenkins/Gitea' not in html


class TestExtractSutUrls:
    """Test extract_sut_urls_from_instance."""

    def test_extracts_all_urls(self):
        tags = {
            'Student': 'legolas_ab12',
            'HttpsDomain': 'legolas-ab12.fellowship.testingfantasy.com',
            'JenkinsDomain': 'jenkins.fellowship.testingfantasy.com',
            'GiteaDomain': 'gitea.fellowship.testingfantasy.com',
            'GiteaOrg': 'fellowship-org',
            'IdeDomain': 'ide.legolas-ab12.fellowship.testingfantasy.com',
        }
        urls = extract_sut_urls_from_instance(tags)

        assert urls['sut_url'] == 'https://legolas-ab12.fellowship.testingfantasy.com'
        assert urls['jenkins_url'] == 'https://jenkins.fellowship.testingfantasy.com/job/legolas_ab12/'
        assert 'gitea.fellowship.testingfantasy.com' in urls['gitea_url']
        assert 'fellowship-sut-legolas_ab12' in urls['gitea_url']
        assert urls['ide_url'] == 'https://ide.legolas-ab12.fellowship.testingfantasy.com'

    def test_handles_empty_tags(self):
        urls = extract_sut_urls_from_instance({})
        assert urls['sut_url'] == ''
        assert urls['jenkins_url'] == ''
        assert urls['gitea_url'] == ''
        assert urls['ide_url'] == ''


class TestEnrichUserInfoWithUrls:
    """Test enrich_user_info_with_urls."""

    def test_enriches_missing_urls(self):
        user_info = {'user_name': 'legolas_ab12'}
        tags = {
            'Student': 'legolas_ab12',
            'HttpsDomain': 'legolas-ab12.fellowship.testingfantasy.com',
            'JenkinsDomain': 'jenkins.fellowship.testingfantasy.com',
            'GiteaDomain': 'gitea.fellowship.testingfantasy.com',
            'IdeDomain': 'ide.legolas-ab12.fellowship.testingfantasy.com',
        }
        result = enrich_user_info_with_urls(user_info, tags)

        assert result['sut_url'] == 'https://legolas-ab12.fellowship.testingfantasy.com'
        assert 'jenkins.fellowship.testingfantasy.com' in result['jenkins_url']

    def test_does_not_overwrite_existing_urls(self):
        user_info = {
            'user_name': 'legolas_ab12',
            'sut_url': 'https://existing-url.com',
        }
        tags = {
            'Student': 'legolas_ab12',
            'HttpsDomain': 'new-domain.com',
        }
        result = enrich_user_info_with_urls(user_info, tags)

        assert result['sut_url'] == 'https://existing-url.com'

    def test_handles_empty_tags(self):
        user_info = {'user_name': 'test_aa11'}
        result = enrich_user_info_with_urls(user_info, {})
        assert 'sut_url' not in result


class TestLambdaHandlerReloadCredentials:
    """Integration-style tests for the reload path ensuring credentials persist."""

    def _make_ec2_response(self, student_name, instance_id='i-0abc123def456'):
        return {
            'Reservations': [{
                'Instances': [{
                    'InstanceId': instance_id,
                    'State': {'Name': 'running'},
                    'PublicIpAddress': '54.1.2.3',
                    'Tags': [
                        {'Key': 'Student', 'Value': student_name},
                        {'Key': 'MachineName', 'Value': student_name},
                        {'Key': 'HttpsDomain', 'Value': f'{student_name.replace("_", "-")}.fellowship.testingfantasy.com'},
                        {'Key': 'JenkinsDomain', 'Value': 'jenkins.fellowship.testingfantasy.com'},
                        {'Key': 'GiteaDomain', 'Value': 'gitea.fellowship.testingfantasy.com'},
                        {'Key': 'IdeDomain', 'Value': f'ide.{student_name.replace("_", "-")}.fellowship.testingfantasy.com'},
                        {'Key': 'Type', 'Value': 'pool'},
                        {'Key': 'AssignedStudent', 'Value': student_name},
                    ],
                }]
            }]
        }

    @patch('aws.fellowship.fellowship_classroom_user_management.get_secret', return_value=[])
    @patch('aws.fellowship.fellowship_classroom_user_management.table')
    @patch('boto3.client')
    def test_reload_with_cookie_instance_id_has_credentials(self, mock_boto_client, mock_table, mock_get_secret):
        """When user reloads with cookie containing instance_id, credentials must appear in HTML."""
        from aws.fellowship.fellowship_classroom_user_management import lambda_handler

        # Mock EC2 client returned by boto3.client
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        mock_ec2.describe_instances.return_value = self._make_ec2_response('legolas_ab12')

        # Mock DynamoDB get_item
        mock_table.get_item.return_value = {
            'Item': {
                'instance_id': 'i-0abc123def456',
                'student_name': 'legolas_ab12',
                'password': 'legolas_ab12',
                'status': 'assigned',
            }
        }

        event = {
            'requestContext': {
                'http': {
                    'method': 'GET',
                    'path': '/',
                }
            },
            'headers': {},
            'cookies': [
                'testus_patronus_user=legolas_ab12',
                'testus_patronus_instance_id=i-0abc123def456',
            ],
        }

        response = lambda_handler(event, None)

        assert response['statusCode'] == 200
        body = response['body']

        # Credentials must be visible
        assert '<span class="credential-value">legolas_ab12</span>' in body
        # Maildog should be present
        assert 'Maildog' in body
        assert 'https://maildog.fellowship.testingfantasy.com' in body

    @patch('aws.fellowship.fellowship_classroom_user_management.get_secret', return_value=[])
    @patch('aws.fellowship.fellowship_classroom_user_management.table')
    @patch('boto3.client')
    def test_reload_with_cookie_username_only_has_credentials(self, mock_boto_client, mock_table, mock_get_secret):
        """When user reloads with only username cookie (no instance_id), credentials must still appear."""
        from aws.fellowship.fellowship_classroom_user_management import lambda_handler

        # Mock EC2 client
        mock_ec2 = MagicMock()
        mock_boto_client.return_value = mock_ec2
        mock_ec2.describe_instances.return_value = self._make_ec2_response('gandalf_zz99')

        # Mock DynamoDB query (student_name-index) — this is the Path B reload
        mock_table.query.return_value = {
            'Items': [{
                'instance_id': 'i-0abc123def456',
                'student_name': 'gandalf_zz99',
                'password': 'gandalf_zz99',
                'status': 'assigned',
            }]
        }

        event = {
            'requestContext': {
                'http': {
                    'method': 'GET',
                    'path': '/',
                }
            },
            'headers': {},
            'cookies': [
                'testus_patronus_user=gandalf_zz99',
            ],
        }

        response = lambda_handler(event, None)

        assert response['statusCode'] == 200
        body = response['body']
        assert '<span class="credential-value">gandalf_zz99</span>' in body
        assert 'Maildog' in body
