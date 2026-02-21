"""Base page object for Playwright tests."""
from playwright.sync_api import Page
from typing import Optional

class BasePage:
    """Base class for all page objects."""
    
    def __init__(self, page: Page, base_url: str = "http://localhost"):
        self.page = page
        self.base_url = base_url
    
    def navigate(self, path: str = "") -> 'BasePage':
        """Navigate to URL."""
        url = f"{self.base_url}{path}" if path else self.base_url
        self.page.goto(url)
        return self
    
    def wait_for_load(self) -> 'BasePage':
        """Wait for page to load."""
        self.page.wait_for_load_state('networkidle')
        return self
    
    def get_title(self) -> str:
        """Get page title."""
        return self.page.title()
    
    def get_url(self) -> str:
        """Get current URL."""
        return self.page.url
