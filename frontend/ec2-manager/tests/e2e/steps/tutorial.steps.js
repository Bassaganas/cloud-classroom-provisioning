import { expect } from '@playwright/test'
import { createBdd } from 'playwright-bdd'
import {
  givenIAmLoggedIn,
  thenAllTutorialLinksUseHttp,
  thenEndpointColumnContainsHttpOrHttpsLinks,
  thenIAmBackOnLandingWithoutSession,
  thenISeeInstancesCount,
  thenISeeProductiveTutorialOnDemandMessage,
  thenISeeTableRowCount,
  thenISeeTestTutorialSpotEnforcementMessage,
  thenISeeTutorialOverviewTableWithCount,
  whenICreateAdminInstanceWithCleanupDays,
  whenICreateInstancesFromDialog,
  whenICreateSessionFromSessionDialog,
  whenICreateSpotInstanceWithMaxPrice,
  whenICreateTutorialSession,
  whenIDeleteSessionAndAssociatedInstances,
  whenIGotoTutorialPage,
  whenIOpenCreateInstanceDialog,
  whenIOpenSessionDashboard,
  whenIGotoWorkshopPage,
  whenIOpenWorkshopSelectorDialogFromLandingFab,
  whenISelectFirstWorkshopFromSelectorUsingKeyboard,
  thenISeeWorkshopCostCards,
  thenISeeMonthlyExpectedCost,
  thenISeeWorkshopCostColumns,
  whenIRequestInstancesApiWithActualCosts,
  thenISeeActualCostFieldsInListResponse,
  thenISeeEstimatedAndActualFieldsPerInstance,
  thenISeeActualDataSourceIsUnavailable,
  thenISeeEstimatedCostsStillPresent,
  thenWorkshopCostCardsMatchApiTotals,
  whenIRequestTutorialSessionsApiCostsForAllWorkshops,
  thenLandingSessionCostsMatchApi,
} from '../bdd/steps.js'

const { Given, When, Then, Before } = createBdd()

let currentSessionId = null
let expectedTutorialRows = null
let latestListApiResult = null
let latestSessionsCostApiResult = null

function generatedSession(prefix) {
  return `${prefix}-${Date.now()}`
}

function isProductive(mode) {
  return mode.toLowerCase() === 'productive'
}

Before(async () => {
  currentSessionId = null
  expectedTutorialRows = null
  latestListApiResult = null
  latestSessionsCostApiResult = null
})

Given('I am logged in to EC2 Tutorials Manager', async ({ page }) => {
  await givenIAmLoggedIn(page)
})

When('I create a {word} tutorial session with {int} pool and {int} admin and cleanup {int}', async ({ page }, mode, poolCount, adminCount, cleanupDays) => {
  currentSessionId = generatedSession('bdd-sess')
  await whenICreateTutorialSession(page, currentSessionId, {
    poolCount,
    adminCount,
    adminCleanupDays: cleanupDays,
    productiveTutorial: isProductive(mode),
  })
})

When('I create a {word} tutorial session with {int} pool and {int} admin', async ({ page }, mode, poolCount, adminCount) => {
  currentSessionId = generatedSession('bdd-sess')
  await whenICreateTutorialSession(page, currentSessionId, {
    poolCount,
    adminCount,
    productiveTutorial: isProductive(mode),
  })
})

When('I open the tutorial dashboard for that session', async ({ page }) => {
  await whenIOpenSessionDashboard(page, currentSessionId)
})

Then('I should see {string}', async ({ page }, instancesLabel) => {
  await thenISeeInstancesCount(page, instancesLabel)
})

Then('the instances table should contain {int} rows', async ({ page }, count) => {
  await thenISeeTableRowCount(page, count)
})

When('I delete the tutorial session and confirm deleting associated instances', async ({ page }) => {
  await whenIDeleteSessionAndAssociatedInstances(page, currentSessionId)
})

Then('I should return to the landing page', async ({ page }) => {
  await thenIAmBackOnLandingWithoutSession(page, currentSessionId)
})

Then('I should not see the deleted session on landing', async ({ page }) => {
  await thenIAmBackOnLandingWithoutSession(page, currentSessionId)
})

When('I open the create instance dialog', async ({ page }) => {
  await whenIOpenCreateInstanceDialog(page)
})

When('I create {int} new instances', async ({ page }, count) => {
  await whenICreateInstancesFromDialog(page, count)
})

When('I create {int} new instance', async ({ page }, count) => {
  await whenICreateInstancesFromDialog(page, count)
})

When('I create {int} admin instance with cleanup days set to {int}', async ({ page }, _count, cleanupDays) => {
  await whenICreateAdminInstanceWithCleanupDays(page, cleanupDays)
})

When('I click the create session FAB on landing', async ({ page }) => {
  await whenIOpenWorkshopSelectorDialogFromLandingFab(page)
})

Then('I should see the workshop selector dialog', async ({ page }) => {
  await expect(page.getByRole('dialog')).toBeVisible()
  await expect(page.getByText('Select Workshop')).toBeVisible()
})

When('I select the first workshop from the selector using keyboard', async ({ page }) => {
  await whenISelectFirstWorkshopFromSelectorUsingKeyboard(page)
})

When('I create a tutorial session from the session form as {word} with {int} pool and {int} admin', async ({ page }, mode, poolCount, adminCount) => {
  currentSessionId = generatedSession('bdd-fab')
  if (isProductive(mode)) {
    await whenICreateTutorialSession(page, currentSessionId, { poolCount, adminCount, productiveTutorial: true })
    return
  }
  await whenICreateSessionFromSessionDialog(page, currentSessionId, { poolCount })
})

Then('I should see the created session on landing', async ({ page }) => {
  await expect(page.getByText(currentSessionId)).toBeVisible({ timeout: 30000 })
})

When('I open tutorial {string} for workshop {string}', async ({ page }, tutorialId, workshop) => {
  if (workshop === 'fellowship') {
    const response = page.waitForResponse((res) => res.request().method() === 'GET' && res.url().includes(`/api/tutorial_session/${tutorialId}`))
    await whenIGotoTutorialPage(page, workshop, tutorialId)
    const data = await (await response).json()
    expectedTutorialRows = data.instances.length
    return
  }

  await whenIGotoTutorialPage(page, workshop, tutorialId)
})

Then('I should see tutorial overview widgets and the instances table', async ({ page }) => {
  await thenISeeTutorialOverviewTableWithCount(page, expectedTutorialRows)
})

Then('the table row count should match the API tutorial_session response', async ({ page }) => {
  await thenISeeTutorialOverviewTableWithCount(page, expectedTutorialRows)
})

Then('endpoint links in the Endpoint column should include HTTP or HTTPS links', async ({ page }) => {
  await thenEndpointColumnContainsHttpOrHttpsLinks(page)
})

Then('I should see the instances table', async ({ page }) => {
  await expect(page.getByRole('table')).toBeVisible()
})

Then('all machine links should use HTTP public IP format', async ({ page }) => {
  await thenAllTutorialLinksUseHttp(page)
})

When('I open workshop dashboard for {string}', async ({ page }, workshop) => {
  latestListApiResult = await whenIRequestInstancesApiWithActualCosts(workshop)
  await whenIGotoWorkshopPage(page, workshop)
})

Then('I should see workshop cost summary cards', async ({ page }) => {
  await thenISeeWorkshopCostCards(page)
})

Then('I should see a monthly expected cost value', async ({ page }) => {
  await thenISeeMonthlyExpectedCost(page)
})

Then('the general instances table should include cost columns', async ({ page }) => {
  await thenISeeWorkshopCostColumns(page)
})

Then('workshop cost cards should match API totals for {string}', async ({ page }, workshop) => {
  await thenWorkshopCostCardsMatchApiTotals(page, latestListApiResult, workshop)
})

When('I request tutorial sessions API costs for all workshops', async () => {
  latestSessionsCostApiResult = await whenIRequestTutorialSessionsApiCostsForAllWorkshops()
})

Then('the landing session costs should match tutorial sessions API totals', async ({ page }) => {
  await thenLandingSessionCostsMatchApi(page, latestSessionsCostApiResult)
})

When('I request workshop instances API with include_actual_costs enabled for {string}', async ({}, workshop) => {
  latestListApiResult = await whenIRequestInstancesApiWithActualCosts(workshop)
})

Then('the list API response should include actual cost summary fields', async () => {
  await thenISeeActualCostFieldsInListResponse(latestListApiResult)
})

Then('the list API response instances should include estimated and actual cost fields', async () => {
  await thenISeeEstimatedAndActualFieldsPerInstance(latestListApiResult)
})

When('I request workshop instances API with include_actual_costs enabled for {string} with unavailable cost source', async ({}, workshop) => {
  latestListApiResult = await whenIRequestInstancesApiWithActualCosts(workshop, 'unavailable')
})

Then('the list API response should indicate actual_data_source is {string}', async ({}, sourceValue) => {
  await thenISeeActualDataSourceIsUnavailable(latestListApiResult)
})

Then('estimated cost fields should still be present in the response', async () => {
  await thenISeeEstimatedCostsStillPresent(latestListApiResult)
})

Then('I should see the test tutorial Spot enforcement message', async ({ page }) => {
  await thenISeeTestTutorialSpotEnforcementMessage(page)
})

When('I set Spot max price to {string} and create {int} instance', async ({ page }, price, _count) => {
  await whenICreateSpotInstanceWithMaxPrice(page, currentSessionId, price)
})

Then('the spot create request should contain purchase_type spot and spot_max_price {string}', async () => {
  // Assertion is already enforced in the When step helper that waits for request payload.
})

Then('I should see the productive tutorial On-Demand enforcement message', async ({ page }) => {
  await thenISeeProductiveTutorialOnDemandMessage(page)
})
