import { expect, test } from '@playwright/test'
import { givenIAmLoggedIn, whenIOpenSessionDashboard } from './bdd/steps.js'
import { SessionFormDialogPage } from './pom/session-form-dialog.page.js'

const isDeployedRun = !!process.env.E2E_BASE_URL
const POLL_INTERVAL_MS = 10_000
const POLL_TIMEOUT_MS = 10 * 60 * 1000

function resolveApiBaseUrl() {
  const explicitApiUrl = process.env.E2E_API_URL
  if (explicitApiUrl) {
    return explicitApiUrl.replace(/\/$/, '')
  }

  const viteApiUrl = process.env.VITE_API_URL
  if (viteApiUrl) {
    return viteApiUrl.replace(/\/$/, '')
  }

  const baseUrl = process.env.E2E_BASE_URL
  if (baseUrl) {
    return `${baseUrl.replace(/\/$/, '')}/api`
  }

  return 'http://127.0.0.1:3001/api'
}

async function createSessionForWorkshop(page, workshopSlug, sessionId) {
  const dialog = new SessionFormDialogPage(page)
  const workshopDisplayName = workshopSlug.replaceAll('_', ' ')

  await page.goto('/')

  const workshopCard = page
    .locator('.MuiCard-root')
    .filter({ has: page.getByRole('heading', { name: new RegExp(workshopDisplayName, 'i') }) })
    .first()

  await expect(workshopCard).toBeVisible({ timeout: 60_000 })
  await workshopCard.getByRole('button', { name: 'Create Session' }).click()

  await dialog.expectVisible(15_000)
  await dialog.fillSessionConfiguration(sessionId, {
    poolCount: 1,
    adminCount: 1,
    productiveTutorial: workshopSlug === 'fellowship',
  })
  await dialog.submitAndWaitForCreateSession()

  await expect(page.getByText(sessionId)).toBeVisible({ timeout: 60_000 })
}

async function waitForSessionInstancesRunning(page, expectedCount) {
  const start = Date.now()

  while (Date.now() - start <= POLL_TIMEOUT_MS) {
    const rows = page.locator('tbody tr')
    const rowCount = await rows.count()

    if (rowCount >= expectedCount) {
      let allRunning = true

      for (let index = 0; index < expectedCount; index += 1) {
        const stateText = (await rows.nth(index).locator('td').nth(4).innerText()).trim().toLowerCase()
        if (!stateText.includes('running')) {
          allRunning = false
          break
        }
      }

      if (allRunning) {
        return
      }
    }

    await page.waitForTimeout(POLL_INTERVAL_MS)

    const refreshButton = page.getByRole('button', { name: 'Refresh' })
    if (await refreshButton.count()) {
      try {
        await refreshButton.click()
      } catch {
        // Best effort only; continue polling.
      }
    } else {
      try {
        await page.reload({ waitUntil: 'domcontentloaded' })
      } catch {
        // Transient DNS/navigation errors can happen while resources are warming up.
      }
    }
  }

  throw new Error(`Instances did not reach running state within ${POLL_TIMEOUT_MS / 60000} minutes`)
}

async function pollUntil(page, checker, label, testInfo) {
  const start = Date.now()
  let cycle = 0

  while (Date.now() - start <= POLL_TIMEOUT_MS) {
    cycle += 1
    const elapsed = Math.round((Date.now() - start) / 1000)
    const pageUrl = page.url()
    const pageTitle = await page.title().catch(() => '(unavailable)')
    console.log(`[pollUntil] cycle=${cycle} elapsed=${elapsed}s label="${label}" url="${pageUrl}" title="${pageTitle}"`)

    const found = await checker(page)
    if (found) {
      console.log(`[pollUntil] FOUND "${label}" after ${elapsed}s`)
      return
    }

    if (testInfo) {
      const screenshotPath = `test-results/poll-debug/${label.replaceAll(' ', '_')}-cycle${cycle}-${elapsed}s.png`
      await page.screenshot({ path: screenshotPath, fullPage: false }).catch(() => {})
    }

    await page.waitForTimeout(POLL_INTERVAL_MS)
    try {
      await page.reload({ waitUntil: 'domcontentloaded' })
    } catch {
      // Keep polling even if endpoint DNS is not yet resolvable.
    }
  }

  const elapsed = Math.round((Date.now() - start) / 1000)
  throw new Error(`${label} did not appear within ${elapsed}s (${POLL_TIMEOUT_MS / 60000} min limit)`)
}

async function verifyEndpointsOpenAndLoad(page, context, expectedCount, checker, label, testInfo) {
  const rows = page.locator('tbody tr')

  for (let index = 0; index < expectedCount; index += 1) {
    const endpointLink = rows.nth(index).locator('td').nth(5).locator('a').first()
    await expect(endpointLink).toBeVisible({ timeout: 30_000 })

    const endpointHref = await endpointLink.getAttribute('href')
    console.log(`[verifyEndpoints] Opening endpoint ${index + 1}/${expectedCount}: ${endpointHref}`)

    const [endpointPage] = await Promise.all([
      context.waitForEvent('page'),
      endpointLink.click(),
    ])

    await endpointPage.waitForLoadState('domcontentloaded', { timeout: 60_000 })
    const initialTitle = await endpointPage.title().catch(() => '(unavailable)')
    console.log(`[verifyEndpoints] Endpoint tab opened. title="${initialTitle}" url="${endpointPage.url()}"`)

    await pollUntil(endpointPage, checker, label, testInfo)
    await endpointPage.close()
  }
}

async function deleteSessionWithInstances(sessionId, workshopSlug) {
  const apiBaseUrl = resolveApiBaseUrl()
  const password = process.env.E2E_INSTANCE_MANAGER_PASSWORD || 'test123'

  const deleteUrl = `${apiBaseUrl}/tutorial_session/${encodeURIComponent(sessionId)}?password=${encodeURIComponent(password)}&workshop=${encodeURIComponent(workshopSlug)}&delete_instances=true`

  try {
    await fetch(deleteUrl, { method: 'DELETE' })
  } catch (error) {
    console.warn(`Cleanup failed for session ${sessionId}:`, error)
  }
}

async function hasFellowshipTitle(page) {
  const heading = page.locator('h1', { hasText: 'The Fellowship Quest Tracker' }).first()
  if ((await heading.count()) === 0) {
    return false
  }

  const className = await heading.getAttribute('class')
  if (!className) {
    return false
  }

  return ['text-4xl', 'md:text-5xl', 'mb-4', 'glow-gold'].every((token) => className.includes(token))
}

async function hasDifyLogo(page) {
  const logo = page.locator('img.block.object-contain.w-16.h-7[alt="Dify logo"][src="/logo/logo.svg"]').first()
  return (await logo.count()) > 0 && (await logo.isVisible())
}

test.describe('Deployed EC2 Manager smoke tests', () => {
  test.skip(!isDeployedRun, 'Smoke tests run only against deployed EC2 manager')
  test.setTimeout(35 * 60 * 1000)

  test('provision fellowship admin+pool and validate endpoint loads quest tracker', async ({ page, context }, testInfo) => {
    const sessionId = `pw-smoke-fellowship-${Date.now()}`

    try {
      await givenIAmLoggedIn(page)
      await createSessionForWorkshop(page, 'fellowship', sessionId)
      await whenIOpenSessionDashboard(page, sessionId)

      await waitForSessionInstancesRunning(page, 2)
      await verifyEndpointsOpenAndLoad(page, context, 2, hasFellowshipTitle, 'Fellowship Quest Tracker title', testInfo)
    } finally {
      await deleteSessionWithInstances(sessionId, 'fellowship')
    }
  })

  test('provision testus patronus admin+pool and validate endpoint loads dify logo', async ({ page, context }, testInfo) => {
    const sessionId = `pw-smoke-testus-${Date.now()}`

    try {
      await givenIAmLoggedIn(page)
      await createSessionForWorkshop(page, 'testus_patronus', sessionId)
      await whenIOpenSessionDashboard(page, sessionId)

      await waitForSessionInstancesRunning(page, 2)
      await verifyEndpointsOpenAndLoad(page, context, 2, hasDifyLogo, 'Dify logo', testInfo)
    } finally {
      await deleteSessionWithInstances(sessionId, 'testus_patronus')
    }
  })
})
