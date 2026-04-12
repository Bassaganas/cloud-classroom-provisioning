"""Unit tests for shared-core student provisioning functionality."""
import pytest
import json
from unittest.mock import Mock, patch, MagicMock
import sys
import os

# Add the functions directory to the path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../functions/common'))

from classroom_instance_manager import (
    get_shared_core_instance_id,
    get_shared_core_credentials,
    invoke_ssm_command,
    provision_student_on_shared_core,
    deprovision_student_on_shared_core
)


@pytest.fixture
def mock_ssm_client():
    """Create a mock SSM client."""
    return Mock()


@pytest.fixture
def mock_secretsmanager_client():
    """Create a mock Secrets Manager client."""
    return Mock()


@pytest.fixture
def mock_aws_clients(mock_ssm_client, mock_secretsmanager_client):
    """Patch AWS clients globally."""
    with patch('classroom_instance_manager.ssm', mock_ssm_client), \
         patch('classroom_instance_manager.secretsmanager', mock_secretsmanager_client):
        yield {
            'ssm': mock_ssm_client,
            'secretsmanager': mock_secretsmanager_client
        }


class TestGetSharedCoreInstanceId:
    """Test suite for get_shared_core_instance_id function."""
    
    def test_retrieve_instance_id_success(self, mock_aws_clients):
        """Test successful retrieval of shared-core instance ID from SSM."""
        mock_aws_clients['ssm'].get_parameter.return_value = {
            'Parameter': {'Value': 'i-1234567890abcdef0'}
        }
        
        result = get_shared_core_instance_id(workshop_name='fellowship')
        
        assert result == 'i-1234567890abcdef0'
        mock_aws_clients['ssm'].get_parameter.assert_called_once()
    
    def test_instance_id_not_found(self, mock_aws_clients):
        """Test when shared-core instance ID parameter is not found."""
        mock_aws_clients['ssm'].get_parameter.side_effect = \
            mock_aws_clients['ssm'].exceptions.ParameterNotFound()
        
        result = get_shared_core_instance_id(workshop_name='fellowship')
        
        assert result is None
    
    def test_instance_id_error_handling(self, mock_aws_clients):
        """Test error handling when retrieving instance ID fails."""
        mock_aws_clients['ssm'].get_parameter.side_effect = Exception("AWS API Error")
        
        result = get_shared_core_instance_id(workshop_name='fellowship')
        
        assert result is None


class TestGetSharedCoreCredentials:
    """Test suite for get_shared_core_credentials function."""
    
    def test_retrieve_credentials_success(self, mock_aws_clients):
        """Test successful retrieval of credentials from both SSM and Secrets Manager."""
        # Mock deploy secret from Secrets Manager
        mock_aws_clients['secretsmanager'].get_secret_value.return_value = {
            'SecretString': json.dumps({
                'gitea_admin_password': 'gitea_pass_123',
                'jenkins_admin_password': 'jenkins_pass_123'
            })
        }
        
        # Mock gitea admin user from SSM
        def get_parameter_side_effect(Name, WithDecryption):
            if 'gitea-admin-user' in Name:
                return {'Parameter': {'Value': 'gitea_admin'}}
            elif 'gitea-org-name' in Name:
                return {'Parameter': {'Value': 'fellowship-org'}}
            raise Exception(f"Unknown parameter: {Name}")
        
        mock_aws_clients['ssm'].get_parameter.side_effect = get_parameter_side_effect
        
        result = get_shared_core_credentials()
        
        assert result['gitea_admin_user'] == 'gitea_admin'
        assert result['gitea_admin_password'] == 'gitea_pass_123'
        assert result['jenkins_admin_user'] == 'fellowship'  # Default
        assert result['jenkins_admin_password'] == 'jenkins_pass_123'
        assert result['gitea_org_name'] == 'fellowship-org'
    
    def test_retrieve_credentials_with_defaults(self, mock_aws_clients):
        """Test that defaults are used when parameters are not found."""
        # Mock deploy secret
        mock_aws_clients['secretsmanager'].get_secret_value.return_value = {
            'SecretString': json.dumps({
                'gitea_admin_password': 'custom_gitea_pass',
                'jenkins_admin_password': 'custom_jenkins_pass'
            })
        }
        
        # All SSM parameters not found
        mock_aws_clients['ssm'].get_parameter.side_effect = \
            mock_aws_clients['ssm'].exceptions.ParameterNotFound()
        
        result = get_shared_core_credentials()
        
        assert result['gitea_admin_user'] == 'fellowship'  # Default
        assert result['gitea_admin_password'] == 'custom_gitea_pass'
        assert result['jenkins_admin_user'] == 'fellowship'  # Default
        assert result['jenkins_admin_password'] == 'custom_jenkins_pass'
        assert result['gitea_org_name'] == 'fellowship-org'  # Default
    
    def test_retrieve_credentials_deploy_secret_not_found(self, mock_aws_clients):
        """Test that defaults are used when deploy secret is not found."""
        # Deploy secret not found
        mock_aws_clients['secretsmanager'].get_secret_value.side_effect = \
            mock_aws_clients['secretsmanager'].exceptions.ResourceNotFoundException()
        
        # SSM parameters found
        def get_parameter_side_effect(Name, WithDecryption):
            if 'gitea-admin-user' in Name:
                return {'Parameter': {'Value': 'custom_user'}}
            elif 'gitea-org-name' in Name:
                return {'Parameter': {'Value': 'custom-org'}}
            raise Exception(f"Unknown parameter: {Name}")
        
        mock_aws_clients['ssm'].get_parameter.side_effect = get_parameter_side_effect
        
        result = get_shared_core_credentials()
        
        assert result['gitea_admin_user'] == 'custom_user'
        assert result['gitea_admin_password'] == 'fellowship123'  # Default
        assert result['jenkins_admin_password'] == 'fellowship123'  # Default
        assert result['gitea_org_name'] == 'custom-org'


class TestInvokeSSMCommand:
    """Test suite for invoke_ssm_command function."""
    
    def test_invoke_command_success(self, mock_aws_clients):
        """Test successful SSM command invocation."""
        command_id = 'cmd-123456'
        
        # Mock send command
        mock_aws_clients['ssm'].send_command.return_value = {
            'Command': {'CommandId': command_id}
        }
        
        # Mock command invocation (success on first poll)
        mock_aws_clients['ssm'].get_command_invocation.return_value = {
            'Status': 'Success',
            'StandardOutputContent': 'Command output',
            'StandardErrorContent': ''
        }
        
        with patch('classroom_instance_manager.time.sleep'):  # Don't actually sleep
            result = invoke_ssm_command(
                instance_id='i-123456',
                script_path='/opt/scripts/test.sh',
                parameters=['param1', 'param2']
            )
        
        assert result['success'] is True
        assert result['command_id'] == command_id
        assert result['status'] == 'Success'
        assert 'Command output' in result['output']
    
    def test_invoke_command_with_environment_variables(self, mock_aws_clients):
        """Test SSM command invocation with environment variables."""
        command_id = 'cmd-123456'
        
        mock_aws_clients['ssm'].send_command.return_value = {
            'Command': {'CommandId': command_id}
        }
        
        mock_aws_clients['ssm'].get_command_invocation.return_value = {
            'Status': 'Success',
            'StandardOutputContent': 'Success',
            'StandardErrorContent': ''
        }
        
        with patch('classroom_instance_manager.time.sleep'):
            result = invoke_ssm_command(
                instance_id='i-123456',
                script_path='/opt/scripts/test.sh',
                parameters=['param1'],
                environment_vars={'GITEA_ADMIN_PASSWORD': 'secret123'}
            )
        
        assert result['success'] is True
        
        # Verify the send_command call included environment variables
        send_command_call = mock_aws_clients['ssm'].send_command.call_args
        command_args = send_command_call[1]['Parameters']['command'][0]
        assert 'GITEA_ADMIN_PASSWORD' in command_args or 'secret123' in command_args
    
    def test_invoke_command_failure(self, mock_aws_clients):
        """Test SSM command invocation with failure."""
        command_id = 'cmd-123456'
        
        mock_aws_clients['ssm'].send_command.return_value = {
            'Command': {'CommandId': command_id}
        }
        
        mock_aws_clients['ssm'].get_command_invocation.return_value = {
            'Status': 'Failed',
            'StandardOutputContent': '',
            'StandardErrorContent': 'Command failed: resource not found'
        }
        
        with patch('classroom_instance_manager.time.sleep'):
            result = invoke_ssm_command(
                instance_id='i-123456',
                script_path='/opt/scripts/test.sh',
                parameters=['param1']
            )
        
        assert result['success'] is False
        assert result['status'] == 'Failed'
        assert 'resource not found' in result['error']
    
    def test_invoke_command_timeout(self, mock_aws_clients):
        """Test SSM command invocation timeout."""
        command_id = 'cmd-123456'
        
        mock_aws_clients['ssm'].send_command.return_value = {
            'Command': {'CommandId': command_id}
        }
        
        # Always return pending status (command never completes)
        mock_aws_clients['ssm'].get_command_invocation.return_value = {
            'Status': 'InProgress',
            'StandardOutputContent': '',
            'StandardErrorContent': ''
        }
        
        with patch('classroom_instance_manager.time.sleep'):
            result = invoke_ssm_command(
                instance_id='i-123456',
                script_path='/opt/scripts/test.sh',
                parameters=['param1']
            )
        
        assert result['success'] is False
        assert 'did not complete within 90 seconds' in result.get('message', '')
    
    def test_invoke_command_with_retry_on_instance_not_ready(self, mock_aws_clients):
        """Test SSM command retry when instance is not SSM-ready."""
        command_id = 'cmd-123456'
        
        mock_aws_clients['ssm'].send_command.return_value = {
            'Command': {'CommandId': command_id}
        }
        
        # First call fails with InvalidInstanceInformationException, then succeeds
        mock_aws_clients['ssm'].get_command_invocation.side_effect = [
            Exception("InvalidInstanceInformationException"),  # Retry 1
            Exception("InvalidInstanceInformationException"),  # Retry 2
            {
                'Status': 'Success',
                'StandardOutputContent': 'Success after retry',
                'StandardErrorContent': ''
            }
        ]
        
        with patch('classroom_instance_manager.time.sleep'):
            result = invoke_ssm_command(
                instance_id='i-123456',
                script_path='/opt/scripts/test.sh',
                parameters=['param1'],
                max_retries=3
            )
        
        assert result['success'] is True


class TestProvisionStudentOnSharedCore:
    """Test suite for provision_student_on_shared_core function."""
    
    def test_provision_student_success(self, mock_aws_clients):
        """Test successful student provisioning."""
        # Mock instance ID retrieval
        mock_aws_clients['ssm'].get_parameter.side_effect = [
            {'Parameter': {'Value': 'i-shared-core'}},  # get_shared_core_instance_id
            {'Parameter': {'Value': 'gitea_admin'}},    # get_shared_core_credentials (gitea user)
            {'Parameter': {'Value': 'fellowship-org'}}, # get_shared_core_credentials (org)
        ]
        
        # Mock deploy secret
        mock_aws_clients['secretsmanager'].get_secret_value.return_value = {
            'SecretString': json.dumps({
                'gitea_admin_password': 'gitea_pass',
                'jenkins_admin_password': 'jenkins_pass'
            })
        }
        
        # Mock SSM command execution
        mock_aws_clients['ssm'].send_command.return_value = {
            'Command': {'CommandId': 'cmd-prov-123'}
        }
        mock_aws_clients['ssm'].get_command_invocation.return_value = {
            'Status': 'Success',
            'StandardOutputContent': '✓ Student provisioned',
            'StandardErrorContent': ''
        }
        
        with patch('classroom_instance_manager.time.sleep'):
            result = provision_student_on_shared_core(
                student_id='student1',
                workshop_name='fellowship',
                student_password='student_pass_123'
            )
        
        assert result['success'] is True
        assert 'Successfully' in result['message']
        assert result['command_id'] == 'cmd-prov-123'
    
    def test_provision_student_shared_core_not_configured(self, mock_aws_clients):
        """Test provisioning when shared-core is not configured."""
        # Instance ID not found
        mock_aws_clients['ssm'].get_parameter.side_effect = \
            mock_aws_clients['ssm'].exceptions.ParameterNotFound()
        
        result = provision_student_on_shared_core(
            student_id='student1',
            workshop_name='fellowship'
        )
        
        # Should succeed but skip (graceful degradation)
        assert result['success'] is True
        assert 'not configured' in result['message'].lower()
        assert result['command_id'] == ''


class TestDeprovisionStudentOnSharedCore:
    """Test suite for deprovision_student_on_shared_core function."""
    
    def test_deprovision_student_success(self, mock_aws_clients):
        """Test successful student deprovisioning."""
        # Mock instance ID retrieval
        mock_aws_clients['ssm'].get_parameter.side_effect = [
            {'Parameter': {'Value': 'i-shared-core'}},  # get_shared_core_instance_id
            {'Parameter': {'Value': 'gitea_admin'}},    # get_shared_core_credentials (gitea user)
            {'Parameter': {'Value': 'fellowship-org'}}, # get_shared_core_credentials (org)
        ]
        
        # Mock deploy secret
        mock_aws_clients['secretsmanager'].get_secret_value.return_value = {
            'SecretString': json.dumps({
                'gitea_admin_password': 'gitea_pass',
                'jenkins_admin_password': 'jenkins_pass'
            })
        }
        
        # Mock SSM command execution
        mock_aws_clients['ssm'].send_command.return_value = {
            'Command': {'CommandId': 'cmd-deprov-123'}
        }
        mock_aws_clients['ssm'].get_command_invocation.return_value = {
            'Status': 'Success',
            'StandardOutputContent': '✓ Student removed',
            'StandardErrorContent': ''
        }
        
        with patch('classroom_instance_manager.time.sleep'):
            result = deprovision_student_on_shared_core(
                student_id='student1',
                workshop_name='fellowship',
                force=True
            )
        
        assert result['success'] is True
        assert 'Successfully' in result['message']
        assert result['command_id'] == 'cmd-deprov-123'
    
    def test_deprovision_student_shared_core_not_configured(self, mock_aws_clients):
        """Test deprovisioning when shared-core is not configured."""
        # Instance ID not found
        mock_aws_clients['ssm'].get_parameter.side_effect = \
            mock_aws_clients['ssm'].exceptions.ParameterNotFound()
        
        result = deprovision_student_on_shared_core(
            student_id='student1',
            workshop_name='fellowship',
            force=True
        )
        
        # Should succeed but skip (graceful degradation)
        assert result['success'] is True
        assert 'not configured' in result['message'].lower()
        assert result['command_id'] == ''


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
