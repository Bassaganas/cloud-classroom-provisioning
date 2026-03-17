import { expect } from '@playwright/test'
import { LoginPage } from '../pom/login.page.js'
import { LandingPage } from '../pom/landing.page.js'
import { SessionFormDialogPage } from '../pom/session-form-dialog.page.js'
import { DashboardPage } from '../pom/dashboard.page.js'
import { CreateInstanceDialogPage } from '../pom/create-instance-dialog.page.js'
import { TutorialOverviewPage } from '../pom/tutorial-overview.page.js'
import { WorkshopOverviewPage } from '../pom/workshop-overview.page.js'

const PASSWORD = 'test123'

function toNumber(value) {
  if (value === null || value === undefined) return null
  const numeric = Number(value)
  return Number.isFinite(numeric) ? numeric : null
}

function formatUsd(value, decimals = 2) {
  const numeric = toNumber(value)
  if (numeric === null) return '-'
  return `$${numeric.toFixed(decimals)}`
}

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

export async function whenIGotoTutorialDashboardAndCaptureExpectedCount(page, workshopSlug, tutorialId) {
  const tutorialOverviewPage = new TutorialOverviewPage(page)
  await tutorialOverviewPage.gotoTutorialPath(`/tutorial/${workshopSlug}/${tutorialId}`)
  await tutorialOverviewPage.expectTableVisible()
  
  // Wait for the API response and extract instance count
  const sessionResponse = await tutorialOverviewPage.waitForTutorialSessionResponse(tutorialId)
  const instances = sessionResponse.instances || []
  return instances.length
}

export async function thenAllTutorialLinksUseHttp(page) {
  const tutorialOverviewPage = new TutorialOverviewPage(page)
  const hrefs = await tutorialOverviewPage.getAllTableAnchorHrefs()

  expect(hrefs.length).toBeGreaterThan(0)
  expect(hrefs.every((href) => href.startsWith('http://'))).toBeTruthy()
}

export async function whenIRequestInstancesApiWithActualCosts(workshop, costSourceMode = null) {
  const query = new URLSearchParams({
    password: PASSWORD,
    workshop,
    include_actual_costs: 'true',
  })
  
  if (costSourceMode) {
    query.append('cost_source_mode', costSourceMode)
  }

  const response = await fetch(`http://127.0.0.1:3001/api/list?${query.toString()}`)
  const payload = await response.json()
  return { status: response.status, payload }
}

export async function whenIRequestTutorialSessionsApiCostsForAllWorkshops() {
  const templatesResponse = await fetch(`http://127.0.0.1:3001/api/templates?password=${PASSWORD}`)
  const templatesPayload = await templatesResponse.json()
  const workshopNames = Object.keys(templatesPayload.templates || {})

  const sessionsByWorkshop = {}
  let totalEstimated = 0

  for (const workshop of workshopNames) {
    const response = await fetch(
      `http://127.0.0.1:3001/api/tutorial_sessions?password=${PASSWORD}&workshop=${encodeURIComponent(workshop)}`
    )
    const payload = await response.json()
    const sessions = payload.sessions || []
    sessionsByWorkshop[workshop] = sessions

    sessions.forEach((session) => {
      totalEstimated += Number(session.aggregated_estimated_cost_usd || 0)
    })
  }

  return {
    sessionsByWorkshop,
    totalEstimated: Number(totalEstimated.toFixed(2))
  }
}

export async function thenISeeActualCostFieldsInListResponse(result) {
  expect(result.status).toBe(200)
  expect(result.payload.success).toBeTruthy()
  expect(result.payload).toHaveProperty('actual_total_usd')
  expect(result.payload).toHaveProperty('actual_data_source')
  expect(Array.isArray(result.payload.instances)).toBeTruthy()
}

export async function thenISeeEstimatedAndActualFieldsPerInstance(result) {
  const items = result.payload.instances || []
  if (items.length === 0) return

  items.forEach((instance) => {
    expect(instance).toHaveProperty('hourly_rate_estimate_usd')
    expect(instance).toHaveProperty('estimated_runtime_hours')
    expect(instance).toHaveProperty('estimated_cost_usd')
    expect(instance).toHaveProperty('estimated_cost_24h_usd')
    expect(instance).toHaveProperty('actual_cost_usd')
  })
}

export async function whenIGotoWorkshopPage(page, workshop) {
  const workshopOverviewPage = new WorkshopOverviewPage(page)
  await workshopOverviewPage.gotoWorkshopPath(workshop)
  await workshopOverviewPage.expectDashboardVisible()
}

export async function thenISeeWorkshopCostCards(page) {
  const workshopOverviewPage = new WorkshopOverviewPage(page)
  await workshopOverviewPage.expectCostCardsVisible()
}

export async function thenISeeMonthlyExpectedCost(page) {
  const workshopOverviewPage = new WorkshopOverviewPage(page)
  await workshopOverviewPage.expectMonthlyEstimateHasCurrencyValue()
}

export async function thenISeeWorkshopCostColumns(page) {
  const workshopOverviewPage = new WorkshopOverviewPage(page)
  await workshopOverviewPage.expectCostColumnsVisible()
}

export async function thenWorkshopCostCardsMatchApiTotals(page, listApiResult, workshop) {
  expect(listApiResult.status).toBe(200)
  const instances = (listApiResult.payload.instances || []).filter(
    (instance) => (instance.workshop === workshop || !instance.workshop) && instance.state !== 'terminated'
  )

  const estimatedHourly = instances.reduce((sum, item) => sum + (Number(item.hourly_rate_estimate_usd) || 0), 0)
  const estimatedAccrued = instances.reduce((sum, item) => sum + (Number(item.estimated_cost_usd) || 0), 0)
  const estimated24h = instances.reduce((sum, item) => sum + (Number(item.estimated_cost_24h_usd) || 0), 0)
  const estimatedMonthly = estimated24h * 30

  const actualValues = instances
    .map((item) => toNumber(item.actual_cost_usd))
    .filter((item) => item !== null)
  const actualTotal = actualValues.length > 0
    ? actualValues.reduce((sum, value) => sum + value, 0)
    : toNumber(listApiResult.payload.actual_total_usd)

  const workshopOverviewPage = new WorkshopOverviewPage(page)
  await workshopOverviewPage.expectCostCardValue('Hourly Burn (Est.)', formatUsd(estimatedHourly))
  await workshopOverviewPage.expectCostCardValue('Accrued (Est.)', formatUsd(estimatedAccrued))
  await workshopOverviewPage.expectCostCardValue('Next 24h (Est.)', formatUsd(estimated24h))
  await workshopOverviewPage.expectCostCardValue('Monthly (Est.)', formatUsd(estimatedMonthly))
  await workshopOverviewPage.expectCostCardValue(/Actual \(Billing\)/, formatUsd(actualTotal))
}

export async function thenLandingSessionCostsMatchApi(page, sessionsApiResult) {
  const landingPage = new LandingPage(page)

  await landingPage.expectSessionCostsSummaryText(formatUsd(sessionsApiResult.totalEstimated))

  const allSessions = Object.values(sessionsApiResult.sessionsByWorkshop).flat()
  for (const session of allSessions) {
    const expected = formatUsd(Number(session.aggregated_estimated_cost_usd || 0))
    await landingPage.expectSessionCostChipText(session.session_id, expected)
  }
}

export async function thenISeeActualDataSourceIsUnavailable(result) {
  expect(result.status).toBe(200)
  expect(result.payload.success).toBeTruthy()
  expect(result.payload.actual_data_source).toBe('unavailable')
}

export async function thenISeeEstimatedCostsStillPresent(result) {
  expect(result.payload).toHaveProperty('instances')
  const items = result.payload.instances || []
  if (items.length === 0) return

  items.forEach((instance) => {
    expect(instance).toHaveProperty('hourly_rate_estimate_usd')
    expect(instance).toHaveProperty('estimated_runtime_hours')
    expect(instance).toHaveProperty('estimated_cost_usd')
    expect(instance).toHaveProperty('estimated_cost_24h_usd')
  })
}
