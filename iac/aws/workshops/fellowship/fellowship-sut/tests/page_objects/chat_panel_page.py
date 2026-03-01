"""Page object for Dashboard NPC chat panel."""

import time


class ChatPanelPage:
    """Encapsulates NPC chat panel interactions for tests."""

    def __init__(self, page):
        self.page = page
        self.panel_title = page.get_by_text("Companion Chat")
        self.chat_input = page.locator('textarea[placeholder*="Reply to"]')
        self.send_button = page.get_by_role("button", name="Send")
        self.new_opener_button = page.get_by_role("button", name="New Opener")
        self.suggested_action_heading = page.get_by_text("Suggested action")
        self.open_action_button = page.get_by_role("button", name="Open Action")

    def wait_until_visible(self, timeout: int = 15000):
        self.panel_title.wait_for(state="visible", timeout=timeout)
        self.chat_input.wait_for(state="visible", timeout=timeout)
        return self

    def message_bubbles(self):
        return self.page.locator("div.rounded-lg.px-3.py-2")

    def wait_for_min_messages(self, minimum: int, timeout: int = 15000):
        deadline = time.time() + (timeout / 1000)
        while time.time() < deadline:
            if self.message_bubbles().count() >= minimum:
                return self
            self.page.wait_for_timeout(200)
        raise TimeoutError(f"Timed out waiting for at least {minimum} chat messages")
        return self

    def send_message(self, content: str):
        self.chat_input.fill(content)
        self.send_button.click()
        return self

    def open_action(self):
        self.open_action_button.click()
        return self
