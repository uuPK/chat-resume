/**
 * 认证流程端到端测试
 *
 * 覆盖：注册、登录、登出、表单校验
 */

import { test, expect } from '@playwright/test'
import { uniqueEmail, DEFAULT_PASSWORD, registerUser } from './helpers'

// ── 注册 ──────────────────────────────────────────────────────────────────

test.describe('注册', () => {
  test('页面包含 Google 登录入口并指向后端启动端点', async ({ page }) => {
    await page.goto('/zh/register')
    const googleLink = page.getByRole('link', { name: '使用谷歌登录' })
    await expect(googleLink).toBeVisible()
    await expect(googleLink).toHaveAttribute('href', 'http://localhost:8000/api/auth/google/login')
  })

  test('新用户注册成功后跳转到 dashboard', async ({ page }) => {
    const email = uniqueEmail('reg')
    await registerUser(page, email)
    await page.waitForURL('**/dashboard', { timeout: 12_000 })
    await expect(page).toHaveURL(/\/dashboard/)
  })

  test('重复邮箱注册显示错误提示', async ({ page }) => {
    const email = uniqueEmail('dup')
    // 第一次成功注册
    await registerUser(page, email)
    await page.waitForURL('**/dashboard', { timeout: 12_000 })

    // 退出：清 storage 模拟登出
    await page.evaluate(() => localStorage.clear())

    // 再次注册同一邮箱
    await registerUser(page, email)

    // 应停留在注册页（不跳转到 dashboard）
    await page.waitForTimeout(2000)
    expect(page.url()).not.toMatch(/\/dashboard/)
  })

  test('两次密码不一致时表单提交被阻止', async ({ page }) => {
    let registerRequests = 0
    await page.route('**/api/auth/register', async route => {
      registerRequests += 1
      await route.fulfill({ status: 500, body: 'unexpected register request' })
    })

    await page.goto('/zh/register')
    await page.fill('input[type="email"]', uniqueEmail('mismatch'))
    const pwInputs = page.locator('input[type="password"]')
    await pwInputs.nth(0).fill(DEFAULT_PASSWORD)
    await pwInputs.nth(1).fill('WrongConfirm123')
    await expect(page.getByText('两次输入的密码不一致')).toBeVisible()

    const checkbox = page.locator('input[type="checkbox"]').first()
    if (await checkbox.count() > 0) await checkbox.check()
    await page.click('button[type="submit"]')

    expect(registerRequests).toBe(0)
    expect(page.url()).not.toMatch(/\/dashboard/)

    await pwInputs.nth(1).fill(DEFAULT_PASSWORD)
    await expect(page.getByText('两次输入的密码不一致')).toBeHidden()
  })

  test('页面包含跳转到登录页的链接', async ({ page }) => {
    await page.goto('/zh/register')
    const loginLink = page.locator('a[href="/zh/login"]')
    await expect(loginLink).toBeVisible()
  })
})

// ── Google OAuth 入口 ─────────────────────────────────────────────────────

test.describe('Google OAuth 入口', () => {
  test('登录页包含 Google 登录入口并指向后端启动端点', async ({ page }) => {
    await page.goto('/zh/login')
    const googleLink = page.getByRole('link', { name: '使用谷歌登录' })
    await expect(googleLink).toBeVisible()
    await expect(googleLink).toHaveAttribute('href', 'http://localhost:8000/api/auth/google/login')
  })

  test('URL 中包含 oauth_error 时展示 Google 登录失败提示', async ({ page }) => {
    await page.goto('/zh/login?oauth_error=invalid_state')
    await expect(page.getByText('登录状态已失效，请重试')).toBeVisible()
  })
})

// ── 登录 ──────────────────────────────────────────────────────────────────

test.describe('登录', () => {
  let testEmail: string

  test.beforeAll(async ({ browser }) => {
    testEmail = uniqueEmail('login')
    const page = await browser.newPage()
    await registerUser(page, testEmail)
    await expect(page).toHaveURL(/\/dashboard/, { timeout: 12_000 })
    await page.close()
  })

  test('正确凭据登录后跳转到 dashboard', async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[type="email"]', testEmail)
    await page.fill('input[type="password"]', DEFAULT_PASSWORD)
    await page.click('button[type="submit"]')
    await page.waitForURL('**/dashboard', { timeout: 12_000 })
    await expect(page).toHaveURL(/\/dashboard/)
  })

  test('登录成功后使用完整页面导航进入 dashboard', async ({ page, context, baseURL }) => {
    const cookieDomain = new URL(baseURL || 'http://localhost:3000').hostname
    const dashboardRscRequests: string[] = []
    const user = {
      id: 909,
      email: testEmail,
      full_name: null,
      is_active: true,
      has_password: true,
      created_at: '2026-05-18T00:00:00Z',
    }

    await page.route('**/api/auth/me', async route => {
      await route.fulfill({ json: user })
    })
    await page.route('**/api/auth/login', async route => {
      await context.addCookies([
        {
          name: 'access_token',
          value: 'test-access-token',
          domain: cookieDomain,
          path: '/',
          httpOnly: true,
          sameSite: 'Lax',
        },
        {
          name: 'refresh_token',
          value: 'test-refresh-token',
          domain: cookieDomain,
          path: '/',
          httpOnly: true,
          sameSite: 'Lax',
        },
      ])
      await route.fulfill({
        json: {
          token_type: 'bearer',
          user,
        },
      })
    })
    page.on('request', request => {
      const url = request.url()
      if (url.includes('/dashboard') && url.includes('_rsc=')) {
        dashboardRscRequests.push(url)
      }
    })

    await page.goto('/zh/login')
    await page.fill('input[type="email"]', testEmail)
    await page.fill('input[type="password"]', DEFAULT_PASSWORD)
    await page.click('button[type="submit"]')

    await page.waitForURL(/\/zh\/dashboard/, { timeout: 12_000 })
    await expect(page).toHaveURL(/\/zh\/dashboard/)
    expect(dashboardRscRequests).toHaveLength(0)
  })

  test('错误密码停留在登录页', async ({ page }) => {
    const consoleErrors: string[] = []
    page.on('console', (message) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text())
      }
    })

    await page.goto('/login')
    await page.fill('input[type="email"]', testEmail)
    await page.fill('input[type="password"]', 'WrongPassword999')
    await page.click('button[type="submit"]')
    await page.waitForTimeout(2000)
    expect(page.url()).not.toMatch(/\/dashboard/)
    expect(consoleErrors.some(message => message.includes('Login error'))).toBe(false)
  })

  test('未填写邮箱不允许提交', async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[type="password"]', DEFAULT_PASSWORD)
    await page.click('button[type="submit"]')
    await page.waitForTimeout(500)
    expect(page.url()).not.toMatch(/\/dashboard/)
  })

  test('未登录访问 dashboard 会跳转到 login 或 register', async ({ page }) => {
    await page.context().clearCookies()
    // 先导航到一个普通页面才能访问 localStorage
    await page.goto('/login')
    await page.evaluate(() => localStorage.clear())
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/(login|register)/, { timeout: 10_000 })
  })

  test('未登录访问所有受保护页面都会被服务端重定向', async ({ page }) => {
    await page.context().clearCookies()
    await page.goto('/login')
    await page.evaluate(() => localStorage.clear())

    for (const protectedPath of ['/dashboard', '/resume/1/edit', '/interviews', '/resumes']) {
      await page.goto(protectedPath)
      await expect(page).toHaveURL(/\/login/, { timeout: 10_000 })
    }
  })

  test('伪造 access_token cookie 也不能进入受保护页面', async ({ page, baseURL }) => {
    const cookieDomain = new URL(baseURL || 'http://localhost:3000').hostname
    await page.context().addCookies([
      {
        name: 'access_token',
        value: 'not-a-real-token',
        domain: cookieDomain,
        path: '/',
        httpOnly: false,
        sameSite: 'Lax',
      },
    ])
    await page.goto('/dashboard')
    await expect(page).toHaveURL(/\/login/, { timeout: 10_000 })
  })

  test('刷新令牌失效时会调用登出接口清理 Cookie', async ({ page, baseURL }) => {
    const cookieDomain = new URL(baseURL || 'http://localhost:3000').hostname
    const logoutRequests: string[] = []
    const consoleErrors: string[] = []
    page.on('console', (message) => {
      if (message.type() === 'error') {
        consoleErrors.push(message.text())
      }
    })
    await page.context().addCookies([
      {
        name: 'refresh_token',
        value: 'stale-refresh-token',
        domain: cookieDomain,
        path: '/',
        httpOnly: true,
        sameSite: 'Lax',
      },
    ])
    await page.route('**/api/auth/me', async (route) => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Not authenticated' }),
      })
    })
    await page.route('**/api/auth/refresh', async (route) => {
      await route.fulfill({
        status: 401,
        contentType: 'application/json',
        body: JSON.stringify({ detail: 'Invalid refresh token' }),
      })
    })
    await page.route('**/api/auth/logout', async (route) => {
      logoutRequests.push(route.request().url())
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ message: 'Logged out' }),
      })
    })

    await page.goto('/dashboard')

    await expect.poll(() => logoutRequests.length).toBe(1)
    expect(consoleErrors.some(message => message.includes('Refresh session error') || message.includes('Auth check error'))).toBe(false)
  })

  test('页面包含跳转到注册页的链接', async ({ page }) => {
    await page.goto('/zh/login')
    const regLink = page.locator('a[href="/zh/register"]')
    await expect(regLink).toBeVisible()
  })
})
