import type {
  CustomSection,
  Education,
  JobApplication,
  Language,
  PersonalInfo,
  Project,
  ResumeContent,
  ResumeHighlight,
  ResumeLink,
  ResumeMeta,
  Skill,
  Summary,
  WorkExperience,
} from '@/types/resume'

// 简历内容接口定义
export interface Resume {
  id: number
  title: string
  content: ResumeContent
  layout_config?: Record<string, unknown> | null
  original_filename?: string
  owner_id: number
  created_at: string
  updated_at?: string
}

export interface ResumeListItem {
  id: number
  title: string
  original_filename?: string
  owner_id: number
  created_at: string
  updated_at?: string
  target_company?: string
  target_title?: string
  preview_content?: Partial<ResumeContent>
}

interface CreateResumeData {
  title: string
  content: ResumeContent
}

interface UpdateResumeData {
  title?: string
  content?: ResumeContent
}

interface ExportResponse {
  download_url: string
  filename: string
  format: string
}

interface JDOcrResponse {
  text: string
}

interface InterviewTurn {
  id: number
  turn_index: number
  round_index: number
  question: string
  question_type: string
  intent?: string
  expected_points?: string[]
  answer?: string
  evaluation?: string
  follow_up_count: number
  status: string
}

interface InterviewReportDimension {
  title: string
  assessment: string
  evidence: string
  advice: string
}

interface InterviewSession {
  id: number
  resume_id: number
  target_title?: string
  target_company?: string
  jd_text?: string
  interview_type: string
  difficulty: string
  language: string
  mode: string
  status: string
  current_round_index: number
  current_turn_index: number
  plan?: {
    rounds?: Array<{ type: string; goal: string }>
  }
  started_at?: string
  ended_at?: string
  report_data?: {
    summary?: string
    strengths?: string[]
    dimensions?: InterviewReportDimension[]
    recurring_issues?: string[]
    weaknesses?: string[]
    next_training_plan?: string[]
    resume_feedback?: string[]
  }
  turns: InterviewTurn[]
  current_turn?: InterviewTurn | null
}

interface InterviewSessionSummary {
  id: number
  resume_id: number
  target_title?: string
  target_company?: string
  interview_type: string
  difficulty: string
  language: string
  mode: string
  status: string
  started_at?: string
  ended_at?: string
  answered_turn_count: number
}

interface InterviewActionResponse {
  session: InterviewSession
  message?: string
  evaluation?: InterviewTurn['evaluation']
  next_action?: string
}

interface InterviewHintResponse {
  hints: string[]
}

interface InterviewStreamTokenEvent {
  type: 'token'
  content: string
}

interface InterviewStreamEvaluationEvent {
  type: 'evaluation'
  turn_id: number
  evaluation: string
}

interface InterviewStreamDoneEvent extends InterviewActionResponse {
  type: 'done'
}

interface DigitalHumanConversation {
  provider: 'tavus' | 'liveavatar' | 'volcengine'
  conversation_id?: string
  conversation_url?: string
  join_url?: string
  session_id?: string
  session_token?: string
  status: string
  meeting_token?: string | null
}

// API基础URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// 统一通过 HttpOnly Cookie 发起带登录态的请求。
function apiFetch(path: string, init: RequestInit = {}) {
  return fetch(`${API_BASE_URL}${path}`, {
    ...init,
    credentials: 'include',
  })
}

// 给外部供应商代理请求设置前端超时，避免 UI 长时间停在连接中。
async function fetchWithTimeout(
  path: string,
  init: RequestInit = {},
  timeoutMs = 45000,
) {
  const controller = new AbortController()
  const timeoutId = window.setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await apiFetch(path, { ...init, signal: controller.signal })
  } finally {
    window.clearTimeout(timeoutId)
  }
}

// 处理API响应
async function handleApiResponse<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    throw new Error(errorData.detail || `API请求失败: ${response.status}`)
  }
  
  return response.json()
}

// 简历API类
class ResumeAPI {
  /**
   * 获取所有简历
   */
  static async getResumes(): Promise<ResumeListItem[]> {
    const response = await apiFetch('/api/resumes/')

    return handleApiResponse<ResumeListItem[]>(response)
  }

  /**
   * 获取单个简历
   */
  static async getResume(id: number): Promise<Resume> {
    const response = await apiFetch(`/api/resumes/${id}`)

    return handleApiResponse<Resume>(response)
  }

  /**
   * 创建新简历
   */
  static async createResume(data: CreateResumeData): Promise<Resume> {
    const response = await apiFetch('/api/resumes/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    })

    return handleApiResponse<Resume>(response)
  }

  /**
   * 更新简历
   */
  static async updateResume(id: number, data: UpdateResumeData): Promise<Resume> {
    const response = await apiFetch(`/api/resumes/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    })

    return handleApiResponse<Resume>(response)
  }

  /**
   * 删除简历
   */
  static async deleteResume(id: number): Promise<void> {
    const response = await apiFetch(`/api/resumes/${id}`, {
      method: 'DELETE',
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `删除简历失败: ${response.status}`)
    }
  }

  /**
   * 上传简历文件
   */
  static async uploadResume(file: File): Promise<Resume> {
    const formData = new FormData()
    formData.append('file', file)

    const response = await apiFetch('/api/upload/resume', {
      method: 'POST',
      body: formData,
    })

    return handleApiResponse<Resume>(response)
  }

  /**
   * 识别 JD 图片中的文字
   */
  static async ocrJobDescriptionImage(file: File): Promise<JDOcrResponse> {
    const formData = new FormData()
    formData.append('file', file)

    const response = await apiFetch('/api/upload/jd-ocr', {
      method: 'POST',
      body: formData,
    })

    return handleApiResponse<JDOcrResponse>(response)
  }

  /**
   * 导出简历
   */
  static async exportResume(
    id: number,
    format: 'pdf' | 'docx' | 'html',
    template: string = 'default'
  ): Promise<ExportResponse> {
    const response = await apiFetch(`/api/resumes/${id}/export`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        format,
        template,
      }),
    })

    return handleApiResponse<ExportResponse>(response)
  }

  static async listInterviewSessions(): Promise<InterviewSessionSummary[]> {
    const response = await apiFetch('/api/interviews/')
    return handleApiResponse<InterviewSessionSummary[]>(response)
  }

  /**
   * 删除一条面试记录
   */
  static async deleteInterviewSession(sessionId: number): Promise<void> {
    const response = await apiFetch(`/api/interviews/${sessionId}`, {
      method: 'DELETE',
    })
    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `删除面试记录失败: ${response.status}`)
    }
  }

  static async createInterviewSession(data: {
    resume_id: number
    target_title?: string
    target_company?: string
    jd_text?: string
    interview_type?: string
    difficulty?: string
    language?: string
    mode?: string
  }): Promise<InterviewActionResponse> {
    const response = await apiFetch('/api/interviews/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    })
    return handleApiResponse<InterviewActionResponse>(response)
  }

  /**
   * 获取练习模式下当前题目的答题提示
   */
  static async getInterviewHint(sessionId: number): Promise<InterviewHintResponse> {
    const response = await apiFetch(`/api/interviews/${sessionId}/hint`, {
      method: 'POST',
    })
    return handleApiResponse<InterviewHintResponse>(response)
  }

  static async getInterviewSession(sessionId: number): Promise<InterviewActionResponse> {
    const response = await apiFetch(`/api/interviews/${sessionId}`)
    return handleApiResponse<InterviewActionResponse>(response)
  }

  static async startInterviewSession(sessionId: number): Promise<InterviewActionResponse> {
    const response = await apiFetch(`/api/interviews/${sessionId}/start`, {
      method: 'POST',
    })
    return handleApiResponse<InterviewActionResponse>(response)
  }

  static async answerInterviewSession(sessionId: number, answer: string): Promise<InterviewActionResponse> {
    const response = await apiFetch(`/api/interviews/${sessionId}/answer`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ answer }),
    })
    return handleApiResponse<InterviewActionResponse>(response)
  }

  static async *answerInterviewSessionStream(
    sessionId: number,
    answer: string,
  ): AsyncGenerator<InterviewStreamTokenEvent | InterviewStreamEvaluationEvent | InterviewStreamDoneEvent> {
    const response = await apiFetch(`/api/interviews/${sessionId}/answer/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ answer }),
    })
    if (!response.ok) {
      const text = await response.text().catch(() => '')
      throw new Error(text || `请求失败 (${response.status})`)
    }
    const reader = response.body!.getReader()
    const decoder = new TextDecoder()
    let buf = ''
    while (true) {
      const { done, value } = await reader.read()
      if (done) break
      buf += decoder.decode(value, { stream: true })
      const lines = buf.split('\n')
      buf = lines.pop() ?? ''
      for (const line of lines) {
        if (!line.startsWith('data: ')) continue
        try {
          yield JSON.parse(line.slice(6))
        } catch {}
      }
    }
  }

  static async endInterviewSession(sessionId: number): Promise<InterviewActionResponse> {
    const response = await apiFetch(`/api/interviews/${sessionId}/end`, {
      method: 'POST',
    })
    return handleApiResponse<InterviewActionResponse>(response)
  }
}

class DigitalHumanAPI {
  /**
   * 为结构化面试创建真实数字人视频会话。
   */
  static async createConversation(interviewSessionId: number): Promise<DigitalHumanConversation> {
    const response = await fetchWithTimeout('/api/digital-human/conversations', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ interview_session_id: interviewSessionId }),
    })
    return handleApiResponse<DigitalHumanConversation>(response)
  }

  /**
   * 结束供应商侧数字人会话，避免持续占用分钟数。
   */
  static async endConversation(conversationId: string): Promise<void> {
    const response = await apiFetch('/api/digital-human/conversations/end', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ conversation_id: conversationId }),
    })
    await handleApiResponse<{ message: string }>(response)
  }
}

// ── 聊天记录 API ──────────────────────────────────────────────────────────────

export interface ChatMessageRecord {
  id: number
  role: 'user' | 'assistant'
  content: string
  stream_events?: Array<{ type: string; [key: string]: unknown }> | null
}

export class ChatHistoryAPI {
  static async getMessages(resumeId: number): Promise<ChatMessageRecord[]> {
    const res = await apiFetch(`/api/resumes/${resumeId}/chat-messages`)
    return handleApiResponse<ChatMessageRecord[]>(res)
  }

  static async appendMessages(
    resumeId: number,
    messages: { role: string; content: string; stream_events?: unknown }[]
  ): Promise<ChatMessageRecord[]> {
    const res = await apiFetch(`/api/resumes/${resumeId}/chat-messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(messages),
    })
    return handleApiResponse<ChatMessageRecord[]>(res)
  }

  static async clearMessages(resumeId: number): Promise<void> {
    const res = await apiFetch(`/api/resumes/${resumeId}/chat-messages`, {
      method: 'DELETE',
    })
    await handleApiResponse<{ message: string }>(res)
  }
}

// 导出API实例
export const resumeApi = ResumeAPI
export const chatHistoryApi = ChatHistoryAPI
export const digitalHumanApi = DigitalHumanAPI

// 导出类型
export type {
  DigitalHumanConversation,
  ResumeContent,
  InterviewActionResponse,
  InterviewHintResponse,
  InterviewSession,
  InterviewSessionSummary,
  InterviewTurn,
  PersonalInfo,
  Education,
  WorkExperience,
  Skill,
  Project,
  CreateResumeData,
  UpdateResumeData,
}
