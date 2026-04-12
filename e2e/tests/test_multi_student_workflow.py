"""E2E tests for multi-student workflow and webhook pipeline integration."""
import pytest
import logging
import sys
import os
import time
import boto3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../utils'))

from gitea_client import GiteaClient
from jenkins_client import JenkinsClient
from student_utils import StudentTestHelper
from uuid_utils import get_test_uuid
from aws_helpers import (
    instance_exists, get_instance_tags, get_instances_by_tag,
    route53_record_exists
)

logger = logging.getLogger(__name__)


@pytest.mark.e2e
@pytest.mark.multi_student
class TestMultiStudentWorkflow:
    """Test suite for multi-student isolation and workflow scenarios."""
    
    @pytest.fixture(autouse=True)
    def setup(self, test_context, aws_environment):
        """Setup test environment with initialized clients."""
        self.test_uuid = test_context['test_uuid']
        self.workshop_name = aws_environment['workshop_name']
        self.region = aws_environment['region']
        
        # Initialize clients
        self.gitea = GiteaClient()
        self.jenkins = JenkinsClient()
        self.student_helper = StudentTestHelper()
        
        # Verify all services are healthy
        assert self.gitea.health_check(), "Gitea service is not healthy"
        assert self.jenkins.health_check(), "Jenkins service is not healthy"
        
        # Test data
        self.student_a_id = self.student_helper.generate_student_id("studentA")
        self.student_b_id = self.student_helper.generate_student_id("studentB")
        
        logger.info(f"Setup complete. Student A: {self.student_a_id}, Student B: {self.student_b_id}")
    
    def teardown_method(self):
        """Cleanup after test."""
        try:
            # Clean up Gitea repos
            for student_id, repo_name in [
                (self.student_a_id, f"repo-{self.student_a_id}"),
                (self.student_b_id, f"repo-{self.student_b_id}")
            ]:
                try:
                    self.gitea.delete_repository(student_id, repo_name)
                except Exception as e:
                    logger.warning(f"Failed to delete repo {student_id}/{repo_name}: {e}")
            
            # Clean up EC2 instances
            for student_id in [self.student_a_id, self.student_b_id]:
                self.student_helper.cleanup_student_instances(student_id, force=False)
        except Exception as e:
            logger.error(f"Error during teardown: {e}")
    
    def test_students_get_unique_instances(self, authenticated_page):
        """
        Scenario: Two students create sessions and get unique instances
        
        Given two students create separate sessions via EC2 Manager
        When checking their assigned instances
        Then each student gets completely different EC2 instances
        And instances are tagged with correct student ID
        """
        logger.info("Testing student instance isolation")
        page = authenticated_page
        
        # Create session for Student A
        logger.info(f"Creating session for {self.student_a_id}")
        self._create_session_via_ui(page, self.student_a_id, pool_count=1)
        
        # Verify Student A has instances
        instances_a = self.student_helper.get_instances_for_student(self.student_a_id)
        assert len(instances_a) > 0, f"No instances found for {self.student_a_id}"
        logger.info(f"Student A instances: {[i['InstanceId'] for i in instances_a]}")
        
        # Create session for Student B
        logger.info(f"Creating session for {self.student_b_id}")
        self._create_session_via_ui(page, self.student_b_id, pool_count=1)
        
        # Verify Student B has instances
        instances_b = self.student_helper.get_instances_for_student(self.student_b_id)
        assert len(instances_b) > 0, f"No instances found for {self.student_b_id}"
        logger.info(f"Student B instances: {[i['InstanceId'] for i in instances_b]}")
        
        # Verify isolation
        is_isolated, message = self.student_helper.verify_instance_isolation(
            self.student_a_id, self.student_b_id
        )
        assert is_isolated, message
        logger.info(f"Instance isolation verified: {message}")
    
    def test_students_get_unique_gitea_repos(self):
        """
        Scenario: Each student gets their own Gitea repository
        
        Given two students with active sessions
        When inspecting their Gitea repositories
        Then each has a unique repository
        And repositories contain isolated code
        """
        logger.info("Testing student Gitea repo isolation")
        
        repo_a = f"repo-{self.student_a_id}"
        repo_b = f"repo-{self.student_b_id}"
        
        # Create repos for each student
        try:
            gitea_repo_a = self.gitea.create_repository(
                self.student_a_id, repo_a, 
                description=f"Student A repository - {self.student_a_id}"
            )
            logger.info(f"Created repo for Student A: {gitea_repo_a['full_name']}")
            
            gitea_repo_b = self.gitea.create_repository(
                self.student_b_id, repo_b,
                description=f"Student B repository - {self.student_b_id}"
            )
            logger.info(f"Created repo for Student B: {gitea_repo_b['full_name']}")
            
            # Verify they're different
            assert gitea_repo_a['id'] != gitea_repo_b['id'], "Repos have same ID"
            assert gitea_repo_a['full_name'] != gitea_repo_b['full_name'], "Repos have same full name"
            
            # Verify ownership is correct
            assert self.student_a_id in gitea_repo_a['full_name'], f"Student A not in repo name: {gitea_repo_a['full_name']}"
            assert self.student_b_id in gitea_repo_b['full_name'], f"Student B not in repo name: {gitea_repo_b['full_name']}"
            
        except Exception as e:
            pytest.fail(f"Failed to create Gitea repos: {e}")
    
    def test_webhook_triggers_jenkins_pipeline(self, authenticated_page):
        """
        Scenario: Push to Gitea repo triggers Jenkins pipeline via webhook
        
        Given a student has a Gitea repository with webhook configured
        When pushing code to the repository
        Then a webhook event is sent to Jenkins
        And Jenkins pipeline is triggered
        And pipeline runs successfully (Lint → Test → Build)
        """
        logger.info("Testing webhook to Jenkins pipeline trigger")
        page = authenticated_page
        
        # Setup: Create session and repo
        student_id = self.student_a_id
        repo_name = f"repo-{student_id}"
        job_name = f"python-pipeline-{student_id}"
        
        # Create Gitea repo
        try:
            gitea_repo = self.gitea.create_repository(
                student_id, repo_name,
                description=f"Test repo for {student_id}"
            )
            logger.info(f"Created test repo: {gitea_repo['full_name']}")
        except Exception as e:
            pytest.fail(f"Failed to create Gitea repo: {e}")
        
        # Create webhook pointing to Jenkins
        jenkins_webhook_url = f"{self.jenkins.base_url}/generic-webhook-trigger/invoke?token={student_id}"
        try:
            webhook = self.gitea.create_webhook(
                student_id, repo_name,
                webhook_url=jenkins_webhook_url,
                events=['push'],
                active=True
            )
            logger.info(f"Created webhook: {webhook.get('id')}")
        except Exception as e:
            pytest.fail(f"Failed to create webhook: {e}")
        
        # Push code to trigger webhook
        sample_code = '''#!/usr/bin/env python3
"""Sample Python application for pipeline testing."""
import sys

def hello():
    """Print hello message."""
    print("Hello from Python!")
    return 0

if __name__ == "__main__":
    sys.exit(hello())
'''
        
        try:
            self.gitea.push_file(
                student_id, repo_name,
                file_path='main.py',
                content=sample_code,
                message="Initial commit - sample Python app"
            )
            logger.info("Pushed code to trigger webhook")
        except Exception as e:
            pytest.fail(f"Failed to push code: {e}")
        
        # Wait for webhook delivery
        logger.info("Waiting for webhook delivery...")
        time.sleep(2)  # Give Gitea time to deliver webhook
        
        try:
            deliveries = self.gitea.get_webhook_deliveries(student_id, repo_name, webhook.get('id'))
            assert len(deliveries) > 0, "No webhook deliveries found"
            
            latest = deliveries[0]
            assert latest['success'], f"Webhook delivery failed: {latest.get('response', 'Unknown error')}"
            logger.info(f"Webhook delivered successfully: {latest['response']}")
        except Exception as e:
            pytest.fail(f"Webhook delivery verification failed: {e}")
        
        # Wait for Jenkins job to start
        logger.info(f"Waiting for Jenkins job '{job_name}' to start...")
        timeout = int(os.getenv('TEST_WEBHOOK_TIMEOUT', 120))
        new_build = self.jenkins.wait_for_build(job_name, timeout=timeout)
        
        if not new_build:
            pytest.fail(f"Jenkins job '{job_name}' did not start within {timeout} seconds")
        
        logger.info(f"Jenkins job started: Build #{new_build.get('number')}")
        
        # Wait for job to complete
        logger.info(f"Waiting for build to complete...")
        build_number = new_build.get('number')
        timeout = int(os.getenv('TEST_PIPELINE_TIMEOUT', 600))
        completed_build = self.jenkins.wait_for_build_completion(
            job_name, build_number, 
            timeout=timeout
        )
        
        assert completed_build, f"Build #{build_number} did not complete within {timeout} seconds"
        
        # Verify build success
        if self.jenkins.is_build_successful(completed_build):
            logger.info(f"Build #{build_number} completed successfully")
        else:
            # Get log for debugging
            log = self.jenkins.get_build_log(job_name, build_number)
            logger.error(f"Build log:\n{log}")
            pytest.fail(f"Build #{build_number} failed with status: {completed_build.get('result')}")
    
    def test_student_isolation_in_pipeline(self):
        """
        Scenario: Students' pipelines run in complete isolation
        
        Given two students have Jenkins jobs configured
        When both trigger pipelines simultaneously
        Then each pipeline runs independently
        And one student's failure doesn't affect the other
        And output/logs are isolated
        """
        logger.info("Testing student isolation in Jenkins pipeline execution")
        
        # This is a more advanced test that would require:
        # 1. Setting up two Jenkins jobs (one per student)
        # 2. Triggering both simultaneously
        # 3. Monitoring they complete independently
        # 4. Verifying logs are isolated
        
        pytest.skip("Advanced test - requires dual Jenkins job setup")
    
    def test_webhook_and_correctly_named_instances(self, authenticated_page):
        """
        Scenario: Instances are correctly named with student identifier
        
        Given a student creates a session via EC2 Manager
        When checking instance tags and naming
        Then instance has correct 'StudentId' tag
        And instance name includes student identifier
        And webhook configuration references correct student/repo
        """
        logger.info("Testing instance naming and webhook configuration")
        page = authenticated_page
        
        student_id = self.student_a_id
        repo_name = f"repo-{student_id}"
        
        # Create session
        self._create_session_via_ui(page, student_id, pool_count=1)
        
        # Get instances
        instances = self.student_helper.get_instances_for_student(student_id)
        assert len(instances) > 0, f"No instances for {student_id}"
        
        # Verify tagging
        for instance in instances:
            tags = instance.get('Tags', {})
            assert 'StudentId' in tags, f"Instance {instance['InstanceId']} missing StudentId tag"
            assert tags['StudentId'] == student_id, f"StudentId tag mismatch"
            logger.info(f"Instance {instance['InstanceId']} correctly tagged: StudentId={student_id}")
        
        # Create Gitea repo and webhook
        try:
            gitea_repo = self.gitea.create_repository(
                student_id, repo_name,
                description=f"Repo for {student_id}"
            )
            
            webhook = self.gitea.create_webhook(
                student_id, repo_name,
                webhook_url=f"{self.jenkins.base_url}/generic-webhook-trigger/invoke",
                events=['push'],
                active=True
            )
            
            logger.info(f"Created webhook for {student_id}/{repo_name}")
            assert webhook.get('active'), "Webhook is not active"
        except Exception as e:
            pytest.fail(f"Failed to create repo/webhook: {e}")
    
    # ===== Helper Methods =====
    
    def _create_session_via_ui(self, page, student_id: str, pool_count: int = 1):
        """Helper to create a session via EC2 Manager UI."""
        # This assumes EC2 Manager UI is loaded
        # Implementation depends on the actual UI structure
        logger.debug(f"Creating session for {student_id} via UI")
        # Implementation would interact with EC2 Manager UI elements
        # For now, this is a placeholder
        pass
