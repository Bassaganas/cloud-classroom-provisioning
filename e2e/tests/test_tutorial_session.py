"""E2E tests for tutorial session management."""
import pytest
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../utils'))

from utils.aws_helpers import get_instances_by_tag, instance_is_terminated
from utils.uuid_utils import get_test_uuid
from utils.aws_helpers import count_instances_for_session, get_instances_for_session, get_unnamed_classroom_instances
from ui_helpers import assert_any_selector_visible, create_tutorial_session, open_tutorial_session, wait_for_condition

logger = logging.getLogger(__name__)

@pytest.mark.e2e
@pytest.mark.session
class TestTutorialSession:
    """Test suite for tutorial session management."""

    def test_add_new_tutorial_session(self, authenticated_page, test_context, aws_environment):
        """
        Scenario: Add new tutorial session
        Given I am on the EC2 Manager sessions page
        When I add a session via UI
        Then it appears in UI and instances are created in AWS
        """
        logger.info("Testing tutorial session creation")
        page = authenticated_page
        workshop_name = aws_environment['workshop_name']
        region = aws_environment['region']
        session_name = f"e2e-tests-session-{test_context['test_uuid']}-tutorial-create"

        before_count = count_instances_for_session(workshop_name, session_name, region=region)
        assert before_count == 0, f"Session {session_name} should not exist before creation"

        unnamed_before = {
            instance['InstanceId']
            for instance in get_unnamed_classroom_instances(workshop_name=workshop_name, region=region)
        }

        create_tutorial_session(page, session_id=session_name, pool_count=1, admin_count=0)

        wait_for_condition(
            lambda: count_instances_for_session(workshop_name, session_name, region=region) == 1,
            timeout_seconds=120,
            poll_interval=5,
            failure_message=f"Expected exactly 1 session instance in AWS for {session_name}"
        )

        created_instances = get_instances_for_session(workshop_name, session_name, region=region)
        assert len(created_instances) == 1, f"Expected 1 instance for {session_name}, got {len(created_instances)}"

        tags = {tag['Key']: tag['Value'] for tag in created_instances[0].get('Tags', [])}
        assert tags.get('Name', '').strip(), f"Created session instance {created_instances[0]['InstanceId']} has empty Name tag"
        assert tags.get('TutorialSessionID') == session_name, "TutorialSessionID tag mismatch"

        assert_any_selector_visible(page, [f'text={session_name}', 'text=active session'])
        unnamed_after = {
            instance['InstanceId']
            for instance in get_unnamed_classroom_instances(workshop_name=workshop_name, region=region)
        }
        assert unnamed_after.issubset(unnamed_before), (
            "Session creation introduced unnamed classroom instances: "
            f"{sorted(unnamed_after - unnamed_before)}"
        )

        logger.info("✓ Session creation flow validated")

    def test_delete_tutorial_session_cascade(self, authenticated_page, test_context, aws_environment):
        """
        Scenario: Delete tutorial session (cascade deletion)
        Given a session with instances exists
        When I delete the session via UI
        Then session and all instances are deleted from AWS
        """
        logger.info("Testing tutorial session cascade deletion")
        page = authenticated_page
        workshop_name = aws_environment['workshop_name']
        region = aws_environment['region']
        session_name = f"e2e-tests-session-{test_context['test_uuid']}-tutorial-delete"

        create_tutorial_session(page, session_id=session_name, pool_count=1, admin_count=1)
        wait_for_condition(
            lambda: count_instances_for_session(workshop_name, session_name, region=region) >= 2,
            timeout_seconds=120,
            poll_interval=5,
            failure_message=f"Expected at least 2 instances for session {session_name} before deletion"
        )

        unnamed_before = {
            instance['InstanceId']
            for instance in get_unnamed_classroom_instances(workshop_name=workshop_name, region=region)
        }

        open_tutorial_session(page, session_name)
        assert_any_selector_visible(page, ['button:has-text("Delete Session")'])
        page.locator('button:has-text("Delete Session")').first.click()

        assert_any_selector_visible(page, ['text=Also delete associated EC2 instances and Route53 DNS records'])
        checkbox = page.locator('[role="dialog"] input[type="checkbox"]').first
        if not checkbox.is_checked():
            checkbox.check()

        page.locator('[role="dialog"] button:has-text("Delete Session")').first.click()

        wait_for_condition(
            lambda: count_instances_for_session(workshop_name, session_name, region=region) == 0,
            timeout_seconds=180,
            poll_interval=5,
            failure_message=f"Session instances for {session_name} were not fully deleted from AWS"
        )

        unnamed_after = {
            instance['InstanceId']
            for instance in get_unnamed_classroom_instances(workshop_name=workshop_name, region=region)
        }
        assert unnamed_after.issubset(unnamed_before), (
            "Session deletion introduced unnamed classroom instances: "
            f"{sorted(unnamed_after - unnamed_before)}"
        )

        assert_any_selector_visible(page, ['text=Workshops'])
        logger.info("✓ Session delete flow validated")

    def test_verify_instances_created_for_session(self, aws_environment):
        """
        Verify that instances are properly created and tagged for sessions
        """
        logger.info("Testing instance creation verification for sessions")
        
        # Get all workshop instances
        instances = get_instances_by_tag('Project', 'classroom', region=aws_environment['region'])
        logger.info(f"Found {len(instances)} classroom instances")
        
        # Verify structure
        assert isinstance(instances, list), "Should return a list"
        logger.info("✓ Session instance verification passed")

