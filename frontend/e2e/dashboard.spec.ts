/**
 * Dashboard 端到端测试
 *
 * 覆盖：仪表板展示、新建简历跳转、编辑后返回列表
 */

import { test, expect, Page } from '@playwright/test'
import { uniqueEmail, registerUser } from './helpers'

/** 注册并等待跳转到 dashboard */
async function loginAs(page: Page, email: string) {
  await registerUser(page, email)
  await page.waitForURL('**/dashboard', { timeout: 12_000 })
}

/** 等待简历列表加载结束，避免在骨架态或 loading 态下断言。 */
async function waitForResumeListLoaded(page: Page) {
  await page.locator('text=加载简历列表...').waitFor({ state: 'detached', timeout: 10_000 }).catch(() => {})
}

/** 从仪表板创建空白简历，并返回新建后的简历 ID 供后续断言使用。 */
async function createResumeFromDashboard(page: Page, email: string): Promise<string> {
  await loginAs(page, email)
  await page.getByRole('button', { name: '新建简历' }).click()
  await page.waitForURL(/\/resume\/\d+\/edit/, { timeout: 12_000 })
  const resumeId = page.url().match(/\/resume\/(\d+)\/edit/)?.[1]
  expect(resumeId, '点击新建简历后应进入编辑页').toBeTruthy()
  return resumeId as string
}

/** 填写岗位目标信息并等待自动保存，确保返回列表时卡片文案已经持久化。 */
async function fillJobApplicationAndWaitForSave(page: Page, company: string, title: string, jd: string) {
  const saveResponse = page.waitForResponse((response) => (
    response.request().method() === 'PUT'
    && /\/api\/resumes\/\d+$/.test(new URL(response.url()).pathname)
    && response.ok()
  ), { timeout: 12_000 })

  await page.getByPlaceholder('请输入目标公司名称').fill(company)
  await page.getByPlaceholder('请输入目标岗位名称').fill(title)
  await page.getByPlaceholder('请粘贴 JD 相关文字/图片').fill(jd)
  await saveResponse
}

// ── Dashboard 基础 ──────────────────────────────────────────────────────────

test.describe('Dashboard', () => {
  test('登录后显示仪表板页面', async ({ page }) => {
    await loginAs(page, uniqueEmail('dash'))
    await expect(page.getByRole('link', { name: '简历中心' })).toBeVisible()
    await expect(page.getByRole('button', { name: '上传简历' })).toBeVisible()
    await expect(page.getByRole('button', { name: '新建简历' })).toBeVisible()
  })

  test('没有简历时显示空状态提示', async ({ page }) => {
    await loginAs(page, uniqueEmail('empty'))
    await page.waitForSelector('.animate-spin', { state: 'detached', timeout: 8_000 }).catch(() => {})
    await expect(page.locator('body')).toContainText('开始优化你的第一份简历')
    await expect(page.locator('body')).not.toContainText('填写 JD')
    await expect(page.locator('body')).not.toContainText('Agent 分析')
    await expect(page.locator('body')).not.toContainText('确认 diff')
  })

  test('页面包含上传简历和新建简历按钮', async ({ page }) => {
    await loginAs(page, uniqueEmail('btn'))
    await expect(page.getByRole('button', { name: '上传简历' })).toBeVisible()
    await expect(page.getByRole('button', { name: '新建简历' })).toBeVisible()
  })
})

// ── 新建简历 ─────────────────────────────────────────────────────────────────

test.describe('新建简历', () => {
  test('点击新建简历后直接跳转到编辑页', async ({ page }) => {
    const resumeId = await createResumeFromDashboard(page, uniqueEmail('create'))
    await expect(page).toHaveURL(new RegExp(`/resume/${resumeId}/edit$`))
    await expect(page.getByText('简历创建成功！')).toBeVisible()
  })

  test('新建后的空白简历展示默认编辑态核心控件', async ({ page }) => {
    await createResumeFromDashboard(page, uniqueEmail('createblank'))
    await expect(page.getByPlaceholder('请输入目标公司名称')).toBeVisible()
    await expect(page.getByPlaceholder('请输入目标岗位名称')).toBeVisible()
    await expect(page.getByRole('button', { name: '布局设置' })).toBeVisible()
    await expect(page.getByRole('button', { name: '导出 PDF' })).toBeVisible()
    await expect(page.getByPlaceholder('输入消息...')).toBeVisible()
  })

  test('编辑页可以返回仪表板', async ({ page }) => {
    await createResumeFromDashboard(page, uniqueEmail('backdash'))
    await page.getByRole('link', { name: '返回仪表板' }).click()
    await page.waitForURL('**/dashboard', { timeout: 12_000 })
    await expect(page.getByRole('link', { name: '简历中心' })).toBeVisible()
    await expect(page.getByRole('button', { name: '新建简历' })).toBeVisible()
  })
})

// ── 简历列表操作 ──────────────────────────────────────────────────────────────

test.describe('简历列表', () => {
  test('编辑岗位信息后返回 dashboard，列表卡片展示目标公司和岗位', async ({ page }) => {
    const resumeId = await createResumeFromDashboard(page, uniqueEmail('listtest'))
    await fillJobApplicationAndWaitForSave(page, 'OpenAI', '前端工程师', '负责前端开发、性能优化和跨团队协作。')

    await page.getByRole('link', { name: '返回仪表板' }).click()
    await page.waitForURL('**/dashboard', { timeout: 12_000 })
    await waitForResumeListLoaded(page)

    const resumeCard = page.locator(`a[href="/zh/resume/${resumeId}/edit"]`).first()
    await expect(resumeCard).toBeVisible()
    await expect(page.locator('body')).toContainText('OpenAI · 前端工程师')
  })

  test('创建简历后列表卡片包含优化按钮，并可再次进入编辑页', async ({ page }) => {
    const resumeId = await createResumeFromDashboard(page, uniqueEmail('chatbtn'))
    await page.getByRole('link', { name: '返回仪表板' }).click()
    await page.waitForURL('**/dashboard', { timeout: 12_000 })
    await waitForResumeListLoaded(page)

    const editEntry = page.locator(`a[href="/zh/resume/${resumeId}/edit"]`).filter({ hasText: '优化' })
    await expect(editEntry).toBeVisible()
    await editEntry.click()
    await expect(page).toHaveURL(new RegExp(`/resume/${resumeId}/edit$`))
  })
})
