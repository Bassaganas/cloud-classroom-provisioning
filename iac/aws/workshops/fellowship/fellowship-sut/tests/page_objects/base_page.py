"""Base page object for Fellowship test suite."""


class BasePage:
    """Small helper base class for POM interactions."""

    def __init__(self, page, base_url: str = "http://localhost"):
        self.page = page
        self.base_url = base_url

    def navigate(self, path: str = ""):
        url = f"{self.base_url}{path}" if path else self.base_url
        self.page.goto(url)
        self.page.wait_for_load_state("networkidle")
        return self
