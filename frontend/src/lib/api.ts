// 简历内容接口定义
interface ResumeHighlight {
  id?: string
  text: string
}

interface ResumeLink {
  id?: string
  label: string
  url: string
}

interface ResumeMeta {
  schema_version?: string
  language?: string
  target_role?: string
}

interface JobApplication {
  target_title?: string
  target_company?: string
  jd_text?: string
  strategy?: string
}

interface PersonalInfo {
  name?: string
  email?: string
  phone?: string
  position?: string
  headline?: string
  location?: string
  github?: string
  linkedin?: string
  website?: string
  address?: string
  links?: ResumeLink[]
}

interface Summary {
  text?: string
}

interface Education {
  id?: string
  school: string
  major: string
  degree: string
  duration: string
  start_date?: string
  end_date?: string
  location?: string
  gpa?: string
  description?: string
  highlights?: ResumeHighlight[]
}

interface WorkExperience {
  id?: string
  company: string
  position: string
  duration: string
  start_date?: string
  end_date?: string
  is_current?: boolean
  location?: string
  employment_type?: string
  highlights?: ResumeHighlight[]
  technologies?: string[]
}

interface Skill {
  id?: string
  category: string
  items: string[]
}

interface Project {
  id?: string
  name: string
  overview?: string
  technologies?: string[]
  role: string
  duration: string
  start_date?: string
  end_date?: string
  github_url?: string
  demo_url?: string
  highlights?: ResumeHighlight[]
  links?: ResumeLink[]
}

interface Language {
  id?: string
  name: string
  level: string
}

interface CustomSection {
  id?: string
  title: string
  content: string
}

interface ResumeContent {
  meta?: ResumeMeta
  parsing_quality?: number
  parsing_method?: string
  job_application?: JobApplication
  personal_info?: PersonalInfo
  summary?: Summary
  education?: Education[]
  work_experience?: WorkExperience[]
  skills?: Skill[]
  projects?: Project[]
  languages?: Language[]
  custom_sections?: CustomSection[]
}

interface Resume {
  id: number
  title: string
  content: ResumeContent
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

interface ResumeProposal {
  id: number
  resume_id: number
  user_message: string
  section?: string
  status: string
  summary?: string
  proposed_content: ResumeContent
  proposed_patch?: Record<string, unknown>
  tool_calls?: Array<{ name: string; result: string }>
  created_at: string
  updated_at?: string
  applied_at?: string
}

// 面试相关类型
interface InterviewSession {
  id: number
  resume_id: number
  resume_title?: string
  job_position: string
  interview_mode?: string
  jd_content: string
  questions: any[]
  answers: any[]
  feedback: any
  status: string
  overall_score?: number
  current_question?: number
  total_questions?: number
  answered_questions?: number
  turns?: InterviewTurn[]
  current_turn?: InterviewTurn | null
  created_at: string
  updated_at?: string
}

interface InterviewConfig {
  job_position: string
  jd_content?: string
}

interface InterviewTurn {
  turn_index: number
  question: string
  question_type: string
  intent?: string
  answer?: string | null
  evaluation?: any
  score?: number | null
  status: string
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

  static async getResumeProposals(id: number): Promise<ResumeProposal[]> {
    const response = await fetch(`${API_BASE_URL}/api/resumes/${id}/proposals`, {
      headers: {
        ...getAuthHeaders(),
      },
    })
    return handleApiResponse<ResumeProposal[]>(response)
  }

  static async applyResumeProposal(id: number, proposalId: number): Promise<ResumeProposal> {
    const response = await fetch(`${API_BASE_URL}/api/resumes/${id}/proposals/${proposalId}/apply`, {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
      },
    })
    return handleApiResponse<ResumeProposal>(response)
  }

  static async rejectResumeProposal(id: number, proposalId: number): Promise<ResumeProposal> {
    const response = await fetch(`${API_BASE_URL}/api/resumes/${id}/proposals/${proposalId}/reject`, {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
      },
    })
    return handleApiResponse<ResumeProposal>(response)
  }
}

// 面试API类
class InterviewAPI {
  /**
   * 获取指定简历的面试记录列表
   */
  static async getInterviewSessions(resumeId: number): Promise<InterviewSession[]> {
    const response = await fetch(`${API_BASE_URL}/api/resumes/${resumeId}/interview/sessions`, {
      method: 'GET',
      headers: {
        ...getAuthHeaders(),
      },
    })

    return handleApiResponse<InterviewSession[]>(response)
  }

  static async getInterviewSession(resumeId: number, sessionId: number): Promise<InterviewSession> {
    const response = await fetch(`${API_BASE_URL}/api/resumes/${resumeId}/interview/${sessionId}`, {
      method: 'GET',
      headers: {
        ...getAuthHeaders(),
      },
    })

    return handleApiResponse<InterviewSession>(response)
  }

  /**
   * 获取当前用户的全部面试记录
   */
  static async getAllInterviewSessions(): Promise<InterviewSession[]> {
    const response = await fetch(`${API_BASE_URL}/api/resumes/interview/sessions`, {
      method: 'GET',
      headers: {
        ...getAuthHeaders(),
      },
    })

    return handleApiResponse<InterviewSession[]>(response)
  }

  /**
   * 开始面试会话
   */
  static async startInterview(resumeId: number, config: InterviewConfig): Promise<InterviewSession> {
    const response = await fetch(`${API_BASE_URL}/api/resumes/${resumeId}/interview/start`, {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(config),
    })

    return handleApiResponse<InterviewSession>(response)
  }

  /**
   * 结束面试会话
   */
  static async endInterview(resumeId: number, sessionId: number): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/resumes/${resumeId}/interview/${sessionId}/end`, {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
      },
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `结束面试失败: ${response.status}`)
    }
  }

  /**
   * 删除面试会话
   */
  static async deleteInterviewSession(resumeId: number, sessionId: number): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/resumes/${resumeId}/interview/${sessionId}`, {
      method: 'DELETE',
      headers: {
        ...getAuthHeaders(),
      },
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || `删除面试记录失败: ${response.status}`)
    }
  }

  /**
   * 为已完成面试计算分数
   */
  static async calculateScoresForCompletedInterviews(resumeId: number): Promise<{message: string, updated_count: number}> {
    const response = await fetch(`${API_BASE_URL}/api/resumes/${resumeId}/interview/calculate-scores`, {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
      },
    })

    return handleApiResponse<{message: string, updated_count: number}>(response)
  }

  /**
   * 获取面试详细报告
   */
  static async getInterviewReport(resumeId: number, sessionId: number, regenerate: boolean = false): Promise<any> {
    const params = new URLSearchParams()
    if (regenerate) {
      params.append('regenerate', 'true')
    }
    
    const response = await fetch(`${API_BASE_URL}/api/resumes/${resumeId}/interview/${sessionId}/report?${params.toString()}`, {
      method: 'GET',
      headers: {
        ...getAuthHeaders(),
      },
    })

    return handleApiResponse<any>(response)
  }

  /**
   * 获取下一个面试问题
   */
  static async getNextInterviewQuestion(resumeId: number, sessionId: number): Promise<{
    question: string
    question_type: string
    question_index: number
  }> {
    const response = await fetch(`${API_BASE_URL}/api/resumes/${resumeId}/interview/${sessionId}/question`, {
      method: 'GET',
      headers: {
        ...getAuthHeaders(),
      },
    })

    return handleApiResponse<{
      question: string
      question_type: string
      question_index: number
    }>(response)
  }

  /**
   * 提交面试答案并获取评估
   */
  static async submitInterviewAnswer(resumeId: number, sessionId: number, answer: string, questionIndex: number): Promise<{
    question: string
    answer: string
    evaluation: any
    score: number
    feedback: string
    suggestions: string[]
    session_status: string
    completed: boolean
    current_turn?: InterviewTurn | null
    next_turn?: InterviewTurn | null
  }> {
    const response = await fetch(`${API_BASE_URL}/api/resumes/${resumeId}/interview/${sessionId}/answer`, {
      method: 'POST',
      headers: {
        ...getAuthHeaders(),
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        answer,
        question_index: questionIndex
      }),
    })

    return handleApiResponse<{
      question: string
      answer: string
      evaluation: any
      score: number
      feedback: string
      suggestions: string[]
      session_status: string
      completed: boolean
      current_turn?: InterviewTurn | null
      next_turn?: InterviewTurn | null
    }>(response)
  }

  /**
   * 流式提交面试答案并生成下一题。
   * 返回一个异步迭代器，依次产出 SSE 事件对象。
   */
  static async *submitInterviewAnswerStream(
    resumeId: number,
    sessionId: number,
    answer: string,
    questionIndex: number,
  ): AsyncGenerator<
    | { type: 'answer_saved'; turn_index: number }
    | { type: 'delta'; content: string }
    | { type: 'done'; completed: boolean; next_turn: InterviewTurn | null }
    | { type: 'error'; message: string }
  > {
    const response = await fetch(
      `${API_BASE_URL}/api/resumes/${resumeId}/interview/${sessionId}/answer/stream`,
      {
        method: 'POST',
        headers: {
          ...getAuthHeaders(),
          'Content-Type': 'application/json',
          Accept: 'text/event-stream',
        },
        body: JSON.stringify({ answer, question_index: questionIndex }),
      },
    )

    if (!response.ok || !response.body) {
      const text = await response.text().catch(() => '')
      throw new Error(text || `提交回答失败 (${response.status})`)
    }

    const reader = response.body.getReader()
    const decoder = new TextDecoder()
    let buffer = ''
    while (true) {
      const { value, done } = await reader.read()
      if (done) break
      buffer += decoder.decode(value, { stream: true })
      let sep: number
      while ((sep = buffer.indexOf('\n\n')) !== -1) {
        const frame = buffer.slice(0, sep)
        buffer = buffer.slice(sep + 2)
        for (const line of frame.split('\n')) {
          if (!line.startsWith('data: ')) continue
          const payload = line.slice(6).trim()
          if (!payload) continue
          try {
            yield JSON.parse(payload)
          } catch {
            // 忽略非 JSON 帧
          }
        }
      }
    }
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
export const interviewApi = InterviewAPI
export const chatHistoryApi = ChatHistoryAPI

// 导出类型
export type {
  Resume,
  ResumeContent,
  PersonalInfo,
  Education,
  WorkExperience,
  Skill,
  Project,
  CreateResumeData,
  UpdateResumeData,
  InterviewSession,
  InterviewConfig,
  InterviewTurn,
}
