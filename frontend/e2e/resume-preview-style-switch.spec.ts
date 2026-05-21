// 用于验证简历预览在切换模板时尺寸保持稳定。
import { expect, test, type Page } from '@playwright/test'

const authUser = {
  id: 1,
  email: 'style-switch@test.example',
  is_active: true,
  created_at: new Date().toISOString(),
}

// 构造足够长的简历内容，让预览面板在编辑页中以缩放状态显示。
function buildResumeResponse() {
  const longText = '负责 Agent 简历优化链路，覆盖结构化解析、差距诊断、建议生成和人工确认，确保输出可追踪、可回滚、可解释。'
  return {
    id: 123,
    title: '样式切换测试简历',
    owner_id: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    content: {
      parsing_quality: 1,
      parsing_method: 'manual',
      job_application: { target_company: '测试公司', target_title: 'Agent 工程师', jd_text: '负责 Agent 开发' },
      personal_info: { name: '样式切换', email: 'style-switch@test.example', phone: '13800000000' },
      education: [{ school: '测试大学', degree: '本科', major: '计算机', duration: '2019-2023' }],
      skills: [{ category: '技术栈', items: ['TypeScript', 'Next.js', 'FastAPI', 'LangChain'] }],
      work_experience: [{ company: '测试科技', position: '核心开发者', duration: '2025.01-2025.12', highlights: [{ text: longText }, { text: longText }] }],
      projects: Array.from({ length: 3 }, (_, index) => ({
        name: `项目 ${index + 1}`,
        role: '核心开发者',
        duration: `2025.0${index + 1}-2025.0${index + 2}`,
        overview: longText,
        highlights: [{ text: longText }, { text: longText }, { text: longText }],
      })),
    },
  }
}

// 安装编辑页依赖的最小 API mock。
async function mockEditorApis(page: Page) {
  const resume = buildResumeResponse()
  await page.addInitScript((storedUser) => {
    window.localStorage.setItem('auth_user', JSON.stringify(storedUser))
  }, authUser)
  await page.context().addCookies([
    { name: 'refresh_token', value: 'test-refresh-token', domain: 'localhost', path: '/', httpOnly: true, sameSite: 'Lax' },
    { name: 'NEXT_LOCALE', value: 'zh', domain: 'localhost', path: '/', sameSite: 'Lax' },
  ])
  await page.route('**/api/auth/me', async route => route.fulfill({ json: authUser }))
  await page.route('**/api/auth/refresh', async route => route.fulfill({ json: { token_type: 'bearer', user: authUser } }))
  await page.route('**/api/resumes/123/chat-messages', async route => route.fulfill({ json: [] }))
  await page.route('**/api/resumes/123/layout', async route => route.fulfill({ json: { ok: true } }))
  await page.route('**/api/resumes/123', async route => route.fulfill({ json: resume }))
}

test('切换简历样式时预览不会先放大再缩回', async ({ page }) => {
  await mockEditorApis(page)
  await page.goto('/zh/resume/123/edit')

  const pageSheet = page.locator('.resume-page').first()
  await expect(pageSheet).toBeVisible()
  await expect(page.getByText('计算中...')).toHaveCount(0)
  const beforeBox = await pageSheet.boundingBox()
  expect(beforeBox?.width).toBeGreaterThan(0)

  await page.evaluate(() => {
    const samples: number[] = []
    Object.assign(window, { __resumePageWidthSamples: samples })
    const sample = () => {
      const pageElement = document.querySelector('.resume-page')
      if (pageElement) {
        samples.push(pageElement.getBoundingClientRect().width)
      }
      if (samples.length < 90) requestAnimationFrame(sample)
    }
    requestAnimationFrame(sample)
  })

  await page.getByRole('button', { name: '简历设置' }).click()
  await page.getByRole('button', { name: '正式黑白' }).click()
  await page.waitForFunction(() => (window as unknown as { __resumePageWidthSamples?: number[] }).__resumePageWidthSamples?.length === 90)

  const samples = await page.evaluate(() => (window as unknown as { __resumePageWidthSamples: number[] }).__resumePageWidthSamples)
  const maxWidth = Math.max(...samples)
  expect(maxWidth).toBeLessThan((beforeBox?.width || 0) * 1.05)
})
