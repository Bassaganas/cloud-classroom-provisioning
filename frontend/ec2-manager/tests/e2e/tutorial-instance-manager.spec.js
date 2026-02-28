import { expect, test } from '@playwright/test'

const PASSWORD = 'test123'

async function login(page) {
  await page.goto('/')
  await page.getByLabel('Password').fill(PASSWORD)
  await page.getByRole('button', { name: 'Login' }).click()
  await expect(page.getByText('EC2 Tutorials Manager')).toBeVisible()
}

async function createTutorialSession(page, sessionId, { poolCount = 1, adminCount = 0, adminCleanupDays = 7 } = {}) {
  await page.getByRole('button', { name: 'Create Session' }).first().click()
  await expect(page.getByRole('dialog', { name: 'Start New Tutorial Session' })).toBeVisible()

  await page.getByLabel('Session ID').fill(sessionId)
  await page.getByLabel('Pool Instances').fill(String(poolCount))
  await page.getByLabel('Admin Instances').fill(String(adminCount))

  if (adminCount > 0) {
    await page.getByLabel('Admin Cleanup Days').fill(String(adminCleanupDays))
  }

  // Wait for the create request to complete
  const sessionCreatedRequest = page.waitForResponse((response) => {
    return response.request().method() === 'POST' &&
      response.url().includes('/api/create_tutorial_session') &&
      response.status() === 200
  })

  await page.getByRole('button', { name: 'Create Session' }).click()
  await sessionCreatedRequest

  // Wait for the session to appear on the page with a longer timeout
  await expect(page.getByText(sessionId)).toBeVisible({ timeout: 30000 })
}

test.describe('Tutorial Instance Manager critical workflows', () => {
  test('1) create tutorial instance and initial instances', async ({ page }) => {
    await login(page)

    const sessionId = `pw-init-${Date.now()}`
    await createTutorialSession(page, sessionId, { poolCount: 2, adminCount: 1, adminCleanupDays: 9 })

    await page.getByText(sessionId).click()
    await expect(page.getByText('Instances (3)')).toBeVisible()
    await expect(page.locator('tbody tr')).toHaveCount(3)
  })

  test('2) delete tutorial instances should delete all its instances', async ({ page }) => {
    await login(page)

    const sessionId = `pw-del-${Date.now()}`
    await createTutorialSession(page, sessionId, { poolCount: 2, adminCount: 1 })

    await page.getByText(sessionId).click()

    await page.getByRole('button', { name: 'Delete Session' }).click()
    await expect(page.getByRole('dialog', { name: 'Delete Tutorial Session' })).toBeVisible()
    await page.getByLabel('Also delete associated EC2 instances').check()

    const deleteRequest = page.waitForRequest((request) => {
      return request.method() === 'DELETE' &&
        request.url().includes(`/api/tutorial_session/${sessionId}`) &&
        request.url().includes('delete_instances=true')
    })

    await page.getByRole('button', { name: /^Delete Session$/ }).last().click()
    await deleteRequest

    await expect(page).toHaveURL('/')
    await expect(page.getByText(sessionId)).toHaveCount(0)
  })

  test('3) create EC2 instances when tutorial instance already exists', async ({ page }) => {
    await login(page)

    const sessionId = `pw-grow-${Date.now()}`
    await createTutorialSession(page, sessionId, { poolCount: 1, adminCount: 0 })
    await page.getByText(sessionId).click()

    await expect(page.getByText('Instances (1)')).toBeVisible()

    await page.getByLabel('Create instance').click()
    await expect(page.getByRole('dialog', { name: 'Create Instance' })).toBeVisible()

    await page.getByLabel('Count').fill('2')
    await page.getByRole('button', { name: /^Create$/ }).click()

    await expect(page.getByText('Instances (3)')).toBeVisible()
    await expect(page.locator('tbody tr')).toHaveCount(3)
  })

  test('4) create admin instances with X days and change amount of days', async ({ page }) => {
    await login(page)

    const sessionId = `pw-admin-${Date.now()}`
    await createTutorialSession(page, sessionId, { poolCount: 1, adminCount: 0 })
    await page.getByText(sessionId).click()

    await page.getByLabel('Create instance').click()
    await expect(page.getByRole('dialog', { name: 'Create Instance' })).toBeVisible()

    await page.getByLabel('Instance Type').click()
    await page.getByRole('option', { name: 'Admin' }).click()
    await page.getByLabel('Count').fill('1')
    await page.getByLabel('Cleanup Days').fill('10')

    const createRequest = page.waitForRequest((request) => {
      if (!(request.method() === 'POST' && request.url().includes('/api/create'))) return false
      const payload = request.postDataJSON()
      return payload?.type === 'admin' && payload?.cleanup_days === 10
    })

    await page.getByRole('button', { name: /^Create$/ }).click()
    await createRequest

    await expect(page.getByText('Instances (2)')).toBeVisible()
  })

  test('5) view tutorial dashboard with all tutorial instances', async ({ page }) => {
    await login(page)

    const sessionResponse = page.waitForResponse((response) => {
      return response.request().method() === 'GET' &&
        response.url().includes('/api/tutorial_session/tut1')
    })

    await page.goto('/tutorial/fellowship/tut1')
    const response = await sessionResponse
    const data = await response.json()
    const expectedCount = data.instances.length

    await expect(page.getByText('Instance State Distribution')).toBeVisible()
    await expect(page.getByRole('table')).toBeVisible()
    await expect(page.locator('tbody tr')).toHaveCount(expectedCount)
  })

  test('6) FAB button shows workshop selector dialog on Landing', async ({ page }) => {
    await login(page)
    
    // Click the FAB button (specific aria-label)
    await page.locator('button[aria-label="Create session"]').click()
    
    // Should show the workshop selector dialog
    await expect(page.getByRole('dialog')).toBeVisible()
    await expect(page.getByText('Select Workshop')).toBeVisible()
    await expect(page.getByText('Choose a workshop to create a new tutorial session')).toBeVisible()
  })

  test('7) FAB workshop selector creates session in selected workshop', async ({ page }) => {
    await login(page)
    
    const sessionId = `pw-fab-${Date.now()}`
    
    // Click the FAB button
    await page.locator('button[aria-label="Create session"]').click()
    const dialog = page.getByRole('dialog')
    await expect(dialog).toBeVisible()
    
    // Find the fellowship workshop item and click it using Tab and keyboard navigation
    // Tab to focus the first list item, then press To activate it
    await page.keyboard.press('Tab')
    await page.keyboard.press('Enter')
    
    // Should now show the tutorial session form
    await expect(page.getByRole('dialog', { name: 'Start New Tutorial Session' })).toBeVisible({ timeout: 15000 })
    
    // Create the session
    await page.getByLabel('Session ID').fill(sessionId)
    await page.getByLabel('Pool Instances').fill('1')
    await page.getByRole('button', { name: 'Create Session' }).click()
    
    
    // Should be back on landing with new session visible
    await expect(page.getByText(sessionId)).toBeVisible({ timeout: 30000 })
  })

  test('8) FAB button in tutorial dashboard creates new instances', async ({ page }) => {
    await login(page)
    
    const sessionId = `pw-fab-inst-${Date.now()}`
    await createTutorialSession(page, sessionId, { poolCount: 1, adminCount: 0 })
    
    // Navigate to tutorial dashboard
    await page.getByText(sessionId).click()
    await expect(page.getByText('Instances (1)')).toBeVisible()
    
    // Click FAB to create more instances
    await page.getByRole('button', { name: 'Create instance' }).click()
    await expect(page.getByRole('dialog', { name: 'Create Instance' })).toBeVisible()
    
    // Fill and submit the form
    await page.getByLabel('Count').fill('3')
    await page.getByRole('button', { name: /^Create$/ }).click()
    
    // Verify instances increased
    await expect(page.getByText('Instances (4)')).toBeVisible()
    await expect(page.locator('tbody tr')).toHaveCount(4)
  })
})
