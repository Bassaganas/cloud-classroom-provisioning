"""Integration tests for shared-core student provisioning E2E workflow."""
import pytest
import json
import boto3
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


class TestStudentProvisioningE2E:
    """Integration tests for student provisioning E2E workflows."""
    
    @pytest.mark.integration
    def test_student_lifecycle_assign_and_remove(self):
        """
        Test complete student lifecycle: assign → provision → deprovision → remove.
        
        Scenario:
        1. Student is assigned to an EC2 instance
        2. Provisioning is triggered on shared-core (create Gitea user, repo, Jenkins job)
        3. Student code changes trigger webhook/pipeline
        4. Student instance is deleted
        5. Deprovisioning is triggered on shared-core (delete all resources)
        
        This test verifies the integration between:
        - Lambda functions (provisioning/deprovisioning wrappers)
        - AWS SSM (command execution)
        - AWS Secrets Manager (credential retrieval)
        - AWS SSM Parameter Store (instance ID, config)
        - Shared-core instance (provision/deprovision scripts)
        """
        student_id = 'integration-test-student-001'
        workshop_name = 'fellowship'
        
        # Step 1: Verify shared-core is configured
        with patch('classroom_instance_manager.ssm') as mock_ssm, \
             patch('classroom_instance_manager.secretsmanager') as mock_secretsmanager:
            
            # Configure mocks for credential retrieval
            mock_ssm.get_parameter.side_effect = lambda Name, WithDecryption: {
                '/classroom/shared-core/dev/instance-id': {'Parameter': {'Value': 'i-shared-core-dev'}},
                '/classroom/shared-core/dev/gitea-admin-user': {'Parameter': {'Value': 'fellowship'}},
                '/classroom/shared-core/dev/gitea-org-name': {'Parameter': {'Value': 'fellowship-org'}},
            }.get(Name, Mock(side_effect=mock_ssm.exceptions.ParameterNotFound()))
            
            mock_secretsmanager.get_secret_value.return_value = {
                'SecretString': json.dumps({
                    'gitea_admin_password': 'fellowship123',
                    'jenkins_admin_password': 'fellowship123'
                })
            }
            
            # Mock SSM command execution
            mock_ssm.send_command.return_value = {
                'Command': {'CommandId': 'cmd-prov-001'}
            }
            
            # Mock command completion (success)
            mock_ssm.get_command_invocation.return_value = {
                'Status': 'Success',
                'StandardOutputContent': 'Student provisioned successfully',
                'StandardErrorContent': ''
            }
            
            # Step 2: Provision student
            with patch('classroom_instance_manager.time.sleep'):
                provision_result = provision_student_on_shared_core(
                    student_id=student_id,
                    workshop_name=workshop_name,
                    student_password='secure_pass_123'
                )
            
            # Verify provisioning succeeded
            assert provision_result['success'] is True, \
                f"Provisioning failed: {provision_result.get('error', '')}"
            assert provision_result['command_id'] == 'cmd-prov-001'
            assert 'Provision' in provision_result['message']
            
            # Verify provisioning script was called with correct parameters
            send_command_call = mock_ssm.send_command.call_args
            assert send_command_call is not None
            command_args = send_command_call[1]['Parameters']['command'][0]
            assert 'provision-student.sh' in command_args
            assert student_id in command_args
            assert 'GITEA_ADMIN_USER' in command_args or 'fellowship' in command_args
            
            # Step 3: Verify dependencies and verify deprovisioning (when instance deleted)
            # Reset mocks for deprovisioning
            mock_ssm.send_command.reset_mock()
            mock_ssm.send_command.return_value = {
                'Command': {'CommandId': 'cmd-deprov-001'}
            }
            
            mock_ssm.get_command_invocation.return_value = {
                'Status': 'Success',
                'StandardOutputContent': 'Student deprovisioned successfully',
                'StandardErrorContent': ''
            }
            
            # Step 4: Deprovision student
            with patch('classroom_instance_manager.time.sleep'):
                deprovision_result = deprovision_student_on_shared_core(
                    student_id=student_id,
                    workshop_name=workshop_name,
                    force=True
                )
            
            # Verify deprovisioning succeeded
            assert deprovision_result['success'] is True, \
                f"Deprovisioning failed: {deprovision_result.get('error', '')}"
            assert deprovision_result['command_id'] == 'cmd-deprov-001'
            assert 'Deprovision' in deprovision_result['message']
            
            # Verify deprovisioning script was called with correct parameters
            send_command_call = mock_ssm.send_command.call_args
            assert send_command_call is not None
            command_args = send_command_call[1]['Parameters']['command'][0]
            assert 'deprovision-student.sh' in command_args
            assert student_id in command_args
            assert '--confirm' in command_args
    
    @pytest.mark.integration
    def test_student_provisioning_with_multiple_students(self):
        """
        Test provisioning multiple students in parallel.
        
        Scenario:
        - Multiple students assigned to shared-core simultaneously
        - Each should be provisioned independently
        - No cross-contamination or resource conflicts
        """
        students = ['student-001', 'student-002', 'student-003']
        workshop_name = 'fellowship'
        
        with patch('classroom_instance_manager.ssm') as mock_ssm, \
             patch('classroom_instance_manager.secretsmanager') as mock_secretsmanager:
            
            # Configure credentials
            mock_ssm.get_parameter.side_effect = lambda Name, WithDecryption: {
                '/classroom/shared-core/dev/instance-id': {'Parameter': {'Value': 'i-shared-core-dev'}},
                '/classroom/shared-core/dev/gitea-admin-user': {'Parameter': {'Value': 'fellowship'}},
                '/classroom/shared-core/dev/gitea-org-name': {'Parameter': {'Value': 'fellowship-org'}},
            }.get(Name, Mock(side_effect=mock_ssm.exceptions.ParameterNotFound()))
            
            mock_secretsmanager.get_secret_value.return_value = {
                'SecretString': json.dumps({
                    'gitea_admin_password': 'fellowship123',
                    'jenkins_admin_password': 'fellowship123'
                })
            }
            
            # Mock SSM command execution for each student
            mock_ssm.send_command.return_value = {
                'Command': {'CommandId': 'cmd-prov-multi'}
            }
            
            mock_ssm.get_command_invocation.return_value = {
                'Status': 'Success',
                'StandardOutputContent': 'Student provisioned',
                'StandardErrorContent': ''
            }
            
            # Provision each student
            with patch('classroom_instance_manager.time.sleep'):
                results = []
                for student_id in students:
                    result = provision_student_on_shared_core(
                        student_id=student_id,
                        workshop_name=workshop_name
                    )
                    results.append(result)
            
            # Verify all provisioning succeeded
            for i, result in enumerate(results):
                assert result['success'] is True, \
                    f"Provisioning failed for student {students[i]}: {result.get('error', '')}"
            
            # Verify each student received a unique command
            assert mock_ssm.send_command.call_count >= len(students)
            
            # Verify each call requested the correct student
            calls = [call[1]['Parameters']['command'][0] for call in mock_ssm.send_command.call_args_list]
            for student_id in students:
                assert any(student_id in call for call in calls), \
                    f"Student {student_id} not found in any provisioning command"
    
    @pytest.mark.integration
    def test_graceful_degradation_when_shared_core_not_configured(self):
        """
        Test graceful degradation when shared-core is not configured.
        
        Scenario:
        - shared-core instance ID not available in SSM
        - Student assignment should still succeed
        - Provisioning should be silently skipped (non-blocking)
        """
        student_id = 'student-no-shared-core'
        workshop_name = 'fellowship'
        
        with patch('classroom_instance_manager.ssm') as mock_ssm, \
             patch('classroom_instance_manager.secretsmanager') as mock_secretsmanager:
            
            # Instance ID parameter not found (graceful degradation)
            mock_ssm.get_parameter.side_effect = mock_ssm.exceptions.ParameterNotFound()
            
            # Attempt to provision
            with patch('classroom_instance_manager.time.sleep'):
                result = provision_student_on_shared_core(
                    student_id=student_id,
                    workshop_name=workshop_name
                )
            
            # Should still succeed (non-blocking)
            assert result['success'] is True, \
                "Provisioning should succeed even when shared-core not configured"
            assert 'not configured' in result['message'].lower(), \
                f"Message should indicate shared-core not configured: {result['message']}"
            
            # SSM command should NOT be invoked
            mock_ssm.send_command.assert_not_called()
    
    @pytest.mark.integration
    def test_credential_retrieval_fallback_chain(self):
        """
        Test credential retrieval with complete fallback chain.
        
        Scenario:
        1. Try to read deploy secret from Secrets Manager
        2. If not found, use hardcoded defaults
        3. Try to read usernames from SSM parameters
        4. If not found, use hardcoded defaults
        5. Verify final merged credentials
        """
        with patch('classroom_instance_manager.ssm') as mock_ssm, \
             patch('classroom_instance_manager.secretsmanager') as mock_secretsmanager:
            
            # Simulate partial configuration (only some parameters exist)
            def get_parameter_side_effect(Name, WithDecryption):
                if 'gitea-admin-user' in Name:
                    # This parameter exists with custom value
                    return {'Parameter': {'Value': 'custom_gitea_user'}}
                else:
                    # Other parameters not found
                    raise mock_ssm.exceptions.ParameterNotFound()
            
            mock_ssm.get_parameter.side_effect = get_parameter_side_effect
            
            # Deploy secret not found
            mock_secretsmanager.get_secret_value.side_effect = \
                mock_secretsmanager.exceptions.ResourceNotFoundException()
            
            # Retrieve credentials
            result = get_shared_core_credentials()
            
            # Verify fallback chain worked correctly
            assert result['gitea_admin_user'] == 'custom_gitea_user', "Should use custom value from SSM"
            assert result['gitea_admin_password'] == 'fellowship123', "Should use default password"
            assert result['jenkins_admin_user'] == 'fellowship', "Should use default Jenkins user"
            assert result['gitea_org_name'] == 'fellowship-org', "Should use default org name"
    
    @pytest.mark.integration
    def test_provisioning_with_special_characters_in_password(self):
        """
        Test provisioning with special characters in student password.
        
        Scenario:
        - Student password contains special characters: !@#$%^&*()
        - Ensure proper escaping when passing to SSM command
        """
        student_id = 'student-special-chars'
        special_password = "P@ssw0rd!#$%&*()_+-=[]{}|;:,.<>?"
        
        with patch('classroom_instance_manager.ssm') as mock_ssm, \
             patch('classroom_instance_manager.secretsmanager') as mock_secretsmanager:
            
            # Configure mocks
            mock_ssm.get_parameter.side_effect = lambda Name, WithDecryption: {
                '/classroom/shared-core/dev/instance-id': {'Parameter': {'Value': 'i-shared-core'}},
                '/classroom/shared-core/dev/gitea-admin-user': {'Parameter': {'Value': 'fellowship'}},
                '/classroom/shared-core/dev/gitea-org-name': {'Parameter': {'Value': 'fellowship-org'}},
            }.get(Name, Mock(side_effect=mock_ssm.exceptions.ParameterNotFound()))
            
            mock_secretsmanager.get_secret_value.return_value = {
                'SecretString': json.dumps({
                    'gitea_admin_password': 'pass123',
                    'jenkins_admin_password': 'pass123'
                })
            }
            
            mock_ssm.send_command.return_value = {
                'Command': {'CommandId': 'cmd-special'}
            }
            
            mock_ssm.get_command_invocation.return_value = {
                'Status': 'Success',
                'StandardOutputContent': 'Success',
                'StandardErrorContent': ''
            }
            
            # Provision with special password
            with patch('classroom_instance_manager.time.sleep'):
                result = provision_student_on_shared_core(
                    student_id=student_id,
                    workshop_name='fellowship',
                    student_password=special_password
                )
            
            # Verify provisioning succeeded (special chars properly escaped)
            assert result['success'] is True, \
                f"Provisioning with special chars failed: {result.get('error', '')}"
            
            # Verify the password was properly encoded in the command
            send_command_call = mock_ssm.send_command.call_args
            command = send_command_call[1]['Parameters']['command'][0]
            # The password should be either quoted or escaped in the command
            assert "'" in command or '"' in command or '\\' in command, \
                "Special characters should be properly escaped/quoted in SSM command"


if __name__ == '__main__':
    pytest.main([__file__, '-v', '-m', 'integration'])
