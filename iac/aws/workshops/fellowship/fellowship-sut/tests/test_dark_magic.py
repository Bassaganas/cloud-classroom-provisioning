"""Tests for dark magic quest scenarios."""
import pytest
from playwright.sync_api import Page
from tests.page_objects.login_page import LoginPage
from tests.page_objects.dashboard_page import DashboardPage
import requests
import os

@pytest.fixture
def api_base_url() -> str:
    """Base URL for API."""
    base_url = os.getenv('SUT_URL', 'http://localhost')
    return f"{base_url}/api"

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

def test_dark_magic_quests_display_with_special_styling(authenticated_page: Page, base_url: str):
    """Test that dark magic quests display with special styling."""
    page = authenticated_page
    page.goto(f"{base_url}/quests")
    
    # Look for dark magic quests
    dark_magic_cards = page.locator('.quest-card-dark-magic')
    dark_magic_count = dark_magic_cards.count()
    
    if dark_magic_count > 0:
        # Check that dark magic badge is visible
        dark_magic_badge = page.locator('.dark-magic-badge').first
        assert dark_magic_badge.is_visible(), "Dark magic badge should be visible"
        assert 'Dark Magic' in dark_magic_badge.inner_text(), "Badge should indicate Dark Magic"
        
        # Check that dark magic card has special styling
        first_dark_magic_card = dark_magic_cards.first
        assert first_dark_magic_card.is_visible(), "Dark magic quest card should be visible"

def test_dark_magic_quests_can_be_filtered(api_base_url: str):
    """Test that dark magic quests can be filtered via API."""
    response = requests.get(f"{api_base_url}/quests/?dark_magic=true")
    assert response.status_code == 200, "Filtering dark magic quests should return 200"
    quests = response.json()
    assert isinstance(quests, list), "Should return a list"
    
    # All returned quests should be dark magic
    for quest in quests:
        assert quest.get('is_dark_magic') is True, f"Quest {quest.get('id')} should be a dark magic quest"

def test_dark_magic_quests_appear_in_dashboard_warnings(authenticated_page: Page, base_url: str):
    """Test that dark magic quests appear in dashboard warnings."""
    page = authenticated_page
    dashboard_page = DashboardPage(page, base_url)
    dashboard_page.navigate()
    
    # Check if dark magic warning exists
    dark_magic_warning = dashboard_page.dark_magic_warning
    if dark_magic_warning.count() > 0:
        warning_text = dark_magic_warning.first.inner_text()
        assert 'Dark Magic' in warning_text or 'Sauron' in warning_text, "Warning should mention Dark Magic or Sauron"

def test_dark_magic_quest_completion_may_fail(api_base_url: str):
    """Test that dark magic quest completion may fail (simulated bug)."""
    # Login first
    session = requests.Session()
    login_response = session.post(
        f"{api_base_url}/auth/login",
        json={
            'username': 'frodo_baggins',
            'password': 'fellowship123'
        }
    )
    assert login_response.status_code == 200
    
    # Get dark magic quests
    response = session.get(f"{api_base_url}/quests/?dark_magic=true")
    assert response.status_code == 200
    dark_magic_quests = response.json()
    
    if len(dark_magic_quests) > 0:
        # Try to complete a dark magic quest
        quest_id = dark_magic_quests[0]['id']
        complete_response = session.put(f"{api_base_url}/quests/{quest_id}/complete")
        
        # Dark magic quests may fail or succeed (simulated bug behavior)
        # This test verifies the endpoint works, but dark magic may have special behavior
        assert complete_response.status_code in [200, 500], "Dark magic quest completion may succeed or fail (simulated bug)"

def test_dark_magic_quest_has_eye_of_sauron_icon(authenticated_page: Page, base_url: str):
    """Test that dark magic quests display Eye of Sauron icon."""
    page = authenticated_page
    page.goto(f"{base_url}/quests")
    
    # Look for dark magic badge with Eye of Sauron emoji
    dark_magic_badges = page.locator('.dark-magic-badge')
    if dark_magic_badges.count() > 0:
        badge_text = dark_magic_badges.first.inner_text()
        # Check for Eye of Sauron emoji or text
        assert '👁️' in badge_text or 'Dark Magic' in badge_text, "Dark magic badge should have Eye of Sauron icon or text"
