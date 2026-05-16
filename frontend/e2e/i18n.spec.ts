import { expect, test } from '@playwright/test'

test.describe('国际化路由', () => {
  test('首次访问根路径时根据浏览器语言进入中文站点', async ({ browser }) => {
    const context = await browser.newContext({ locale: 'zh-CN' })
    const page = await context.newPage()
    await page.goto('/')

    await expect(page).toHaveURL(/\/zh(?:\/)?$/)
    await expect(page.locator('html')).toHaveAttribute('lang', 'zh')
    await expect(page.getByRole('banner').getByRole('link', { name: '免费开始' })).toBeVisible()
    await context.close()
  })

  test('首次访问根路径时国际用户默认进入英文站点', async ({ browser }) => {
    const context = await browser.newContext({ locale: 'en-US' })
    const page = await context.newPage()
    await page.goto('/')

    await expect(page).toHaveURL(/\/en(?:\/)?$/)
    await expect(page.locator('html')).toHaveAttribute('lang', 'en')
    await expect(page.getByRole('banner').getByRole('link', { name: 'Get started' })).toBeVisible()
    await context.close()
  })

  test('用户可以手动切换语言并持久化选择', async ({ page, context }) => {
    await page.goto('/zh')
    const localeButton = page.getByRole('button', { name: 'Switch to English' })
    await expect(localeButton).toHaveCSS('background-color', 'rgb(255, 255, 255)')
    await localeButton.click()

    await expect(page).toHaveURL(/\/en(?:\/)?$/)
    await expect(page.getByRole('banner').getByRole('link', { name: 'Get started' })).toBeVisible()

    const cookies = await context.cookies()
    expect(cookies.some((cookie) => cookie.name === 'NEXT_LOCALE' && cookie.value === 'en')).toBeTruthy()
  })
})
