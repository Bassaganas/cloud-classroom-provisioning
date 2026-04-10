import { test } from '@playwright/test'

import {
  givenIAmLoggedIn,
  thenISeeEndpointLinkForInstance,
  whenIGotoTutorialPage,
} from './bdd/steps.js'

const isDeployedRun = !!process.env.E2E_BASE_URL

test.describe('Tutorial endpoint resolution', () => {
  test('prefers https_domain over legacy https_url when rendering endpoint links', async ({ page }) => {
    test.skip(isDeployedRun, 'Depends on deterministic mock tutorial data')

    await givenIAmLoggedIn(page)
    await whenIGotoTutorialPage(page, 'fellowship', 'tut1')
    await thenISeeEndpointLinkForInstance(
      page,
      'i-1234567890abcdef0',
      'fellowship-pool-0.fellowship.testingfantasy.com',
      'https://fellowship-pool-0.fellowship.testingfantasy.com'
    )
  })
})