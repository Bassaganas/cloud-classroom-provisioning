import { expect } from '@playwright/test'

export class DashboardPage {
  constructor(page) {
    this.page = page
  }

  async expectInstancesLabel(countOrPattern, timeout = undefined) {
    const locator = this.page.getByText(
      typeof countOrPattern === 'number' ? `Instances (${countOrPattern})` : countOrPattern,
    )

    if (timeout) {
      await expect(locator).toBeVisible({ timeout })
      return
    }

    await expect(locator).toBeVisible()
  }

  async expectTableRowCount(count) {
    await expect(this.page.locator('tbody tr')).toHaveCount(count)
  }

  async openCreateInstanceDialog() {
    await this.page.getByRole('button', { name: 'Create instance' }).click()
    await expect(this.page.getByRole('dialog', { name: 'Create Instance' })).toBeVisible()
  }

  async openDeleteSessionDialog() {
    await this.page.getByRole('button', { name: 'Delete Session' }).click()
    await expect(this.page.getByRole('dialog', { name: 'Delete Tutorial Session' })).toBeVisible()
  }

  async confirmDeleteSessionWithInstances(sessionId) {
    await this.page.getByLabel('Also delete associated EC2 instances').check()

    const deleteRequest = this.page.waitForRequest((request) => {
      return request.method() === 'DELETE' &&
        request.url().includes(`/api/tutorial_session/${sessionId}`) &&
        request.url().includes('delete_instances=true')
    })

    await this.page.getByRole('button', { name: /^Delete Session$/ }).last().click()
    await deleteRequest
  }
}
