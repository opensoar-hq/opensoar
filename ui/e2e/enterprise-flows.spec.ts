import { expect, test, type Page } from '@playwright/test'

import { mockEnterpriseApi } from './support/mockEnterpriseApi'

async function openEnterpriseSettings(page: Page): Promise<void> {
  await mockEnterpriseApi(page)
  await page.goto('/settings')
  await page.getByRole('button', { name: 'Enterprise' }).click()
  await expect(page.getByRole('heading', { name: 'Tenants' })).toBeVisible()
}

test('shows external provider login for enterprise auth', async ({ page }) => {
  await mockEnterpriseApi(page, {
    authenticated: false,
    analyst: null,
    authCapabilities: {
      local_login_enabled: false,
      local_registration_enabled: false,
      providers: [
        {
          id: 'provider-okta',
          name: 'Okta Workforce',
          type: 'oidc',
          login_url: 'https://login.example.com/auth',
        },
      ],
    },
  })
  await page.route('https://login.example.com/auth', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'text/html',
      body: '<html><body>okta</body></html>',
    })
  })

  await page.goto('/login')

  await expect(page.getByRole('button', { name: 'Continue with Okta Workforce' })).toBeVisible()
  await expect(page.getByLabel('Username')).toHaveCount(0)

  await page.getByRole('button', { name: 'Continue with Okta Workforce' }).click()
  await page.waitForURL('https://login.example.com/auth')
})

test('creates a tenant from enterprise settings', async ({ page }) => {
  await openEnterpriseSettings(page)

  await page.getByRole('button', { name: 'Add Tenant' }).click()
  await expect(page.getByRole('heading', { name: 'Create Tenant' })).toBeVisible()

  await page.getByLabel('Name').fill('Acme Managed Defense')
  await page.getByLabel('Slug').fill('acme-managed-defense')
  await page.getByLabel('Legacy Partner Key').fill('acme-corp')
  await page.getByLabel('Partner Aliases').fill('acme, acme-soc')
  await page.getByRole('button', { name: 'Create' }).click()

  await expect(page.getByText('Acme Managed Defense')).toBeVisible()
  await expect(page.getByText('acme-managed-defense')).toBeVisible()
})

test('creates an OIDC provider from enterprise settings', async ({ page }) => {
  await openEnterpriseSettings(page)

  await page.getByRole('button', { name: 'Add Provider' }).click()
  await expect(page.getByRole('heading', { name: 'Create OIDC Provider' })).toBeVisible()

  await page.getByLabel('Name').fill('Okta Workforce')
  await page.getByLabel('Issuer').fill('https://login.example.com')
  await page.getByLabel('Client ID').fill('okta-client')
  await page.getByLabel('Client Secret').fill('top-secret')
  await page.getByLabel('Authorize URL').fill('https://login.example.com/oauth2/v1/authorize')
  await page.getByLabel('Token URL').fill('https://login.example.com/oauth2/v1/token')
  await page.getByLabel('Userinfo URL').fill('https://login.example.com/oauth2/v1/userinfo')
  await page.getByLabel('JWKS URI').fill('https://login.example.com/oauth2/v1/keys')
  await page.getByLabel('Scope').fill('openid profile email groups')
  await page.getByLabel('Extra Config (JSON)').fill('{"prompt":"login"}')
  await page.getByRole('button', { name: 'Create' }).click()

  await expect(page.getByText('Okta Workforce')).toBeVisible()
  await expect(page.getByText('https://login.example.com')).toBeVisible()
})

test('updates scoped API key ownership from enterprise settings', async ({ page }) => {
  await openEnterpriseSettings(page)

  await page.getByRole('button', { name: 'Manage Scope' }).click()
  await expect(page.getByRole('heading', { name: 'Manage Key Scope' })).toBeVisible()

  await page.getByLabel('Scopes').fill('alerts:read, webhooks:ingest')
  await page.getByLabel('Tenant').selectOption({ label: 'Northwind Operations' })
  await page.getByRole('button', { name: 'Save', exact: true }).click()

  await page.getByRole('button', { name: 'Manage Scope' }).click()
  await expect(page.getByLabel('Scopes')).toHaveValue('alerts:read, webhooks:ingest')
  await expect(page.getByLabel('Tenant')).toHaveValue('tenant-1')
})

test('creates and runs a report schedule from enterprise settings', async ({ page }) => {
  await openEnterpriseSettings(page)

  await page.getByRole('button', { name: 'Add Schedule' }).click()
  await expect(page.getByRole('heading', { name: 'Create Report Schedule' })).toBeVisible()

  await page.getByLabel('Report Type').selectOption('sla_compliance')
  await page.getByLabel('Format').selectOption('pdf')
  await page.getByLabel('Cadence').selectOption('daily')
  await page.getByLabel('Tenant').selectOption({ label: 'Northwind Operations' })
  await page.getByLabel('Destination Email').fill('soc@example.com')
  await page.getByLabel('Config (JSON)').fill('{"hour":6}')
  await page.getByRole('button', { name: 'Create' }).click()

  await expect(page.getByText('sla_compliance · pdf')).toBeVisible()
  await expect(page.getByText('daily · soc@example.com')).toBeVisible()

  await page.getByTitle('Run now').click()
  await expect(page.getByText('last: success')).toBeVisible()
})

test('updates retention policy from enterprise settings', async ({ page }) => {
  await openEnterpriseSettings(page)

  await expect(page.getByRole('heading', { name: 'Data Retention' })).toBeVisible()
  await page.getByLabel('Audit Log Retention (Days)').fill('30')
  await page.getByLabel('Report Run Metadata Retention (Days)').fill('14')
  await page.getByLabel('Notes').fill('Short retention for staging')
  await page.getByLabel('Automatically enforce on the background worker').check()
  await page.getByRole('button', { name: 'Save Retention Policy' }).click()
  await page.getByRole('button', { name: 'Run Enforcement Now' }).click()

  await expect(page.getByText(/Last enforced/)).toBeVisible()
})
