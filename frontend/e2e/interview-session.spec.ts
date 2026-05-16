/**
 * 面试会话生命周期端到端测试。
 *
 * 覆盖面试页结束会话和历史列表入口状态。
 */

import { expect, test, type Page } from '@playwright/test'

const authUser = {
  id: 1,
  email: 'interview-session@test.example',
  full_name: 'Interview Tester',
  is_active: true,
  created_at: '2026-05-16T00:00:00Z',
}

const resume = {
  id: 123,
  title: '前端工程师简历',
  owner_id: 1,
  created_at: '2026-05-16T00:00:00Z',
  updated_at: '2026-05-16T00:00:00Z',
  content: {
    personal_info: { name: '张三' },
    job_application: {
      target_title: '前端工程师',
      target_company: 'Acme',
      jd_text: 'React engineer',
    },
  },
}

const activeSession = {
  id: 456,
  resume_id: 123,
  target_title: '前端工程师',
  target_company: 'Acme',
  jd_text: 'React engineer',
  interview_type: 'general',
  difficulty: 'medium',
  language: 'zh-CN',
  mode: 'practice',
  status: 'in_progress',
  current_round_index: 0,
  current_turn_index: 0,
  started_at: '2026-05-16T00:00:00Z',
  turns: [],
  current_turn: null,
}

const completedSession = {
  ...activeSession,
  status: 'completed',
  ended_at: '2026-05-16T00:05:00Z',
  report_data: null,
}

const completedSessionWithReport = {
  ...completedSession,
  report_data: {
    summary: '回答完整但需要补充量化结果',
    strengths: ['结构清晰', '项目相关', '表达自然'],
    weaknesses: ['量化不足'],
    next_training_plan: ['补充数据', '练习追问', '压缩表达'],
    resume_feedback: ['强化项目成果'],
  },
}

/**
 * 为面试页测试准备认证和后端 API mock。
 */
async function mockInterviewApis(page: Page) {
  await page.context().addCookies([
    {
      name: 'refresh_token',
      value: 'test-refresh-token',
      domain: 'localhost',
      path: '/',
      sameSite: 'Lax',
    },
    {
      name: 'NEXT_LOCALE',
      value: 'zh',
      domain: 'localhost',
      path: '/',
      sameSite: 'Lax',
    },
  ])
  await page.route('**/api/auth/me', async route => {
    await route.fulfill({ json: authUser })
  })
  await page.route('**/api/auth/refresh', async route => {
    await route.fulfill({ json: { token_type: 'bearer', user: authUser } })
  })
  await page.route('**/api/resumes/123', async route => {
    await route.fulfill({ json: resume })
  })
  await page.route('**/api/digital-human/conversations', async route => {
    await route.fulfill({
      json: {
        provider: 'volcengine',
        conversation_id: 'conv-456',
        status: 'created',
      },
    })
  })
  await page.route('**/api/digital-human/conversations/end', async route => {
    await route.fulfill({ json: { status: 'ended' } })
  })
}

test('结束面试会把 session 标记为 completed 并显示报告入口', async ({ page }) => {
  await mockInterviewApis(page)

  await page.route(/\/api\/interviews\/456$/, async route => {
    await route.fulfill({ json: { session: activeSession } })
  })
  await page.route(/\/api\/interviews\/456\/end$/, async route => {
    await route.fulfill({ json: { session: completedSession, next_action: 'completed' } })
  })

  await page.goto('/zh/resume/123/interview?session=456')

  const endButton = page.getByRole('button', { name: '结束面试' })
  await expect(endButton).toBeVisible()
  const [endRequest] = await Promise.all([
    page.waitForRequest('**/api/interviews/456/end'),
    endButton.click(),
  ])

  expect(endRequest.method()).toBe('POST')
  await expect(endButton).toBeHidden()
  await expect(page.getByRole('link', { name: '查看报告' })).toBeVisible()
})

test('completed 面试可以点击生成报告并展示摘要', async ({ page }) => {
  await mockInterviewApis(page)

  await page.route(/\/api\/interviews\/456$/, async route => {
    await route.fulfill({ json: { session: completedSession } })
  })
  await page.route(/\/api\/interviews\/456\/report$/, async route => {
    await route.fulfill({ json: { session: completedSessionWithReport, next_action: 'report' } })
  })

  await page.goto('/zh/resume/123/interview?session=456')

  const generateButton = page.getByRole('button', { name: '生成报告' })
  await expect(generateButton).toBeVisible()
  const [reportRequest] = await Promise.all([
    page.waitForRequest('**/api/interviews/456/report'),
    generateButton.click(),
  ])

  expect(reportRequest.method()).toBe('POST')
  await expect(generateButton).toBeHidden()
  await expect(page.getByRole('heading', { name: '面试评估报告' })).toBeVisible()
  await expect(page.getByText('回答完整但需要补充量化结果')).toBeVisible()
})

test('面试列表对 completed session 显示查看报告', async ({ page }) => {
  await mockInterviewApis(page)
  await page.route('**/api/resumes/', async route => {
    await route.fulfill({ json: [resume] })
  })
  await page.route('**/api/interviews/', async route => {
    await route.fulfill({
      json: [
        {
          ...completedSession,
          answered_turn_count: 1,
        },
        {
          ...activeSession,
          id: 457,
          answered_turn_count: 0,
        },
      ],
    })
  })

  await page.goto('/zh/interviews')

  await expect(page.getByRole('link', { name: '查看报告' })).toBeVisible()
  await expect(page.getByRole('link', { name: '继续面试' })).toBeVisible()
})

test('创建面试表单的简历选择控件和文本输入视觉一致', async ({ page }) => {
  await mockInterviewApis(page)
  await page.route('**/api/resumes/', async route => {
    await route.fulfill({ json: [resume] })
  })
  await page.route('**/api/interviews/', async route => {
    await route.fulfill({ json: [] })
  })

  await page.goto('/zh/interviews')
  await page.getByRole('button', { name: '创建面试' }).click()

  const dialog = page.getByRole('dialog', { name: '创建面试' })
  const resumeSelect = dialog.locator('select')
  const companyInput = dialog.getByPlaceholder('例如：腾讯 / 字节跳动')
  const targetInput = dialog.getByPlaceholder('例如：前端工程师 / 产品经理')
  const startButton = dialog.getByRole('button', { name: '开始面试' })

  await expect(resumeSelect).toBeVisible()
  await expect(resumeSelect).toHaveCount(1)
  await expect(companyInput).toBeVisible()
  await expect(targetInput).toBeVisible()
  await expect(startButton).toBeVisible()

  const selectVisualState = await resumeSelect.evaluate((selectElement) => {
    const selectStyle = window.getComputedStyle(selectElement)
    const selectRect = selectElement.getBoundingClientRect()
    return {
      appearance: selectStyle.appearance,
      borderColor: selectStyle.borderColor,
      borderRadius: selectStyle.borderRadius,
      color: selectStyle.color,
      height: selectRect.height,
    }
  })
  const companyVisualState = await companyInput.evaluate((companyElement) => {
    const companyStyle = window.getComputedStyle(companyElement)
    const companyRect = (companyElement as HTMLElement).getBoundingClientRect()
    return {
      borderColor: companyStyle.borderColor,
      borderRadius: companyStyle.borderRadius,
      height: companyRect.height,
    }
  })

  expect(selectVisualState.appearance).toBe('none')
  expect(selectVisualState.borderColor).toBe(companyVisualState.borderColor)
  expect(selectVisualState.borderRadius).toBe(companyVisualState.borderRadius)
  expect(Math.abs(selectVisualState.height - companyVisualState.height)).toBeLessThan(1)
  expect(selectVisualState.color).toBe('rgb(156, 163, 175)')
  await expect(dialog.locator('select + svg')).toHaveCount(1)

  const startButtonStyle = await startButton.evaluate((buttonElement) => {
    const style = window.getComputedStyle(buttonElement)
    return {
      backgroundColor: style.backgroundColor,
      borderColor: style.borderColor,
      color: style.color,
    }
  })
  expect(startButtonStyle.backgroundColor).toBe('rgb(0, 82, 255)')
  expect(startButtonStyle.borderColor).toBe('rgb(0, 82, 255)')
  expect(startButtonStyle.color).toBe('rgb(255, 255, 255)')
})
