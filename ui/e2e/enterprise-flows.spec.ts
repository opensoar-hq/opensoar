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

test('updates an analyst role to playbook author', async ({ page }) => {
  await mockEnterpriseApi(page)
  await page.goto('/settings')
  await page.getByRole('button', { name: 'Analysts' }).click()

  const roleSelect = page.locator('select').nth(1)
  await roleSelect.selectOption('playbook_author')
  await expect(roleSelect).toHaveValue('playbook_author')
})

test('resets an analyst password from the analysts tab', async ({ page }) => {
  await mockEnterpriseApi(page)
  await page.goto('/settings')
  await page.getByRole('button', { name: 'Analysts' }).click()

  await page.getByRole('button', { name: 'Reset Password' }).first().click()
  await expect(page.getByRole('heading', { name: 'Reset Password' })).toBeVisible()
  await page.getByLabel('New Password').fill('new-password')
  await page.getByRole('button', { name: 'Reset', exact: true }).click()
})

test('changes the signed-in user password from the sidebar', async ({ page }) => {
  await mockEnterpriseApi(page)
  await page.goto('/settings')

  await page.getByRole('button', { name: 'Change password' }).click()
  await expect(page.getByRole('heading', { name: 'Change Password' })).toBeVisible()
  await page.getByLabel('Current Password').fill('old-password')
  await page.getByLabel('New Password').fill('new-password')
  await page.getByRole('button', { name: 'Save' }).click()
})

test('selects a workspace from the sidebar switcher', async ({ page }) => {
  await mockEnterpriseApi(page)
  await page.goto('/settings')

  await page.getByLabel('Workspace').selectOption('tenant-1')
  await expect(page.getByLabel('Workspace')).toHaveValue('tenant-1')
})

test('applies workspace selection to incidents and runs pages', async ({ page }) => {
  await mockEnterpriseApi(page)
  await page.goto('/settings')
  await page.getByLabel('Workspace').selectOption('tenant-1')

  await page.goto('/incidents')
  await expect(page.getByText('Northwind Workspace Incident')).toBeVisible()
  await expect(page.getByText('Global Incident')).toHaveCount(0)

  await page.goto('/runs')
  await expect(page.getByRole('button', { name: /Northwind Playbook/ })).toBeVisible()
  await expect(page.getByText('Global Playbook')).toHaveCount(0)
})

test('assigns ownership to a global playbook', async ({ page }) => {
  await mockEnterpriseApi(page)
  await page.goto('/playbooks')

  await expect(page.getByText('Global Playbook')).toBeVisible()
  await expect(page.getByText('Execution order: 20')).toBeVisible()
  await page.getByLabel('Assign owner').first().selectOption('northwind')
  await expect(page.getByText('Owner: northwind')).toBeVisible()
})

test('shows run sequence position on the runs page', async ({ page }) => {
  await mockEnterpriseApi(page)
  await page.goto('/runs')

  await expect(page.getByText('1/2')).toBeVisible()
  await expect(page.getByText('2/2')).toBeVisible()
})

test('assigns ownership to a global integration and shows migration queue', async ({ page }) => {
  await mockEnterpriseApi(page)
  await page.goto('/settings')

  await expect(page.getByText('Global Slack')).toBeVisible()
  await page.getByLabel('Assign owner').first().selectOption('northwind')
  await expect(page.getByText('owner: northwind')).toBeVisible()

  await page.getByRole('button', { name: 'Enterprise' }).click()
  await expect(page.getByRole('heading', { name: 'Global Resource Migration' })).toBeVisible()
})

test('manages incident collaboration workflow from the incident detail page', async ({ page }) => {
  await mockEnterpriseApi(page)
  await page.goto('/incidents/incident-1')

  await expect(page.getByRole('heading', { name: 'Northwind Workspace Incident' })).toBeVisible()

  await page.getByRole('button', { name: 'Assign to me' }).click()
  await expect(page.getByRole('button', { name: 'Reassign' })).toBeVisible()

  await page.getByPlaceholder('Add a comment...').fill('Need malware triage before handoff')
  await page.getByRole('button', { name: 'Comment' }).click()
  await expect(page.getByText('Need malware triage before handoff')).toBeVisible()

  await page.getByPlaceholder('Observable value').fill('198.51.100.23')
  await page.getByRole('button', { name: 'Add' }).click()
  await expect(page.getByText('ip:198.51.100.23', { exact: true })).toBeVisible()
})

test('creates an incident from a correlation suggestion', async ({ page }) => {
  await mockEnterpriseApi(page)
  await page.goto('/incidents')

  await expect(page.getByRole('heading', { name: 'Incidents' })).toBeVisible()
  await expect(page.getByText('Correlation Suggestions')).toBeVisible()
  await expect(page.getByText('203.0.113.42', { exact: true })).toBeVisible()

  await page.getByRole('button', { name: 'Create Incident' }).click()
  await expect(page).toHaveURL(/\/incidents\/incident-/)
  await expect(page.getByRole('heading', { name: 'Correlated activity from 203.0.113.42' })).toBeVisible()
  await expect(page.getByText('Northwind suspicious login', { exact: true })).toBeVisible()
})

test('tenant admin only sees enterprise settings tab', async ({ page }) => {
  await mockEnterpriseApi(page, {
    analyst: {
      id: 'tenant-admin-1',
      username: 'tenantadmin',
      display_name: 'Tenant Admin',
      email: 'tenantadmin@example.com',
      is_active: true,
      has_local_password: true,
      role: 'tenant_admin',
      created_at: '2026-04-04T00:00:00.000Z',
    },
  })
  await page.goto('/settings')

  await expect(page.getByRole('button', { name: 'Enterprise' })).toBeVisible()
  await expect(page.getByRole('button', { name: 'Integrations' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'API Keys' })).toHaveCount(0)
  await expect(page.getByRole('button', { name: 'Analysts' })).toHaveCount(0)
  await expect(page.getByRole('heading', { name: 'Tenants' })).toBeVisible()
  await expect(page.getByText('Provider management restricted')).toBeVisible()
})
