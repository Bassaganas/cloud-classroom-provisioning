"""BDD-style real-stack tests for NPC chat journey."""

from urllib.parse import parse_qs, urlparse

import pytest
from pytest_bdd import given, scenarios, then, when

from tests.page_objects.chat_panel_page import ChatPanelPage
from tests.page_objects.login_page import LoginPage


scenarios("features/npc_chat_realstack.feature")


@given("the real Fellowship SUT stack is running via docker compose")
def real_stack_running(ensure_real_stack):
    """Ensure stack is up using session fixture."""


@given("I am logged into the Fellowship dashboard", target_fixture="dashboard_page")
def logged_in_dashboard(page, base_url, test_credentials):
    login_page = LoginPage(page, base_url)
    login_page.login(test_credentials["username"], test_credentials["password"])
    login_page.wait_for_dashboard()
    return page


@when("the companion chat panel initializes", target_fixture="chat_panel")
def companion_chat_initializes(dashboard_page):
    panel = ChatPanelPage(dashboard_page)
    panel.wait_until_visible()
    panel.wait_for_min_messages(1)
    return panel


@when("I send a message in companion chat", target_fixture="chat_after_reply")
def send_message(chat_panel):
    before_count = chat_panel.message_bubbles().count()
    chat_panel.send_message("Guide me toward the best next quest.")
    chat_panel.wait_for_min_messages(before_count + 2)
    return chat_panel


@then("I should receive a companion reply")
def should_receive_reply(chat_after_reply):
    bubbles = chat_after_reply.message_bubbles()
    assert bubbles.count() >= 3


@then("I should see a suggested action nudge")
def should_see_suggested_action(chat_after_reply):
    chat_after_reply.suggested_action_heading.wait_for(state="visible", timeout=15000)
    chat_after_reply.open_action_button.wait_for(state="visible", timeout=15000)


@when("I open the suggested action", target_fixture="post_action_page")
def open_suggested_action(chat_after_reply):
    chat_after_reply.open_action()
    return chat_after_reply.page


@then("I should be navigated to a valid in-app route")
def should_navigate_in_app(post_action_page):
    post_action_page.wait_for_load_state("networkidle")
    assert any(path in post_action_page.url for path in ["/quests", "/dashboard", "/map"])


@then("the destination should contain targeted action context")
def destination_contains_targeted_context(post_action_page):
    parsed = urlparse(post_action_page.url)
    query = parse_qs(parsed.query)

    if parsed.path.endswith("/quests"):
        assert any(key in query for key in ["focusQuestId", "status"])
        return

    if parsed.path.endswith("/map"):
        assert any(key in query for key in ["selectedQuestId", "zoomToLocation"])
        return

    assert parsed.path.endswith("/dashboard")


@pytest.mark.realstack
@pytest.mark.bdd
@pytest.mark.npc
@pytest.mark.chat
@pytest.mark.login
def test_realstack_npc_bdd_marker_anchor():
    """Anchor test to make marker selection straightforward."""
    assert True
