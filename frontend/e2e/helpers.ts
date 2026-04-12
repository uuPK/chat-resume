/**
 * 测试辅助工具
 *
 * 封装测试中常用的注册/登录/初始化操作，避免每个 spec 文件重复写相同逻辑。
 */

import { Page } from '@playwright/test'

/** 生成不重复的测试邮箱（基于时间戳 + 随机数） */
export function uniqueEmail(prefix = 'e2e'): string {
  return `${prefix}_${Date.now()}_${Math.floor(Math.random() * 9999)}@test.example`
}

export const DEFAULT_PASSWORD = 'Test@12345'

/**
 * 通过 UI 注册新用户。
 * 填写：姓名、邮箱、密码×2、服务条款复选框，然后提交。
 * 注意：不在此函数内等待跳转，由调用方负责。
 */
export async function registerUser(page: Page, email: string, password = DEFAULT_PASSWORD) {
  await page.goto('/register')
  await page.fill('input[placeholder="请输入您的姓名"]', '测试用户')
  await page.fill('input[type="email"]', email)
  const pwInputs = page.locator('input[type="password"]')
  await pwInputs.nth(0).fill(password)
  await pwInputs.nth(1).fill(password)
  // 勾选服务条款复选框
  const checkbox = page.locator('input[type="checkbox"]').first()
  if (await checkbox.count() > 0) {
    await checkbox.check()
  }
  await page.click('button[type="submit"]')
}

/** 通过 UI 登录，等待跳转到 dashboard */
export async function loginUser(page: Page, email: string, password = DEFAULT_PASSWORD) {
  await page.goto('/login')
  await page.fill('input[type="email"]', email)
  await page.fill('input[type="password"]', password)
  await page.click('button[type="submit"]')
  await page.waitForURL('**/dashboard', { timeout: 10_000 })
}

/** 注册 → 等待跳转 → 返回 email */
export async function registerAndLogin(page: Page, prefix = 'e2e'): Promise<string> {
  const email = uniqueEmail(prefix)
  await registerUser(page, email)
  await page.waitForURL('**/dashboard', { timeout: 10_000 })
  return email
}
