// 覆盖前端 proxy 的生产域名入口规则。
import { expect, test } from '@playwright/test'

test.describe('生产域名规范化', () => {
  test('旧 Vercel 域名会跳转到正式域名并保留路径查询', async ({ request }) => {
    const response = await request.get('/zh/login?next=%2Fdashboard', {
      headers: {
        host: 'chatresu.vercel.app',
        'x-forwarded-host': 'chatresu.vercel.app',
        'x-forwarded-proto': 'https',
      },
      maxRedirects: 0,
    })

    expect(response.status()).toBe(308)
    expect(response.headers()['location']).toBe(
      'https://www.chatresume.tech/zh/login?next=%2Fdashboard'
    )
  })

  test('裸域会跳转到正式 www 域名', async ({ request }) => {
    const response = await request.get('/zh/dashboard', {
      headers: {
        host: 'chatresume.tech',
        'x-forwarded-host': 'chatresume.tech',
        'x-forwarded-proto': 'https',
      },
      maxRedirects: 0,
    })

    expect(response.status()).toBe(308)
    expect(response.headers()['location']).toBe('https://www.chatresume.tech/zh/dashboard')
  })
})
