"""Pytest fixtures for e2e tests."""
import pytest
import os
import sys
from dotenv import load_dotenv
import logging
from datetime import datetime
from playwright.sync_api import sync_playwright

# Load environment
load_dotenv()

# Add utils to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../utils'))

from utils.uuid_utils import get_test_uuid
from utils.aws_helpers import cleanup_e2e_resources

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Store test state
_test_context = {}

# Global Playwright instance (shared across tests)
_playwright = None
_browser = None


def _require_ui() -> bool:
    """Whether UI tests must fail if browser/page cannot be created."""
    return os.getenv('TEST_REQUIRE_UI', 'true').lower() == 'true'


def _browser_name() -> str:
    """Browser engine to use for UI tests."""
    return os.getenv('TEST_BROWSER', 'chromium').lower()

@pytest.fixture(scope="session")
def test_uuid():
    """Get unique test UUID."""
    uuid = get_test_uuid()
    logger.info(f"Test session UUID: {uuid}")
    return uuid

@pytest.fixture(scope="session", autouse=True)
def cleanup_after_all_tests():
    """Clean up all E2E resources after tests."""
    yield
    logger.info(f"Running global cleanup for test session...")
    cleanup_e2e_resources(prefix='e2e-tests-')
    logger.info("Global cleanup completed")

@pytest.fixture
def test_context():
    """Fixture for test state."""
    state = {
        'instance_ids': [],
        'session_name': None,
        'last_instance_id': None,
        'test_uuid': get_test_uuid()
    }
    yield state
    # Cleanup after each test (optional - global cleanup also runs)
    state.clear()

@pytest.fixture
def aws_environment():
    """Get AWS configuration from environment."""
    return {
        'region': os.getenv('AWS_REGION', 'eu-west-3'),
        'workshop_name': os.getenv('WORKSHOP_NAME', 'fellowship'),
        'environment': os.getenv('ENVIRONMENT', 'dev'),
        'hosted_zone_id': os.getenv('INSTANCE_MANAGER_HOSTED_ZONE_ID'),
        'base_domain': os.getenv('INSTANCE_MANAGER_BASE_DOMAIN', 'testingfantasy.com'),
        'ec2_manager_url': os.getenv('EC2_MANAGER_URL', 'https://ec2-management-dev.testingfantasy.com')
    }

@pytest.fixture(scope="session")
def browser_session():
    """Session-scoped browser fixture - optional usage."""
    try:
        headless = os.getenv('TEST_HEADLESS', 'true').lower() != 'false'
        browser_name = _browser_name()
        logger.info(f"Launching browser '{browser_name}' (headless={headless})")
        
        playwright = sync_playwright().start()
        if browser_name == 'firefox':
            browser = playwright.firefox.launch(headless=headless)
        elif browser_name == 'webkit':
            browser = playwright.webkit.launch(headless=headless)
        else:
            browser = playwright.chromium.launch(headless=headless)
        
        yield browser
        
        logger.info("Closing browser")
        browser.close()
        playwright.stop()
    except Exception as e:
        if _require_ui():
            pytest.fail(f"Browser launch failed in strict UI mode: {e}")
        logger.warning(f"Browser launch failed (tests will use AWS validation only): {e}")
        yield None

@pytest.fixture
def browser_context(browser_session):
    """Browser context fixture - skipped if browser not available."""
    if browser_session is None:
        if _require_ui():
            pytest.fail("Browser context unavailable in strict UI mode")
        logger.info("Skipping browser context - browser not available")
        yield None
    else:
        context = None
        try:
            context = browser_session.new_context()
            yield context
        except Exception as e:
            logger.warning(f"Browser context creation failed: {e}")
            yield None
        finally:
            if context is not None:
                try:
                    context.close()
                except Exception as e:
                    logger.warning(f"Failed to close browser context cleanly: {e}")

@pytest.fixture
def page(browser_context):
    """Page fixture - skipped if browser not available."""
    if browser_context is None:
        if _require_ui():
            pytest.fail("Page unavailable in strict UI mode")
        logger.info("Skipping page fixture - browser context not available")
        yield None
    else:
        try:
            page = browser_context.new_page()
            yield page
            page.close()
        except Exception as e:
            if _require_ui():
                pytest.fail(f"Page creation failed in strict UI mode: {e}")
            logger.warning(f"Page creation failed: {e}")
            yield None


def assert_any_selector_visible(page, selectors, timeout=10000):
    """Assert that at least one selector in the list becomes visible."""
    last_error = None
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state='visible', timeout=timeout)
            return selector
        except Exception as error:
            last_error = error

    selector_list = ", ".join(selectors)
    pytest.fail(
        f"None of the expected selectors became visible: [{selector_list}]"
        + (f". Last error: {last_error}" if last_error else "")
    )


@pytest.fixture
def authenticated_page(page, aws_environment):
    """Return an authenticated page; fail if authentication cannot be completed."""
    if page is None:
        pytest.fail("Page fixture is unavailable in strict UI mode")

    ec2_manager_url = aws_environment['ec2_manager_url']
    page.goto(ec2_manager_url, wait_until='domcontentloaded')

    password_input = page.locator('input[type="password"]').first
    login_form_visible = False

    try:
        password_input.wait_for(state='visible', timeout=5000)
        login_form_visible = True
    except Exception:
        login_form_visible = '/login' in page.url

    if login_form_visible:
        password = os.getenv('EC2_MANAGER_PASSWORD')
        if not password:
            pytest.fail(
                "Login page detected but EC2_MANAGER_PASSWORD is not set. "
                "Set EC2_MANAGER_PASSWORD in e2e/.env to run strict UI tests."
            )

        password_input.fill(password)
        login_button = page.locator('button:has-text("Login")').first
        login_button.wait_for(state='visible', timeout=10000)
        login_button.click()

    assert_any_selector_visible(
        page,
        [
            'text=Workshops',
            'text=Tutorial Sessions',
            'input[placeholder="Search workshops or session IDs"]'
        ],
        timeout=15000
    )

    return page

# Markers
def pytest_configure(config):
    """Configure pytest markers."""
    config.addinivalue_line("markers", "e2e: e2e test")
    config.addinivalue_line("markers", "slow: slow test")
    config.addinivalue_line("markers", "instance: instance management test")
    config.addinivalue_line("markers", "admin: admin instance test")
    config.addinivalue_line("markers", "session: tutorial session test")
    config.addinivalue_line("markers", "landing: landing page test")
