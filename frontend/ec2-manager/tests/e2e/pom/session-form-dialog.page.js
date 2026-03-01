import { expect } from '@playwright/test'

export class SessionFormDialogPage {
  constructor(page) {
    this.page = page
  }

  dialog() {
    return this.page.getByRole('dialog', { name: 'Start New Tutorial Session' })
  }

  async expectVisible(timeout = 15000) {
    await expect(this.dialog()).toBeVisible({ timeout })
  }

  async fillSessionConfiguration(sessionId, { poolCount = 1, adminCount = 0, adminCleanupDays = 7, productiveTutorial = false } = {}) {
    await this.page.getByLabel('Session ID').fill(sessionId)
    await this.page.getByLabel('Pool Instances').fill(String(poolCount))
    await this.page.getByLabel('Admin Instances').fill(String(adminCount))

    if (adminCount > 0) {
      await this.page.getByLabel('Admin Cleanup Days').fill(String(adminCleanupDays))
    }

    if (productiveTutorial) {
      await this.page.getByLabel('Productive tutorial (use On-Demand only)').check()
    }
  }

  async submitAndWaitForCreateSession() {
    const sessionCreatedRequest = this.page.waitForResponse((response) => {
      return response.request().method() === 'POST' &&
        response.url().includes('/api/create_tutorial_session') &&
        response.status() === 200
    })

    await this.page.getByRole('button', { name: 'Create Session' }).click()
    await sessionCreatedRequest
  }
}
