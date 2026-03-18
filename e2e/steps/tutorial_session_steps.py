"""Step definitions for tutorial session management scenarios."""
import pytest
from pytest_bdd import given, when, then
import logging
import time
from utils.aws_helpers import (
    get_instances_by_tag, get_instance_by_id,
    count_instances_by_tag, instance_is_terminated,
    route53_record_exists
)
from utils.uuid_utils import get_session_name

logger = logging.getLogger(__name__)

# Scenario: Add new tutorial session
@when("I add a new tutorial session via the UI")
def step_add_tutorial_session(page):
    """Add a new tutorial session via the UI."""
    session_name = get_session_name()
    page.context.state['session_name'] = session_name
    
    # Click on add session button
    page.click("button:has-text('Add Session')")
    page.wait_for_load_state("networkidle")
    
    # Fill in session details
    page.fill("input[name='sessionName']", session_name)
    page.select_option("select[name='workshopId']", "fellowship")
    page.click("button:has-text('Create')")
    page.wait_for_load_state("networkidle")
    
    logger.info(f"Added tutorial session: {session_name}")

@then("the session appears in the UI")
def step_session_appears_in_ui(page):
    """Verify the session appears in the UI."""
    session_name = page.context.state.get('session_name')
    
    # Check if session is visible
    elements = page.query_selector_all(f"text='{session_name}'")
    assert len(elements) > 0, f"Session {session_name} not found in UI"
    
    logger.info(f"Verified session {session_name} appears in UI")

@then("a corresponding EC2 instance pool is created in AWS")
def step_ec2_pool_created_in_aws(page):
    """Verify an EC2 instance pool is created in AWS."""
    session_name = page.context.state.get('session_name')
    
    time.sleep(2)
    
    # Look for instances tagged with the session name
    instances = get_instances_by_tag('WorkshopSession', session_name)
    assert len(instances) > 0, f"No instances found for session {session_name}"
    
    page.context.state['session_instances'] = [i['InstanceId'] for i in instances]
    
    logger.info(f"Verified {len(instances)} instances created in AWS for session {session_name}")

# Scenario: Delete tutorial session (cascade)
@given("a tutorial session with instances exists")
def step_session_with_instances_exists(page):
    """Ensure a session with instances exists."""
    if 'session_name' not in page.context.state:
        step_add_tutorial_session(page)
        step_session_appears_in_ui(page)
        step_ec2_pool_created_in_aws(page)

@when("I delete the session via the UI")
def step_delete_session_via_ui(page):
    """Delete a session via the UI."""
    session_name = page.context.state.get('session_name')
    
    # Find the session card and click delete
    page.click(f"[data-session='{session_name}'] button:has-text('Delete')")
    page.wait_for_load_state("networkidle")
    
    # Confirm deletion
    page.click("button:has-text('Confirm')")
    page.wait_for_load_state("networkidle")
    
    logger.info(f"Deleted session {session_name} via UI")

@then("the session disappears from the UI")
def step_session_disappears_from_ui(page):
    """Verify the session is no longer visible."""
    session_name = page.context.state.get('session_name')
    
    time.sleep(1)
    
    # Refresh page if needed
    page.reload()
    page.wait_for_load_state("networkidle")
    
    elements = page.query_selector_all(f"text='{session_name}'")
    assert len(elements) == 0, f"Session {session_name} still visible in UI"
    
    logger.info(f"Verified session {session_name} disappeared from UI")

@then("all instances in the session are terminated in AWS")
def step_all_instances_terminated_in_aws(page):
    """Verify all instances in the session are terminated."""
    instance_ids = page.context.state.get('session_instances', [])
    
    time.sleep(3)
    
    for instance_id in instance_ids:
        assert instance_is_terminated(instance_id), f"Instance {instance_id} not terminated"
    
    logger.info(f"Verified {len(instance_ids)} instances terminated in AWS")

@then("all Route53 records for those instances are deleted")
def step_all_route53_records_deleted(page):
    """Verify all Route53 records are deleted."""
    instance_ids = page.context.state.get('session_instances', [])
    
    time.sleep(2)
    
    for instance_id in instance_ids:
        instance = get_instance_by_id(instance_id)
        if instance:
            tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
            domain = tags.get('HttpsDomain')
            if domain:
                assert not route53_record_exists(domain), f"Route53 record still exists for {domain}"
    
    logger.info(f"Verified all Route53 records deleted for {len(instance_ids)} instances")
