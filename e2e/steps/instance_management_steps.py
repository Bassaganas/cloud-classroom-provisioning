"""Step definitions for instance management scenarios."""
import pytest
from pytest_bdd import given, when, then, scenario
import logging
from utils.aws_helpers import (
    instance_exists, instance_is_terminated, get_instance_tags,
    route53_record_exists, delete_route53_record,
    get_instances_by_tag, count_instances_by_tag
)
from utils.uuid_utils import get_test_uuid
import time

logger = logging.getLogger(__name__)

# Scenario: Create pool instance via UI
@when("I create a new pool instance via the UI")
def step_create_pool_instance(page):
    """Create a new pool instance through the UI."""
    page.context.state['instance_ids'] = []
    
    # Click on create instance button
    page.click("button:has-text('Create')")
    page.wait_for_load_state("networkidle")
    
    # Fill in instance details (assuming a modal or form)
    page.select_option("select[name='type']", "pool")
    page.click("button:has-text('Create Instance')")
    page.wait_for_load_state("networkidle")
    
    # Extract instance ID from the newly created row
    # Assuming instance ID is shown in a table or list
    instance_id = page.text_content("tr:last-of-type td:first-of-type")
    page.context.state['instance_ids'].append(instance_id)
    page.context.state['last_instance_id'] = instance_id
    logger.info(f"Created instance: {instance_id}")

@then("the new instance ID appears in the UI")
def step_instance_id_appears_in_ui(page):
    """Verify the instance ID is visible in the UI."""
    instance_id = page.context.state.get('last_instance_id')
    assert instance_id, "No instance ID captured"
    
    # Check if instance ID is displayed in the table
    elements = page.query_selector_all(f"text='{instance_id}'")
    assert len(elements) > 0, f"Instance ID {instance_id} not found in UI"
    logger.info(f"Verified instance {instance_id} appears in UI")

@then("the instance exists in AWS EC2 with \"pool\" type tag")
def step_instance_exists_in_aws_with_tag(page):
    """Verify the instance exists in AWS with correct tags."""
    instance_id = page.context.state.get('last_instance_id')
    assert instance_id, "No instance ID to verify"
    
    # Wait a moment for AWS to process
    time.sleep(2)
    
    # Verify instance exists
    assert instance_exists(instance_id), f"Instance {instance_id} not found in AWS"
    
    # Verify it's a pool type
    tags = get_instance_tags(instance_id)
    assert tags.get('Type') == 'pool', f"Instance type is {tags.get('Type')}, expected 'pool'"
    logger.info(f"Verified instance {instance_id} exists in AWS with pool type")

@then("a Route53 record exists for that instance")
def step_route53_record_exists(page):
    """Verify a Route53 record exists for the instance."""
    instance_id = page.context.state.get('last_instance_id')
    tags = get_instance_tags(instance_id)
    domain = tags.get('HttpsDomain')
    
    assert domain, f"No HttpsDomain tag found for instance {instance_id}"
    
    time.sleep(1)
    assert route53_record_exists(domain), f"Route53 record not found for domain {domain}"
    logger.info(f"Verified Route53 record exists for {domain}")

# Scenario: Delete pool instance via UI
@given("a pool instance exists in the UI")
def step_pool_instance_exists(page):
    """Ensure a pool instance exists."""
    # If no instance was just created, create one
    if 'last_instance_id' not in page.context.state:
        step_create_pool_instance(page)

@when("I select and delete it in the UI")
def step_select_and_delete_instance(page):
    """Select and delete an instance in the UI."""
    instance_id = page.context.state.get('last_instance_id')
    
    # Find the row with the instance ID and click the delete button
    page.click(f"tr:has-text('{instance_id}') button:has-text('Delete')")
    page.wait_for_load_state("networkidle")
    
    # Confirm deletion in modal/dialog
    page.click("button:has-text('Confirm')")
    page.wait_for_load_state("networkidle")
    
    logger.info(f"Deleted instance {instance_id} via UI")

@then("it disappears from the UI")
def step_instance_disappears_from_ui(page):
    """Verify the instance is no longer visible in the UI."""
    instance_id = page.context.state.get('last_instance_id')
    
    # Wait for the instance to disappear
    page.wait_for_selector(f"text='{instance_id}'", state="hidden", timeout=5000)
    
    elements = page.query_selector_all(f"text='{instance_id}'")
    assert len(elements) == 0, f"Instance {instance_id} still visible in UI"
    logger.info(f"Verified instance {instance_id} disappeared from UI")

@then("the EC2 instance is terminated in AWS")
def step_instance_terminated_in_aws(page):
    """Verify the instance is terminated in AWS."""
    instance_id = page.context.state.get('last_instance_id')
    
    # Wait for termination
    time.sleep(3)
    
    assert instance_is_terminated(instance_id), f"Instance {instance_id} not terminated"
    logger.info(f"Verified instance {instance_id} is terminated in AWS")

@then("the Route53 record is deleted")
def step_route53_record_deleted(page):
    """Verify the Route53 record is deleted."""
    instance_id = page.context.state.get('last_instance_id')
    tags = get_instance_tags(instance_id)
    domain = tags.get('HttpsDomain')
    
    time.sleep(2)
    assert not route53_record_exists(domain), f"Route53 record still exists for {domain}"
    logger.info(f"Verified Route53 record deleted for {domain}")

# Scenario: Bulk delete pool instances
@given("multiple pool instance IDs are shown in the UI")
def step_multiple_pool_instances_exist(page):
    """Ensure multiple pool instances exist."""
    if 'instance_ids' not in page.context.state or len(page.context.state['instance_ids']) < 2:
        page.context.state['instance_ids'] = []
        # Create 2 instances
        for i in range(2):
            step_create_pool_instance(page)

@when("I select all and delete them in the UI")
def step_select_all_and_delete(page):
    """Select all instances and delete them."""
    # Click "select all" checkbox
    page.click("input[type='checkbox'][id='select-all']")
    page.wait_for_load_state("networkidle")
    
    # Click delete button
    page.click("button:has-text('Delete Selected')")
    page.wait_for_load_state("networkidle")
    
    # Confirm
    page.click("button:has-text('Confirm')")
    page.wait_for_load_state("networkidle")
    
    logger.info("Bulk deleted all selected instances")

@then("all instances disappear from the UI and AWS")
def step_all_instances_deleted(page):
    """Verify all instances are deleted."""
    instance_ids = page.context.state.get('instance_ids', [])
    
    # Wait for deletion
    time.sleep(3)
    
    for instance_id in instance_ids:
        elements = page.query_selector_all(f"text='{instance_id}'")
        assert len(elements) == 0, f"Instance {instance_id} still visible in UI"
        assert instance_is_terminated(instance_id), f"Instance {instance_id} not terminated in AWS"
    
    logger.info(f"Verified all {len(instance_ids)} instances deleted")

@then("all Route53 records are deleted")
def step_all_route53_records_deleted(page):
    """Verify all Route53 records are deleted."""
    instance_ids = page.context.state.get('instance_ids', [])
    
    time.sleep(2)
    for instance_id in instance_ids:
        tags = get_instance_tags(instance_id)
        domain = tags.get('HttpsDomain')
        if domain:
            assert not route53_record_exists(domain), f"Route53 record still exists for {domain}"
    
    logger.info(f"Verified all Route53 records deleted for {len(instance_ids)} instances")

# Scenario: Delete admin instance via UI
@given("an admin instance exists in the UI")
def step_admin_instance_exists(page):
    """Ensure an admin instance exists."""
    # For now, assume it exists; in real tests, we'd filter by type
    # Or create one if needed
    page.context.state['instance_type'] = 'admin'
    
    # Get first admin instance from the table
    admin_instance = page.first("tr:has-text('admin')")
    if admin_instance:
        instance_id = page.text_content("tr:has-text('admin') td:first-of-type")
        page.context.state['last_instance_id'] = instance_id
        logger.info(f"Found admin instance: {instance_id}")
