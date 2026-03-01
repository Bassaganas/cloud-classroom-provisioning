"""Login page object for Fellowship BDD tests."""
from .base_page import BasePage


class LoginPage(BasePage):
    """Page object for login page interactions."""

    def __init__(self, page, base_url: str = "http://localhost"):
        super().__init__(page, base_url)
        self.username_input = page.locator("#username")
        self.password_input = page.locator("#password")
        self.login_button = page.locator("button[type='submit']")
        self.error_message = page.locator(".error-message")

    def open(self):
        return self.navigate("/login")

    def login(self, username: str, password: str):
        self.open()
        self.username_input.fill(username)
        self.password_input.fill(password)
        self.login_button.click()
        return self

    def wait_for_dashboard(self, timeout: int = 15000):
        self.page.wait_for_url("**/dashboard", timeout=timeout)
        return self
