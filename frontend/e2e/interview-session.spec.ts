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
