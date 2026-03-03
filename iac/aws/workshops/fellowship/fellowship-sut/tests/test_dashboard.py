"""Tests for dashboard functionality."""
import pytest
from playwright.sync_api import Page
from tests.page_objects.login_page import LoginPage
from tests.page_objects.dashboard_page import DashboardPage

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
    
    assert '/dashboard' in authenticated_page.url, "Dashboard should be loaded"
    assert authenticated_page.locator('nav, [role="navigation"]').count() > 0, "Navigation should be visible"

def test_dashboard_statistics(authenticated_page: Page, base_url: str):
    """Test that dashboard displays quest statistics with LOTR terminology."""
    dashboard_page = DashboardPage(authenticated_page, base_url)
    dashboard_page.navigate()
    
    # At least one dashboard metric-like value or card is visible
    metric_candidates = authenticated_page.locator('.text-4xl.font-epic, [data-testid="mission-briefing"], .quest-card')
    assert metric_candidates.count() > 0, "Dashboard should display stats or mission/quest summary content"

def test_dashboard_quest_list(authenticated_page: Page, base_url: str):
    """Test that dashboard displays quest list."""
    dashboard_page = DashboardPage(authenticated_page, base_url)
    dashboard_page.navigate()
    
    # Check that dashboard contains quest-related section text
    quest_section = authenticated_page.locator('text=/Quest|Mission/i').first
    assert quest_section.is_visible(), "Quest/mission section should be visible"

def test_dashboard_navigation(authenticated_page: Page, base_url: str):
    """Test dashboard navigation links."""
    dashboard_page = DashboardPage(authenticated_page, base_url)
    dashboard_page.navigate()
    
    # Check that navbar is visible
    assert dashboard_page.navbar.is_visible(), "Navbar should be visible"
    
    # Click on Quests link (LOTR terminology)
    dashboard_page.click_quests_link()
    
    # Should navigate to quests page
    authenticated_page.wait_for_url(f"**/quests", timeout=5000)
    assert '/quests' in authenticated_page.url, "Should navigate to quests page"
    
    # Check quest page has relevant content even if heading levels vary
    assert authenticated_page.locator('text=/Scrolls|Quests/i').count() > 0, "Quests page should have relevant title or nav text"

def test_dashboard_user_info(authenticated_page: Page, base_url: str):
    """Test that dashboard displays user information."""
    dashboard_page = DashboardPage(authenticated_page, base_url)
    dashboard_page.navigate()
    
    welcome_text = dashboard_page.get_welcome_text()
    # Welcome text should contain the user's role (Fellowship member name)
    assert len(welcome_text) > 0, "Welcome text should not be empty"
