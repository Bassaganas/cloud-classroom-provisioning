"""Page Object Model for the Map Page used in test suite."""
from .base_page import BasePage


class MapPage(BasePage):
    """Page object for the Map of Middle-earth page."""

    def __init__(self, page, base_url: str):
        super().__init__(page, base_url)
        self.page_title = page.locator('text=Map of Middle-earth').first
        self.map_container = page.locator('.middle-earth-map-container')
        self.filter_sidebar = page.locator('.filter-sidebar')

    def navigate(self):
        self.page.goto(f"{self.base_url}/dashboard")
        self.page.locator('a[href="/map"]').first.click()
        self.page.wait_for_url('**/map')
        self.page.wait_for_load_state('networkidle')
        return self

    def is_loaded(self) -> bool:
        return self.map_container.is_visible(timeout=5000)

    def wait_for_map(self, timeout: int = 10000):
        self.map_container.wait_for(state='visible', timeout=timeout)
        self.page.wait_for_function(
            'window.L && document.querySelector(".leaflet-container")',
            timeout=timeout,
        )

    def get_quest_markers_count(self) -> int:
        return self.page.locator('.quest-marker-icon').count()

    def get_location_markers_count(self) -> int:
        return self.page.locator('.location-marker-icon').count()

    def click_quest_marker(self, quest_title: str):
        marker = self.page.locator(f'.quest-marker-icon[title="{quest_title}"]')
        marker.wait_for(state='visible', timeout=5000)
        marker.click()

    def is_quest_popup_visible(self, quest_title: str) -> bool:
        popup = self.page.locator('.quest-popup')
        if not popup.is_visible():
            return False
        return quest_title in popup.locator('h4').inner_text()

    def get_quest_popup_content(self) -> str:
        popup = self.page.locator('.quest-popup')
        if popup.is_visible():
            return popup.inner_text()
        return ""

    def click_view_quest_button(self):
        button = self.page.locator('.btn-view-quest')
        button.wait_for(state='visible', timeout=3000)
        button.click()

    def get_quest_count_in_list(self) -> int:
        return self.get_quest_markers_count()

    def clear_location_filter(self):
        clear_button = self.page.locator('button:has-text("View All Quests")')
        if clear_button.is_visible():
            clear_button.click()
