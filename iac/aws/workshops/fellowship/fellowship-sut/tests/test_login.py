"""Tests for login functionality."""
import pytest
from playwright.sync_api import Page
from playwright.page_objects.login_page import LoginPage
from playwright.page_objects.dashboard_page import DashboardPage

def test_valid_login(page: Page, base_url: str, test_credentials: dict):
    """Test successful login with valid credentials."""
    login_page = LoginPage(page, base_url)
    dashboard_page = DashboardPage(page, base_url)
    
    login_page.login(
        test_credentials['username'],
        test_credentials['password']
    )
    
    # Wait for redirect to dashboard
    assert login_page.wait_for_redirect('/dashboard'), "Should redirect to dashboard after login"
    assert dashboard_page.is_loaded(), "Dashboard should be loaded"
    welcome_text = dashboard_page.get_welcome_text()
    assert 'Welcome' in welcome_text or 'Council Chamber' in welcome_text, "Welcome message should be displayed with LOTR terminology"

def test_invalid_login(page: Page, base_url: str):
    """Test login failure with invalid credentials."""
    login_page = LoginPage(page, base_url)
    
    login_page.login('invalid_user', 'wrong_password')
    
    # Should show error message and not redirect
    assert login_page.is_error_visible(), "Error message should be visible"
    assert 'Invalid credentials' in login_page.get_error_text() or 'Invalid' in login_page.get_error_text(), "Should show invalid credentials error"
    assert page.url.endswith('/login'), "Should not redirect on invalid login"

def test_empty_credentials(page: Page, base_url: str):
    """Test login with empty credentials."""
    login_page = LoginPage(page, base_url)
    
    login_page.navigate()
    login_page.click_login()
    
    # Browser validation should prevent submission, but if it submits, should show error
    # This test may vary based on browser validation behavior
    page.wait_for_timeout(1000)  # Wait a bit to see if form submits
    
    # If still on login page, that's fine (browser validation)
    # If error appears, that's also fine
    assert page.url.endswith('/login') or login_page.is_error_visible(), "Should stay on login page or show error"

def test_login_hint_displayed(page: Page, base_url: str):
    """Test that login hint is displayed on login page."""
    login_page = LoginPage(page, base_url)
    login_page.navigate()
    
    assert login_page.is_hint_visible(), "Login hint should be visible"
    assert 'fellowship123' in login_page.hint_text.inner_text(), "Hint should contain default password"

def test_logout(page: Page, base_url: str, test_credentials: dict):
    """Test logout functionality."""
    login_page = LoginPage(page, base_url)
    dashboard_page = DashboardPage(page, base_url)
    
    # Login first
    login_page.login(
        test_credentials['username'],
        test_credentials['password']
    )
    
    # Wait for dashboard
    assert login_page.wait_for_redirect('/dashboard'), "Should be on dashboard"
    
    # Logout
    dashboard_page.click_logout()
    
    # Should redirect to login
    assert dashboard_page.wait_for_redirect_to_login(), "Should redirect to login after logout"
