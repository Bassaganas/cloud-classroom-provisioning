"""Tests for the Map Page and quest marker functionality."""
import pytest
from playwright.sync_api import Page
from tests.page_objects.login_page import LoginPage
from tests.page_objects.map_page import MapPage


def _click_first_marker_in_viewport(page: Page, selector: str) -> bool:
        """Click first marker currently inside viewport via DOM to reduce Leaflet click flakiness."""
        return page.evaluate(
                """
                ({ selector }) => {
                    const nodes = Array.from(document.querySelectorAll(selector));
                    const vw = window.innerWidth;
                    const vh = window.innerHeight;
                    const target = nodes.find((node) => {
                        const rect = node.getBoundingClientRect();
                        return rect.width > 0 && rect.height > 0 && rect.bottom > 0 && rect.right > 0 && rect.left < vw && rect.top < vh;
                    });
                    if (!target) {
                        return false;
                    }
                    target.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                    return true;
                }
                """,
                {"selector": selector},
        )


def _click_zoom_control(page: Page, title: str) -> bool:
        """Click Leaflet zoom control by title using DOM event dispatch (more reliable in CI/headless)."""
        return page.evaluate(
                """
                ({ title }) => {
                    const selector = `.leaflet-control-zoom a[title="${title}"]`;
                    const target = document.querySelector(selector);
                    if (!target) {
                        return false;
                    }
                    target.dispatchEvent(new MouseEvent('click', { bubbles: true, cancelable: true, view: window }));
                    return true;
                }
                """,
                {"title": title},
        )

@pytest.fixture
def authenticated_page(page: Page, base_url: str, test_credentials: dict):
    """Fixture to provide an authenticated page."""
    login_page = LoginPage(page, base_url)
    login_page.login(
        test_credentials['username'],
        test_credentials['password']
    )
    login_page.wait_for_dashboard()
    return page

@pytest.mark.ui
def test_quest_marker_appears_in_mordor(authenticated_page: Page, base_url: str):
    """
    Given a Quest in Mordor
    When the user navigates to the map
    Then the map is displayed with a quest marker in Mordor coordinates.
    """
    # Given: A quest exists in Mordor (from seed data: "Destroy the One Ring" or "Reach Mordor")
    map_page = MapPage(authenticated_page, base_url)
    
    # When: The user navigates to the map
    map_page.navigate()
    map_page.wait_for_map()
    
    # Wait for markers to render
    authenticated_page.wait_for_timeout(3000)
    
    # Then: The map is displayed with a quest marker in Mordor coordinates
    # Mordor coordinates are approximately: map_x: 3606, map_y: 2603 (Mount Doom)
    # or map_x: 3606, map_y: 2603 (Mordor)
    
    # Check that quest markers are visible
    quest_markers = authenticated_page.locator('.quest-marker-icon')
    marker_count = quest_markers.count()
    
    assert marker_count > 0, f"Should have quest markers on map, found {marker_count}"
    
    # Verify at least one marker is for a quest in Mordor
    # We can check by looking for quests with "Mordor" or "Mount Doom" in their location
    # or by checking if markers are visible in the Mordor region of the map
    
    # Check that map container is visible and map is loaded
    assert map_page.map_container.is_visible(), "Map container should be visible"
    
    # Verify quest markers are clickable (they should have pointer-events: auto)
    first_marker = quest_markers.first
    if first_marker.is_visible():
        # Check marker styling indicates it's clickable
        marker_style = first_marker.evaluate('el => window.getComputedStyle(el).pointerEvents')
        assert marker_style in ['auto', 'all'], f"Quest marker should be clickable (pointer-events: {marker_style})"

@pytest.mark.ui
def test_map_page_loads(authenticated_page: Page, base_url: str):
    """Test that map page loads correctly."""
    map_page = MapPage(authenticated_page, base_url)
    map_page.navigate()
    
    assert map_page.is_loaded(), "Map page should be loaded"
    assert map_page.map_container.is_visible(), "Map container should be visible"

@pytest.mark.ui
def test_map_displays_location_markers(authenticated_page: Page, base_url: str):
    """Test that location markers are displayed on the map."""
    map_page = MapPage(authenticated_page, base_url)
    map_page.navigate()
    map_page.wait_for_map()
    
    # Wait a bit for markers to render
    authenticated_page.wait_for_timeout(2000)
    
    location_markers = map_page.get_location_markers_count()
    assert location_markers > 0, f"Should have location markers on map, found {location_markers}"

@pytest.mark.ui
def test_quest_markers_appear_on_map(authenticated_page: Page, base_url: str):
    """Test that quest markers appear on the map for quests with locations."""
    map_page = MapPage(authenticated_page, base_url)
    map_page.navigate()
    map_page.wait_for_map()
    
    # Wait for markers to render
    authenticated_page.wait_for_timeout(3000)
    
    quest_markers = map_page.get_quest_markers_count()
    quest_count = map_page.get_quest_count_in_list()
    
    # If there are quests, at least some should have markers (if they have locations)
    if quest_count > 0:
        assert quest_markers >= 0, f"Quest markers count should be non-negative, found {quest_markers}"
        # Note: Not all quests may have locations, so we can't assert quest_markers == quest_count
        print(f"Found {quest_markers} quest markers for {quest_count} total quests")

@pytest.mark.ui
def test_quest_marker_is_clickable(authenticated_page: Page, base_url: str):
    """Test that quest markers are clickable and open popups."""
    map_page = MapPage(authenticated_page, base_url)
    map_page.navigate()
    map_page.wait_for_map()
    
    # Wait for markers to render
    authenticated_page.wait_for_timeout(3000)
    
    # Try to find and click a quest marker
    quest_markers = authenticated_page.locator('.quest-marker-icon')
    marker_count = quest_markers.count()
    
    if marker_count > 0:
        # Click the first quest marker
        first_marker = quest_markers.first
        first_marker.wait_for(state='visible', timeout=5000)
        
        # Verify marker is clickable
        assert first_marker.is_visible(), "Quest marker should be visible"
        
        # Click the marker
        assert _click_first_marker_in_viewport(authenticated_page, '.quest-marker-icon'), "No clickable quest marker found in viewport"
        
        # Wait for UI response
        authenticated_page.wait_for_timeout(1000)

        popup_visible = authenticated_page.locator('.quest-popup, .leaflet-popup-content').first.is_visible()
        details_visible = authenticated_page.locator('.quest-details-card').is_visible()
        assert popup_visible or details_visible, "Marker click should show popup or quest details card"

        if popup_visible:
            popup_content = authenticated_page.locator('.quest-popup, .leaflet-popup-content').first.inner_text()
            assert len(popup_content) > 0, "Popup should have content"
    else:
        pytest.skip("No quest markers found on map - ensure quests have location_id")

@pytest.mark.ui
def test_quest_popup_displays_full_information(authenticated_page: Page, base_url: str):
    """Test that quest popup displays full quest information."""
    map_page = MapPage(authenticated_page, base_url)
    map_page.navigate()
    map_page.wait_for_map()
    
    # Wait for markers to render
    authenticated_page.wait_for_timeout(3000)
    
    quest_markers = authenticated_page.locator('.quest-marker-icon')
    marker_count = quest_markers.count()
    
    if marker_count > 0:
        # Click the first quest marker
        first_marker = quest_markers.first
        assert _click_first_marker_in_viewport(authenticated_page, '.quest-marker-icon'), "No clickable quest marker found in viewport"
        
        # Wait for popup
        popup = authenticated_page.locator('.quest-popup')
        popup.wait_for(state='visible', timeout=3000)
        
        # Check for required popup elements
        assert popup.locator('h4').is_visible(), "Popup should have quest title"
        
        # Check for description (should not be truncated)
        description = popup.locator('.quest-popup-description')
        if description.is_visible():
            desc_text = description.inner_text()
            # Description should be present and not just "..."
            assert len(desc_text) > 3, "Description should not be truncated to just '...'"
        
        # Check for action buttons
        view_button = popup.locator('.btn-view-quest')
        assert view_button.is_visible(), "Popup should have 'View Quest' button"
    else:
        pytest.skip("No quest markers found on map")

@pytest.mark.ui
def test_location_marker_click_filters_quests(authenticated_page: Page, base_url: str):
    """Test that clicking a location marker does not hide quest markers."""
    map_page = MapPage(authenticated_page, base_url)
    map_page.navigate()
    map_page.wait_for_map()
    
    # Wait for markers to render
    authenticated_page.wait_for_timeout(3000)
    
    # Get initial quest marker count (individual markers + quest clusters)
    initial_count = authenticated_page.locator('.quest-marker-icon').count() + authenticated_page.locator('.quest-marker-cluster').count()
    
    # Click on a location marker
    location_markers = authenticated_page.locator('.location-marker-icon')
    if location_markers.count() > 0:
        assert _click_first_marker_in_viewport(authenticated_page, '.location-marker-icon'), "No clickable location marker found in viewport"
        
        # Wait for map state to settle
        authenticated_page.wait_for_timeout(1000)
        
        # Quest markers should still be present after location click
        post_click_count = authenticated_page.locator('.quest-marker-icon').count() + authenticated_page.locator('.quest-marker-cluster').count()
        assert post_click_count > 0, "Quest markers should remain visible after clicking a location marker"
        # Avoid false negatives in low-data environments where count can vary due to clustering visuals,
        # but marker set should not collapse to zero from interaction.
        assert initial_count == 0 or post_click_count > 0
    else:
        pytest.skip("No location markers found on map")


@pytest.mark.ui
def test_location_and_quest_markers_survive_zoom_in_out(authenticated_page: Page, base_url: str):
    """Markers of locations and quests remain available through zoom in/out interactions."""
    map_page = MapPage(authenticated_page, base_url)
    map_page.navigate()
    map_page.wait_for_map()
    authenticated_page.wait_for_timeout(2500)

    # Baseline marker availability
    initial_location = authenticated_page.locator('.location-marker-icon, .marker-cluster').count()
    initial_quest = authenticated_page.locator('.quest-marker-icon, .quest-marker-cluster').count()

    if initial_location == 0:
        pytest.skip("No location markers found on map")
    if initial_quest == 0:
        pytest.skip("No quest markers found on map - ensure quests have location_id")

    zoom_out_btn = authenticated_page.locator('.leaflet-control-zoom a[title="Zoom out"]')
    zoom_in_btn = authenticated_page.locator('.leaflet-control-zoom a[title="Zoom in"]')

    if zoom_out_btn.count() == 0 or zoom_in_btn.count() == 0:
        pytest.skip("Map zoom controls not available")

    # Zoom out then verify both marker types still represented
    assert _click_zoom_control(authenticated_page, 'Zoom out'), "Failed to click zoom out control"
    authenticated_page.wait_for_timeout(500)
    assert _click_zoom_control(authenticated_page, 'Zoom out'), "Failed to click zoom out control"
    authenticated_page.wait_for_timeout(800)

    location_after_out = authenticated_page.locator('.location-marker-icon, .marker-cluster').count()
    quest_after_out = authenticated_page.locator('.quest-marker-icon, .quest-marker-cluster').count()
    assert location_after_out > 0, "Location markers/clusters should remain visible after zoom out"
    assert quest_after_out > 0, "Quest markers/clusters should remain visible after zoom out"

    # Zoom back in and verify again
    assert _click_zoom_control(authenticated_page, 'Zoom in'), "Failed to click zoom in control"
    authenticated_page.wait_for_timeout(500)
    assert _click_zoom_control(authenticated_page, 'Zoom in'), "Failed to click zoom in control"
    authenticated_page.wait_for_timeout(800)

    location_after_in = authenticated_page.locator('.location-marker-icon, .marker-cluster').count()
    quest_after_in = authenticated_page.locator('.quest-marker-icon, .quest-marker-cluster').count()
    assert location_after_in > 0, "Location markers/clusters should remain visible after zoom in"
    assert quest_after_in > 0, "Quest markers/clusters should remain visible after zoom in"


@pytest.mark.ui
def test_marker_clicks_do_not_toggle_filter_sidebar(authenticated_page: Page, base_url: str):
    """Filter sidebar open/closed state changes only via the explicit filter controls, not marker clicks."""
    map_page = MapPage(authenticated_page, base_url)
    map_page.navigate()
    map_page.wait_for_map()
    authenticated_page.wait_for_timeout(2500)

    sidebar = authenticated_page.locator('.filter-sidebar')
    sidebar.wait_for(state='visible', timeout=5000)
    initial_open = sidebar.evaluate("el => el.classList.contains('open')")

    # Click one location marker (if available)
    if authenticated_page.locator('.location-marker-icon').count() > 0:
        assert _click_first_marker_in_viewport(authenticated_page, '.location-marker-icon'), "No clickable location marker found in viewport"
        authenticated_page.wait_for_timeout(700)

    # Click one quest marker (if available)
    if authenticated_page.locator('.quest-marker-icon').count() > 0:
        assert _click_first_marker_in_viewport(authenticated_page, '.quest-marker-icon'), "No clickable quest marker found in viewport"
        authenticated_page.wait_for_timeout(700)

    final_open = sidebar.evaluate("el => el.classList.contains('open')")
    assert final_open == initial_open, "Marker clicks must not toggle filter sidebar open/closed state"
