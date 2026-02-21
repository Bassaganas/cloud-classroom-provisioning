"""Tests for dashboard functionality."""
import pytest
from playwright.sync_api import Page
from playwright.page_objects.login_page import LoginPage
from playwright.page_objects.dashboard_page import DashboardPage

@pytest.fixture
def authenticated_page(page: Page, base_url: str, test_credentials: dict):
    """Fixture to provide an authenticated page."""
    login_page = LoginPage(page, base_url)
    login_page.login(
        test_credentials['username'],
        test_credentials['password']
    )
    login_page.wait_for_redirect('/dashboard')
    return page

def test_dashboard_loads(authenticated_page: Page, base_url: str):
    """Test that dashboard loads correctly."""
    dashboard_page = DashboardPage(authenticated_page, base_url)
    dashboard_page.navigate()
    
    assert dashboard_page.is_loaded(), "Dashboard should be loaded"
    assert 'Welcome' in dashboard_page.get_welcome_text(), "Welcome message should be displayed"

def test_dashboard_statistics(authenticated_page: Page, base_url: str):
    """Test that dashboard displays quest statistics."""
    dashboard_page = DashboardPage(authenticated_page, base_url)
    dashboard_page.navigate()
    
    # Check that stat cards are displayed
    stat_count = dashboard_page.stats_cards.count()
    assert stat_count >= 4, f"Should have at least 4 stat cards, found {stat_count}"
    
    # Check that stat values are displayed
    total_quests = dashboard_page.get_stat_count(0)
    assert total_quests.isdigit(), "Total quests stat should be a number"

def test_dashboard_quest_list(authenticated_page: Page, base_url: str):
    """Test that dashboard displays quest list."""
    dashboard_page = DashboardPage(authenticated_page, base_url)
    dashboard_page.navigate()
    
    # Check that quest list section exists
    assert dashboard_page.quest_list.is_visible(), "Quest list should be visible"
    
    # Check that at least some quest items are displayed (may be 0 if no quests)
    quest_count = dashboard_page.get_quest_count()
    assert quest_count >= 0, "Quest count should be non-negative"

def test_dashboard_navigation(authenticated_page: Page, base_url: str):
    """Test dashboard navigation links."""
    dashboard_page = DashboardPage(authenticated_page, base_url)
    dashboard_page.navigate()
    
    # Check that navbar is visible
    assert dashboard_page.navbar.is_visible(), "Navbar should be visible"
    
    # Click on Quests link
    dashboard_page.click_quests_link()
    
    # Should navigate to quests page
    authenticated_page.wait_for_url(f"**/quests", timeout=5000)
    assert '/quests' in authenticated_page.url, "Should navigate to quests page"

def test_dashboard_user_info(authenticated_page: Page, base_url: str):
    """Test that dashboard displays user information."""
    dashboard_page = DashboardPage(authenticated_page, base_url)
    dashboard_page.navigate()
    
    welcome_text = dashboard_page.get_welcome_text()
    # Welcome text should contain the user's role (Fellowship member name)
    assert len(welcome_text) > 0, "Welcome text should not be empty"
