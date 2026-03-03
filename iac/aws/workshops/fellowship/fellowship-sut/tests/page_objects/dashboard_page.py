"""Dashboard page object for Fellowship BDD tests."""
from .base_page import BasePage


class DashboardPage(BasePage):
    """Page object for dashboard assertions."""

    def __init__(self, page, base_url: str = "http://localhost"):
        super().__init__(page, base_url)
        self.council_heading = page.get_by_text("The Council Chamber")
        self.chat_panel = page.get_by_text("Companion Chat")
        self.navbar = page.locator("nav, [role='navigation']").first
        self.stats_cards = page.locator(
            "text=Total Quest Objectives, "
            "text=The Road Goes Ever On..., "
            "text=It Is Done, "
            "text=Not Yet Begun, "
            "text=The Shadow Falls, "
            "text=Active Fellowship Members"
        )
        self.quest_list = page.locator("text=Recent Quest Objectives, text=Filtered Quests").first
        self.dark_magic_warning = page.locator("text=/Dark Magic|Sauron/i")

    def navigate(self):
        return super().navigate("/dashboard")

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

    def get_welcome_text(self) -> str:
        welcome = self.page.locator("text=/Welcome,/i").first
        if welcome.count() > 0:
            return welcome.inner_text()
        heading = self.page.locator("h1, h2").first
        if heading.count() > 0:
            return heading.inner_text()
        return ""

    def get_stat_count(self, index: int) -> str:
        values = self.page.locator(".text-4xl.font-epic")
        if values.count() <= index:
            return "0"
        text = values.nth(index).inner_text().strip()
        digits = "".join(ch for ch in text if ch.isdigit())
        return digits or "0"

    def get_stat_label(self, index: int) -> str:
        labels = self.page.locator(
            "text=Total Quest Objectives, "
            "text=The Road Goes Ever On..., "
            "text=It Is Done, "
            "text=Not Yet Begun, "
            "text=The Shadow Falls, "
            "text=Active Fellowship Members"
        )
        if labels.count() <= index:
            return ""
        return labels.nth(index).inner_text().strip()

    def get_quest_count(self) -> int:
        return self.page.locator(".quest-card, .quest-item").count()

    def click_quests_link(self):
        quest_link = self.page.get_by_role("link", name="Scrolls")
        if quest_link.count() == 0:
            quest_link = self.page.get_by_role("link", name="Quests")
        if quest_link.count() == 0:
            quest_link = self.page.locator("a[href='/quests']").first
        quest_link.click()
        return self

    def click_logout(self):
        logout = self.page.get_by_role("button", name="Leave Fellowship")
        if logout.count() == 0:
            logout = self.page.get_by_role("button", name="Logout")
        if logout.count() == 0:
            logout = self.page.get_by_role("button", name="Sign Out")
        if logout.count() == 0:
            logout = self.page.locator("button:has-text('Logout'), button:has-text('Sign Out')").first
        logout.click()
        return self

    def wait_for_redirect_to_login(self, timeout: int = 15000) -> bool:
        try:
            self.page.wait_for_url("**/login", timeout=timeout)
            return True
        except Exception:
            return False
