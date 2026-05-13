/**
 * 编辑页工作流端到端测试
 *
 * 用于补齐上传、导出 PDF 和面试工作台的关键前端链路验证。
 */

import { expect, test, Page } from '@playwright/test'
import fs from 'node:fs/promises'

import { registerUser, uniqueEmail } from './helpers'

/**
 * 注册新用户并等待进入 dashboard，供编辑页相关场景复用。
 */
async function loginAs(page: Page, email: string) {
  await registerUser(page, email)
  await page.waitForURL('**/dashboard', { timeout: 12_000 })
}

/**
 * 从仪表板创建空白简历并返回新建后的简历 ID。
 */
async function createResumeFromDashboard(page: Page, email: string): Promise<string> {
  await loginAs(page, email)
  await page.getByRole('button', { name: '新建简历' }).click()
  await page.waitForURL(/\/resume\/\d+\/edit/, { timeout: 12_000 })
  const resumeId = page.url().match(/\/resume\/(\d+)\/edit/)?.[1]
  expect(resumeId, '点击新建简历后应进入编辑页').toBeTruthy()
  return resumeId as string
}

/**
 * 构造一份最小可用的简历响应体，供上传和面试页面复用。
 */
function buildResumeResponse(id: number) {
  return {
    id,
    title: '测试简历',
    owner_id: 1,
    created_at: new Date().toISOString(),
    updated_at: new Date().toISOString(),
    content: {
      parsing_quality: 0,
      parsing_method: 'fallback',
      job_application: { target_company: '测试公司', target_title: '前端工程师', jd_text: '负责前端开发' },
      personal_info: { name: '测试用户', email: 'e2e@test.example' },
      education: [],
      work_experience: [],
      skills: [],
      projects: [],
    },
  }
}

/**
 * 为编辑页安装最小登录态和 API mock，避免测试依赖真实账号注册。
 */
async function installEditorApiMock(page: Page, resume = buildResumeResponse(123)) {
  const user = {
    id: 1,
    email: 'editor@test.example',
    is_active: true,
    created_at: new Date().toISOString(),
  }

  await page.addInitScript((storedUser) => {
    window.localStorage.setItem('auth_user', JSON.stringify(storedUser))
  }, user)
  await page.context().addCookies([
    {
      name: 'refresh_token',
      value: 'test-refresh-token',
      domain: 'localhost',
      path: '/',
      httpOnly: true,
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

  await page.route('**/api/auth/me', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(user),
    })
  })
  await page.route('**/api/auth/refresh', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ token_type: 'bearer', user }),
    })
  })
  await page.route(`**/api/resumes/${resume.id}/chat-messages`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '[]',
    })
  })
  await page.route(`**/api/resumes/${resume.id}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify(resume),
    })
  })
}

/**
 * 在浏览器里注入一个可控的 Resume Agent mock，用于真实驱动流式 diff 确认交互。
 */
async function installResumeAgentMock(page: Page) {
  await page.addInitScript(() => {
    const originalFetch = window.fetch.bind(window)
    const diffSummary = [
      '改前：负责前端开发',
      '改后：主导前端重构，首屏加载提速 35%',
      '改动理由：补充量化结果',
    ].join('\n')

    ;(window as Window & {
      __resumeAgentConfirmCalls?: Array<{ session_id: string; call_id: string; confirmed: boolean }>
      __resumeAgentResolve?: (confirmed: boolean) => void
    }).__resumeAgentConfirmCalls = []

    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const requestUrl =
        typeof input === 'string'
          ? input
          : input instanceof Request
            ? input.url
            : input.toString()
      const method = (init?.method || (input instanceof Request ? input.method : 'GET')).toUpperCase()

      if (requestUrl.includes('/chat-messages')) {
        return new Response('[]', {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }

      if (requestUrl.includes('/api/ai/chat/confirm-tool')) {
        const payload = init?.body && typeof init.body === 'string'
          ? JSON.parse(init.body)
          : { confirmed: false }
        const runtimeWindow = window as Window & {
          __resumeAgentConfirmCalls?: Array<{ session_id: string; call_id: string; confirmed: boolean }>
          __resumeAgentResolve?: (confirmed: boolean) => void
        }
        runtimeWindow.__resumeAgentConfirmCalls?.push(payload)
        runtimeWindow.__resumeAgentResolve?.(Boolean(payload.confirmed))

        return new Response(JSON.stringify({ ok: true }), {
          status: 200,
          headers: { 'Content-Type': 'application/json' },
        })
      }

      if (requestUrl.includes('/api/ai/chat/stream')) {
        const encoder = new TextEncoder()
        const stream = new ReadableStream({
          async start(controller) {
            const runtimeWindow = window as Window & {
              __resumeAgentResolve?: (confirmed: boolean) => void
            }
            const decision = new Promise<boolean>((resolve) => {
              runtimeWindow.__resumeAgentResolve = resolve
            })
            const pushEvent = (payload: Record<string, unknown>) => {
              controller.enqueue(encoder.encode(`data: ${JSON.stringify(payload)}\n\n`))
            }
            const sleep = (ms: number) => new Promise((resolve) => window.setTimeout(resolve, ms))

            pushEvent({ session_id: 'resume_session_e2e', content: '', done: false })
            await sleep(50)
            pushEvent({ content: '我建议先强化项目结果表达。', done: false })
            await sleep(50)
            pushEvent({
              tool_pending: true,
              call_id: 'call_e2e',
              tool_name: '优化项目经历',
              tool_display_name: '优化项目经历',
              diff_summary: diffSummary,
              diff_items: [
                {
                  before: '负责前端开发',
                  after: '主导前端重构，首屏加载提速 35%',
                  reason: '补充量化结果',
                },
              ],
              done: false,
            })

            const confirmed = await decision
            await sleep(50)
            pushEvent({
              [confirmed ? 'tool_confirmed' : 'tool_rejected']: true,
              call_id: 'call_e2e',
              tool_name: '优化项目经历',
              tool_display_name: '优化项目经历',
              diff_summary: diffSummary,
              diff_items: [
                {
                  before: '负责前端开发',
                  after: '主导前端重构，首屏加载提速 35%',
                  reason: '补充量化结果',
                },
              ],
              done: false,
            })
            await sleep(50)
            pushEvent({
              content: confirmed ? '已应用修改。' : '已保留原文。',
              done: false,
            })
            await sleep(30)
            pushEvent({ done: true })
            controller.close()
          },
        })

        return new Response(stream, {
          status: 200,
          headers: { 'Content-Type': 'text/event-stream' },
        })
      }

      return originalFetch(input, init)
    }
  })
}

/**
 * 读取浏览器侧记录下来的确认请求，验证用户点击是否真的发出了对应确认结果。
 */
async function readResumeAgentConfirmCalls(page: Page) {
  return page.evaluate(() => {
    const runtimeWindow = window as Window & {
      __resumeAgentConfirmCalls?: Array<{ session_id: string; call_id: string; confirmed: boolean }>
    }
    return runtimeWindow.__resumeAgentConfirmCalls || []
  })
}

test.describe('编辑页工作流', () => {
  test('选中预览内容后可以粘贴到聊天输入框', async ({ page }) => {
    const resume = buildResumeResponse(123)
    resume.content.work_experience = [
      {
        company: '测试公司',
        position: '前端工程师',
        duration: '2024',
        highlights: [{ text: '负责前端开发与性能优化' }],
      },
    ]
    await installEditorApiMock(page, resume)

    await page.goto('/zh/resume/123/edit')
    const resumePage = page.locator('.resume-page').first()
    await expect(resumePage).toContainText('负责前端开发与性能优化')
    const selectedText = resumePage.locator('li').filter({ hasText: '负责前端开发与性能优化' })
    const textBox = await selectedText.boundingBox()
    expect(textBox, '应找到可拖选的预览文本').toBeTruthy()
    await page.mouse.move(textBox!.x + 2, textBox!.y + textBox!.height / 2)
    await page.mouse.down()
    await page.mouse.move(textBox!.x + textBox!.width - 2, textBox!.y + textBox!.height / 2, { steps: 8 })
    await page.mouse.up()

    await page.getByRole('button', { name: '添加至对话框' }).click()
    await expect(page.getByPlaceholder('输入消息...')).toHaveValue('负责前端开发与性能优化')
  })

  test('上传真实文件后轮询解析任务，完成后进入编辑页并加载简历', async ({ page }) => {
    await loginAs(page, uniqueEmail('uploadflow'))
    const uploadedResume = buildResumeResponse(999)

    await page.route('**/api/upload/resume', async (route) => {
      await route.fulfill({
        status: 202,
        contentType: 'application/json',
        body: JSON.stringify({ job_id: 'upload-job-999', status: 'queued' }),
      })
    })
    await page.route('**/api/upload/resume-jobs/upload-job-999', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          job_id: 'upload-job-999',
          status: 'completed',
          resume_id: 999,
          error: null,
          original_filename: 'resume.txt',
        }),
      })
    })
    await page.route('**/api/resumes/999', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(uploadedResume),
      })
    })
    await page.route('**/api/resumes/999/chat-messages', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: '[]',
      })
    })

    const fileInput = page.locator('input[type="file"]')
    await fileInput.setInputFiles({
      name: 'resume.txt',
      mimeType: 'text/plain',
      buffer: Buffer.from('测试用户\n前端工程师\nOpenAI'),
    })

    await page.waitForURL('**/resume/999/edit', { timeout: 12_000 })
    await expect(page.getByPlaceholder('请输入目标公司名称')).toHaveValue('测试公司')
    await expect(page.getByPlaceholder('请输入目标岗位名称')).toHaveValue('前端工程师')
  })

  test('点击导出 PDF 后会真正触发下载并拿到 PDF 文件', async ({ page }, testInfo) => {
    await createResumeFromDashboard(page, uniqueEmail('pdfdownload'))

    await page.route('**/api/resumes/*/export', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          download_url: '/files/test-resume.pdf',
          filename: 'resume_test.pdf',
          format: 'pdf',
        }),
      })
    })
    await page.route('http://localhost:8000/files/test-resume.pdf', async (route) => {
      await route.fulfill({
        status: 200,
        headers: {
          'Content-Type': 'application/pdf',
          'Content-Disposition': 'attachment; filename="resume_test.pdf"',
        },
        body: '%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF',
      })
    })

    const downloadPromise = page.waitForEvent('download')
    await page.getByRole('button', { name: '导出 PDF' }).click()
    const download = await downloadPromise
    const savedPath = testInfo.outputPath('resume_test.pdf')
    await download.saveAs(savedPath)

    expect(download.suggestedFilename()).toBe('resume_test.pdf')
    const bytes = await fs.readFile(savedPath, 'utf8')
    expect(bytes.startsWith('%PDF-1.4')).toBeTruthy()
  })

  test('面试工作台只保留实时语音面试入口', async ({ page }) => {
    const resumeId = await createResumeFromDashboard(page, uniqueEmail('interviewflow'))
    const baseResume = buildResumeResponse(Number(resumeId))

    const voiceSession = {
      id: 1,
      resume_id: Number(resumeId),
      target_title: '前端工程师',
      target_company: '测试公司',
      jd_text: '负责前端开发与性能优化',
      interview_type: 'general',
      difficulty: 'medium',
      language: 'zh-CN',
      mode: 'practice',
      status: 'interview_ready',
      current_round_index: 0,
      current_turn_index: 0,
      plan: null,
      turns: [],
      current_turn: null,
    }

    await page.route(`**/api/resumes/${resumeId}`, async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(baseResume),
      })
    })
    await page.route('**/api/interviews/', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          session: voiceSession,
          next_action: 'voice',
        }),
      })
    })
    await page.route('**/api/interviews/1/end', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          session: { ...voiceSession, status: 'completed', ended_at: new Date().toISOString() },
          next_action: 'completed',
        }),
      })
    })
    await page.route('**/api/digital-human/conversations', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          provider: 'volcengine',
          session_id: '1',
          status: 'ready',
        }),
      })
    })

    await page.goto(`/resume/${resumeId}/interview`)
    await expect(page.getByText('语音面试')).toBeVisible()
    await expect(page.getByText('对话内容会实时显示在这里')).toBeVisible()
    await expect(page.getByPlaceholder('输入你的回答...')).toHaveCount(0)
    await expect(page.getByRole('button', { name: '提交回答' })).toHaveCount(0)
    await expect(page.getByRole('button', { name: '给我提示' })).toHaveCount(0)
  })

  test('Resume Agent 可以展示流式 diff 并确认修改', async ({ page }) => {
    const resumeId = await createResumeFromDashboard(page, uniqueEmail('agentconfirm'))

    await installResumeAgentMock(page)
    await page.goto(`/resume/${resumeId}/edit`)
    await page.waitForLoadState('networkidle')

    const input = page.getByPlaceholder('输入消息...')
    await input.fill('请帮我优化项目经历')
    await input.press('Enter')

    await expect(page.getByText('优化项目经历')).toBeVisible()
    await expect(page.getByText('主导前端重构，首屏加载提速 35%')).toBeVisible()
    await page.getByRole('button', { name: '确认修改' }).click()

    await expect(page.getByText('已应用修改。')).toBeVisible()
    const confirmCalls = await readResumeAgentConfirmCalls(page)
    expect(confirmCalls).toHaveLength(1)
    expect(confirmCalls[0]).toMatchObject({
      session_id: 'resume_session_e2e',
      call_id: 'call_e2e',
      confirmed: true,
    })
  })

  test('Resume Agent 可以拒绝待确认的 diff 修改', async ({ page }) => {
    const resumeId = await createResumeFromDashboard(page, uniqueEmail('agentreject'))

    await installResumeAgentMock(page)
    await page.goto(`/resume/${resumeId}/edit`)
    await page.waitForLoadState('networkidle')

    const input = page.getByPlaceholder('输入消息...')
    await input.fill('请帮我优化项目经历')
    await input.press('Enter')

    await expect(page.getByText('优化项目经历')).toBeVisible()
    await page.getByRole('button', { name: '拒绝' }).click()

    await expect(page.getByText('已保留原文。')).toBeVisible()
    const confirmCalls = await readResumeAgentConfirmCalls(page)
    expect(confirmCalls).toHaveLength(1)
    expect(confirmCalls[0]).toMatchObject({
      session_id: 'resume_session_e2e',
      call_id: 'call_e2e',
      confirmed: false,
    })
  })
})
