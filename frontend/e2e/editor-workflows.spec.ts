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

test.describe('编辑页工作流', () => {
  test('上传真实文件后会进入编辑页并加载返回的简历', async ({ page }) => {
    await loginAs(page, uniqueEmail('uploadflow'))
    const uploadedResume = buildResumeResponse(999)

    await page.route('**/api/upload/resume', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify(uploadedResume),
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

  test('面试工作台可以完成开始、回答、收到反馈并结束查看报告', async ({ page }) => {
    const resumeId = await createResumeFromDashboard(page, uniqueEmail('interviewflow'))
    const baseResume = buildResumeResponse(Number(resumeId))

    const startedSession = {
      id: 1,
      resume_id: Number(resumeId),
      target_title: '前端工程师',
      target_company: '测试公司',
      jd_text: '负责前端开发与性能优化',
      interview_type: 'general',
      difficulty: 'medium',
      language: 'zh-CN',
      mode: 'practice',
      status: 'waiting_user_answer',
      current_round_index: 0,
      current_turn_index: 1,
      plan: { rounds: [{ type: 'warmup', goal: '自我介绍与背景确认' }] },
      turns: [
        {
          id: 101,
          turn_index: 1,
          round_index: 0,
          question: '你好，请先做一个和目标岗位最相关的自我介绍。',
          question_type: 'warmup',
          intent: '自我介绍与背景确认',
          follow_up_count: 0,
          status: 'asked',
        },
      ],
      current_turn: {
        id: 101,
        turn_index: 1,
        round_index: 0,
        question: '你好，请先做一个和目标岗位最相关的自我介绍。',
        question_type: 'warmup',
        intent: '自我介绍与背景确认',
        follow_up_count: 0,
        status: 'asked',
      },
    }

    const sessionAfterAnswer = {
      ...startedSession,
      current_turn_index: 2,
      turns: [
        {
          id: 101,
          turn_index: 1,
          round_index: 0,
          question: '你好，请先做一个和目标岗位最相关的自我介绍。',
          question_type: 'warmup',
          intent: '自我介绍与背景确认',
          answer: '我最近主要做前端性能优化和智能简历相关产品。',
          evaluation: '面试系统反馈：有直接回答问题，接下来可以再补一段更具体的项目结果。',
          follow_up_count: 0,
          status: 'done',
        },
        {
          id: 102,
          turn_index: 2,
          round_index: 0,
          question: '继续说一个你亲自负责并拿到明确结果的项目。',
          question_type: 'resume_deep_dive',
          intent: '项目深挖与个人贡献',
          follow_up_count: 0,
          status: 'asked',
        },
      ],
      current_turn: {
        id: 102,
        turn_index: 2,
        round_index: 0,
        question: '继续说一个你亲自负责并拿到明确结果的项目。',
        question_type: 'resume_deep_dive',
        intent: '项目深挖与个人贡献',
        follow_up_count: 0,
        status: 'asked',
      },
    }

    const completedSession = {
      ...sessionAfterAnswer,
      status: 'completed',
      ended_at: new Date().toISOString(),
      report_data: {
        summary: '这轮回答基本切题，但还需要补更多结果指标。',
        dimensions: [
          {
            title: '切题度',
            assessment: '回答能基本回应问题。',
            evidence: '第一题已经说明了近期方向。',
            advice: '下一轮先给结论再展开。',
          },
        ],
        recurring_issues: ['量化结果不足。'],
        next_training_plan: ['补充更明确的项目结果。'],
        resume_feedback: ['把项目成果补成数字。'],
      },
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
          session: {
            ...startedSession,
            status: 'interview_ready',
            turns: [],
            current_turn: null,
            current_turn_index: 0,
          },
          next_action: 'start',
        }),
      })
    })
    await page.route('**/api/interviews/1/start', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          session: startedSession,
          message: startedSession.current_turn.question,
          next_action: 'answer',
        }),
      })
    })
    await page.route('**/api/interviews/1/answer/stream', async (route) => {
      const body = [
        'data: {"type":"token","content":"继续说一个你亲自负责并拿到明确结果的项目。"}',
        '',
        'data: {"type":"evaluation","turn_id":101,"evaluation":"面试系统反馈：有直接回答问题，接下来可以再补一段更具体的项目结果。"}',
        '',
        `data: ${JSON.stringify({ type: 'done', next_action: 'next_question', message: sessionAfterAnswer.current_turn.question, session: sessionAfterAnswer }, null, 0)}`,
        '',
      ].join('\n')
      await route.fulfill({
        status: 200,
        contentType: 'text/event-stream',
        body,
      })
    })
    await page.route('**/api/interviews/1/end', async (route) => {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          session: completedSession,
          next_action: 'completed',
        }),
      })
    })

    await page.goto(`/resume/${resumeId}/interview`)
    await expect(page.getByText('你好，请先做一个和目标岗位最相关的自我介绍。')).toBeVisible()
    await page.getByPlaceholder('输入你的回答...').fill('我最近主要做前端性能优化和智能简历相关产品。')
    await page.getByRole('button', { name: '提交回答' }).click()
    await expect(page.getByText('面试系统反馈：有直接回答问题，接下来可以再补一段更具体的项目结果。')).toBeVisible()
    await expect(page.getByText('继续说一个你亲自负责并拿到明确结果的项目。')).toBeVisible()
    await page.getByRole('button', { name: '结束面试' }).click()
    await expect(page.getByText('面试报告')).toBeVisible()
    await expect(page.getByText('这轮回答基本切题，但还需要补更多结果指标。')).toBeVisible()
  })
})
