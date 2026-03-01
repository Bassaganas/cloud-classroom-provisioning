"""Playwright E2E tests for NPC chat journey."""
import re

from playwright.sync_api import expect, Page


def _login(page: Page, base_url: str):
    page.goto(base_url)
    page.locator('#username').fill('frodo_baggins')
    page.locator('#password').fill('fellowship123')
    page.get_by_role('button', name='Enter Middle-earth').click()
    expect(page.get_by_role('heading', name='The Council Chamber')).to_be_visible(timeout=15000)


def test_npc_chat_opener_and_reply(page: Page, base_url: str):
    _login(page, base_url)

    expect(page.get_by_text('Companion Chat')).to_be_visible(timeout=15000)

    chat_box = page.locator('textarea[placeholder*="Reply to"]')
    expect(chat_box).to_be_visible()

    chat_box.fill('Guide me toward the best next quest.')
    page.get_by_role('button', name='Send').click()

    expect(page.get_by_text('Suggested action')).to_be_visible(timeout=15000)
    companion_panel = page.locator('aside').filter(has_text='Companion Chat').first
    expect(companion_panel.get_by_role('button', name=re.compile(r'Open Action|Scout on Map|Create Side Quest|Contain Dark Magic'))).to_be_visible(timeout=15000)


def test_npc_chat_character_switch(page: Page, base_url: str):
    _login(page, base_url)

    expect(page.get_by_text('Companion Chat')).to_be_visible(timeout=15000)

    page.get_by_role('button', name='🧙‍♂️ Gandalf').click()
    page.get_by_role('button', name='🧝 Frodo').click()
    page.get_by_role('button', name='👨‍🌾 Sam').click()

    expect(page.get_by_role('button', name='New Opener')).to_be_visible()
