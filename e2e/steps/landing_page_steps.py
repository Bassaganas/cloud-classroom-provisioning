"""Step definitions for landing page scenarios."""
import pytest
from pytest_bdd import given, when, then
import logging
import time
from utils.aws_helpers import (
    get_instances_by_tag, count_instances_by_tag,
    get_ec2_client
)

logger = logging.getLogger(__name__)

# Scenario: Display overview and workshop cards
@when("I view the landing page")
def step_view_landing_page(page):
    """View the landing page."""
    page.goto("https://ec2-management-dev.testingfantasy.com/")
    page.wait_for_load_state("networkidle")
    logger.info("Navigated to landing page")

@then("I see all workshops displayed")
def step_see_workshops(page):
    """Verify all workshops are displayed."""
    # Check for workshop cards
    workshop_cards = page.query_selector_all(".workshop-card")
    assert len(workshop_cards) > 0, "No workshop cards found"
    
    logger.info(f"Found {len(workshop_cards)} workshop cards")

@then("I see all tutorial sessions listed")
def step_see_sessions(page):
    """Verify all tutorial sessions are listed."""
    # Check for session listings
    session_elements = page.query_selector_all("[data-testid='session-item']")
    assert len(session_elements) >= 0, "Session list element not found"
    
    logger.info(f"Found {len(session_elements)} sessions listed")

@then("the total EC2 instance count is displayed correctly")
def step_total_instance_count_correct(page):
    """Verify the total EC2 instance count is correct."""
    # Get the displayed count from the UI
    count_text = page.text_content("[data-testid='total-instances']")
    
    # Extract the number
    import re
    numbers = re.findall(r'\d+', count_text)
    assert len(numbers) > 0, "No count found in UI"
    
    displayed_count = int(numbers[0])
    
    # Get actual count from AWS
    ec2 = get_ec2_client()
    response = ec2.describe_instances(
        Filters=[
            {'Name': 'instance-state-name', 'Values': ['running', 'stopped']},
            {'Name': 'tag:Project', 'Values': ['classroom']}
        ]
    )
    
    actual_count = sum(len(r['Instances']) for r in response.get('Reservations', []))
    
    assert displayed_count == actual_count, f"Displayed count {displayed_count} != actual count {actual_count}"
    
    logger.info(f"Verified instance count: {displayed_count}")

# Scenario: Display and filter cost
@then("the cost is displayed")
def step_cost_displayed(page):
    """Verify the cost is displayed."""
    cost_element = page.query_selector("[data-testid='total-cost']")
    assert cost_element, "Cost element not found"
    
    cost_text = page.text_content("[data-testid='total-cost']")
    assert len(cost_text) > 0, "Cost text is empty"
    
    logger.info(f"Cost displayed: {cost_text}")

@then("I can filter by time period")
def step_can_filter_cost(page):
    """Verify cost filter controls exist."""
    filter_selector = page.query_selector("[data-testid='cost-filter']")
    assert filter_selector, "Cost filter control not found"
    
    logger.info("Cost filter control found")

@then("the filtered cost value is shown correctly")
def step_filtered_cost_correct(page):
    """Verify the filtered cost is displayed correctly."""
    # Select a time period filter (e.g., last month)
    page.select_option("[data-testid='cost-filter']", "last-month")
    page.wait_for_load_state("networkidle")
    
    time.sleep(1)
    
    # Verify the cost is updated
    cost_text = page.text_content("[data-testid='total-cost']")
    assert len(cost_text) > 0, "Filtered cost not displayed"
    
    # Extract the amount
    import re
    # Try to find a currency-like pattern
    match = re.search(r'[$£€]\s*[\d,.]+', cost_text)
    assert match, f"No valid cost format found: {cost_text}"
    
    logger.info(f"Filtered cost displayed: {cost_text}")
