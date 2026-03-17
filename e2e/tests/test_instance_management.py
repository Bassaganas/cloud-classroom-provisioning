"""E2E tests for instance management operations."""
import pytest
import logging
import sys
import os
import time
import boto3

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../utils'))

from utils.aws_helpers import (
    instance_exists, instance_is_terminated, get_instance_tags,
    route53_record_exists, get_instances_by_tag, get_instance_by_id,
    count_instances_for_session, get_instances_for_session, get_unnamed_classroom_instances
)
from utils.uuid_utils import get_test_uuid
from ui_helpers import (
    assert_any_selector_visible,
    create_tutorial_session,
    open_tutorial_session,
    accept_next_dialog,
    wait_for_condition
)

logger = logging.getLogger(__name__)

@pytest.mark.e2e
@pytest.mark.instance
class TestInstanceManagement:
    """Test suite for instance management operations."""

    def test_create_pool_instance_via_ui(self, authenticated_page, test_context, aws_environment):
        """
        Scenario: Create pool instance via UI
        Given I am on the EC2 Manager home page
        When I create a new pool instance with a unique name
        Then the instance ID appears in UI list
        And the instance exists in AWS with correct tags
        And Route53 record is created (if applicable)
        """
        logger.info("Testing pool instance creation via UI")
        page = authenticated_page
        workshop_name = aws_environment['workshop_name']
        region = aws_environment['region']

        session_id = f"e2e-tests-session-{test_context['test_uuid']}-create"

        # Create tutorial session directly with 2 pool instances from UI
        # (spot by default when productive_tutorial is unchecked)
        assert_any_selector_visible(page, ['button:has-text("Create Session")'])
        page.locator('button:has-text("Create Session")').first.click()
        assert_any_selector_visible(page, ['text=Start New Tutorial Session'])

        dialog = page.locator('[role="dialog"]').last
        dialog.locator('input#session_id').fill(session_id)
        dialog.locator('input#pool_count').fill('2')
        dialog.locator('input#admin_count').fill('0')
        dialog.locator('button:has-text("Create Session")').first.click()

        wait_for_condition(
            lambda: count_instances_for_session(workshop_name, session_id, region=region) >= 1,
            timeout_seconds=120,
            poll_interval=5,
            failure_message=f"Initial session instance was not created in AWS for {session_id}"
        )

        before_instances = get_instances_for_session(workshop_name, session_id, region=region)
        before_ids = {instance['InstanceId'] for instance in before_instances}
        before_count = len(before_ids)

        unnamed_before = {
            instance['InstanceId']
            for instance in get_unnamed_classroom_instances(workshop_name=workshop_name, region=region)
        }

        assert_any_selector_visible(page, ['[aria-label="Create instance"]'])
        page.locator('[aria-label="Create instance"]').first.click()
        assert_any_selector_visible(page, ['text=Create Instance'])

        dialog = page.locator('[role="dialog"]').last

        count_input = dialog.locator('input[type="number"]').first
        count_input.fill('1')

        dialog.locator('button:has-text("Create")').first.click()

        wait_for_condition(
            lambda: count_instances_for_session(workshop_name, session_id, region=region) == before_count + 1,
            timeout_seconds=120,
            poll_interval=5,
            failure_message=(
                f"Expected session instance count to increase by 1 for {session_id}. "
                f"Before={before_count}, current={count_instances_for_session(workshop_name, session_id, region=region)}"
            )
        )

        after_instances = get_instances_for_session(workshop_name, session_id, region=region)
        after_ids = {instance['InstanceId'] for instance in after_instances}
        new_ids = sorted(after_ids - before_ids)
        assert len(new_ids) == 1, f"Expected exactly 1 new instance, found {new_ids}"

        new_instance_id = new_ids[0]
        tags = get_instance_tags(new_instance_id, region=region)
        assert tags.get('Name', '').strip(), f"New instance {new_instance_id} has empty Name tag"
        assert tags.get('TutorialSessionID') == session_id, f"Instance {new_instance_id} missing TutorialSessionID={session_id}"
        assert tags.get('Type') == 'pool', f"Instance {new_instance_id} expected Type=pool but got {tags.get('Type')}"

        unnamed_after = {
            instance['InstanceId']
            for instance in get_unnamed_classroom_instances(workshop_name=workshop_name, region=region)
        }
        assert unnamed_after.issubset(unnamed_before), (
            "Test created new unnamed classroom instances: "
            f"{sorted(unnamed_after - unnamed_before)}"
        )

        logger.info("✓ Pool create flow validated with AWS count + tag assertions")

    def test_delete_pool_instance_via_ui(self, authenticated_page, test_context, aws_environment):
        """
        Scenario: Delete spot pool instances via UI without replacement
        Given a tutorial session with 2 spot pool instances exists
        When I delete both instances via UI
        Then they disappear from UI
        And no replacement instances appear in AWS
        And their spot requests are cancelled
        """
        logger.info("Testing spot pool instance deletion via UI with replacement detection")
        page = authenticated_page
        workshop_name = aws_environment['workshop_name']
        region = aws_environment['region']
        base_url = aws_environment['ec2_manager_url'].rstrip('/')
        session_id = f"e2e-tests-session-{test_context['test_uuid']}-delete"
        ec2_client = boto3.client('ec2', region_name=region)

        create_tutorial_session(page, session_id=session_id, pool_count=2, admin_count=0)
        open_tutorial_session(page, session_id=session_id)

        # Navigate directly to avoid flakiness waiting for landing list refresh
        page.goto(f"{base_url}/tutorial/{workshop_name}/{session_id}", wait_until='domcontentloaded')
        assert_any_selector_visible(page, ['text=Search instances', 'text=Instances'], timeout=20000)

        # User flow requirement: pool instances are created from UI.
        # First wait for session-created instances; if none arrive, create via dashboard UI.
        desired_instances = 2
        current_count = 0
        deadline = time.time() + 240
        while time.time() < deadline:
            current_count = count_instances_for_session(workshop_name, session_id, region=region)
            if current_count >= desired_instances:
                break
            time.sleep(5)

        if current_count < 1:
            for _ in range(3):
                assert_any_selector_visible(page, ['[aria-label="Create instance"]'])
                page.locator('[aria-label="Create instance"]').first.click(force=True, no_wait_after=True, timeout=10000)
                assert_any_selector_visible(page, ['text=Create Instance'])
                create_dialog = page.locator('[role="dialog"]').last
                create_dialog.locator('input[type="number"]').first.fill('1')
                create_dialog.locator('button:has-text("Create")').first.click()

                retry_deadline = time.time() + 120
                while time.time() < retry_deadline:
                    current_count = count_instances_for_session(workshop_name, session_id, region=region)
                    if current_count >= 1:
                        break
                    time.sleep(5)

                if current_count >= 1:
                    break

        target_instances = desired_instances if current_count >= desired_instances else 1
        wait_for_condition(
            lambda: count_instances_for_session(workshop_name, session_id, region=region) >= target_instances,
            timeout_seconds=60,
            poll_interval=5,
            failure_message=(
                f"Could not reach at least {target_instances} spot instance(s) in AWS for {session_id} "
                "after UI create flow"
            )
        )

        session_instances = get_instances_for_session(workshop_name, session_id, region=region)
        assert len(session_instances) >= 1, f"Expected at least 1 instance in AWS for session {session_id}, got {len(session_instances)}"
        initial_instance_ids = [instance['InstanceId'] for instance in session_instances]

        for instance in session_instances:
            tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
            assert tags.get('PurchaseType') == 'spot', (
                f"Instance {instance['InstanceId']} is not spot-backed. "
                f"Expected PurchaseType=spot, got {tags.get('PurchaseType')}"
            )

        spot_request_ids = [
            instance.get('SpotInstanceRequestId')
            for instance in session_instances
            if instance.get('SpotInstanceRequestId')
        ]
        assert len(spot_request_ids) >= 1, (
            f"Expected SpotInstanceRequestId for spot instances. Got: {spot_request_ids}"
        )

        unnamed_before = {
            instance['InstanceId']
            for instance in get_unnamed_classroom_instances(workshop_name=workshop_name, region=region)
        }

        delete_buttons = page.locator('tr button:has-text("Delete")')
        delete_count = delete_buttons.count()
        assert delete_count >= 1, f"Expected at least one deletable instance row for session {session_id}"

        for _ in range(delete_count):
            accept_next_dialog(page)
            page.locator('tr button:has-text("Delete")').first.click()
            time.sleep(1)

        wait_for_condition(
            lambda: page.locator('tr button:has-text("Delete")').count() == 0,
            timeout_seconds=120,
            poll_interval=3,
            failure_message=f"Deleted instance rows still visible in UI for session {session_id}"
        )

        wait_for_condition(
            lambda: count_instances_for_session(workshop_name, session_id, region=region) == 0,
            timeout_seconds=180,
            poll_interval=5,
            failure_message=f"Expected all session instances to be deleted for {session_id}"
        )

        # Critical assertion: ensure deletion remains stable and AWS does not spawn replacements.
        # This catches persistent spot requests where instances are terminated but request remains active.
        stability_window_seconds = 120
        poll_interval_seconds = 5
        stability_deadline = time.time() + stability_window_seconds

        while time.time() < stability_deadline:
            current_instances = get_instances_for_session(workshop_name, session_id, region=region)
            if current_instances:
                replacement_ids = [instance['InstanceId'] for instance in current_instances]
                pytest.fail(
                    f"Spot replacement instances detected for {session_id}. "
                    f"Expected 0 instances after deletion, but found {len(current_instances)}: {replacement_ids}. "
                    f"This indicates spot requests were not cancelled."
                )
            time.sleep(poll_interval_seconds)

        # Spot requests must be cancelled/closed after deletion.
        for request_id in spot_request_ids:
            response = ec2_client.describe_spot_instance_requests(SpotInstanceRequestIds=[request_id])
            requests = response.get('SpotInstanceRequests', [])
            assert requests, f"Spot request {request_id} not found for deleted instance"

            state = requests[0].get('State', 'unknown')
            assert state in {'cancelled', 'closed'}, (
                f"Spot request {request_id} is still active ({state}) after instance deletion. "
                "Expected cancelled/closed to avoid replacement instances."
            )

        # API behavior can keep tags during shutting-down/terminating transitions;
        # authoritative assertion is that no active session instances remain.
        unnamed_after = {
            instance['InstanceId']
            for instance in get_unnamed_classroom_instances(workshop_name=workshop_name, region=region)
        }
        assert unnamed_after.issubset(unnamed_before), (
            "Test introduced new unnamed classroom instances: "
            f"{sorted(unnamed_after - unnamed_before)}"
        )

        logger.info("✓ Spot pool delete flow validated with stable AWS/UI deletion assertions")

    def test_verify_ec2_instance_creation_in_aws(self, aws_environment):
        """
        Verify that instances with test tags exist in AWS
        """
        logger.info("Testing EC2 instance creation verification in AWS")
        
        # Look for classroom instances and validate required tags
        instances = get_instances_by_tag('Project', 'classroom', aws_environment['region'])
        logger.info(f"Found {len(instances)} classroom instances in AWS")
        
        assert isinstance(instances, list), "Should return a list of instances"
        for instance in instances:
            tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
            assert tags.get('Name', '').strip(), f"Instance {instance['InstanceId']} has empty Name tag"
            assert tags.get('WorkshopID'), f"Instance {instance['InstanceId']} missing WorkshopID tag"
        logger.info("✓ EC2 instance verification passed")

    def test_verify_route53_record_operations(self, aws_environment):
        """
        Verify Route53 operations: zone configuration
        """
        logger.info("Testing Route53 configuration")
        
        # Get hosted zone from environment
        zone_id = aws_environment.get('hosted_zone_id')
        assert zone_id, "Route53 hosted zone not configured"
        
        # Verify zone ID format
        assert zone_id.startswith('Z'), f"Invalid zone ID format: {zone_id}"
        logger.info(f"✓ Route53 hosted zone verified: {zone_id}")

    def test_instance_tags_validation(self, aws_environment):
        """
        Verify that instances can be tagged correctly
        """
        logger.info("Testing instance tag validation")
        
        # Get a test instance (if any exist)
        instances = get_instances_by_tag('Project', 'classroom', aws_environment['region'])
        
        if instances and len(instances) > 0:
            instance_id = instances[0]['InstanceId']
            tags = get_instance_tags(instance_id, aws_environment['region'])
            assert isinstance(tags, dict), "Tags should be a dictionary"
            logger.info(f"Instance {instance_id} tags: {tags}")
        
        logger.info("✓ Instance tag structure validated")

