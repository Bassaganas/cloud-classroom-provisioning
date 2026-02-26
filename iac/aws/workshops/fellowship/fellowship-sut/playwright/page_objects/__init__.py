"""Page objects for Playwright tests."""
from .base_page import BasePage
from .login_page import LoginPage
from .dashboard_page import DashboardPage
from .map_page import MapPage

__all__ = ['BasePage', 'LoginPage', 'DashboardPage', 'MapPage']
