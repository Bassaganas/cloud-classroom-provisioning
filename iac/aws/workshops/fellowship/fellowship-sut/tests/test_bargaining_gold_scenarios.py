"""Playwright E2E tests for bargaining market gold and edge case scenarios."""
import re

import pytest
from playwright.sync_api import Page, expect


def _login(page: Page, base_url: str, username: str = 'frodo_baggins', password: str = 'fellowship123'):
    """Login helper for tests."""
    page.goto(f"{base_url}/login")
    page.locator('#username').fill(username)
    page.locator('#password').fill(password)
    page.get_by_role('button', name='Enter Middle-earth').click()
    page.wait_for_url('**/dashboard', timeout=15000)


@pytest.mark.ui
def test_user_has_sufficient_gold_on_fresh_login(page: Page, base_url: str):
    """Fresh login provides user with initial gold amount."""
    _login(page, base_url)

    # Get gold counter from navigation
    nav_gold = page.get_by_role('navigation').get_by_text(re.compile(r'Gold\s*:\s*\d+', re.IGNORECASE)).first
    expect(nav_gold).to_be_visible(timeout=10000)
    
    gold_text = nav_gold.inner_text()
    gold_match = re.search(r'\d+', gold_text)
    current_gold = int(gold_match.group(0)) if gold_match else 0
    
    # Fresh login should start with 300 gold (from test reset)
    assert current_gold >= 300, f'Expected initial gold >= 300, got {current_gold}'


@pytest.mark.ui
def test_character_responds_to_bargain_attempts_with_gold(page: Page, base_url: str):
    """Character panel opens and shows bargain controls when user has gold."""
    _login(page, base_url)

    # Navigate to map
    page.get_by_role('link', name=re.compile('Map of Middle-earth', re.IGNORECASE)).click()
    page.wait_for_url('**/map', timeout=15000)
    page.wait_for_timeout(2500)
    
    # Click character marker
    page.evaluate(
        """
        () => {
            const marker = document.querySelector('.character-marker-icon');
            if (marker) marker.click();
            return true;
        }
        """
    )
    panel = page.locator('.map-character-panel').first
    expect(panel).to_be_visible(timeout=8000)
    
    # Wait for shop items and bargain button
    page.wait_for_timeout(2000)  # Wait for async shop items load
    
    bargain_buttons = panel.get_by_role('button', name='Bargain')
    assert bargain_buttons.count() > 0, 'Expected bargain buttons when user has gold'
    
    # Verify user still has sufficient gold
    nav_gold = page.get_by_role('navigation').get_by_text(re.compile(r'Gold\s*:\s*(\d+)', re.IGNORECASE)).first
    gold_text = nav_gold.inner_text()
    gold_match = re.search(r'\d+', gold_text)
    current_gold = int(gold_match.group(0)) if gold_match else 0
    assert current_gold > 0, 'User should have gold to bargain'


@pytest.mark.ui
def test_successful_purchase_deducts_gold(page: Page, base_url: str):
    """Gold balance decreases after successful purchase."""
    _login(page, base_url)

    # Navigate to map first
    page.get_by_role('link', name=re.compile('Map of Middle-earth', re.IGNORECASE)).click()
    page.wait_for_url('**/map', timeout=15000)
    page.wait_for_timeout(2500)

    # Get initial gold from nav
    nav_gold = page.get_by_role('navigation').get_by_text(re.compile(r'Gold\s*:\s*(\d+)', re.IGNORECASE)).first
    expect(nav_gold).to_be_visible(timeout=10000)
    initial_gold_text = nav_gold.inner_text()
    initial_gold_match = re.search(r'\d+', initial_gold_text)
    initial_gold = int(initial_gold_match.group(0)) if initial_gold_match else 0
    
    # Click character marker
    page.evaluate(
        """
        () => {
            const marker = document.querySelector('.character-marker-icon');
            if (marker) marker.click();
            return true;
        }
        """
    )
    panel = page.locator('.map-character-panel').first
    expect(panel).to_be_visible(timeout=8000)
    page.wait_for_timeout(3000)
    
    # Use the first item's bargain button
    bargain_buttons = panel.get_by_role('button', name='Bargain').all()
    if len(bargain_buttons) > 0:
        bargain_buttons[0].click()
        expect(panel.get_by_text(re.compile(r'Gold', re.IGNORECASE)).first).to_be_visible(timeout=12000)
        
        # Make offers - escalating
        offer_input = panel.locator('input[placeholder="Offer amount"]')
        offer_input.fill('50')
        panel.get_by_role('button', name='Send Offer').click()
        expect(panel.get_by_text(re.compile(r'counter|offer|gold', re.IGNORECASE)).first).to_be_visible(timeout=12000)
        page.wait_for_timeout(2000)
        
        offer_input.fill('75')
        panel.get_by_role('button', name='Send Offer').click()
        expect(panel.get_by_text(re.compile(r'counter|offer|gold', re.IGNORECASE)).first).to_be_visible(timeout=12000)
        page.wait_for_timeout(2000)
        
        # Say deal
        chat_box = panel.locator('textarea[placeholder*="Reply to"]')
        chat_box.fill('deal')
        panel.get_by_role('button', name='Send', exact=True).click()
        expect(panel.get_by_text(re.compile(r'accepted|sale|deal|inventory', re.IGNORECASE)).first).to_be_visible(timeout=12000)
        page.wait_for_timeout(1500)
        
        # Close panel and navigate to inventory to verify purchase
        close_button_on_panel = page.locator('.map-character-panel button[aria-label="Close"]')
        if close_button_on_panel.is_visible(timeout=2000):
            close_button_on_panel.click()
            page.wait_for_selector('.map-character-panel', state='hidden', timeout=5000)
        page.wait_for_timeout(500)
        
        # Navigate to inventory to confirm purchase and check gold
        inventory_link = page.get_by_role('link', name=re.compile('Inventory', re.IGNORECASE))
        inventory_link.click()
        page.wait_for_url('**/inventory', timeout=15000)
        page.wait_for_timeout(1000)
        
        # Get updated gold from nav
        updated_nav_gold = page.get_by_role('navigation').get_by_text(re.compile(r'Gold\s*:\s*(\d+)', re.IGNORECASE)).first
        updated_gold_text = updated_nav_gold.inner_text()
        updated_gold_match = re.search(r'\d+', updated_gold_text)
        updated_gold = int(updated_gold_match.group(0)) if updated_gold_match else 0
        
        # Gold should have decreased
        assert updated_gold < initial_gold, f'Gold should decrease after purchase: {initial_gold} -> {updated_gold}. Gold deducted: {initial_gold - updated_gold}'
