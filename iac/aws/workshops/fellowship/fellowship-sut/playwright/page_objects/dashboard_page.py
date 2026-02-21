"""Dashboard page object for Playwright tests."""
from playwright.sync_api import Page
from playwright.page_objects.base_page import BasePage

class DashboardPage(BasePage):
    """Page object for dashboard page."""
    
    def __init__(self, page: Page, base_url: str = "http://localhost"):
        super().__init__(page, base_url)
        self.welcome_message = page.locator('.dashboard-header h1')
        self.stats_cards = page.locator('.stat-card')
        self.quest_list = page.locator('.quest-list')
        self.quest_items = page.locator('.quest-item')
        self.logout_button = page.locator('button:has-text("Logout")')
        self.navbar = page.locator('.navbar')
    
    def navigate(self) -> 'DashboardPage':
        """Navigate to dashboard page."""
        super().navigate('/dashboard')
        self.wait_for_load()
        return self
    
    def is_loaded(self) -> bool:
        """Check if dashboard is loaded."""
        return self.welcome_message.is_visible()
    
    def get_welcome_text(self) -> str:
        """Get welcome message text."""
        return self.welcome_message.inner_text()
    
    def get_stat_count(self, index: int = 0) -> str:
        """Get stat value by index."""
        return self.stats_cards.nth(index).locator('.stat-value').inner_text()
    
    def get_stat_label(self, index: int = 0) -> str:
        """Get stat label by index."""
        return self.stats_cards.nth(index).locator('.stat-label').inner_text()
    
    def get_quest_count(self) -> int:
        """Get number of quest items displayed."""
        return self.quest_items.count()
    
    def click_logout(self) -> 'DashboardPage':
        """Click logout button."""
        self.logout_button.click()
        return self
    
    def click_quests_link(self) -> 'DashboardPage':
        """Click quests navigation link."""
        self.page.locator('a:has-text("Quests")').click()
        return self
    
    def wait_for_redirect_to_login(self, timeout: int = 5000) -> bool:
        """Wait for redirect to login page after logout."""
        try:
            self.page.wait_for_url("**/login", timeout=timeout)
            return True
        except:
            return False
