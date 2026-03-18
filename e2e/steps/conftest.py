"""Shared fixtures and configuration for Playwright BDD tests."""
import pytest
from pytest_bdd import given, when, then
from playwright.async_api import async_playwright
import asyncio
import logging
from utils.aws_helpers import cleanup_e2e_resources
from utils.uuid_utils import get_test_uuid

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global browser and context for tests
_browser = None
_context = None
_page = None

@pytest.fixture(scope="session")
def event_loop():
    """Create an event loop for async tests."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()

@pytest.fixture(scope="session")
async def browser():
    """Initialize Playwright browser for the test session."""
    global _browser
    async with async_playwright() as p:
        _browser = await p.chromium.launch(headless=True)
        yield _browser
        await _browser.close()

@pytest.fixture
async def page(browser):
    """Create a new page for each test."""
    global _context, _page
    _context = await browser.new_context()
    _page = await _context.new_page()
    yield _page
    await _page.close()
    await _context.close()

@pytest.fixture(scope="session", autouse=True)
def cleanup_after_tests():
    """Global cleanup after all tests."""
    yield
    logger.info(f"Running global cleanup for test UUID: {get_test_uuid()}")
    cleanup_e2e_resources(prefix='e2e-tests-')

# Shared step fixtures
@given("I am authenticated and on the tutorial session page")
def step_authenticated_on_session_page(page):
    """Navigate to the tutorial session page."""
    page.goto("https://ec2-management-dev.testingfantasy.com/")

@given("I am authenticated and on the landing page")
def step_authenticated_on_landing_page(page):
    """Navigate to the landing page."""
    page.goto("https://ec2-management-dev.testingfantasy.com/")

@given("the EC2 Manager UI is loaded")
def step_ui_is_loaded(page):
    """Wait for the UI to load."""
    page.wait_for_load_state("networkidle")
