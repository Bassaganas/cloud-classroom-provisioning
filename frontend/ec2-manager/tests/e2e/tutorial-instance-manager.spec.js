import { expect, test } from '@playwright/test'
import {
  cleanupTestTutorialSessions,
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
  whenIGotoTutorialDashboardAndCaptureExpectedCount,
  whenIGotoTutorialPage,
  whenIOpenCreateInstanceDialog,
  whenIOpenSessionDashboard,
  whenIOpenWorkshopSelectorDialogFromLandingFab,
  whenISelectFirstWorkshopFromSelectorUsingKeyboard,
} from './bdd/steps.js'

const isDeployedRun = !!process.env.E2E_BASE_URL

test.describe('Tutorial Instance Manager critical workflows', () => {
  test.afterAll(async () => {
    await cleanupTestTutorialSessions(['pw-'])
  })

  test('1) create tutorial instance and initial instances', async ({ page }) => {
    await givenIAmLoggedIn(page)

    const sessionId = `pw-init-${Date.now()}`
    await whenICreateTutorialSession(page, sessionId, { poolCount: 2, adminCount: 1, adminCleanupDays: 9 })

    await whenIOpenSessionDashboard(page, sessionId)
    await thenISeeInstancesCount(page, 3)
    await thenISeeTableRowCount(page, 3)
  })

  test('2) delete tutorial instances should delete all its instances', async ({ page }) => {
    await givenIAmLoggedIn(page)

    const sessionId = `pw-del-${Date.now()}`
    await whenICreateTutorialSession(page, sessionId, { poolCount: 2, adminCount: 1 })

    await whenIOpenSessionDashboard(page, sessionId)
    await whenIDeleteSessionAndAssociatedInstances(page, sessionId)
    await thenIAmBackOnLandingWithoutSession(page, sessionId)
  })

  test('3) create EC2 instances when tutorial instance already exists', async ({ page }) => {
    await givenIAmLoggedIn(page)

    const sessionId = `pw-grow-${Date.now()}`
    await whenICreateTutorialSession(page, sessionId, { poolCount: 1, adminCount: 0 })
    await whenIOpenSessionDashboard(page, sessionId)

    await thenISeeInstancesCount(page, 1)

    await whenIOpenCreateInstanceDialog(page)
    await whenICreateInstancesFromDialog(page, 2)

    await thenISeeInstancesCount(page, 3)
    await thenISeeTableRowCount(page, 3)
  })

  test('4) create admin instances with X days and change amount of days', async ({ page }) => {
    await givenIAmLoggedIn(page)

    const sessionId = `pw-admin-${Date.now()}`
    await whenICreateTutorialSession(page, sessionId, { poolCount: 1, adminCount: 0 })
    await whenIOpenSessionDashboard(page, sessionId)

    await whenIOpenCreateInstanceDialog(page)
    await whenICreateAdminInstanceWithCleanupDays(page, 10)

    await thenISeeInstancesCount(page, 2)
  })

  test('5) view tutorial dashboard with all tutorial instances', async ({ page }) => {
    test.skip(isDeployedRun, 'Depends on seeded tutorial IDs that are only guaranteed in mock mode')

    await givenIAmLoggedIn(page)

    const expectedCount = await whenIGotoTutorialDashboardAndCaptureExpectedCount(page, 'fellowship', 'tut1')
    await thenISeeTutorialOverviewTableWithCount(page, expectedCount)
    await thenEndpointColumnContainsHttpOrHttpsLinks(page)
  })

  test('11) testus patronus machines fallback to public IP links when HTTPS URL is unavailable', async ({ page }) => {
    test.skip(isDeployedRun, 'Depends on seeded tutorial IDs that are only guaranteed in mock mode')

    await givenIAmLoggedIn(page)

    await whenIGotoTutorialPage(page, 'testus_patronus', 'tutorial_wetest_athenes')
    await thenAllTutorialLinksUseHttp(page)
  })

  test('6) FAB button shows workshop selector dialog on Landing', async ({ page }) => {
    await givenIAmLoggedIn(page)
    await whenIOpenWorkshopSelectorDialogFromLandingFab(page)
  })

  test('7) FAB workshop selector creates session in selected workshop', async ({ page }) => {
    await givenIAmLoggedIn(page)

    const sessionId = `pw-fab-${Date.now()}`

    await whenIOpenWorkshopSelectorDialogFromLandingFab(page)
    await whenISelectFirstWorkshopFromSelectorUsingKeyboard(page)
    await whenICreateSessionFromSessionDialog(page, sessionId, { poolCount: 1 })
  })

  test('8) FAB button in tutorial dashboard creates new instances', async ({ page }) => {
    test.skip(isDeployedRun, 'Provisioning latency is variable on deployed environments')

    await givenIAmLoggedIn(page)

    const sessionId = `pw-fab-inst-${Date.now()}`
    await whenICreateTutorialSession(page, sessionId, { poolCount: 1, adminCount: 0 })

    await whenIOpenSessionDashboard(page, sessionId)
    await thenISeeInstancesCount(page, 1)

    await whenIOpenCreateInstanceDialog(page)
    await whenICreateInstancesFromDialog(page, 3)

    await thenISeeInstancesCount(page, 4)
    await thenISeeTableRowCount(page, 4)
  })

  test('9) test tutorial enforces Spot when creating instances', async ({ page }) => {
    test.skip(isDeployedRun, 'Provisioning latency is variable on deployed environments')

    await givenIAmLoggedIn(page)

    const sessionId = `pw-spot-${Date.now()}`
    await whenICreateTutorialSession(page, sessionId, { poolCount: 1, adminCount: 0, productiveTutorial: false })

    await whenIOpenSessionDashboard(page, sessionId)
    await thenISeeInstancesCount(page, 1)

    await whenIOpenCreateInstanceDialog(page)
    await thenISeeTestTutorialSpotEnforcementMessage(page)
    await whenICreateSpotInstanceWithMaxPrice(page, sessionId, '0.011')

    await thenISeeInstancesCount(page, /Instances \(2\)/, 20000)
  })

  test('10) productive tutorial enforces On-Demand when creating instances', async ({ page }) => {
    await givenIAmLoggedIn(page)

    const sessionId = `pw-prod-${Date.now()}`
    await whenICreateTutorialSession(page, sessionId, { poolCount: 1, adminCount: 0, productiveTutorial: true })

    await whenIOpenSessionDashboard(page, sessionId)
    await thenISeeInstancesCount(page, 1)

    await whenIOpenCreateInstanceDialog(page)
    await thenISeeProductiveTutorialOnDemandMessage(page)
    await whenICreateInstancesFromDialog(page, 1)

    await thenISeeInstancesCount(page, /Instances \(2\)/, 20000)
  })
})
