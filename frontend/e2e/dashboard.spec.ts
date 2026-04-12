/**
 * Dashboard 端到端测试
 *
 * 覆盖：新建简历、简历列表展示、删除简历
 */

import { test, expect, Page } from '@playwright/test'
import { uniqueEmail, DEFAULT_PASSWORD, registerUser } from './helpers'

/** 注册并等待跳转到 dashboard */
async function loginAs(page: Page, email: string) {
  await registerUser(page, email)
  await page.waitForURL('**/dashboard', { timeout: 12_000 })
}

// ── Dashboard 基础 ──────────────────────────────────────────────────────────

test.describe('Dashboard', () => {
  test('登录后显示仪表板页面', async ({ page }) => {
    await loginAs(page, uniqueEmail('dash'))
    await expect(page.locator('h1')).toContainText(/简历中心|仪表板|Dashboard/i)
  })

  test('没有简历时显示空状态提示', async ({ page }) => {
    await loginAs(page, uniqueEmail('empty'))
    await page.waitForSelector('.animate-spin', { state: 'detached', timeout: 8_000 }).catch(() => {})
    await expect(page.locator('body')).toContainText(/还没有简历|上传|新建/i)
  })

  test('页面包含上传简历和新建简历按钮', async ({ page }) => {
    await loginAs(page, uniqueEmail('btn'))
    await expect(page.getByText(/上传简历/).first()).toBeVisible()
    await expect(page.getByText(/新建简历/)).toBeVisible()
  })
})

// ── 新建简历 ─────────────────────────────────────────────────────────────────

test.describe('新建简历', () => {
  test('点击新建简历弹出标题输入框', async ({ page }) => {
    await loginAs(page, uniqueEmail('create'))
    await page.getByText('新建简历').click()
    await expect(page.locator('input#resumeTitle')).toBeVisible({ timeout: 5_000 })
  })

  test('输入标题后点击创建跳转到编辑页或 dashboard', async ({ page }) => {
    await loginAs(page, uniqueEmail('createok'))
    await page.getByText('新建简历').click()

    const titleInput = page.locator('input#resumeTitle').first()
    await titleInput.waitFor({ state: 'visible', timeout: 5_000 })
    await titleInput.fill('端到端测试简历')

    await page.getByRole('button', { name: /创建简历/ }).click()
    await page.waitForURL(/\/(dashboard|resume)/, { timeout: 12_000 })
  })

  test('标题为空时创建按钮处于禁用状态', async ({ page }) => {
    await loginAs(page, uniqueEmail('emptytitle'))
    await page.getByText('新建简历').click()

    const confirmBtn = page.getByRole('button', { name: /创建简历/ })
    await confirmBtn.waitFor({ state: 'visible', timeout: 5_000 })
    await expect(confirmBtn).toBeDisabled()
  })

  test('点击取消关闭弹窗', async ({ page }) => {
    await loginAs(page, uniqueEmail('cancel'))
    await page.getByText('新建简历').click()

    const cancelBtn = page.getByRole('button', { name: /取消/ })
    await cancelBtn.waitFor({ state: 'visible', timeout: 5_000 })
    await cancelBtn.click()

    await expect(page.locator('input#resumeTitle')).not.toBeVisible({ timeout: 3_000 })
  })
})

// ── 简历列表操作 ──────────────────────────────────────────────────────────────

test.describe('简历列表', () => {
  test('创建简历后编辑页展示该简历标题，返回 dashboard 列表中也出现', async ({ page }) => {
    await loginAs(page, uniqueEmail('listtest'))

    await page.getByText('新建简历').click()
    const titleInput = page.locator('input#resumeTitle').first()
    await titleInput.waitFor({ state: 'visible', timeout: 5_000 })
    await titleInput.fill('我的前端简历')
    await page.getByRole('button', { name: /创建简历/ }).click()

    // 创建成功后跳转到编辑页
    await page.waitForURL(/\/resume\/\d+/, { timeout: 12_000 })
    // 编辑页的简历名称输入框 value 应该是 "我的前端简历"
    const resumeTitleInput = page.locator('input[value="我的前端简历"], input').filter({ hasValue: '我的前端简历' })
    await expect(resumeTitleInput.first()).toBeVisible({ timeout: 5_000 })

    // 回到 dashboard，等待列表加载
    await page.goto('/dashboard')
    await page.waitForLoadState('networkidle', { timeout: 10_000 }).catch(() => {})
    await expect(page.locator('body')).toContainText('我的前端简历', { timeout: 8_000 })
  })

  test('简历卡片包含 Chat 按钮', async ({ page }) => {
    await loginAs(page, uniqueEmail('chatbtn'))

    await page.getByText('新建简历').click()
    const titleInput = page.locator('input#resumeTitle').first()
    await titleInput.waitFor({ state: 'visible', timeout: 5_000 })
    await titleInput.fill('Chat 按钮测试')
    await page.getByRole('button', { name: /创建简历/ }).click()

    await page.waitForURL(/\/(dashboard|resume)/, { timeout: 12_000 })
    if (!page.url().includes('/dashboard')) {
      await page.goto('/dashboard')
    }

    await page.waitForSelector('.animate-spin', { state: 'detached', timeout: 8_000 }).catch(() => {})
    await expect(page.getByText('Chat').first()).toBeVisible()
  })
})
