/**
 * 认证流程端到端测试
 *
 * 覆盖：注册、登录、登出、表单校验
 */

import { test, expect } from '@playwright/test'
import { uniqueEmail, DEFAULT_PASSWORD, registerUser } from './helpers'

// ── 注册 ──────────────────────────────────────────────────────────────────

test.describe('注册', () => {
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
    await page.goto('/register')
    await page.fill('input[placeholder="请输入您的姓名"]', '不一致')
    await page.fill('input[type="email"]', uniqueEmail('mismatch'))
    const pwInputs = page.locator('input[type="password"]')
    await pwInputs.nth(0).fill(DEFAULT_PASSWORD)
    await pwInputs.nth(1).fill('WrongConfirm123')
    const checkbox = page.locator('input[type="checkbox"]').first()
    if (await checkbox.count() > 0) await checkbox.check()
    await page.click('button[type="submit"]')

    await page.waitForTimeout(1000)
    expect(page.url()).not.toMatch(/\/dashboard/)
  })

  test('页面包含跳转到登录页的链接', async ({ page }) => {
    await page.goto('/register')
    const loginLink = page.locator('a[href="/login"]')
    await expect(loginLink).toBeVisible()
  })
})

// ── 登录 ──────────────────────────────────────────────────────────────────

test.describe('登录', () => {
  let testEmail: string

  test.beforeAll(async ({ browser }) => {
    testEmail = uniqueEmail('login')
    const page = await browser.newPage()
    await registerUser(page, testEmail)
    await page.waitForURL('**/dashboard', { timeout: 12_000 })
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

  test('错误密码停留在登录页', async ({ page }) => {
    await page.goto('/login')
    await page.fill('input[type="email"]', testEmail)
    await page.fill('input[type="password"]', 'WrongPassword999')
    await page.click('button[type="submit"]')
    await page.waitForTimeout(2000)
    expect(page.url()).not.toMatch(/\/dashboard/)
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
    await page.waitForURL(/\/(login|register)/, { timeout: 10_000 })
    expect(page.url()).toMatch(/\/(login|register)/)
  })

  test('未登录访问所有受保护页面都会被服务端重定向', async ({ page }) => {
    await page.context().clearCookies()
    await page.goto('/login')
    await page.evaluate(() => localStorage.clear())

    for (const protectedPath of ['/dashboard', '/resume/1/edit', '/interviews', '/resumes']) {
      await page.goto(protectedPath)
      await page.waitForURL(/\/login/, { timeout: 10_000 })
      expect(page.url()).toMatch(/\/login/)
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
    await page.waitForURL(/\/login/, { timeout: 10_000 })
    expect(page.url()).toMatch(/\/login/)
  })

  test('页面包含跳转到注册页的链接', async ({ page }) => {
    await page.goto('/login')
    const regLink = page.locator('a[href="/register"]')
    await expect(regLink).toBeVisible()
  })
})
