import { expect } from '@playwright/test'
import { LoginPage } from '../pom/login.page.js'
import { LandingPage } from '../pom/landing.page.js'
import { SessionFormDialogPage } from '../pom/session-form-dialog.page.js'
import { DashboardPage } from '../pom/dashboard.page.js'
import { CreateInstanceDialogPage } from '../pom/create-instance-dialog.page.js'
import { TutorialOverviewPage } from '../pom/tutorial-overview.page.js'

const PASSWORD = 'test123'

export async function givenIAmLoggedIn(page) {
  const loginPage = new LoginPage(page)
  await loginPage.login(PASSWORD)
}

export async function whenICreateTutorialSession(page, sessionId, options = {}) {
  const landingPage = new LandingPage(page)
  const sessionFormDialogPage = new SessionFormDialogPage(page)

  await landingPage.openCreateSessionDialog()
  await sessionFormDialogPage.fillSessionConfiguration(sessionId, options)
  await sessionFormDialogPage.submitAndWaitForCreateSession()
  await landingPage.waitForSessionVisible(sessionId, 30000)
}

export async function whenIOpenSessionDashboard(page, sessionId) {
  const landingPage = new LandingPage(page)
  await landingPage.openSession(sessionId)
}

export async function thenISeeInstancesCount(page, count, timeout = undefined) {
  const dashboardPage = new DashboardPage(page)
  await dashboardPage.expectInstancesLabel(count, timeout)
}

export async function thenISeeTableRowCount(page, count) {
  const dashboardPage = new DashboardPage(page)
  await dashboardPage.expectTableRowCount(count)
}

export async function whenIDeleteSessionAndAssociatedInstances(page, sessionId) {
  const dashboardPage = new DashboardPage(page)
  await dashboardPage.openDeleteSessionDialog()
  await dashboardPage.confirmDeleteSessionWithInstances(sessionId)
}

export async function thenIAmBackOnLandingWithoutSession(page, sessionId) {
  const landingPage = new LandingPage(page)
  await expect(page).toHaveURL('/')
  await expect(landingPage.sessionLink(sessionId)).toHaveCount(0)
}

export async function whenIOpenCreateInstanceDialog(page) {
  const dashboardPage = new DashboardPage(page)
  await dashboardPage.openCreateInstanceDialog()
}

export async function whenICreateInstancesFromDialog(page, count) {
  const createInstanceDialogPage = new CreateInstanceDialogPage(page)
  await createInstanceDialogPage.fillCount(count)
  await createInstanceDialogPage.submitCreate()
}

export async function whenICreateAdminInstanceWithCleanupDays(page, cleanupDays) {
  const createInstanceDialogPage = new CreateInstanceDialogPage(page)
  await createInstanceDialogPage.selectInstanceTypeAdmin()
  await createInstanceDialogPage.fillCount(1)
  await createInstanceDialogPage.fillCleanupDays(cleanupDays)

  const createRequest = createInstanceDialogPage.waitForCreateRequestWithAdminCleanupDays(cleanupDays)
  await createInstanceDialogPage.submitCreate()
  await createRequest
}

export async function thenISeeTutorialOverviewTableWithCount(page, expectedCount) {
  const tutorialOverviewPage = new TutorialOverviewPage(page)
  await tutorialOverviewPage.expectOverviewVisible()
  await tutorialOverviewPage.expectTableRowCount(expectedCount)
}

export async function thenEndpointColumnContainsHttpOrHttpsLinks(page) {
  const tutorialOverviewPage = new TutorialOverviewPage(page)
  const hrefs = await tutorialOverviewPage.getEndpointColumnHrefs()

  expect(hrefs.length).toBeGreaterThan(0)
  const hasHttps = hrefs.some((href) => href.startsWith('https://'))
  const hasHttp = hrefs.some((href) => href.startsWith('http://'))
  expect(hasHttps || hasHttp).toBeTruthy()
}

export async function whenIOpenWorkshopSelectorDialogFromLandingFab(page) {
  const landingPage = new LandingPage(page)
  await landingPage.openWorkshopSelectorDialogFromFab()
}

export async function whenISelectFirstWorkshopFromSelectorUsingKeyboard(page) {
  const landingPage = new LandingPage(page)
  const sessionFormDialogPage = new SessionFormDialogPage(page)

  await landingPage.selectFirstWorkshopWithKeyboard()
  await sessionFormDialogPage.expectVisible(15000)
}

export async function whenICreateSessionFromSessionDialog(page, sessionId, { poolCount = 1 } = {}) {
  const sessionFormDialogPage = new SessionFormDialogPage(page)
  const landingPage = new LandingPage(page)

  await sessionFormDialogPage.fillSessionConfiguration(sessionId, { poolCount, adminCount: 0 })
  await sessionFormDialogPage.submitAndWaitForCreateSession()
  await landingPage.waitForSessionVisible(sessionId, 30000)
}

export async function thenISeeTestTutorialSpotEnforcementMessage(page) {
  await expect(page.getByText('This is a test tutorial. New instances are always created as Spot.')).toBeVisible()
}

export async function whenICreateSpotInstanceWithMaxPrice(page, sessionId, spotMaxPrice) {
  const createInstanceDialogPage = new CreateInstanceDialogPage(page)
  await createInstanceDialogPage.fillSpotMaxPrice(spotMaxPrice)
  await createInstanceDialogPage.fillCount(1)

  const createRequest = createInstanceDialogPage.waitForCreateRequestWithSpotPricing(sessionId, spotMaxPrice)
  await createInstanceDialogPage.submitCreate()
  await createRequest
}

export async function thenISeeProductiveTutorialOnDemandMessage(page) {
  await expect(page.getByText('This is a productive tutorial. New instances are always created as On-Demand.')).toBeVisible()
}

export async function whenIGotoTutorialPage(page, workshopSlug, tutorialId) {
  const tutorialOverviewPage = new TutorialOverviewPage(page)
  await tutorialOverviewPage.gotoTutorialPath(`/tutorial/${workshopSlug}/${tutorialId}`)
  await tutorialOverviewPage.expectTableVisible()
}

export async function thenAllTutorialLinksUseHttp(page) {
  const tutorialOverviewPage = new TutorialOverviewPage(page)
  const hrefs = await tutorialOverviewPage.getAllTableAnchorHrefs()

  expect(hrefs.length).toBeGreaterThan(0)
  expect(hrefs.every((href) => href.startsWith('http://'))).toBeTruthy()
}
