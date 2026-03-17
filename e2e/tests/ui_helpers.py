"""Shared UI assertion helpers for e2e tests."""

import pytest
import time


def assert_any_selector_visible(page, selectors, timeout=10000):
    """Assert that at least one selector in the list becomes visible."""
    last_error = None
    for selector in selectors:
        try:
            locator = page.locator(selector).first
            locator.wait_for(state='visible', timeout=timeout)
            return selector
        except Exception as error:
            last_error = error

    selector_list = ", ".join(selectors)
    pytest.fail(
        f"None of the expected selectors became visible: [{selector_list}]"
        + (f". Last error: {last_error}" if last_error else "")
    )


def create_tutorial_session(page, session_id, pool_count=1, admin_count=0):
    """Create a tutorial session from landing page via UI."""
    assert_any_selector_visible(page, ['button:has-text("Create Session")'])
    page.locator('button:has-text("Create Session")').first.click()
    assert_any_selector_visible(page, ['text=Start New Tutorial Session'])

    dialog = page.locator('[role="dialog"]').last
    dialog.locator('input#session_id').fill(session_id)

    pool_input = dialog.locator('input#pool_count')
    pool_input.fill('')
    pool_input.fill(str(pool_count))

    admin_input = dialog.locator('input#admin_count')
    admin_input.fill('')
    admin_input.fill(str(admin_count))

    dialog.locator('button:has-text("Create Session")').first.click()
    assert_any_selector_visible(page, [f'text={session_id}'], timeout=15000)


def open_tutorial_session(page, session_id):
    """Open a tutorial session from landing page."""
    assert_any_selector_visible(page, [f'text={session_id}'])
    page.locator(f'text={session_id}').first.click()
    assert_any_selector_visible(page, ['text=Search instances', 'text=Instances'], timeout=15000)


def accept_next_dialog(page):
    """Accept the next browser confirm/alert dialog."""
    page.once('dialog', lambda dialog: dialog.accept())


def wait_for_condition(check_fn, timeout_seconds=60, poll_interval=3, failure_message='Condition not met'):
    """Poll a condition function until true or timeout."""
    end_time = time.time() + timeout_seconds
    while time.time() < end_time:
        if check_fn():
            return
        time.sleep(poll_interval)
    pytest.fail(failure_message)
