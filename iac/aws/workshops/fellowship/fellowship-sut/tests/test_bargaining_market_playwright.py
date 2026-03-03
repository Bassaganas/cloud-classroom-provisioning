"""Playwright E2E tests for bargaining market gameplay."""
import re

import pytest
from playwright.sync_api import Page, expect


def _login(page: Page, base_url: str):
    page.goto(f"{base_url}/login")
    page.locator('#username').fill('frodo_baggins')
    page.locator('#password').fill('fellowship123')
    page.get_by_role('button', name='Enter Middle-earth').click()
    page.wait_for_url('**/dashboard', timeout=15000)


@pytest.mark.ui
def test_map_has_character_seller_markers(page: Page, base_url: str):
    """Map shows dedicated character seller markers and bargain CTA."""
    _login(page, base_url)

    page.get_by_role('link', name=re.compile('Map of Middle-earth', re.IGNORECASE)).click()
    page.wait_for_url('**/map', timeout=15000)
    page.wait_for_timeout(2500)

    character_markers = page.locator('.character-marker-icon')
    assert character_markers.count() > 0, 'Expected character seller markers on map'

    page.evaluate(
        """
        () => {
            const marker = document.querySelector('.character-marker-icon');
            if (!marker) return false;
            marker.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
            return true;
        }
        """
    )
    expect(page.locator('.character-popup')).to_be_visible(timeout=5000)
    expect(page.get_by_role('button', name=re.compile('Start Bargain', re.IGNORECASE))).to_be_visible()


@pytest.mark.ui
def test_header_displays_gold_balance_counter(page: Page, base_url: str):
    """Header includes a visible gold counter after login."""
    _login(page, base_url)

    expect(
        page.get_by_role('navigation').get_by_text(re.compile(r'Gold\s*:\s*\d+', re.IGNORECASE)).first
    ).to_be_visible(timeout=10000)


@pytest.mark.ui
def test_inventory_page_displays_user_items_and_stats(page: Page, base_url: str):
    """Users can navigate to inventory and view personal bargain stats."""
    _login(page, base_url)

    page.get_by_role('link', name=re.compile('Inventory', re.IGNORECASE)).click()
    expect(page).to_have_url(re.compile(r'/inventory'))
    expect(page.get_by_role('heading', name=re.compile('Inventory', re.IGNORECASE))).to_be_visible(timeout=10000)
    expect(page.get_by_text(re.compile('Best Bargain', re.IGNORECASE))).to_be_visible(timeout=10000)
