import { expect } from '@playwright/test'

export class LandingPage {
  constructor(page) {
    this.page = page
  }

  createSessionButton() {
    return this.page.getByRole('button', { name: 'Create Session' }).first()
  }

  createSessionFabButton() {
    return this.page.locator('button[aria-label="Create session"]')
  }

  workshopSelectorDialog() {
    return this.page.getByRole('dialog')
  }

  sessionLink(sessionId) {
    return this.page.getByText(sessionId)
  }

  async openCreateSessionDialog() {
    await this.createSessionButton().click()
    await expect(this.page.getByRole('dialog', { name: 'Start New Tutorial Session' })).toBeVisible()
  }

  async openWorkshopSelectorDialogFromFab() {
    await this.createSessionFabButton().click()
    await expect(this.workshopSelectorDialog()).toBeVisible()
    await expect(this.page.getByText('Select Workshop')).toBeVisible()
    await expect(this.page.getByText('Choose a workshop to create a new tutorial session')).toBeVisible()
  }

  async selectFirstWorkshopWithKeyboard() {
    await this.page.keyboard.press('Tab')
    await this.page.keyboard.press('Enter')
  }

  async waitForSessionVisible(sessionId, timeout = 30000) {
    await expect(this.sessionLink(sessionId)).toBeVisible({ timeout })
  }

  async openSession(sessionId) {
    await this.sessionLink(sessionId).click()
  }

  async gotoLanding() {
    await this.page.goto('/')
    await expect(this.page.getByText('Workshops')).toBeVisible()
  }

  sessionCostsSummaryValueLocator() {
    const summaryCard = this.page
      .locator('div.MuiCard-root')
      .filter({ has: this.page.getByText('Session Costs (Est.)') })
      .first()

    return summaryCard.locator('h4')
  }

  sessionCostChipLocator(sessionId) {
    const row = this.page
      .getByRole('button')
      .filter({ has: this.page.getByText(sessionId, { exact: true }) })
      .first()

    return row.locator('span.MuiChip-label').filter({ hasText: /^\$\d+(\.\d{2})?$/ }).last()
  }

  async expectSessionCostsSummaryText(expectedText) {
    await expect(this.sessionCostsSummaryValueLocator()).toHaveText(expectedText)
  }

  async expectSessionCostChipText(sessionId, expectedText) {
    await expect(this.sessionCostChipLocator(sessionId)).toHaveText(expectedText)
  }
}
