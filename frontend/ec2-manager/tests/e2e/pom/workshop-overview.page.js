import { expect } from '@playwright/test'

export class WorkshopOverviewPage {
  constructor(page) {
    this.page = page
  }

  async gotoWorkshopPath(workshop) {
    await this.page.goto(`/workshop/${workshop}`)
  }

  async expectDashboardVisible() {
    await expect(this.page.getByText('Workshop instance management')).toBeVisible()
    await expect(this.page.getByRole('table')).toBeVisible()
  }

  async expectCostCardsVisible() {
    await expect(this.page.getByText('Hourly Burn (Est.)')).toBeVisible()
    await expect(this.page.getByText('Accrued (Est.)')).toBeVisible()
    await expect(this.page.getByText('Next 24h (Est.)')).toBeVisible()
    await expect(this.page.getByText('Monthly (Est.)')).toBeVisible()
    await expect(this.page.getByText(/Actual \(Billing\)/)).toBeVisible()
  }

  async expectMonthlyEstimateHasCurrencyValue() {
    const monthlyCard = this.page
      .locator('div.MuiCard-root')
      .filter({ has: this.page.getByText('Monthly (Est.)') })
      .first()

    await expect(monthlyCard.locator('h5')).toHaveText(/^\$\d+(\.\d{2})?$/)
  }

  async expectCostColumnsVisible() {
    await expect(this.page.getByRole('columnheader', { name: 'Hourly (Est.)' })).toBeVisible()
    await expect(this.page.getByRole('columnheader', { name: 'Cost (Est./Actual)' })).toBeVisible()
  }

  costCardValueLocator(label) {
    const card = this.page
      .locator('div.MuiCard-root')
      .filter({ has: this.page.getByText(label) })
      .first()

    return card.locator('h5')
  }

  async expectCostCardValue(label, expectedValue) {
    const valueLocator = this.costCardValueLocator(label)
    await expect(valueLocator).toHaveText(expectedValue)
  }
}
