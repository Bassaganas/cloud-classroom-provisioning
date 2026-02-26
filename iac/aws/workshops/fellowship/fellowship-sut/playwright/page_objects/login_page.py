"""Login page object for Playwright tests."""
from playwright.sync_api import Page
from .base_page import BasePage

class LoginPage(BasePage):
    """Page object for login page."""
    
    def __init__(self, page: Page, base_url: str = "http://localhost"):
        super().__init__(page, base_url)
        self.username_input = page.locator('#username')
        self.password_input = page.locator('#password')
        self.login_button = page.locator('button[type="submit"]')
        self.error_message = page.locator('.error-message')
        self.hint_text = page.locator('.login-hint')
    
    def navigate(self) -> 'LoginPage':
        """Navigate to login page."""
        super().navigate('/login')
        self.wait_for_load()
        return self
    
    def fill_username(self, username: str) -> 'LoginPage':
        """Fill username field."""
        self.username_input.fill(username)
        return self
    
    def fill_password(self, password: str) -> 'LoginPage':
        """Fill password field."""
        self.password_input.fill(password)
        return self
    
    def click_login(self) -> 'LoginPage':
        """Click login button."""
        self.login_button.click()
        return self
    
    def login(self, username: str, password: str) -> 'LoginPage':
        """Complete login flow."""
        return (self
                .navigate()
                .fill_username(username)
                .fill_password(password)
                .click_login())
    
    def is_error_visible(self) -> bool:
        """Check if error message is visible."""
        return self.error_message.is_visible()
    
    def get_error_text(self) -> str:
        """Get error message text."""
        return self.error_message.inner_text()
    
    def is_hint_visible(self) -> bool:
        """Check if login hint is visible."""
        return self.hint_text.is_visible()
    
    def wait_for_redirect(self, expected_path: str = "/dashboard", timeout: int = 5000) -> bool:
        """Wait for redirect after login."""
        try:
            self.page.wait_for_url(f"**{expected_path}", timeout=timeout)
            return True
        except:
            return False
