import { expect, test } from '@playwright/test'

function encodePrintPayload(payload: Record<string, unknown>) {
  return Buffer.from(JSON.stringify(payload)).toString('base64url')
}

test.describe('简历模板样式', () => {
  test('绿色页眉模板按截图风格渲染页眉和分隔标题', async ({ page }) => {
    const payload = encodePrintPayload({
      template: 'emerald',
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
        work_experience: [
          {
            company: '世优科技',
            position: 'AI Agent开发工程师',
            duration: '2025/08 - 2025/11',
            highlights: [{ text: '参与设计并实现了 MoYi AI 的核心架构' }],
          },
        ],
        projects: [],
      },
    })

    await page.goto(`/resume/print?data=${payload}`)

    const pageSheet = page.locator('.resume-page.resume-template-emerald')
    await expect(pageSheet).toBeVisible()

    const header = pageSheet.locator('.resume-emerald-personal')
    await expect(header).toBeVisible()
    await expect(header).toHaveCSS('background-color', 'rgb(5, 150, 105)')
    await expect(header).toContainText('psx849261680@gmail.com')
    await expect(header).toContainText('个人网站')

    const educationHeading = pageSheet.getByRole('heading', { name: '教育经历' })
    await expect(educationHeading).toHaveCSS('text-align', 'center')
    await expect(educationHeading).toHaveCSS('border-bottom-width', '0px')
  })

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
