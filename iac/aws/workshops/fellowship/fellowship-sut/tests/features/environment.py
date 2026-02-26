"""Behave environment configuration for Playwright tests."""
import os
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

# Add parent directory to Python path so we can import playwright.page_objects
parent_dir = Path(__file__).parent.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))


def before_all(context):
    """Set up Playwright before all scenarios."""
    # Start Playwright
    context.playwright = sync_playwright().start()
    
    # Try different browsers in order of preference (Firefox is most stable on macOS)
    browser_type = os.getenv('BROWSER', 'firefox').lower()
    browser_launched = False
    
    # Try Firefox first (most stable on macOS)
    if browser_type == 'firefox' or not browser_launched:
        try:
            context.browser = context.playwright.firefox.launch(headless=True)
            browser_launched = True
            print("✓ Using Firefox browser")
        except Exception as e:
            print(f"Warning: Firefox not available: {e}")
    
    # Try WebKit if Firefox failed
    if not browser_launched and (browser_type == 'webkit' or browser_type == 'firefox'):
        try:
            context.browser = context.playwright.webkit.launch(headless=True)
            browser_launched = True
            print("✓ Using WebKit browser")
        except Exception as e:
            print(f"Warning: WebKit not available: {e}")
    
    # Fallback to Chromium with minimal args
    if not browser_launched:
        try:
            context.browser = context.playwright.chromium.launch(
                headless=True,
                args=['--disable-dev-shm-usage', '--disable-gpu']
            )
            browser_launched = True
            print("✓ Using Chromium browser")
        except Exception as e:
            raise RuntimeError(f"Failed to launch any browser: {e}")
    
    # Set base URL from environment or use default
    context.base_url = os.getenv('SUT_URL', 'http://localhost')
    
    # Set test credentials
    context.test_username = os.getenv('TEST_USERNAME', 'frodo_baggins')
    context.test_password = os.getenv('TEST_PASSWORD', 'fellowship123')


def before_scenario(context, scenario):
    """Set up a new page for each scenario."""
    # Create a new browser context for each scenario
    context.browser_context = context.browser.new_context()
    context.page = context.browser_context.new_page()


def after_scenario(context, scenario):
    """Clean up after each scenario."""
    # Close the page and context
    if hasattr(context, 'page'):
        context.page.close()
    if hasattr(context, 'browser_context'):
        context.browser_context.close()


def after_all(context):
    """Clean up Playwright after all scenarios."""
    # Close browser
    if hasattr(context, 'browser'):
        context.browser.close()
    
    # Stop Playwright
    if hasattr(context, 'playwright'):
        context.playwright.stop()
