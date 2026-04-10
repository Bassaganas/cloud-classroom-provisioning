import { expect } from '@playwright/test'

export class TutorialOverviewPage {
  constructor(page) {
    this.page = page
  }

  async gotoTutorialPath(pathname) {
    await this.page.goto(pathname)
  }

  async waitForTutorialSessionResponse(sessionId) {
    const sessionResponse = this.page.waitForResponse((response) => {
      return response.request().method() === 'GET' &&
        response.url().includes(`/api/tutorial_session/${sessionId}`)
    })

    const response = await sessionResponse
    return response.json()
  }

  async expectOverviewVisible() {
    await expect(this.page.getByText('Instance State Distribution')).toBeVisible()
    await expect(this.page.getByRole('table')).toBeVisible()
  }

  async expectTableVisible() {
    await expect(this.page.getByRole('table')).toBeVisible()
  }

  async expectTableRowCount(count) {
    await expect(this.page.locator('tbody tr')).toHaveCount(count)
  }

  async getEndpointColumnHrefs() {
    const tableRows = this.page.locator('tbody tr')
    const hrefs = []
    const headerCells = this.page.locator('thead tr th')
    const headerCount = await headerCells.count()
    let endpointColumnIndex = -1

    for (let i = 0; i < headerCount; i++) {
      const headerText = (await headerCells.nth(i).innerText()).trim().toLowerCase()
      if (headerText.includes('endpoint')) {
        endpointColumnIndex = i
        break
      }
    }

    if (endpointColumnIndex === -1) {
      return []
    }

    for (let i = 0; i < await tableRows.count(); i++) {
      const row = tableRows.nth(i)
      const endpointCell = row.locator('td').nth(endpointColumnIndex)
      const link = endpointCell.locator('a')
      const linkCountInCell = await link.count()

      if (linkCountInCell > 0) {
        hrefs.push(await link.getAttribute('href'))
      }
    }

    return hrefs.filter(Boolean)
  }

  async getAllTableAnchorHrefs() {
    const visitLinks = this.page.locator('table tbody tr td a')
    const hrefs = await visitLinks.evaluateAll((links) => links.map((link) => link.getAttribute('href') || ''))
    return hrefs
  }

  async expectEndpointLinkForInstance(instanceId, expectedLabel, expectedHref) {
    const row = this.page.locator('tbody tr').filter({ hasText: instanceId }).first()
    await expect(row).toBeVisible()

    const link = row.locator('td a').first()
    await expect(link).toHaveText(expectedLabel)
    await expect(link).toHaveAttribute('href', expectedHref)
  }
}
