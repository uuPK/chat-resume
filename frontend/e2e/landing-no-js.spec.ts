import { expect, test } from '@playwright/test'

test.describe('Landing page no-JavaScript fallback', () => {
  test('shows landing content in server-rendered HTML before hydration', async ({ browser }) => {
    const context = await browser.newContext({
      javaScriptEnabled: false,
      locale: 'en-US',
    })
    const page = await context.newPage()

    await page.goto('/en')

    const html = await page.content()
    expect(html).toContain('Make every resume')
    expect(html).toContain('Get started')
    expect(html).not.toContain('style="opacity:0')

    await context.close()
  })
})
