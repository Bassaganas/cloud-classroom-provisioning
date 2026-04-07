"""Step definitions for admin instance days management scenarios."""
import pytest
from pytest_bdd import given, when, then
import logging
import time
from utils.aws_helpers import (
    instance_exists, instance_is_terminated, get_instance_tags,
    invoke_lambda, get_instance_by_id
)

logger = logging.getLogger(__name__)

# Scenario: Display remaining days for admin instance
@then("the UI shows the correct remaining days for that instance")
def step_ui_shows_remaining_days(page):
    """Verify the UI shows correct remaining days."""
    instance_id = page.context.state.get('last_instance_id')
    
    # Get the cleanup days from AWS tags
    instance = get_instance_by_id(instance_id)
    if not instance:
        raise AssertionError(f"Instance {instance_id} not found in AWS")
    
    tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
    cleanup_days = int(tags.get('CleanupDays', 7))
    
    # Get launch time
    launch_time = instance['LaunchTime']
    from datetime import datetime, timezone
    age_days = (datetime.now(timezone.utc) - launch_time).days
    remaining_days = max(0, cleanup_days - age_days)
    
    # Verify UI shows the remaining days
    remaining_text = page.text_content(f"tr:has-text('{instance_id}') td:has-text('days')")
    assert str(remaining_days) in remaining_text, f"Remaining days {remaining_days} not found in UI"
    
    logger.info(f"Verified remaining days: {remaining_days} for instance {instance_id}")

# Scenario: Extend admin instance days
@when("I extend the days via the UI for that instance")
def step_extend_days_via_ui(page):
    """Extend the days for an admin instance via UI."""
    instance_id = page.context.state.get('last_instance_id')
    
    # Find the extend button for this instance
    page.click(f"tr:has-text('{instance_id}') button:has-text('Extend')")
    page.wait_for_load_state("networkidle")
    
    # Fill in the new days (e.g., 14)
    page.fill("input[name='days']", "14")
    page.click("button:has-text('Save')")
    page.wait_for_load_state("networkidle")
    
    logger.info(f"Extended days for instance {instance_id} to 14")

@then("the new value is shown in the UI")
def step_new_value_shown_in_ui(page):
    """Verify the new value is shown in the UI."""
    instance_id = page.context.state.get('last_instance_id')
    
    # Verify the UI shows the updated remaining days
    # The exact remaining days depends on age, but should be close to 14
    remaining_text = page.text_content(f"tr:has-text('{instance_id}') td:contains('day')")
    
    # Should contain a number close to 14
    import re
    numbers = re.findall(r'\d+', remaining_text)
    assert len(numbers) > 0, "No day numbers found in UI"
    
    remaining = int(numbers[0])
    assert remaining >= 13, f"Expected remaining days >= 13, got {remaining}"
    
    logger.info(f"Verified UI shows updated days for instance {instance_id}")

@then("the CleanupDays tag is updated in AWS")
def step_cleanup_days_tag_updated_in_aws(page):
    """Verify the CleanupDays tag is updated in AWS."""
    instance_id = page.context.state.get('last_instance_id')
    
    time.sleep(2)
    
    instance = get_instance_by_id(instance_id)
    assert instance, f"Instance {instance_id} not found in AWS"
    
    tags = {tag['Key']: tag['Value'] for tag in instance.get('Tags', [])}
    cleanup_days = int(tags.get('CleanupDays', 7))
    
    # Should be 14 or close to it
    assert cleanup_days == 14, f"Expected CleanupDays=14, got {cleanup_days}"
    
    logger.info(f"Verified CleanupDays tag updated to {cleanup_days} in AWS")

# Scenario: Admin instance is auto-deleted after days expire
@given("an admin instance with 0 days remaining is created")
def step_admin_instance_with_zero_days_created(page):
    """Create an admin instance with 0 days remaining."""
    from utils.aws_helpers import get_ec2_client
    from datetime import datetime, timezone, timedelta
    
    ec2 = get_ec2_client()
    
    # Create instance with very short expiry
    response = ec2.run_instances(
        ImageId='ami-12345678',
        MinCount=1,
        MaxCount=1,
        MetadataOptions={
            'HttpTokens': 'required',
            'HttpEndpoint': 'enabled',
            'HttpPutResponseHopLimit': 2
        },
        TagSpecifications=[{
            'ResourceType': 'instance',
            'Tags': [
                {'Key': 'Project', 'Value': 'classroom'},
                {'Key': 'Type', 'Value': 'admin'},
                {'Key': 'CleanupDays', 'Value': '0'},
                {'Key': 'HttpsDomain', 'Value': f"admin-{page.context.state['test_uuid']}.testingfantasy.com"}
            ]
        }]
    )
    
    instance_id = response['Instances'][0]['InstanceId']
    page.context.state['last_instance_id'] = instance_id
    
    logger.info(f"Created admin instance {instance_id} with 0 days remaining")

@when("I trigger the backend cleanup Lambda")
def step_trigger_cleanup_lambda(page):
    """Trigger the cleanup Lambda function."""
    # Invoke the classroom_admin_cleanup Lambda
    response = invoke_lambda(
        'classroom_admin_cleanup',
        payload='{}'
    )
    
    assert response, "Failed to invoke cleanup Lambda"
    assert response.get('StatusCode') == 200, f"Lambda invocation failed: {response}"
    
    logger.info("Triggered cleanup Lambda")
    
    # Wait for Lambda execution
    time.sleep(5)

@then("the instance no longer appears in the UI")
def step_instance_not_in_ui(page):
    """Verify the instance is no longer visible in the UI."""
    instance_id = page.context.state.get('last_instance_id')
    
    # Refresh the page
    page.reload()
    page.wait_for_load_state("networkidle")
    
    # Wait for the instance to disappear
    try:
        page.wait_for_selector(f"text='{instance_id}'", state="hidden", timeout=10000)
    except:
        pass  # OK if already hidden
    
    elements = page.query_selector_all(f"text='{instance_id}'")
    assert len(elements) == 0, f"Instance {instance_id} still visible in UI"
    
    logger.info(f"Verified instance {instance_id} removed from UI")

@then("the instance is terminated in AWS")
def step_instance_terminated_by_cleanup(page):
    """Verify the instance is terminated."""
    instance_id = page.context.state.get('last_instance_id')
    
    assert instance_is_terminated(instance_id), f"Instance {instance_id} not terminated"
    
    logger.info(f"Verified instance {instance_id} terminated by cleanup Lambda")

@then("the Route53 record is deleted")
def step_route53_deleted_by_cleanup(page):
    """Verify the Route53 record is deleted."""
    instance_id = page.context.state.get('last_instance_id')
    
    from utils.aws_helpers import get_instance_tags, route53_record_exists
    
    tags = get_instance_tags(instance_id)
    domain = tags.get('HttpsDomain')
    
    time.sleep(2)
    assert not route53_record_exists(domain), f"Route53 record still exists for {domain}"
    
    logger.info(f"Verified Route53 record deleted for {domain}")
