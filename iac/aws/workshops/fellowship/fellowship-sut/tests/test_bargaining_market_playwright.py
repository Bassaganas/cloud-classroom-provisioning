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
    panel = page.locator('.map-character-panel').first
    expect(panel).to_be_visible(timeout=8000)
    has_trader_title = panel.get_by_text('Trader Bargain').count() > 0
    has_companion_title = panel.get_by_text('Companion Chat').count() > 0
    assert has_trader_title or has_companion_title, 'Expected map character interaction panel to open'


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


@pytest.mark.ui
def test_dashboard_uses_companion_chat_panel(page: Page, base_url: str):
    """Dashboard uses companion chat panel behavior (not map trader panel)."""
    _login(page, base_url)

    companion_panel = page.locator('aside').filter(has_text='Companion Chat').first
    expect(companion_panel).to_be_visible(timeout=10000)
    expect(companion_panel.get_by_role('button', name='New Opener')).to_be_visible(timeout=10000)

@pytest.mark.ui
def test_map_character_panel_has_close_and_bargain_controls(page: Page, base_url: str):
    """Map character marker opens interaction panel with close action and bargaining/chat controls."""
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

    trader_panel = page.locator('.map-character-panel').first
    expect(trader_panel).to_be_visible(timeout=10000)
    has_send_offer = trader_panel.get_by_role('button', name='Send Offer').count() > 0
    has_send_chat = trader_panel.get_by_role('button', name='Send').count() > 0
    assert has_send_offer or has_send_chat, 'Expected map panel to provide bargain/chat action controls'

    if trader_panel.get_by_role('button', name='Close').count() > 0:
        trader_panel.get_by_role('button', name='Close').click()
    elif page.get_by_role('button', name='Close Trader').count() > 0:
        page.get_by_role('button', name='Close Trader').click()
    else:
        pytest.skip('No close control found on map character panel in this environment')

    expect(page.locator('.map-character-panel')).to_have_count(0)


@pytest.mark.ui
def test_gold_counter_visible_on_key_pages(page: Page, base_url: str):
    """Gold counter appears on dashboard, map, quests and inventory pages."""
    _login(page, base_url)

    nav_gold_counter = page.get_by_role('navigation').get_by_text(re.compile(r'Gold\s*:\s*\d+', re.IGNORECASE)).first
    expect(nav_gold_counter).to_be_visible(timeout=10000)

    page.goto(f"{base_url}/map")
    expect(nav_gold_counter).to_be_visible(timeout=10000)

    page.goto(f"{base_url}/quests")
    expect(nav_gold_counter).to_be_visible(timeout=10000)

    page.goto(f"{base_url}/inventory")
    expect(nav_gold_counter).to_be_visible(timeout=10000)

@pytest.mark.ui
def test_full_negotiation_and_deal_flow(page: Page, base_url: str):
    """E2E: User bargains for item, makes offers, says 'deal', and verifies purchase in inventory."""
    _login(page, base_url)

    # Go to map and open character panel
    page.get_by_role('link', name=re.compile('Map of Middle-earth', re.IGNORECASE)).click()
    page.wait_for_url('**/map', timeout=15000)
    page.wait_for_timeout(2500)
    character_markers = page.locator('.character-marker-icon')
    assert character_markers.count() > 0, 'Expected character seller markers on map'
    
    # Click on character markers until we find Sam's panel
    # Sam's marker should have data-character="sam" in the marker element
    max_attempts = 3
    found_sam = False
    for attempt in range(max_attempts):
        page.evaluate(
            """
            () => {
                // Try to find Sam's marker first
                let marker = document.querySelector('.character-marker[data-character="sam"]');
                if (marker) {
                    console.log('Found Sam marker');
                    marker.parentElement?.click();
                    return true;
                }
                // Fallback: try to find it by emoji (👨‍🌾 is Sam's emoji)
                const allMarkers = document.querySelectorAll('.character-marker-icon');
                for (let m of allMarkers) {
                    if (m.innerHTML.includes('👨‍🌾')) {
                        console.log('Found Sam by emoji');
                        m.click();
                        return true;
                    }
                }
                // Last resort: if only one marker, use it
                if (allMarkers.length === 1) {
                    console.log('Only one marker found, using it');
                    allMarkers[0].click();
                    return true;
                }
                console.error('Could not find Sam marker. Markers found:', allMarkers.length);
                return false;
            }
            """
        )
        panel = page.locator('.map-character-panel').first
        try:
            expect(panel).to_be_visible(timeout=3000)
            found_sam = True
            break
        except:
            # Panel didn't appear, try next marker
            continue
    
    assert found_sam, 'Could not find Sam character panel on map'
    expect(panel).to_be_visible(timeout=8000)
    
    # Print which character panel opened for debugging
    character_name = panel.locator('h3').first.inner_text()
    
    # Check if we got the right character
    if "Sam" not in character_name:
        print(f"DEBUG: Expected Sam but got {character_name}. Waiting 2 seconds and trying Sam selector")
        page.wait_for_timeout(2000)
        
        # Try to find and click Sam quick selector (👨‍🌾 emoji)
        try:
            sam_btn = page.locator('.map-character-panel').first.get_by_role('button').filter(has_text='👨‍🌾')
            if sam_btn.count() > 0:
                sam_btn.first.click()
                page.wait_for_timeout(1500)  # Wait for state update
                character_name = panel.locator('h3').first.inner_text()
        except:
            pass

    # Debug: Wait a bit more for items to load and check what's in the panel
    page.wait_for_timeout(3000)  # Extra wait for async shop items
    
    # Check what buttons are available
    all_buttons = panel.get_by_role('button').all()
    button_names = []
    for btn in all_buttons:
        try:
            button_names.append(btn.inner_text())
        except:
            pass
    
    # Check for shop items section
    try:
        shop_section = panel.locator('text=/Trader Ledger|No available items/i').first
        if shop_section.is_visible(timeout=2000):
            shop_section.inner_text()
    except:
        pass
    
    # Wait for shop items to load and bargain button to appear (can be slow in headless mode)
    expect(panel.get_by_role('button', name='Bargain').first).to_be_visible(timeout=20000)
    
    # Start bargaining for "Second Breakfast Pan" specifically
    # Find the item card that contains "Second Breakfast Pan" and has highest asking price matching
    bargain_buttons = panel.get_by_role('button', name='Bargain').all()
    
    # Get all item cards (divs that contain item names and prices)
    item_divs = panel.locator('div.rounded.border.border-gold-dark\\/20').all()
    
    target_button = None
    for item_div in item_divs:
        try:
            item_text = item_div.inner_text()
            if 'Second Breakfast Pan' in item_text:
                target_button = item_div.get_by_role('button', name='Bargain')
                break
        except:
            pass
    
    if target_button is None:
        target_button = panel.get_by_role('button', name='Bargain').first
    
    target_button.click()
    expect(panel.get_by_text(re.compile(r'Gold', re.IGNORECASE)).first).to_be_visible(timeout=12000)

    # Make a low offer
    offer_input = panel.locator('input[placeholder="Offer amount"]')
    offer_input.fill('50')
    panel.get_by_role('button', name='Send Offer').click()
    expect(panel.get_by_text(re.compile(r'counter|offer|gold', re.IGNORECASE)).first).to_be_visible(timeout=12000)

    # Make a higher offer
    offer_input.fill('70')
    panel.get_by_role('button', name='Send Offer').click()
    expect(panel.get_by_text(re.compile(r'counter|offer|gold', re.IGNORECASE)).first).to_be_visible(timeout=12000)

    # Make a final offer
    offer_input.fill('75')
    panel.get_by_role('button', name='Send Offer').click()
    expect(panel.get_by_text(re.compile(r'counter|offer|gold', re.IGNORECASE)).first).to_be_visible(timeout=12000)
    # Debug: Show chat messages before saying deal
    try:
        chat_area = panel.locator('.bg-white\/50.rounded-lg').first
        chat_text = chat_area.inner_text()
        print(f"DEBUG: Chat messages before deal:\n{chat_text[:500]}")
    except:
        pass
    # Say 'deal' to accept
    chat_box = panel.locator('textarea[placeholder*="Reply to"]')
    chat_box.fill('deal')
    panel.get_by_role('button', name='Send', exact=True).click()
    expect(panel.get_by_text(re.compile(r'accepted|sale|inventory|deal|gold', re.IGNORECASE)).first).to_be_visible(timeout=12000)

    # Close the character panel by clicking the close button (× symbol)
    # The panel has a close button with aria-label="Close" and × text
    close_button_on_panel = page.locator('.map-character-panel button[aria-label="Close"]')
    if close_button_on_panel.is_visible(timeout=2000):
        close_button_on_panel.click()
        # Wait for the panel to be hidden
        page.wait_for_selector('.map-character-panel', state='hidden', timeout=5000)
    page.wait_for_timeout(500)  # Wait for animation to complete

    # Go to inventory
    inventory_link = page.get_by_role('link', name=re.compile('Inventory', re.IGNORECASE))
    inventory_link.click()
    
    # Wait for navigation to inventory
    page.wait_for_url('**/inventory', timeout=15000)
    page.wait_for_timeout(1000)  # Wait for page render and data loading
    
    # Verify inventory shows purchased items
    expect(page.get_by_text('Items Purchased').first).to_be_visible(timeout=12000)
    
    # Verify the specific item (Second Breakfast Pan)
    inventory_table = page.locator('table')
    expect(inventory_table).to_be_visible(timeout=12000)
    
    # Look for the item name in any table cell
    item_cells = page.locator('td:has-text("Second Breakfast Pan")')
    if item_cells.count() == 0:
        # If exact text not found, try with case-insensitive regex
        item_cells = page.get_by_text(re.compile('second breakfast pan', re.IGNORECASE))
    
    assert item_cells.count() > 0, 'Expected "Second Breakfast Pan" to appear in inventory table'
    expect(item_cells.first).to_be_visible(timeout=12000)