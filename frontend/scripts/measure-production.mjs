#!/usr/bin/env node
// 用于提供 measure-production.mjs 前端脚本逻辑。

import fs from 'node:fs/promises'
import { performance } from 'node:perf_hooks'
import { chromium } from '@playwright/test'

const DEFAULT_FRONTEND_URL = 'http://localhost:3000'
const DEFAULT_API_URL = 'http://localhost:8000'
const DEFAULT_PASSWORD = 'password123'
const DEFAULT_RUNS = 3
const DEFAULT_TIMEOUT_MS = 20000
const BENCHMARK_RESUME_TITLE = '性能测速基准简历'

// 用于处理printhelp。
function printHelp() {
  console.log(`
用法:
  npm run perf:prod -- --frontend-url http://localhost:3000 --api-url http://localhost:8000

可选参数:
  --frontend-url <url>   前端地址，默认 ${DEFAULT_FRONTEND_URL}
  --api-url <url>        后端 API 地址，默认 ${DEFAULT_API_URL}
  --email <email>        测速账号邮箱，默认自动生成
  --password <password>  测速账号密码，默认 ${DEFAULT_PASSWORD}
  --runs <n>             每个页面 / 接口重复次数，默认 ${DEFAULT_RUNS}
  --timeout-ms <ms>      单次请求 / 页面等待超时，默认 ${DEFAULT_TIMEOUT_MS}
  --headed               以有界面浏览器运行
  --output <file>        将完整结果输出为 JSON 文件
  --help                 显示帮助

说明:
  1. 这个脚本假设前后端已经以“生产模式”启动。
  2. 它会自动注册 / 登录测速账号，准备一份简历和一个面试 session。
  3. 输出会同时包含 API 探针和真实浏览器页面测速。
`)
}

// 用于处理parseargs。
function parseArgs(argv) {
  const args = {
    frontendUrl: DEFAULT_FRONTEND_URL,
    apiUrl: DEFAULT_API_URL,
    email: `perf_${Date.now()}@example.com`,
    password: DEFAULT_PASSWORD,
    runs: DEFAULT_RUNS,
    timeoutMs: DEFAULT_TIMEOUT_MS,
    headed: false,
    output: '',
    help: false,
  }

  for (let i = 0; i < argv.length; i += 1) {
    const arg = argv[i]
    if (arg === '--frontend-url') args.frontendUrl = argv[++i]
    else if (arg === '--api-url') args.apiUrl = argv[++i]
    else if (arg === '--email') args.email = argv[++i]
    else if (arg === '--password') args.password = argv[++i]
    else if (arg === '--runs') args.runs = Number(argv[++i] || DEFAULT_RUNS)
    else if (arg === '--timeout-ms') args.timeoutMs = Number(argv[++i] || DEFAULT_TIMEOUT_MS)
    else if (arg === '--output') args.output = argv[++i] || ''
    else if (arg === '--headed') args.headed = true
    else if (arg === '--help' || arg === '-h') args.help = true
    else throw new Error(`未知参数: ${arg}`)
  }

  args.frontendUrl = args.frontendUrl.replace(/\/$/, '')
  args.apiUrl = args.apiUrl.replace(/\/$/, '')
  args.runs = Number.isFinite(args.runs) && args.runs > 0 ? Math.floor(args.runs) : DEFAULT_RUNS
  args.timeoutMs = Number.isFinite(args.timeoutMs) && args.timeoutMs > 0 ? Math.floor(args.timeoutMs) : DEFAULT_TIMEOUT_MS

  return args
}

// 用于处理sleep。
function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms))
}

// 用于处理avg。
function avg(values) {
  if (!values.length) return 0
  return values.reduce((sum, value) => sum + value, 0) / values.length
}

// 用于处理percentile。
function percentile(values, p) {
  if (!values.length) return 0
  const sorted = [...values].sort((a, b) => a - b)
  const index = Math.min(sorted.length - 1, Math.max(0, Math.ceil((p / 100) * sorted.length) - 1))
  return sorted[index]
}

// 用于处理summarize。
function summarize(values) {
  return {
    count: values.length,
    minMs: values.length ? Math.min(...values) : 0,
    avgMs: avg(values),
    p95Ms: percentile(values, 95),
    maxMs: values.length ? Math.max(...values) : 0,
  }
}

// 用于处理formatms。
function formatMs(value) {
  return `${value.toFixed(1)} ms`
}

// 用于处理shortpath。
function shortPath(urlString) {
  try {
    const url = new URL(urlString)
    return `${url.pathname}${url.search}`
  } catch {
    return urlString
  }
}

// Split a combined Set-Cookie header without breaking Expires-style commas.
// 用于处理splitsetcookieheader。
function splitSetCookieHeader(headerValue) {
  if (!headerValue) return []
  return headerValue
    .split(/,(?=\s*[^;,=\s]+=)/)
    .map((value) => value.trim())
    .filter(Boolean)
}

// Read Set-Cookie values across Node versions.
// 用于获取setcookieheaders。
function getSetCookieHeaders(response) {
  if (typeof response.headers.getSetCookie === 'function') {
    return response.headers.getSetCookie()
  }
  return splitSetCookieHeader(response.headers.get('set-cookie'))
}

// Keep backend HttpOnly session cookies available to API and browser probes.
// 用于创建cookiejar。
function createCookieJar() {
  const cookies = new Map()

  return {
    // 用于处理capture。
    capture(response) {
      for (const headerValue of getSetCookieHeaders(response)) {
        const [cookiePair, ...attributes] = headerValue
          .split(';')
          .map((part) => part.trim())
        const separatorIndex = cookiePair.indexOf('=')
        if (separatorIndex <= 0) continue

        const name = cookiePair.slice(0, separatorIndex)
        const value = cookiePair.slice(separatorIndex + 1)
        const cookie = {
          name,
          value,
          path: '/',
          httpOnly: false,
          secure: false,
          sameSite: 'Lax',
        }

        for (const attribute of attributes) {
          const [rawKey, ...rawValueParts] = attribute.split('=')
          const key = rawKey.toLowerCase()
          const rawValue = rawValueParts.join('=')
          if (key === 'path' && rawValue) cookie.path = rawValue
          else if (key === 'httponly') cookie.httpOnly = true
          else if (key === 'secure') cookie.secure = true
          else if (key === 'samesite' && rawValue) {
            const normalized = rawValue.toLowerCase()
            if (normalized === 'strict') cookie.sameSite = 'Strict'
            else if (normalized === 'none') cookie.sameSite = 'None'
            else cookie.sameSite = 'Lax'
          }
        }

        if (!value) cookies.delete(name)
        else cookies.set(name, cookie)
      }
    },

    // 用于处理header。
    header() {
      return [...cookies.values()]
        .map((cookie) => `${cookie.name}=${cookie.value}`)
        .join('; ')
    },

    // 用于处理browsercookies。
    browserCookies(urls) {
      const result = []
      const seen = new Set()
      for (const url of urls) {
        for (const cookie of cookies.values()) {
          const hostname = new URL(url).hostname
          const key = `${hostname}:${cookie.name}`
          if (seen.has(key)) continue
          seen.add(key)
          result.push({
            name: cookie.name,
            value: cookie.value,
            url,
            httpOnly: cookie.httpOnly,
            secure: cookie.secure,
            sameSite: cookie.sameSite,
          })
        }
      }
      return result
    },
  }
}

// 用于处理请求json。
async function requestJson(
  baseUrl,
  path,
  {
    method = 'GET',
    token = '',
    body,
    headers = {},
    timeoutMs = DEFAULT_TIMEOUT_MS,
    cookieJar = null,
  } = {},
) {
  const url = path.startsWith('http') ? path : `${baseUrl}${path}`
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  const startedAt = performance.now()
  const cookieHeader = cookieJar?.header() || ''

  try {
    const response = await fetch(url, {
      method,
      headers: {
        ...(body ? { 'Content-Type': 'application/json' } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
        ...(cookieHeader ? { Cookie: cookieHeader } : {}),
        ...headers,
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    })
    cookieJar?.capture(response)
    const elapsedMs = performance.now() - startedAt
    const text = await response.text()
    let data = null

    try {
      data = text ? JSON.parse(text) : null
    } catch {
      data = text
    }

    if (!response.ok) {
      const detail = typeof data === 'object' && data && 'detail' in data ? data.detail : text
      const error = new Error(`${method} ${path} failed (${response.status}): ${detail || 'unknown error'}`)
      error.status = response.status
      error.data = data
      throw error
    }

    return { data, elapsedMs, status: response.status }
  } finally {
    clearTimeout(timeout)
  }
}

// 用于处理请求form。
async function requestForm(
  baseUrl,
  path,
  formBody,
  { timeoutMs = DEFAULT_TIMEOUT_MS, cookieJar = null } = {},
) {
  const controller = new AbortController()
  const timeout = setTimeout(() => controller.abort(), timeoutMs)
  const startedAt = performance.now()
  const cookieHeader = cookieJar?.header() || ''

  try {
    const response = await fetch(`${baseUrl}${path}`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        ...(cookieHeader ? { Cookie: cookieHeader } : {}),
      },
      body: new URLSearchParams(formBody),
      signal: controller.signal,
    })
    cookieJar?.capture(response)
    const elapsedMs = performance.now() - startedAt
    const text = await response.text()
    let data = null

    try {
      data = text ? JSON.parse(text) : null
    } catch {
      data = text
    }

    if (!response.ok) {
      const detail = typeof data === 'object' && data && 'detail' in data ? data.detail : text
      const error = new Error(`POST ${path} failed (${response.status}): ${detail || 'unknown error'}`)
      error.status = response.status
      error.data = data
      throw error
    }

    return { data, elapsedMs, status: response.status }
  } finally {
    clearTimeout(timeout)
  }
}

// 用于处理buildseed简历content。
function buildSeedResumeContent(email) {
  return {
    job_application: {
      target_company: '性能测试科技',
      target_title: '全栈工程师',
      jd_text: '负责 Web 产品开发、性能优化与工程质量建设。',
      strategy: '突出性能优化、全栈交付与工程效率提升。',
    },
    personal_info: {
      name: '性能测试用户',
      email,
      phone: '13800000000',
      position: '全栈工程师',
      github: 'https://github.com/example/perf-user',
    },
    summary: {
      text: '关注页面性能、接口延迟与工程可维护性的全栈工程师。',
    },
    education: [
      {
        school: '性能大学',
        major: '计算机科学与技术',
        degree: '本科',
        duration: '2016 - 2020',
      },
    ],
    work_experience: [
      {
        company: '极限速度科技',
        position: '高级前端工程师',
        duration: '2022 - 至今',
        highlights: [
          { text: '将核心页面首屏可交互时间缩短 35%。' },
          { text: '推动列表页接口合并，减少 N+1 请求。' },
        ],
      },
    ],
    skills: [
      {
        category: '前端',
        items: ['React', 'Next.js', 'TypeScript'],
      },
      {
        category: '后端',
        items: ['FastAPI', 'PostgreSQL', 'Redis'],
      },
    ],
    projects: [
      {
        name: '性能分析平台',
        overview: '统一采集页面与接口耗时，支持性能回归分析。',
        role: '负责人',
        duration: '2023 - 2024',
        highlights: [
          { text: '搭建浏览器和接口双视角的性能看板。' },
          { text: '让线上性能回归定位时间缩短 60%。' },
        ],
      },
    ],
  }
}

// 用于处理ensure用户。
async function ensureUser(config, cookieJar) {
  try {
    await requestJson(config.apiUrl, '/api/auth/register', {
      method: 'POST',
      body: {
        email: config.email,
        password: config.password,
        full_name: '性能测速用户',
      },
      timeoutMs: config.timeoutMs,
      cookieJar,
    })
  } catch (error) {
    if (error.status !== 400) throw error
  }

  const login = await requestForm(
    config.apiUrl,
    '/api/auth/login',
    { username: config.email, password: config.password },
    { timeoutMs: config.timeoutMs, cookieJar },
  )
  return login.data
}

// 用于处理ensure简历。
async function ensureResume(config, cookieJar) {
  const list = await requestJson(config.apiUrl, '/api/resumes/', {
    timeoutMs: config.timeoutMs,
    cookieJar,
  })
  const existing = Array.isArray(list.data)
    ? list.data.find((item) => item.title === BENCHMARK_RESUME_TITLE)
    : null

  if (existing) return existing

  const created = await requestJson(config.apiUrl, '/api/resumes/', {
    method: 'POST',
    body: {
      title: BENCHMARK_RESUME_TITLE,
      content: buildSeedResumeContent(config.email),
    },
    timeoutMs: config.timeoutMs,
    cookieJar,
  })
  return created.data
}

// 用于处理ensureinterview会话。
async function ensureInterviewSession(config, cookieJar, resume) {
  const list = await requestJson(config.apiUrl, '/api/interviews/', {
    timeoutMs: config.timeoutMs,
    cookieJar,
  })

  const existing = Array.isArray(list.data)
    ? list.data.find((item) => item.resume_id === resume.id)
    : null

  if (existing) {
    if (existing.status === 'completed') {
      return {
        sessionId: existing.id,
        routeReady: true,
        note: '复用已完成面试 session。',
      }
    }

    try {
      await requestJson(config.apiUrl, `/api/interviews/${existing.id}/start`, {
        method: 'POST',
        timeoutMs: config.timeoutMs,
        cookieJar,
      })
      return {
        sessionId: existing.id,
        routeReady: true,
        note: '复用已有面试 session，并已成功启动。',
      }
    } catch (error) {
      return {
        sessionId: existing.id,
        routeReady: false,
        note: `复用已有面试 session，但启动失败，已跳过面试工作台测速。原因: ${error.message}`,
      }
    }
  }

  let created
  try {
    created = await requestJson(config.apiUrl, '/api/interviews/', {
      method: 'POST',
      body: {
        resume_id: resume.id,
        target_title: resume.target_title || '全栈工程师',
        target_company: resume.target_company || '性能测试科技',
        jd_text: '负责 Web 产品开发、性能优化与工程质量建设。',
        interview_type: 'general',
        difficulty: 'medium',
        language: 'zh-CN',
        mode: 'text',
      },
      timeoutMs: config.timeoutMs,
      cookieJar,
    })
  } catch (error) {
    if (error.status === 403) {
      return {
        sessionId: null,
        routeReady: false,
        note: `测速账号没有面试权限，已跳过面试工作台测速。原因: ${error.message}`,
      }
    }
    throw error
  }

  const createdSession = created.data?.session
  if (!createdSession?.id) {
    return {
      sessionId: null,
      routeReady: false,
      note: '创建面试 session 成功，但响应里没有 session id，已跳过面试工作台测速。',
    }
  }

  try {
    await requestJson(config.apiUrl, `/api/interviews/${createdSession.id}/start`, {
      method: 'POST',
      timeoutMs: config.timeoutMs,
      cookieJar,
    })
    return {
      sessionId: createdSession.id,
      routeReady: true,
      note: '已创建并启动新的面试 session。',
    }
  } catch (error) {
    return {
      sessionId: createdSession.id,
      routeReady: false,
      note: `面试 session 已创建，但启动失败，已跳过面试工作台测速。原因: ${error.message}`,
    }
  }
}

// 用于测量APIprobe。
async function measureApiProbe(config, cookieJar, probe) {
  const samples = []

  for (let i = 0; i < config.runs; i += 1) {
    const result = await requestJson(config.apiUrl, probe.path, {
      timeoutMs: config.timeoutMs,
      cookieJar,
    })
    samples.push(result.elapsedMs)
    await sleep(200)
  }

  return {
    ...probe,
    samplesMs: samples,
    summary: summarize(samples),
  }
}

// 用于处理buildstoragescript。
function buildStorageScript(authState) {
  return ({ user }) => {
    localStorage.setItem('auth_user', JSON.stringify(user))
  }
}

// 用于测量browserroute。
async function measureBrowserRoute(browser, config, authState, cookieJar, routeConfig) {
  const samples = []
  const url = `${config.frontendUrl}${routeConfig.path}`

  for (let i = 0; i < config.runs; i += 1) {
    const context = await browser.newContext()
    await context.addInitScript(buildStorageScript(authState), authState)
    await context.addCookies(cookieJar.browserCookies([config.frontendUrl, config.apiUrl]))

    const page = await context.newPage()
    const startedAt = performance.now()

    try {
      await page.goto(url, {
        waitUntil: 'domcontentloaded',
        timeout: config.timeoutMs,
      })
      await page.waitForSelector(routeConfig.readySelector, {
        timeout: config.timeoutMs,
      })
      await page.waitForLoadState('networkidle', { timeout: 5000 }).catch(() => {})

      const wallMs = performance.now() - startedAt
      const navigation = await page.evaluate(() => {
        const entry = performance.getEntriesByType('navigation')[0]
        if (!entry) return null
        return {
          responseStart: entry.responseStart,
          domContentLoaded: entry.domContentLoadedEventEnd,
          loadEventEnd: entry.loadEventEnd,
          transferSize: entry.transferSize || 0,
        }
      })
      const resources = await page.evaluate((apiBase) => {
        return performance
          .getEntriesByType('resource')
          .filter((entry) => entry.name.startsWith(apiBase))
          .map((entry) => ({
            name: entry.name,
            initiatorType: entry.initiatorType,
            duration: entry.duration,
            transferSize: entry.transferSize || 0,
          }))
      }, config.apiUrl)

      const apiDurations = resources.map((entry) => entry.duration)
      const slowestApi = [...resources]
        .sort((a, b) => b.duration - a.duration)
        .slice(0, 5)
        .map((entry) => ({
          path: shortPath(entry.name),
          durationMs: entry.duration,
        }))

      samples.push({
        run: i + 1,
        wallMs,
        navigation,
        apiRequestCount: resources.length,
        apiSummary: summarize(apiDurations),
        slowestApi,
      })
    } finally {
      await context.close()
    }
  }

  return {
    ...routeConfig,
    url,
    samples,
    summary: summarize(samples.map((sample) => sample.wallMs)),
  }
}

// 用于处理printAPIsection。
function printApiSection(results) {
  console.log('\n=== API 探针 ===')
  for (const result of results) {
    console.log(
      `- ${result.name}: avg ${formatMs(result.summary.avgMs)}, p95 ${formatMs(result.summary.p95Ms)}, max ${formatMs(result.summary.maxMs)}`
    )
  }
}

// 用于处理printbrowsersection。
function printBrowserSection(results) {
  console.log('\n=== 浏览器页面测速 ===')
  for (const result of results) {
    console.log(
      `- ${result.name}: avg ${formatMs(result.summary.avgMs)}, p95 ${formatMs(result.summary.p95Ms)}, max ${formatMs(result.summary.maxMs)}`
    )

    const firstSample = result.samples[0]
    if (firstSample?.navigation) {
      console.log(
        `  首次样本: TTFB ${formatMs(firstSample.navigation.responseStart)}, DOMContentLoaded ${formatMs(firstSample.navigation.domContentLoaded)}, load ${formatMs(firstSample.navigation.loadEventEnd)}`
      )
    }

    if (firstSample?.slowestApi?.length) {
      console.log(`  首次样本最慢接口:`)
      for (const entry of firstSample.slowestApi.slice(0, 3)) {
        console.log(`    ${entry.path}: ${formatMs(entry.durationMs)}`)
      }
    }
  }
}

// 用于执行当前数据。
async function main() {
  const config = parseArgs(process.argv.slice(2))
  if (config.help) {
    printHelp()
    return
  }

  console.log(`前端地址: ${config.frontendUrl}`)
  console.log(`后端地址: ${config.apiUrl}`)
  console.log(`测速账号: ${config.email}`)
  console.log(`重复次数: ${config.runs}`)

  const cookieJar = createCookieJar()
  const login = await ensureUser(config, cookieJar)
  const authState = {
    user: login.user,
  }

  const resume = await ensureResume(config, cookieJar)
  const interviewSetup = await ensureInterviewSession(config, cookieJar, resume)

  console.log(`基准简历 ID: ${resume.id}`)
  console.log(interviewSetup.note)

  const apiProbes = [
    { name: 'GET /api/auth/me', path: '/api/auth/me' },
    { name: 'GET /api/resumes/', path: '/api/resumes/' },
    { name: `GET /api/resumes/${resume.id}`, path: `/api/resumes/${resume.id}` },
    { name: 'GET /api/interviews/', path: '/api/interviews/' },
  ]

  if (interviewSetup.sessionId) {
    apiProbes.push({
      name: `GET /api/interviews/${interviewSetup.sessionId}`,
      path: `/api/interviews/${interviewSetup.sessionId}`,
    })
  }

  const apiResults = []
  for (const probe of apiProbes) {
    apiResults.push(await measureApiProbe(config, cookieJar, probe))
  }

  let browser
  try {
    browser = await chromium.launch({ headless: !config.headed })
  } catch (error) {
    if (String(error.message || error).includes('Executable doesn\'t exist')) {
      throw new Error('Playwright 浏览器未安装。先在 frontend/ 下运行: npx playwright install chromium')
    }
    throw error
  }

  try {
    const browserRoutes = [
      {
        name: '简历中心',
        path: '/resumes',
        readySelector: 'text=简历中心',
      },
      {
        name: '面试中心',
        path: '/interviews',
        readySelector: 'text=面试中心',
      },
      {
        name: '简历编辑页',
        path: `/resume/${resume.id}/edit`,
        readySelector: 'text=导出 PDF',
      },
    ]

    if (interviewSetup.sessionId && interviewSetup.routeReady) {
      browserRoutes.push({
        name: '面试工作台',
        path: `/resume/${resume.id}/interview?session=${interviewSetup.sessionId}`,
        readySelector: 'text=结束面试',
      })
    }

    const browserResults = []
    for (const route of browserRoutes) {
      browserResults.push(await measureBrowserRoute(browser, config, authState, cookieJar, route))
    }

    printApiSection(apiResults)
    printBrowserSection(browserResults)

    const report = {
      generatedAt: new Date().toISOString(),
      config: {
        frontendUrl: config.frontendUrl,
        apiUrl: config.apiUrl,
        runs: config.runs,
        timeoutMs: config.timeoutMs,
      },
      benchmarkData: {
        userEmail: config.email,
        resumeId: resume.id,
        interviewSessionId: interviewSetup.sessionId,
      },
      apiResults,
      browserResults,
    }

    if (config.output) {
      await fs.writeFile(config.output, JSON.stringify(report, null, 2), 'utf8')
      console.log(`\n完整 JSON 报告已写入: ${config.output}`)
    }
  } finally {
    await browser?.close()
  }
}

main().catch((error) => {
  console.error('\n测速失败:')
  console.error(error?.stack || String(error))
  process.exitCode = 1
})
