export class CreateInstanceDialogPage {
  constructor(page) {
    this.page = page
  }

  async fillCount(count) {
    await this.page.getByLabel('Count').fill(String(count))
  }

  async selectInstanceTypeAdmin() {
    await this.page.getByLabel('Instance Type').click()
    await this.page.getByRole('option', { name: 'Admin' }).click()
  }

  async fillCleanupDays(days) {
    await this.page.getByLabel('Cleanup Days').fill(String(days))
  }

  async fillSpotMaxPrice(pricePerHour) {
    await this.page.getByLabel('Spot Max Price ($/hour, optional)').fill(String(pricePerHour))
  }

  async submitCreate() {
    await this.page.getByRole('button', { name: /^Create$/ }).click()
  }

  waitForCreateRequestWithAdminCleanupDays(cleanupDays) {
    return this.page.waitForRequest((request) => {
      if (!(request.method() === 'POST' && request.url().includes('/api/create'))) return false
      const payload = request.postDataJSON()
      return payload?.type === 'admin' && payload?.cleanup_days === cleanupDays
    })
  }

  waitForCreateRequestWithSpotPricing(sessionId, spotMaxPrice) {
    return this.page.waitForRequest((request) => {
      if (!(request.method() === 'POST' && request.url().includes('/api/create'))) return false
      const payload = request.postDataJSON()
      return payload?.purchase_type === 'spot' &&
        payload?.spot_max_price === String(spotMaxPrice) &&
        payload?.tutorial_session_id === sessionId
    })
  }
}
