"""Login page object for Fellowship BDD tests."""
from .base_page import BasePage


class LoginPage(BasePage):
    """Page object for login page interactions."""

    def __init__(self, page, base_url: str = "http://localhost"):
        super().__init__(page, base_url)
        self.username_input = page.locator("#username")
        self.password_input = page.locator("#password")
        self.login_button = page.locator("button[type='submit']")
        self.error_message = page.locator("[role='alert'], .alert-error, text=/Invalid credentials|Gate Remains Closed/i").first
        self.hint_text = page.get_by_text("Default password:").first

    def open(self):
        return super().navigate("/login")

    def navigate(self):
        return self.open()

    def login(self, username: str, password: str):
        self.open()
        self.username_input.fill(username)
        self.password_input.fill(password)
        self.login_button.click()
        return self

    def click_login(self):
        self.login_button.click()
        return self

    def wait_for_dashboard(self, timeout: int = 15000):
        self.page.wait_for_url("**/dashboard", timeout=timeout)
        return self

    def wait_for_redirect(self, path: str, timeout: int = 15000) -> bool:
        try:
            self.page.wait_for_url(f"**{path}", timeout=timeout)
            return True
        except Exception:
            return False

    def is_error_visible(self) -> bool:
        try:
            return self.error_message.first.is_visible(timeout=3000)
        except Exception:
            return False

    def get_error_text(self) -> str:
        if self.error_message.count() == 0:
            return ""
        try:
            return self.error_message.first.inner_text()
        except Exception:
            return ""

    def is_hint_visible(self) -> bool:
        if self.hint_text.count() == 0:
            return False
        try:
            return self.hint_text.is_visible(timeout=3000)
        except Exception:
            return False
