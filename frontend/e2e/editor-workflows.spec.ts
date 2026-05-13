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
  await page.route(`**/api/resumes/${resume.id}/layout`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({ ok: true }),
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

/**
 * 在预览页内选中一段可见文本，复用浏览器原生 Selection 触发浮动工具条。
 */
async function selectResumePreviewText(page: Page, text: string) {
  const resumePage = page.locator('.resume-page').first()
  await expect(resumePage).toContainText(text)
  const selectedTextElement = resumePage.getByText(text, { exact: true })
  await expect(selectedTextElement).toBeVisible()
  const selectedText = await selectedTextElement.evaluate((targetElement) => {
    const range = document.createRange()
    range.selectNodeContents(targetElement)
    const selection = window.getSelection()
    selection?.removeAllRanges()
    selection?.addRange(range)
    document.querySelector('main')?.dispatchEvent(new MouseEvent('mouseup', { bubbles: true }))
    return selection?.toString() || ''
  })
  expect(selectedText).toContain(text)
}

/**
 * 用真实鼠标拖拽选中多条预览内容，覆盖用户手动跨行选区的交互路径。
 */
async function dragSelectResumePreviewText(page: Page, startText: string, endText: string) {
  const resumePage = page.locator('.resume-page').first()
  const start = resumePage.getByText(startText, { exact: true })
  const end = resumePage.getByText(endText, { exact: true })
  await expect(start).toBeVisible()
  await expect(end).toBeVisible()

  const startBox = await start.boundingBox()
  const endBox = await end.boundingBox()
  expect(startBox, '拖拽选区起点应可见').toBeTruthy()
  expect(endBox, '拖拽选区终点应可见').toBeTruthy()
  if (!startBox || !endBox) return

  await page.mouse.move(startBox.x + 2, startBox.y + startBox.height / 2)
  await page.mouse.down()
  await page.mouse.move(endBox.x + endBox.width - 2, endBox.y + endBox.height / 2, { steps: 12 })
  await page.mouse.up()

  await expect.poll(() => (
    page.evaluate(() => window.getSelection()?.toString() || '')
  )).toContain(startText.slice(0, 8))
}

/**
 * 读取预览区选区相关的全部视觉状态，避免只清掉原生 Selection 却漏掉自定义高亮。
 */
async function readResumeSelectionVisualState(page: Page) {
  return page.evaluate(() => {
    const highlightRegistry = CSS as typeof CSS & {
      highlights?: { has?: (name: string) => boolean }
    }
    return {
      selectedText: window.getSelection()?.toString() || '',
      hasCustomHighlight: Boolean(highlightRegistry.highlights?.has?.('resume-preview-selection')),
      drawnHighlightCount: document.querySelectorAll('[data-testid="resume-selection-highlight"]').length,
    }
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
    await selectResumePreviewText(page, '负责前端开发与性能优化')

    await expect(page.getByRole('button', { name: '快速优化' })).toBeVisible()
    await page.getByRole('button', { name: '添加至对话框' }).click()
    await expect.poll(() => (
      page.evaluate(() => window.getSelection()?.toString() || '')
    )).toBe('')
    const chatInputBox = page.getByTestId('resume-chat-input-box')
    await expect(chatInputBox.getByTestId('selected-resume-context')).toContainText('负责前端开发与性能优化')
    const chatInput = page.getByPlaceholder('输入消息...')
    await expect(chatInput).toBeFocused()
    await chatInput.press('Backspace')
    await expect(chatInputBox.getByTestId('selected-resume-context')).toBeHidden()
    await expect(chatInput).toBeFocused()
  })

  test('点击预览区外部会取消选区颜色', async ({ page }) => {
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
    await selectResumePreviewText(page, '负责前端开发与性能优化')
    await expect(page.getByRole('button', { name: '快速优化' })).toBeVisible()

    await page.getByText('简历智能体').click()

    await expect(page.getByRole('button', { name: '快速优化' })).toBeHidden()
    await expect.poll(() => (
      page.evaluate(() => window.getSelection()?.toString() || '')
    )).toBe('')
  })

  test('按下预览区外部时会立刻取消选区颜色', async ({ page }) => {
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
    await selectResumePreviewText(page, '负责前端开发与性能优化')
    await expect(page.getByRole('button', { name: '快速优化' })).toBeVisible()

    await page.getByText('简历智能体').dispatchEvent('pointerdown', { bubbles: true })

    await expect(page.getByRole('button', { name: '快速优化' })).toBeHidden()
    await expect.poll(() => (
      page.evaluate(() => window.getSelection()?.toString() || '')
    )).toBe('')
  })

  test('快速优化会通过对话框 Agent 发送选区和要求', async ({ page }) => {
    const resume = buildResumeResponse(123)
    resume.content.work_experience = [
      {
        company: '测试公司',
        position: '前端工程师',
        duration: '2024',
        highlights: [{ text: '负责前端开发与性能优化' }],
      },
    ]
    let streamPayload: { message?: string } | null = null
    await installEditorApiMock(page, resume)
    await page.route('**/api/ai/chat/stream', async (route) => {
      const body = route.request().postData()
      streamPayload = body ? JSON.parse(body) : null
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: 'data: {"done":true}\n\n',
      })
    })

    await page.goto('/zh/resume/123/edit')
    await selectResumePreviewText(page, '负责前端开发与性能优化')
    await page.getByRole('button', { name: '快速优化' }).click()
    await expect(page.getByTestId('resume-selection-highlight').first()).toBeVisible()
    await expect.poll(() => readResumeSelectionVisualState(page)).toEqual({
      selectedText: '',
      hasCustomHighlight: false,
      drawnHighlightCount: 1,
    })
    const quickEditInput = page.getByPlaceholder('输入优化要求')
    await expect(quickEditInput).toBeVisible()
    await page.getByRole('button', { name: '关闭快速优化' }).click()
    await expect.poll(() => readResumeSelectionVisualState(page)).toEqual({
      selectedText: '',
      hasCustomHighlight: false,
      drawnHighlightCount: 0,
    })

    await selectResumePreviewText(page, '负责前端开发与性能优化')
    await page.getByRole('button', { name: '快速优化' }).click()
    await quickEditInput.fill('改得更有结果导向')
    await page.getByRole('button', { name: '发送快速优化' }).click()

    await expect.poll(() => streamPayload?.message || '').toContain('负责前端开发与性能优化')
    expect(streamPayload?.message).toContain('改得更有结果导向')
    await expect(quickEditInput).toBeHidden()
  })

  test('发送快速优化后会立刻关闭输入框', async ({ page }) => {
    const resume = buildResumeResponse(123)
    resume.content.work_experience = [
      {
        company: '测试公司',
        position: '前端工程师',
        duration: '2024',
        highlights: [{ text: '负责前端开发与性能优化' }],
      },
    ]
    let releaseStream: (() => void) | null = null
    await installEditorApiMock(page, resume)
    await page.route('**/api/ai/chat/stream', async (route) => {
      await new Promise<void>((resolve) => {
        releaseStream = resolve
      })
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body: 'data: {"done":true}\n\n',
      })
    })

    await page.goto('/zh/resume/123/edit')
    await selectResumePreviewText(page, '负责前端开发与性能优化')
    await page.getByRole('button', { name: '快速优化' }).click()
    const quickEditInput = page.getByPlaceholder('输入优化要求')
    await expect(quickEditInput).toBeVisible()
    await quickEditInput.fill('asd')

    await page.getByRole('button', { name: '发送快速优化' }).click()

    await expect(quickEditInput).toBeHidden()
    releaseStream?.()
  })

  test('按下快速优化关闭按钮会立刻取消选区颜色', async ({ page }) => {
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
    await selectResumePreviewText(page, '负责前端开发与性能优化')
    await page.getByRole('button', { name: '快速优化' }).click()
    const quickEditInput = page.getByPlaceholder('输入优化要求')
    await expect(quickEditInput).toBeVisible()

    await page.getByRole('button', { name: '关闭快速优化' }).dispatchEvent('pointerdown', { bubbles: true })

    await expect(quickEditInput).toBeHidden()
    await expect.poll(() => readResumeSelectionVisualState(page)).toEqual({
      selectedText: '',
      hasCustomHighlight: false,
      drawnHighlightCount: 0,
    })
  })

  test('关闭快速优化后不会在鼠标释放时恢复选区颜色', async ({ page }) => {
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
    await selectResumePreviewText(page, '负责前端开发与性能优化')
    await page.getByRole('button', { name: '快速优化' }).click()
    const quickEditInput = page.getByPlaceholder('输入优化要求')
    await expect(quickEditInput).toBeVisible()
    await page.locator('.resume-page').first().getByText('负责前端开发与性能优化', { exact: true }).evaluate((targetElement) => {
      const range = document.createRange()
      range.selectNodeContents(targetElement)
      ;(window as Window & { __restoreResumeSelection?: () => string }).__restoreResumeSelection = () => {
        const nextSelection = window.getSelection()
        nextSelection?.removeAllRanges()
        nextSelection?.addRange(range.cloneRange())
        return nextSelection?.toString() || ''
      }
    })

    await page.getByRole('button', { name: '关闭快速优化' }).click()
    await expect(page.evaluate(() => (
      (window as Window & { __restoreResumeSelection?: () => string }).__restoreResumeSelection?.() || ''
    ))).resolves.toContain('负责前端开发与性能优化')

    await expect(quickEditInput).toBeHidden()
    await expect.poll(() => readResumeSelectionVisualState(page)).toEqual({
      selectedText: '',
      hasCustomHighlight: false,
      drawnHighlightCount: 0,
    })
  })

  test('手动跨行选区关闭快速优化后会清掉选区颜色', async ({ page }) => {
    const resume = buildResumeResponse(123)
    const firstHighlight = '基于BOSS直聘MCP实现职位实时搜索，自动生成简历优化建议，打通求职-优化闭环'
    const secondHighlight = '设计专用提示词驱动大模型完成简历结构化解析，准确率显著优于传统规则方法'
    resume.content.work_experience = [
      {
        company: '测试公司',
        position: '前端工程师',
        duration: '2024',
        highlights: [
          { text: firstHighlight },
          { text: secondHighlight },
          { text: '集成语音识别与合成实现端到端语音交互，高度还原真实面试场景' },
        ],
      },
    ]
    await installEditorApiMock(page, resume)

    await page.goto('/zh/resume/123/edit')
    await dragSelectResumePreviewText(page, firstHighlight, secondHighlight)
    await expect(page.getByRole('button', { name: '快速优化' })).toBeVisible()
    await page.getByRole('button', { name: '快速优化' }).click()
    const quickEditInput = page.getByPlaceholder('输入优化要求')
    await expect(quickEditInput).toBeVisible()

    await page.getByRole('button', { name: '关闭快速优化' }).click()

    await expect(quickEditInput).toBeHidden()
    await expect.poll(() => readResumeSelectionVisualState(page)).toEqual({
      selectedText: '',
      hasCustomHighlight: false,
      drawnHighlightCount: 0,
    })
  })

  test('智能一页会把不足一页的简历尽量撑满', async ({ page }) => {
    await installEditorApiMock(page, buildResumeResponse(123))

    await page.goto('/zh/resume/123/edit')
    const exportContent = page.locator('#resume-export-content')
    await expect(exportContent).toBeVisible()

    const initialScale = await exportContent.evaluate((element) =>
      Number(getComputedStyle(element).getPropertyValue('--spacing-scale'))
    )
    expect(initialScale).toBe(1)

    await page.getByRole('button', { name: '智能一页' }).click()

    await expect.poll(async () => (
      exportContent.evaluate((element) =>
        Number(getComputedStyle(element).getPropertyValue('--spacing-scale'))
      )
    )).toBeGreaterThan(1)
  })

  test('编辑器长文本输入框会按内容增高', async ({ page }) => {
    const resume = buildResumeResponse(123)
    resume.content.education = [
      {
        school: '东北大学',
        major: '信息安全',
        degree: '硕士',
        duration: '2018.09 - 2022.06',
        highlights: [
          {
            text: '主要课程：计算机组成原理、计算机网络、数据结构与算法、计算机操作系统、数据库系统与信息安全工程实践',
          },
        ],
      },
    ]
    resume.content.work_experience = [
      {
        company: '测试公司',
        position: '销售智能体工程师',
        duration: '2025',
        highlights: [
          {
            text: '端侧集成 ASR 实现电话录音自动转文本与关键信息抽取，自动生成跟进任务，消除销售通话后的人工整理环节',
          },
        ],
      },
    ]
    resume.content.projects = [
      {
        name: 'Chat Resume',
        role: '全栈工程师',
        duration: '2025',
        overview: 'AI 驱动的求职辅导平台，提供简历诊断、模拟面试、能力评估功能。通过 BOSS 直聘 MCP 工具实时搜索职位并生成简历优化建议。',
        highlights: [
          {
            text: '集成BOSS直聘MCP实现职位实时搜索与简历优化建议自动生成，打通求职-优化闭环',
          },
        ],
      },
    ]
    await installEditorApiMock(page, resume)

    await page.goto('/zh/resume/123/edit')
    await page.getByRole('button', { name: '工作' }).click()
    const highlightInput = page.getByPlaceholder('负责后端系统重构，接口平均响应时间下降 35%')
    await expect(highlightInput).toBeVisible()
    expect(await highlightInput.evaluate((element) =>
      element.clientHeight >= element.scrollHeight - 1
    )).toBe(true)

    await page.getByRole('button', { name: '项目' }).click()
    const overviewInput = page.getByPlaceholder('一句话说明项目背景、目标或你的角色...')
    const projectHighlightInput = page.getByPlaceholder('实现了用户友好的拖拽式简历编辑界面，提升编辑效率50%')
    await expect(overviewInput).toBeVisible()
    await expect(projectHighlightInput).toBeVisible()
    expect(await overviewInput.evaluate((element) =>
      element.clientHeight >= element.scrollHeight - 1
    )).toBe(true)
    expect(await projectHighlightInput.evaluate((element) =>
      element.clientHeight >= element.scrollHeight - 1
    )).toBe(true)

    await page.getByRole('button', { name: '教育' }).click()
    const educationHighlightInput = page.getByPlaceholder('985高校、主要课程、奖项、研究方向等')
    await expect(educationHighlightInput).toBeVisible()
    expect(await educationHighlightInput.evaluate((element) =>
      element.clientHeight >= element.scrollHeight - 1
    )).toBe(true)
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
