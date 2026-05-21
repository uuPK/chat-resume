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

const completedTurns = [
  {
    id: 900,
    turn_index: 0,
    round_index: 0,
    question: '请介绍一下你做过的 Agent 项目',
    question_type: 'general',
    answer: '我做过简历优化 Agent，并接入了语音面试流程。',
    evaluation: {
      summary: '项目背景清楚，但缺少量化结果。',
      gaps: ['没有说明用户规模'],
      evidence: ['提到了简历优化 Agent'],
      advice: '补充延迟、转化率或用户反馈数据。',
    },
    follow_up_count: 0,
    status: 'answered',
  },
]

const pausedActiveSession = {
  ...activeSession,
  turns: completedTurns,
  current_turn: completedTurns[0],
}
const completedEmptySession = {
  ...activeSession,
  status: 'completed',
  ended_at: '2026-05-16T00:05:00Z',
  report_data: null,
}


const completedSession = {
  ...activeSession,
  status: 'completed',
  ended_at: '2026-05-16T00:05:00Z',
  report_data: null,
  turns: completedTurns,
  current_turn: completedTurns[0],
}

const completedSessionWithReport = {
  ...completedSession,
  report_data: {
    summary: '边缘通过，岗位方向相关但证据不足',
    candidate_verdict: {
      level: 'borderline',
      label: '边缘通过',
      reason: '项目方向相关，但负责边界和量化结果没有证明清楚。',
    },
    job_match: {
      target_title: 'Agent 工程师',
      target_company: 'Acme',
      required_capabilities: ['Agent 编排', '工具调用', '线上效果优化'],
      covered_capabilities: ['Agent 编排'],
      missing_capabilities: ['量化结果', '负责边界'],
      interviewer_concerns: ['无法判断候选人是否主导核心链路'],
      likely_followups: ['你具体负责哪一层？'],
    },
    strengths: ['结构清晰', '项目相关', '表达自然'],
    weaknesses: ['量化不足'],
    interviewer_risks: ['负责边界不清，面试官可能继续追问具体贡献。'],
    answer_rewrites: [
      {
        turn_index: 0,
        original_problem: '回答只说做过 Agent，没有说明你的职责和结果。',
        recommended_answer: '我负责 Agent 工具编排和确认链路，首轮响应耗时降低 30%。',
        why_better: '这句话同时补充了职责边界、技术动作和量化结果。',
      },
    ],
    dimensions: [
      {
        title: '岗位相关度',
        score: 4,
        assessment: '方向匹配',
        evidence: '提到了简历优化 Agent 和语音面试流程。',
        advice: '补充工具调用、编排和线上指标。',
      },
    ],
    next_training_plan: ['补充数据', '练习追问', '压缩表达'],
    resume_feedback: ['强化项目成果'],
  },
}

/**
 * 把报告生成事件序列编码为 SSE 响应体。
 */
function reportStreamBody(events: object[]) {
  return events.map(event => `data: ${JSON.stringify(event)}\n\n`).join('')
}

/**
 * 创建报告生成阶段事件。
 */
function reportPhase(phase: string, label: string, status: string, progress: number) {
  return { event_type: 'phase', phase, label, status, progress }
}

/**
 * 创建报告生成结束事件。
 */
function reportDone(session: object, nextAction = 'report') {
  return {
    event_type: 'done',
    phase: 'done',
    label: '报告已生成',
    status: nextAction === 'report' ? 'completed' : 'skipped',
    progress: 100,
    done: true,
    generated: nextAction === 'report',
    next_action: nextAction,
    session,
  }
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
        session_id: 'conv-456',
        status: 'created',
      },
    })
  })
  await page.route('**/api/digital-human/conversations/end', async route => {
    await route.fulfill({ json: { status: 'ended' } })
  })
}

test('结束面试会把 session 标记为 completed 并返回面试列表', async ({ page }) => {
  await mockInterviewApis(page)

  await page.route(/\/api\/interviews\/456$/, async route => {
    await route.fulfill({ json: { session: pausedActiveSession } })
  })
  await page.route(/\/api\/interviews\/456\/end$/, async route => {
    await route.fulfill({ json: { session: completedSession, next_action: 'completed' } })
  })
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
      ],
    })
  })

  await page.goto('/zh/resume/123/interview?session=456')

  await expect(page.getByText('模拟面试 · Acme · 前端工程师')).toBeVisible()
  await expect(page.getByText('模拟面试 · 张三')).toHaveCount(0)
  const endButton = page.getByRole('button', { name: '结束面试' })
  await expect(endButton).toBeVisible()
  await expect(page.getByRole('button', { name: '继续面试' })).toBeVisible()
  const [endRequest] = await Promise.all([
    page.waitForRequest('**/api/interviews/456/end'),
    endButton.click(),
  ])

  expect(endRequest.method()).toBe('POST')
  await expect(page).toHaveURL(/\/zh\/interviews$/)
  await expect(page.getByRole('link', { name: '查看报告' })).toBeVisible()
})

test('completed 面试可以点击生成报告并展示摘要', async ({ page }) => {
  await mockInterviewApis(page)

  await page.route(/\/api\/interviews\/456$/, async route => {
    await route.fulfill({ json: { session: completedSession } })
  })
  await page.route(/\/api\/interviews\/456\/report\/stream$/, async route => {
    await route.fulfill({
      contentType: 'text/event-stream',
      body: reportStreamBody([reportDone(completedSessionWithReport)]),
    })
  })

  await page.goto('/zh/resume/123/interview?session=456')

  const generateButton = page.getByRole('button', { name: '生成报告', exact: true })
  await expect(generateButton).toBeVisible()
  const [reportRequest] = await Promise.all([
    page.waitForRequest('**/api/interviews/456/report/stream'),
    generateButton.click(),
  ])

  expect(reportRequest.method()).toBe('POST')
  await expect(generateButton).toBeHidden()
  await expect(page.getByRole('heading', { name: '面试作战报告' })).toBeVisible()
  await expect(page.getByText('边缘通过，岗位方向相关但证据不足')).toBeVisible()
  await expect(page.getByRole('button', { name: '查看对话' })).toHaveCount(0)
})

test('completed 空面试点击报告入口会提示无法生成', async ({ page }) => {
  await mockInterviewApis(page)

  await page.route(/\/api\/interviews\/456$/, async route => {
    await route.fulfill({ json: { session: completedEmptySession } })
  })
  await page.route(/\/api\/interviews\/456\/report\/stream$/, async route => {
    await route.fulfill({
      contentType: 'text/event-stream',
      body: reportStreamBody([reportDone(completedEmptySession, 'report_skipped')]),
    })
  })

  await page.goto('/zh/resume/123/interview?session=456')

  const [reportRequest] = await Promise.all([
    page.waitForRequest('**/api/interviews/456/report/stream'),
    page.getByRole('button', { name: '开始生成报告' }).click(),
  ])

  expect(reportRequest.method()).toBe('POST')
  await expect(page.getByText('这场面试还没有可复盘的回答，先完成一次问答后再生成报告。')).toBeVisible()
  await expect(page.getByRole('heading', { name: '生成面试复盘报告' })).toBeVisible()
})

test('生成报告进度使用后端 SSE 阶段', async ({ page }) => {
  await mockInterviewApis(page)
  await page.addInitScript(({ session }) => {
    const originalFetch = window.fetch.bind(window)
    window.fetch = async (input, init) => {
      const url = typeof input === 'string' ? input : input instanceof Request ? input.url : input.toString()
      if (!url.includes('/api/interviews/456/report/stream')) return originalFetch(input, init)

      const encoder = new TextEncoder()
      const events = [
        { event_type: 'phase', phase: 'validate_session', label: '校验面试状态', status: 'running', progress: 5 },
        { event_type: 'phase', phase: 'validate_session', label: '校验面试状态', status: 'completed', progress: 12 },
        { event_type: 'phase', phase: 'load_turns', label: '读取面试回答', status: 'running', progress: 18 },
        { event_type: 'phase', phase: 'load_turns', label: '读取面试回答', status: 'completed', progress: 28 },
        { event_type: 'phase', phase: 'request_llm', label: '调用 AI 生成报告', status: 'running', progress: 36 },
        { event_type: 'phase', phase: 'request_llm', label: '调用 AI 生成报告', status: 'completed', progress: 68 },
        { event_type: 'phase', phase: 'parse_report', label: '解析报告结构', status: 'running', progress: 74 },
        { event_type: 'done', phase: 'done', label: '报告已生成', status: 'completed', progress: 100, done: true, generated: true, next_action: 'report', session },
      ]
      const body = new ReadableStream({
        start(controller) {
          events.forEach((event, index) => {
            window.setTimeout(() => {
              controller.enqueue(encoder.encode(`data: ${JSON.stringify(event)}\n\n`))
              if (index === events.length - 1) controller.close()
            }, 200 + index * 700)
          })
        },
      })
      return new Response(body, {
        status: 200,
        headers: { 'Content-Type': 'text/event-stream' },
      })
    }
  }, { session: completedSessionWithReport })

  await page.route(/\/api\/interviews\/456$/, async route => {
    await route.fulfill({ json: { session: completedSession } })
  })

  await page.goto('/zh/resume/123/interview?session=456')

  const status = page.getByRole('status')
  await page.getByRole('button', { name: '生成报告', exact: true }).click()

  await expect(status).toContainText('校验面试状态')
  await expect(status).toContainText('调用 AI 生成报告', { timeout: 5_000 })
  await expect(page.getByRole('progressbar', { name: '报告生成进度' })).toBeVisible()
  await expect(status).toContainText('解析报告结构', { timeout: 2_000 })
  await expect(page.getByRole('heading', { name: '面试作战报告' })).toBeVisible()
})

test('completed 面试报告展示行动报告结构', async ({ page }) => {
  await mockInterviewApis(page)

  await page.route(/\/api\/interviews\/456$/, async route => {
    await route.fulfill({ json: { session: completedSessionWithReport } })
  })

  await page.goto('/zh/resume/123/interview?session=456')

  await expect(page.getByRole('heading', { name: '面试作战报告' })).toBeVisible()
  await expect(page.getByText('边缘通过，岗位方向相关但证据不足')).toBeVisible()
  await expect(page.getByRole('heading', { name: '面试官结论' })).toBeVisible()
  await expect(page.getByRole('heading', { name: '岗位匹配' })).toBeVisible()
  await expect(page.getByText('量化结果', { exact: true })).toBeVisible()
  await expect(page.getByRole('heading', { name: '风险追问' })).toBeVisible()
  await expect(page.getByText('负责边界不清，面试官可能继续追问具体贡献。')).toBeVisible()
  await expect(page.getByRole('heading', { name: '逐题重写' })).toBeVisible()
  await expect(page.getByText('我负责 Agent 工具编排和确认链路，首轮响应耗时降低 30%。')).toBeVisible()
  await expect(page.getByRole('heading', { name: '下一步行动' })).toBeVisible()
  await expect(page.getByText('强化项目成果')).toBeVisible()
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
  await page.getByRole('button', { name: '岗位定向练习' }).click()

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

test('创建面试订阅不足时不暴露后端错误码', async ({ page }) => {
  await mockInterviewApis(page)
  await page.route('**/api/resumes/', async route => {
    await route.fulfill({ json: [resume] })
  })
  await page.route('**/api/interviews/', async route => {
    if (route.request().method() === 'POST') {
      await route.fulfill({
        status: 403,
        json: { detail: 'active_subscription_required' },
      })
      return
    }
    await route.fulfill({ json: [] })
  })

  await page.goto('/zh/interviews')
  await page.getByRole('button', { name: '岗位定向练习' }).click()

  const dialog = page.getByRole('dialog', { name: '创建面试' })
  await dialog.locator('select').selectOption(String(resume.id))
  await dialog.getByRole('button', { name: '开始面试' }).click()

  await expect(dialog).toContainText('该功能需要 Plus 套餐，升级后即可使用。')
  await expect(dialog).not.toContainText('active_subscription_required')
})
