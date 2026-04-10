export class CreateInstanceDialogPage {
  constructor(page) {
    this.page = page
  }

  async expectEc2SizeOptionsVisible() {
    await this.page.getByRole('combobox', { name: 'EC2 Instance Size' }).click()
    await this.page.getByRole('option', { name: /t3\.small/i }).waitFor()
    await this.page.getByRole('option', { name: /t3\.medium/i }).waitFor()
    await this.page.getByRole('option', { name: /t3\.large/i }).waitFor()
    await this.page.getByRole('option', { name: /t2\.small/i }).waitFor()
    await this.page.getByRole('option', { name: /t2\.medium/i }).waitFor()
    await this.page.getByRole('option', { name: /t2\.large/i }).waitFor()
    await this.page.keyboard.press('Escape')
  }

  async selectEc2InstanceSize(instanceSize) {
    await this.page.getByRole('combobox', { name: 'EC2 Instance Size' }).click()
    await this.page.getByRole('option', { name: new RegExp(`^${instanceSize}\\b`, 'i') }).click()
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

  waitForCreateRequestWithEc2Size(instanceSize) {
    return this.page.waitForRequest((request) => {
      if (!(request.method() === 'POST' && request.url().includes('/api/create'))) return false
      const payload = request.postDataJSON()
      return payload?.ec2_instance_type === instanceSize
    })
  }
}
