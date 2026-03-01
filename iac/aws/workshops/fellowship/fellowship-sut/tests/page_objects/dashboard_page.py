"""Dashboard page object for Fellowship BDD tests."""
from .base_page import BasePage


class DashboardPage(BasePage):
    """Page object for dashboard assertions."""

    def __init__(self, page, base_url: str = "http://localhost"):
        super().__init__(page, base_url)
        self.council_heading = page.get_by_text("The Council Chamber")
        self.chat_panel = page.get_by_text("Companion Chat")

    def is_loaded(self) -> bool:
        try:
            if self.council_heading.is_visible(timeout=15000):
                return True
        except Exception:
            pass

        try:
            return self.chat_panel.is_visible(timeout=15000)
        except Exception:
            return False
