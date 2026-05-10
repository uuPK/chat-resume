import { expect, test } from '@playwright/test'

function encodePrintPayload(payload: Record<string, unknown>) {
  return Buffer.from(JSON.stringify(payload)).toString('base64url')
}

test.describe('简历模板样式', () => {
  test('正式黑白模板按截图风格渲染联系信息和页面样式', async ({ page }) => {
    const payload = encodePrintPayload({
      template: 'formal',
      content: {
        personal_info: {
          name: '彭世雄',
          position: 'AI Agent开发工程师',
          phone: '18980162782',
          email: 'psx849261680@gmail.com',
          github: 'https://github.com/849261680',
          website: 'https://psx1.vercel.app',
        },
        education: [
          {
            school: '东北大学',
            degree: '本科',
            major: '信息安全',
            duration: '2019–2023',
          },
        ],
        skills: [
          {
            category: '编程语言',
            items: ['Python'],
          },
        ],
        work_experience: [],
        projects: [],
      },
    })

    await page.goto(`/resume/print?data=${payload}`)

    const pageSheet = page.locator('.resume-page.resume-template-formal')
    await expect(pageSheet).toBeVisible()
    await expect(page.getByRole('heading', { name: '彭世雄' })).toHaveCSS('text-align', 'left')
    await expect(pageSheet).toContainText('GitHub: https://github.com/849261680')
    await expect(pageSheet).toContainText('个人网站: https://psx1.vercel.app')
  })
})
