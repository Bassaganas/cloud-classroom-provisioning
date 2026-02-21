"""Pytest configuration and fixtures for Playwright tests."""
import pytest
import os
from playwright.sync_api import sync_playwright, Page, Browser, BrowserContext

@pytest.fixture(scope="session")
def playwright():
    """Playwright instance (session-scoped)."""
    with sync_playwright() as p:
        yield p

@pytest.fixture(scope="session")
def browser(playwright):
    """Browser instance (session-scoped)."""
    browser = playwright.chromium.launch(headless=True)
    yield browser
    browser.close()

@pytest.fixture
def context(browser: Browser):
    """Browser context fixture."""
    context = browser.new_context()
    yield context
    context.close()

@pytest.fixture
def page(context: BrowserContext) -> Page:
    """Browser page fixture."""
    page = context.new_page()
    yield page
    page.close()

@pytest.fixture
def base_url() -> str:
    """Base URL for SUT."""
    return os.getenv('SUT_URL', 'http://localhost')

@pytest.fixture
def test_credentials():
    """Test user credentials."""
    return {
        'username': 'frodo_baggins',
        'password': 'fellowship123'
    }
