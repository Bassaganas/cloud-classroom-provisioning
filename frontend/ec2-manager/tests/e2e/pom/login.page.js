import { expect } from '@playwright/test'

export class LoginPage {
  constructor(page) {
    this.page = page
  }

  passwordInput() {
    return this.page.getByLabel('Password')
  }

  loginButton() {
    return this.page.getByRole('button', { name: 'Login' })
  }

  headerTitle() {
    return this.page.getByText('EC2 Tutorials Manager')
  }

  async goto() {
    await this.page.goto('/')
  }

  async login(password) {
    await this.goto()
    await this.passwordInput().fill(password)
    await this.loginButton().click()
    await expect(this.headerTitle()).toBeVisible()
  }
}
