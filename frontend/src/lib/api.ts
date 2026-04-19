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
interface Resume {
  id: number
  title: string
  content: ResumeContent
  layout_config?: Record<string, unknown> | null
  original_filename?: string
  owner_id: number
  created_at: string
  updated_at?: string
}

interface ResumeListItem {
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
    weaknesses?: string[]
    next_training_plan?: string[]
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

// API基础URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// 获取认证头部信息
function getAuthHeaders(): Record<string, string> {
  const token = localStorage.getItem('access_token')
  return token ? { Authorization: `Bearer ${token}` } : {}
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
    const response = await fetch(`${API_BASE_URL}/api/resumes/`, {
      headers: {
        ...getAuthHeaders(),
      },
    })

    return handleApiResponse<ResumeListItem[]>(response)
  }

  /**
   * 获取单个简历
   */
  static async getResume(id: number): Promise<Resume> {
    const response = await fetch(`${API_BASE_URL}/api/resumes/${id}`, {
      headers: {
        ...getAuthHeaders(),
      },
    })

    return handleApiResponse<Resume>(response)
  }

  /**
   * 创建新简历
   */
  static async createResume(data: CreateResumeData): Promise<Resume> {
    const response = await fetch(`${API_BASE_URL}/api/resumes/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify(data),
    })

    return handleApiResponse<Resume>(response)
  }

  /**
   * 更新简历
   */
  static async updateResume(id: number, data: UpdateResumeData): Promise<Resume> {
    const response = await fetch(`${API_BASE_URL}/api/resumes/${id}`, {
      method: 'PUT',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify(data),
    })

    return handleApiResponse<Resume>(response)
  }

  /**
   * 删除简历
   */
  static async deleteResume(id: number): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/resumes/${id}`, {
      method: 'DELETE',
      headers: {
        ...getAuthHeaders(),
      },
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

    const response = await fetch(`${API_BASE_URL}/api/upload/resume`, {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
      },
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

    const response = await fetch(`${API_BASE_URL}/api/upload/jd-ocr`, {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
      },
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
    const response = await fetch(`${API_BASE_URL}/api/resumes/${id}/export`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify({
        format,
        template,
      }),
    })

    return handleApiResponse<ExportResponse>(response)
  }

  static async listInterviewSessions(): Promise<InterviewSessionSummary[]> {
    const response = await fetch(`${API_BASE_URL}/api/interviews/`, {
      headers: { ...getAuthHeaders() },
    })
    return handleApiResponse<InterviewSessionSummary[]>(response)
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
    const response = await fetch(`${API_BASE_URL}/api/interviews/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify(data),
    })
    return handleApiResponse<InterviewActionResponse>(response)
  }

  /**
   * 获取练习模式下当前题目的答题提示
   */
  static async getInterviewHint(sessionId: number): Promise<InterviewHintResponse> {
    const response = await fetch(`${API_BASE_URL}/api/interviews/${sessionId}/hint`, {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
      },
    })
    return handleApiResponse<InterviewHintResponse>(response)
  }

  static async getInterviewSession(sessionId: number): Promise<InterviewActionResponse> {
    const response = await fetch(`${API_BASE_URL}/api/interviews/${sessionId}`, {
      headers: {
        ...getAuthHeaders(),
      },
    })
    return handleApiResponse<InterviewActionResponse>(response)
  }

  static async startInterviewSession(sessionId: number): Promise<InterviewActionResponse> {
    const response = await fetch(`${API_BASE_URL}/api/interviews/${sessionId}/start`, {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
      },
    })
    return handleApiResponse<InterviewActionResponse>(response)
  }

  static async answerInterviewSession(sessionId: number, answer: string): Promise<InterviewActionResponse> {
    const response = await fetch(`${API_BASE_URL}/api/interviews/${sessionId}/answer`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
      },
      body: JSON.stringify({ answer }),
    })
    return handleApiResponse<InterviewActionResponse>(response)
  }

  static async *answerInterviewSessionStream(
    sessionId: number,
    answer: string,
  ): AsyncGenerator<{ type: 'token'; content: string } | { type: 'done' } & InterviewActionResponse> {
    const response = await fetch(`${API_BASE_URL}/api/interviews/${sessionId}/answer/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders(),
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
    const response = await fetch(`${API_BASE_URL}/api/interviews/${sessionId}/end`, {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
      },
    })
    return handleApiResponse<InterviewActionResponse>(response)
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
    const token = localStorage.getItem('access_token')
    const res = await fetch(`${API_BASE_URL}/api/resumes/${resumeId}/chat-messages`, {
      headers: { Authorization: `Bearer ${token}` },
    })
    return handleApiResponse<ChatMessageRecord[]>(res)
  }

  static async appendMessages(
    resumeId: number,
    messages: { role: string; content: string; stream_events?: unknown }[]
  ): Promise<ChatMessageRecord[]> {
    const token = localStorage.getItem('access_token')
    const res = await fetch(`${API_BASE_URL}/api/resumes/${resumeId}/chat-messages`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
      body: JSON.stringify(messages),
    })
    return handleApiResponse<ChatMessageRecord[]>(res)
  }

  static async clearMessages(resumeId: number): Promise<void> {
    const token = localStorage.getItem('access_token')
    const res = await fetch(`${API_BASE_URL}/api/resumes/${resumeId}/chat-messages`, {
      method: 'DELETE',
      headers: { Authorization: `Bearer ${token}` },
    })
    await handleApiResponse<{ message: string }>(res)
  }
}

// 导出API实例
export const resumeApi = ResumeAPI
export const chatHistoryApi = ChatHistoryAPI

// 导出类型
export type {
  Resume,
  ResumeListItem,
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
