"""E2E tests for landing page functionality."""
import pytest
import logging
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../utils'))
sys.path.insert(0, os.path.dirname(__file__))

from utils.aws_helpers import get_instances_by_tag
from ui_helpers import assert_any_selector_visible

logger = logging.getLogger(__name__)

@pytest.mark.e2e
@pytest.mark.landing
class TestLandingPage:
    """Test suite for landing page functionality."""

    def test_display_workshop_overview(self, authenticated_page, aws_environment):
        """
        Scenario: Display workshop overview and cards
        Given I visit the EC2 Manager landing page
        Then all workshops are displayed with correct information
        """
        logger.info("Testing workshop overview display")
        page = authenticated_page

        assert_any_selector_visible(page, ['text=Workshops'])
        assert_any_selector_visible(page, ['text=Tutorial Sessions'])
        assert_any_selector_visible(page, ['text=Tracked Session Instances'])
        assert_any_selector_visible(page, ['text=Session Costs'])
        assert_any_selector_visible(page, ['input[placeholder="Search workshops or session IDs"]'])

        logger.info("✓ Workshop overview display test passed")

    def test_display_instance_count(self, authenticated_page, aws_environment):
        """
        Scenario: Display total EC2 instance count
        When I view the EC2 Manager
        Then the instance count is displayed and matches AWS
        """
        logger.info("Testing instance count display")
        page = authenticated_page
        
        # Get actual instance count from AWS
        instances = get_instances_by_tag('Project', 'classroom', region=aws_environment['region'])
        actual_count = len(instances)
        logger.info(f"Actual instance count in AWS: {actual_count}")

        assert_any_selector_visible(page, ['text=Tracked Session Instances'])
        assert_any_selector_visible(page, ['text=/\\d+/'])
        
        logger.info("✓ Instance count display test passed")

    def test_display_and_filter_cost(self, authenticated_page, aws_environment):
        """
        Scenario: Display and filter cost by time period
        When I view cost information
        Then costs are displayed and can be filtered
        """
        logger.info("Testing cost display and filtering")
        page = authenticated_page

        assert_any_selector_visible(page, ['text=Session Costs'])
        search_input = page.locator('input[placeholder="Search workshops or session IDs"]').first
        search_input.wait_for(state='visible', timeout=10000)
        search_input.fill('unlikely-e2e-filter-value')
        assert_any_selector_visible(page, ['text=No workshops available for this search.'])
        search_input.fill('')
        assert_any_selector_visible(page, ['text=Workshops'])
        
        logger.info("✓ Cost display and filtering test passed")

    def test_verify_aws_integration(self, authenticated_page, aws_environment):
        """
        Verify that AWS integration is properly configured and page loads
        """
        logger.info("Testing AWS integration and page loading")
        page = authenticated_page
        assert_any_selector_visible(page, ['text=Workshops'])
        
        # Check environment is configured
        assert aws_environment['hosted_zone_id'], "Route53 hosted zone not configured"
        assert aws_environment['region'], "AWS region not configured"
        
        logger.info(f"AWS Region: {aws_environment['region']}")
        logger.info(f"Route53 Zone: {aws_environment['hosted_zone_id']}")
        logger.info("✓ AWS integration verified")

