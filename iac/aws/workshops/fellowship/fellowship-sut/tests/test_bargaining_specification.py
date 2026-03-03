"""Playwright suite for bargaining chatbot specification."""
import re

import pytest
from playwright.sync_api import Page, expect


def _login(page: Page, base_url: str) -> None:
    page.goto(f"{base_url}/login")
    page.locator('#username').fill('frodo_baggins')
    page.locator('#password').fill('fellowship123')
    page.get_by_role('button', name='Enter Middle-earth').click()
    page.wait_for_url('**/dashboard', timeout=15000)


def _open_map_character_panel(page: Page, base_url: str) -> None:
    page.get_by_role('link', name=re.compile('Map of Middle-earth', re.IGNORECASE)).click()
    page.wait_for_url('**/map', timeout=15000)
    page.wait_for_timeout(2000)

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

    expect(page.locator('.map-character-panel').first).to_be_visible(timeout=8000)


@pytest.mark.ui
def test_bargain_panel_opens_and_shows_controls(page: Page, base_url: str):
    _login(page, base_url)
    _open_map_character_panel(page, base_url)

    panel = page.locator('.map-character-panel').first
    expect(panel.get_by_text('Trader Bargain')).to_be_visible(timeout=8000)
    expect(panel.get_by_role('button', name='Send Offer')).to_be_visible(timeout=8000)
    expect(panel.locator('input[placeholder="Offer amount"]')).to_be_visible(timeout=8000)


@pytest.mark.ui
def test_bargain_start_updates_chat_and_status(page: Page, base_url: str):
    _login(page, base_url)
    _open_map_character_panel(page, base_url)

    panel = page.locator('.map-character-panel').first
    bargain_button = panel.get_by_role('button', name='Bargain').first
    bargain_button.click()

    expect(panel.get_by_text(re.compile(r'Gold', re.IGNORECASE)).first).to_be_visible(timeout=12000)
    expect(panel.get_by_text(re.compile(r'Negotiation:\s*active', re.IGNORECASE))).to_be_visible(timeout=12000)


@pytest.mark.ui
def test_offer_submission_shows_npc_response(page: Page, base_url: str):
    _login(page, base_url)
    _open_map_character_panel(page, base_url)

    panel = page.locator('.map-character-panel').first
    panel.get_by_role('button', name='Bargain').first.click()
    expect(panel.get_by_text(re.compile(r'Gold', re.IGNORECASE)).first).to_be_visible(timeout=12000)

    offer_input = panel.locator('input[placeholder="Offer amount"]')
    offer_input.fill('50')
    panel.get_by_role('button', name='Send Offer').click()

    expect(
        panel.get_by_text(re.compile(r'gold|deal|offer|sale|accept|counter|low', re.IGNORECASE)).first
    ).to_be_visible(timeout=12000)


@pytest.mark.ui
def test_flattery_offer_flow_continues_negotiation(page: Page, base_url: str):
    _login(page, base_url)
    _open_map_character_panel(page, base_url)

    panel = page.locator('.map-character-panel').first
    panel.get_by_role('button', name='Bargain').first.click()
    expect(panel.get_by_text(re.compile(r'Gold', re.IGNORECASE)).first).to_be_visible(timeout=12000)

    chat_box = panel.locator('textarea[placeholder*="Reply to"]')
    chat_box.fill('You are a truly wise and remarkable trader. I offer 65 gold.')
    panel.get_by_role('button', name='Send', exact=True).click()

    expect(
        panel.get_by_text(re.compile(r'gold|deal|offer|sale|accept|counter|low', re.IGNORECASE)).first
    ).to_be_visible(timeout=12000)


@pytest.mark.ui
def test_stop_bargain_state_after_repeated_low_offers(page: Page, base_url: str):
    _login(page, base_url)
    _open_map_character_panel(page, base_url)

    panel = page.locator('.map-character-panel').first
    panel.get_by_role('button', name='Bargain').first.click()
    expect(panel.get_by_text(re.compile(r'Gold', re.IGNORECASE)).first).to_be_visible(timeout=12000)

    offer_input = panel.locator('input[placeholder="Offer amount"]')
    send_offer = panel.get_by_role('button', name='Send Offer')

    for _ in range(8):
        offer_input.fill('1')
        send_offer.click()
        page.wait_for_timeout(300)

    expect(
        panel.get_by_text(re.compile(r'Negotiation:\s*(stop-bargain|accepted|active)', re.IGNORECASE)).first
    ).to_be_visible(timeout=12000)
