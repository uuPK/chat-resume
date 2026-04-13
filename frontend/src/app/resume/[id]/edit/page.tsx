'use client'

import { motion } from 'framer-motion'
import { useEffect, useState, useRef, useMemo, useCallback } from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import { useAuth } from '@/lib/auth'
import { resumeApi } from '@/lib/api'
import toast from 'react-hot-toast'
import Link from 'next/link'
import {
  ArrowLeftIcon,
  ArrowUpIcon,
  ArrowDownTrayIcon,
  XMarkIcon,
  ChevronLeftIcon,
  ChevronRightIcon,
  TrashIcon
} from '@heroicons/react/24/outline'
import JobApplicationEditor from '@/components/editor/JobApplicationEditor'
import PersonalInfoEditor from '@/components/editor/PersonalInfoEditor'
import EducationEditor from '@/components/editor/EducationEditor'
import WorkExperienceEditor from '@/components/editor/WorkExperienceEditor'
import SkillsEditor from '@/components/editor/SkillsEditor'
import ProjectsEditor from '@/components/editor/ProjectsEditor'
import ResumePreview from '@/components/preview/ResumePreview'
import ResumeLayoutControls from '@/components/preview/ResumeLayoutControls'
import { ModuleConfig } from '@/components/preview/PaginatedResumePreview'
import {
  ResumeLayoutConfig,
  ResumeModule,
  loadLayoutConfig,
  saveLayoutConfig,
  saveLayoutConfigToServer,
  deserializeLayoutConfig,
  MODULE_LABELS,
  DEFAULT_LAYOUT_CONFIG
} from '@/lib/resumeLayoutConfig'
import MarkdownMessage from '@/components/ui/MarkdownMessage'
import StreamingMessage from '@/components/ui/StreamingMessage'
import { useStreamingChat, ChatMessage, StreamEvent } from '@/hooks/useStreamingChat'
import { chatHistoryApi, type InterviewSession } from '@/lib/api'

type IVMessage = {
  id: string
  type: 'user' | 'ai' | 'system'
  content: string
}

function buildIVMessages(session: InterviewSession): IVMessage[] {
  const msgs: IVMessage[] = []
  for (const turn of session.turns || []) {
    msgs.push({ id: `q-${turn.id}`, type: 'ai', content: turn.question })
    if (turn.answer) msgs.push({ id: `a-${turn.id}`, type: 'user', content: turn.answer })
    if (turn.evaluation) {
      const gaps = turn.evaluation.gaps || []
      const evidence = turn.evaluation.evidence || []
      const scores = turn.evaluation.dimension_scores || {}
      const scoreLine = Object.keys(scores).length > 0
        ? `评分：${Object.entries(scores).map(([k, v]) => `${k} ${v}`).join(' / ')}`
        : ''
      const detailLine = gaps.length > 0
        ? `问题：${gaps.join('；')}`
        : evidence.length > 0 ? `亮点：${evidence.join('；')}` : ''
      msgs.push({
        id: `e-${turn.id}`,
        type: 'system',
        content: [turn.evaluation.summary, scoreLine, detailLine].filter(Boolean).join('\n'),
      })
    }
  }
  return msgs
}

interface Resume {
  id: number
  title: string
  content: {
    job_application?: {
      target_company?: string
      target_title?: string
      jd_text?: string
      strategy?: string
    }
    personal_info?: {
      name?: string
      email?: string
      phone?: string
      position?: string
      github?: string
    }
    education?: Array<{
      id?: string
      school: string
      major: string
      degree: string
      duration: string
      description?: string
      highlights?: Array<{ id?: string; text: string }>
    }>
    work_experience?: Array<{
      id?: string
      company: string
      position: string
      duration: string
      description?: string
      location?: string
      employment_type?: string
      highlights?: Array<{ id?: string; text: string }>
    }>
    skills?: Array<{
      id?: string
      category: string
      items: string[]
    }>
    projects?: Array<{
      id?: string
      name: string
      description?: string
      summary?: string
      overview?: string
      technologies?: string[]
      role: string
      duration: string
      github_url?: string
      demo_url?: string
      achievements?: string[]
      highlights?: Array<{ id?: string; text: string }>
    }>
  }
  created_at: string
  updated_at?: string
}

type AutoSaveStatus = 'idle' | 'pending' | 'saving' | 'success' | 'error'

const AUTO_SAVE_DELAY = 1500

const EDITOR_SECTION_TO_MODULE: Partial<Record<string, ResumeModule>> = {
  personal: 'personal',
  education: 'education',
  work: 'work',
  projects: 'projects',
  skills: 'skills',
}

const AUTO_SAVE_STATUS_MESSAGE: Record<
  AutoSaveStatus,
  { text: string; className: string }
> = {
  idle: { text: '', className: 'text-gray-400' },
  pending: { text: '有未保存的更改…', className: 'text-amber-500' },
  saving: { text: '自动保存中…', className: 'text-primary-600' },
  success: { text: '已自动保存', className: 'text-green-600' },
  error: { text: '自动保存失败，请检查网络或手动保存', className: 'text-red-600' }
}

/** 将 diffSummary 文本解析为带颜色的 diff 行 */
function parseDiffSummary(raw: string): Array<{ type: 'remove' | 'add' | 'meta'; text: string }> {
  const lines = raw.split('\n')
  const result: Array<{ type: 'remove' | 'add' | 'meta'; text: string }> = []
  for (const line of lines) {
    if (!line.trim()) continue
    // 跳过标题行（修改摘要/新增/删除）
    if (line.endsWith('修改摘要') || line.endsWith('新增') || line.endsWith('删除')) continue
    if (line.startsWith('改前：') || line.startsWith('  改前：')) {
      const text = line.replace(/^\s*改前：/, '').trim()
      if (text === '（新增）') continue
      result.push({ type: 'remove', text: '- ' + text })
    } else if (line.startsWith('改后：') || line.startsWith('  改后：')) {
      const text = line.replace(/^\s*改后：/, '').trim()
      if (text === '（已删除）') continue
      result.push({ type: 'add', text: '+ ' + text })
    }
  }
  return result
}

export default function ResumeEditPage() {
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()
  const { user, isAuthenticated, isLoading } = useAuth()
  const [mounted, setMounted] = useState(false)
  const [resume, setResume] = useState<Resume | null>(null)
  const [resumeLoading, setResumeLoading] = useState(true)
  const [exporting, setExporting] = useState(false)
  const [autoSaveStatus, setAutoSaveStatus] = useState<AutoSaveStatus>('idle')
  const [activeSection, setActiveSection] = useState('job_application')
  const [editorOpen, setEditorOpen] = useState(true)
  const [editorFlex, setEditorFlex] = useState(30)
  const [agentFlex, setAgentFlex] = useState(30)
  const mainPanelsRef = useRef<HTMLDivElement>(null)
  const autoSaveTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const statusResetTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const resumeRef = useRef<Resume | null>(null)
  const hasUnsavedChangesRef = useRef(false)
  const savePromiseRef = useRef<Promise<void> | null>(null)

  // 拖拽调节编辑区宽度
  const handleEditorDividerPointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault()
    const startX = e.clientX
    const startFlex = editorFlex
    document.body.style.userSelect = 'none'
    document.body.style.cursor = 'col-resize'
    const onPointerMove = (ev: PointerEvent) => {
      if (!mainPanelsRef.current) return
      const containerWidth = mainPanelsRef.current.offsetWidth
      const delta = ev.clientX - startX
      const deltaFlex = (delta / containerWidth) * 100
      const nextEditorFlex = Math.min(45, Math.max(18, startFlex + deltaFlex))
      const previewFlex = 100 - nextEditorFlex - agentFlex
      if (previewFlex >= 25) {
        setEditorFlex(nextEditorFlex)
      }
    }
    const onPointerUp = () => {
      document.body.style.userSelect = ''
      document.body.style.cursor = ''
      document.removeEventListener('pointermove', onPointerMove)
      document.removeEventListener('pointerup', onPointerUp)
    }
    document.addEventListener('pointermove', onPointerMove)
    document.addEventListener('pointerup', onPointerUp)
  }, [editorFlex, agentFlex])

  // 拖拽调节预览/Agent 宽度
  const handleAgentDividerPointerDown = useCallback((e: React.PointerEvent) => {
    e.preventDefault()
    const startX = e.clientX
    const startFlex = agentFlex
    document.body.style.userSelect = 'none'
    document.body.style.cursor = 'col-resize'
    const onPointerMove = (ev: PointerEvent) => {
      if (!mainPanelsRef.current) return
      const containerWidth = mainPanelsRef.current.offsetWidth
      const delta = startX - ev.clientX
      const deltaFlex = (delta / containerWidth) * 100
      const nextAgentFlex = Math.min(45, Math.max(18, startFlex + deltaFlex))
      const previewFlex = 100 - editorFlex - nextAgentFlex
      if (previewFlex >= 25) {
        setAgentFlex(nextAgentFlex)
      }
    }
    const onPointerUp = () => {
      document.body.style.userSelect = ''
      document.body.style.cursor = ''
      document.removeEventListener('pointermove', onPointerMove)
      document.removeEventListener('pointerup', onPointerUp)
    }
    document.addEventListener('pointermove', onPointerMove)
    document.addEventListener('pointerup', onPointerUp)
  }, [editorFlex, agentFlex])

  // 聊天相关状态
  const [messageBuckets, setMessageBuckets] = useState<Record<'resume', ChatMessage[]>>({
    resume: [],
  })
  const [inputMessage, setInputMessage] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [isClearingMessages, setIsClearingMessages] = useState(false)
  const [proposalActionLoadingId, setProposalActionLoadingId] = useState<number | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)
  const [agentType, setAgentType] = useState<'resume' | 'interview'>('resume')

  // 面试相关状态
  const [ivSession, setIvSession] = useState<InterviewSession | null>(null)
  const [ivMessages, setIvMessages] = useState<IVMessage[]>([])
  const [ivInput, setIvInput] = useState('')
  const [ivSending, setIvSending] = useState(false)
  const [ivError, setIvError] = useState<string | null>(null)
  const ivMessagesEndRef = useRef<HTMLDivElement>(null)
  const [qrImages, setQrImages] = useState<string[]>([])
  const [isQrModalOpen, setIsQrModalOpen] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // 布局配置状态
  const [layoutConfig, setLayoutConfig] = useState<ResumeLayoutConfig>(DEFAULT_LAYOUT_CONFIG)
  const layoutSaveTimeoutRef = useRef<ReturnType<typeof setTimeout> | null>(null)

  // 智能一页状态
  const [previewTotalPages, setPreviewTotalPages] = useState(0)
  const [isSmartFitting, setIsSmartFitting] = useState(false)
  const smartFitTriggerRef = useRef<(() => Promise<any>) | null>(null)

  const resumeId = params?.id as string
  const previewFlex = 100 - editorFlex - agentFlex
  const collapsedAgentFlex = 100 - previewFlex
  const messages = messageBuckets['resume']

  const appendMessageForAgent = useCallback(
    (targetAgent: 'resume', message: ChatMessage) => {
      setMessageBuckets(prev => ({
        ...prev,
        [targetAgent]: [...prev[targetAgent], message]
      }))
    },
    []
  )

  const replaceMessagesForAgent = useCallback(
    (targetAgent: 'resume', nextMessages: ChatMessage[]) => {
      setMessageBuckets(prev => ({
        ...prev,
        [targetAgent]: nextMessages
      }))
    },
    []
  )

  // 流式聊天Hook
  const {
    isStreaming,
    currentStreamingMessage,
    currentToolCalls,
    currentProposal,
    streamEvents,
    sendStreamingMessage,
    stopStreaming,
    confirmTool,
  } = useStreamingChat(parseInt(resumeId), {
    visibleModules: Array.from(layoutConfig.visibleModules),
    agentType: 'resume',
    onMessage: (message: ChatMessage) => {
      appendMessageForAgent('resume', message)
      if (resumeId) {
        chatHistoryApi.appendMessages(parseInt(resumeId), [
          {
            role: 'assistant',
            content: message.content,
            stream_events: message.streamEvents || null,
          },
        ]).catch(console.error)
      }
    },
    onError: (error) => {
      setApiError(error)
      const errorMessage: ChatMessage = {
        id: Date.now().toString(),
        type: 'ai',
        content: `抱歉，发生了错误：${error}`,
        timestamp: new Date()
      }
      appendMessageForAgent('resume', errorMessage)
    },
    onQrImages: (images) => {
      if (images && images.length > 0) {
        setQrImages(images)
        setIsQrModalOpen(true)
      }
    },
    onResumeUpdate: (content) => {
      hasUnsavedChangesRef.current = false
      setAutoSaveStatus('idle')
      setResume(prev => {
        if (!prev) return prev
        const updated = { ...prev, content: content as Resume['content'] }
        resumeRef.current = updated
        return updated
      })
    },
  })

  useEffect(() => {
    setMounted(true)
  }, [])

  useEffect(() => {
    const requestedAgent = searchParams?.get('agent')
    if (requestedAgent === 'interview' || requestedAgent === 'interviewer') {
      setAgentType('interview')
    } else if (requestedAgent === 'resume') {
      setAgentType('resume')
    }
  }, [searchParams])

  useEffect(() => {
    setApiError(null)
    setIvError(null)
    if (agentType === 'interview') {
      setEditorOpen(false)
    } else {
      setEditorOpen(true)
    }
  }, [agentType])

  // 切换到面试模式时自动创建并启动 session
  useEffect(() => {
    if (agentType !== 'interview' || !resume || ivSession || ivSending) return
    const jobApp = resume.content?.job_application || {}
    setIvSending(true)
    resumeApi.createInterviewSession({
      resume_id: resume.id,
      target_title: jobApp.target_title,
      target_company: jobApp.target_company,
      jd_text: jobApp.jd_text,
      interview_type: 'general',
      difficulty: 'medium',
      language: 'zh-CN',
      mode: 'text',
    })
      .then((created) => resumeApi.startInterviewSession(created.session.id))
      .then((started) => {
        setIvSession(started.session)
        setIvMessages(buildIVMessages(started.session))
      })
      .catch((err) => setIvError(err instanceof Error ? err.message : '启动面试失败'))
      .finally(() => setIvSending(false))
  }, [agentType, resume])

  // 面试消息自动滚动
  useEffect(() => {
    ivMessagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [ivMessages])

  const sendInterviewAnswer = async () => {
    const text = ivInput.trim()
    if (!text || !ivSession || ivSending || ivSession.status === 'completed') return
    setIvSending(true)
    setIvError(null)
    setIvInput('')
    const userMsgId = `user-${Date.now()}`
    const aiMsgId = `ai-stream-${Date.now()}`
    setIvMessages((prev) => [...prev, { id: userMsgId, type: 'user', content: text }])
    setIvMessages((prev) => [...prev, { id: aiMsgId, type: 'ai', content: '' }])
    try {
      for await (const event of resumeApi.answerInterviewSessionStream(ivSession.id, text)) {
        if (event.type === 'token') {
          setIvMessages((prev) =>
            prev.map((m) => m.id === aiMsgId ? { ...m, content: m.content + event.content } : m)
          )
        } else if (event.type === 'done') {
          setIvSession(event.session)
          setIvMessages(buildIVMessages(event.session))
        }
      }
    } catch (err) {
      setIvMessages((prev) => prev.filter((m) => m.id !== aiMsgId))
      setIvError(err instanceof Error ? err.message : '提交回答失败')
    } finally {
      setIvSending(false)
    }
  }

  const endInterview = async () => {
    if (!ivSession || ivSending || ivSession.status === 'completed') return
    setIvSending(true)
    try {
      const result = await resumeApi.endInterviewSession(ivSession.id)
      setIvSession(result.session)
      setIvMessages(buildIVMessages(result.session))
    } catch (err) {
      setIvError(err instanceof Error ? err.message : '结束面试失败')
    } finally {
      setIvSending(false)
    }
  }

  const resetInterview = () => {
    setIvSession(null)
    setIvMessages([])
    setIvInput('')
    setIvError(null)
  }

  useEffect(() => {
    if (mounted && !isLoading && !isAuthenticated) {
      router.push('/login')
    }
  }, [mounted, isLoading, isAuthenticated, router])

  // 获取简历数据
  const fetchResume = async () => {
    if (!resumeId || !isAuthenticated) return

    try {
      setResumeLoading(true)
      const data = await resumeApi.getResume(parseInt(resumeId))
      setResume(data)
      resumeRef.current = data
      hasUnsavedChangesRef.current = false
      setAutoSaveStatus('idle')
      // 优先使用服务端布局配置，回退到 localStorage 缓存
      const serverConfig = deserializeLayoutConfig(data.layout_config as Record<string, unknown> | null)
      setLayoutConfig(serverConfig)
      saveLayoutConfig(parseInt(resumeId), serverConfig) // 同步更新本地缓存
    } catch (error) {
      console.error('Failed to fetch resume:', error)
      toast.error('获取简历失败')
      router.push('/dashboard')
    } finally {
      setResumeLoading(false)
    }
  }

  useEffect(() => {
    if (mounted && isAuthenticated) {
      fetchResume()
      loadChatHistory()
    }
  }, [mounted, isAuthenticated, resumeId])

  // 加载聊天历史
  const loadChatHistory = async () => {
    if (!resumeId) return
    try {
      const records = await chatHistoryApi.getMessages(parseInt(resumeId))
      if (records.length > 0) {
        const loaded: ChatMessage[] = records.map((r) => ({
          id: r.id.toString(),
          type: r.role === 'user' ? 'user' : 'ai',
          content: r.content,
          timestamp: new Date(),
          streamEvents: (r as { stream_events?: StreamEvent[] }).stream_events || undefined,
        }))
        replaceMessagesForAgent('resume', loaded)
      }
    } catch (e) {
      console.error('Failed to load chat history:', e)
    }
  }

  // 页面首次渲染时先从 localStorage 读取布局配置（避免服务端数据回来前闪烁默认值）
  useEffect(() => {
    if (resumeId) {
      const cached = loadLayoutConfig(parseInt(resumeId))
      setLayoutConfig(cached)
    }
  }, [resumeId])

  useEffect(() => {
    resumeRef.current = resume
  }, [resume])

  useEffect(() => {
    return () => {
      if (autoSaveTimeoutRef.current) {
        clearTimeout(autoSaveTimeoutRef.current)
      }
      if (statusResetTimeoutRef.current) {
        clearTimeout(statusResetTimeoutRef.current)
      }
      if (layoutSaveTimeoutRef.current) {
        clearTimeout(layoutSaveTimeoutRef.current)
      }
    }
  }, [])

  // 处理布局配置变化：立即更新本地状态，800ms debounce 后同步到服务端
  const handleLayoutConfigChange = (newConfig: ResumeLayoutConfig) => {
    setLayoutConfig(newConfig)
    if (!resumeId) return
    const id = parseInt(resumeId)
    saveLayoutConfig(id, newConfig) // 即时更新 localStorage
    if (layoutSaveTimeoutRef.current) {
      clearTimeout(layoutSaveTimeoutRef.current)
    }
    layoutSaveTimeoutRef.current = setTimeout(() => {
      saveLayoutConfigToServer(id, newConfig)
    }, 800)
  }

  // 智能一页按钮点击
  const handleSmartFitHeaderClick = async () => {
    if (!smartFitTriggerRef.current || isSmartFitting) return
    setIsSmartFitting(true)
    try {
      const result = await smartFitTriggerRef.current()
      if (!result) return
      if (result.status === 'already_fits') {
        toast('当前简历已是一页，无需调整', { icon: '✅' })
      } else if (result.status === 'too_much_content') {
        toast.error(`内容过多（约 ${result.pages} 页），建议删减内容`)
      } else if (result.status === 'success') {
        toast.success(`已将间距从 ${result.oldScale.toFixed(2)}× 调整为 ${result.newScale.toFixed(2)}×，简历适配一页`)
      }
    } finally {
      setIsSmartFitting(false)
    }
  }

  // 将 ResumeLayoutConfig 转换为 ModuleConfig[]
  // 使用 useMemo 确保 layoutConfig 变化时重新计算
  const moduleOrder = useMemo<ModuleConfig[]>(() => {
    return layoutConfig.moduleOrder.map((module, index) => ({
      type: module,
      visible: layoutConfig.visibleModules.has(module),
      order: index,
      label: MODULE_LABELS[module]
    }))
  }, [layoutConfig])

  const editorSections = useMemo(() => {
    const allSections = [
      { key: 'job_application', label: '岗位' },
      { key: 'personal', label: '个人' },
      { key: 'education', label: '教育' },
      { key: 'work', label: '工作' },
      { key: 'projects', label: '项目' },
      { key: 'skills', label: '技能' }
    ]

    return allSections.filter((section) => {
      const mappedModule = EDITOR_SECTION_TO_MODULE[section.key]
      return mappedModule ? layoutConfig.visibleModules.has(mappedModule) : true
    })
  }, [layoutConfig.visibleModules])

  useEffect(() => {
    const activeModule = EDITOR_SECTION_TO_MODULE[activeSection]
    if (!activeModule || layoutConfig.visibleModules.has(activeModule)) {
      return
    }

    const fallbackSection = editorSections[0]?.key || 'job_application'
    if (fallbackSection !== activeSection) {
      setActiveSection(fallbackSection)
    }
  }, [activeSection, editorSections, layoutConfig.visibleModules])

  const scheduleStatusReset = useCallback(() => {
    if (statusResetTimeoutRef.current) {
      clearTimeout(statusResetTimeoutRef.current)
    }
    statusResetTimeoutRef.current = setTimeout(() => {
      setAutoSaveStatus((status) => (status === 'success' ? 'idle' : status))
    }, 2000)
  }, [])

  const performAutoSave = useCallback(
    async ({ showSuccessToast = false }: { showSuccessToast?: boolean } = {}) => {
      if (!resumeRef.current) {
        return
      }

      if (!hasUnsavedChangesRef.current) {
        return
      }

      if (savePromiseRef.current) {
        return savePromiseRef.current
      }

      if (autoSaveTimeoutRef.current) {
        clearTimeout(autoSaveTimeoutRef.current)
        autoSaveTimeoutRef.current = null
      }

      const snapshot = resumeRef.current
      const saveTask = (async () => {
        setAutoSaveStatus('saving')
        try {
          const savedResume = await resumeApi.updateResume(snapshot.id, {
            title: snapshot.title,
            content: snapshot.content
          })
          if (resumeRef.current?.id === savedResume.id && resumeRef.current === snapshot) {
            const updated = savedResume as Resume
            resumeRef.current = updated
            setResume(updated)
            hasUnsavedChangesRef.current = false
            setAutoSaveStatus('success')
            scheduleStatusReset()
          } else {
            setAutoSaveStatus('pending')
          }
          if (showSuccessToast) {
            toast.success('简历保存成功')
          }
        } catch (error) {
          console.error('Auto save error:', error)
          setAutoSaveStatus('error')
          toast.error('自动保存失败，请检查网络或手动保存')
          throw error
        } finally {
          savePromiseRef.current = null
        }
      })()

      savePromiseRef.current = saveTask
      return saveTask
    },
    [scheduleStatusReset]
  )

  const scheduleAutoSave = useCallback(() => {
    if (autoSaveTimeoutRef.current) {
      clearTimeout(autoSaveTimeoutRef.current)
    }
    setAutoSaveStatus('pending')
    autoSaveTimeoutRef.current = setTimeout(() => {
      performAutoSave().catch(() => {
        // 错误情况已在 performAutoSave 中处理
      })
    }, AUTO_SAVE_DELAY)
  }, [performAutoSave])

  // 导出PDF
  const handleExportPDF = async () => {
    if (!resume) {
      toast.error('简历不存在')
      return
    }

    try {
      setExporting(true)
      const toastId = toast.loading('正在生成PDF...')
      const result = await resumeApi.exportResume(resume.id, 'pdf')
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const downloadUrl = `${apiBaseUrl}${result.download_url}`
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = result.filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      toast.success('PDF导出成功', { id: toastId })
    } catch (error) {
      console.error('PDF export error:', error)
      toast.error(error instanceof Error ? error.message : 'PDF导出失败')
    } finally {
      setExporting(false)
    }
  }

  // 更新简历内容
  const updateResumeContent = (section: string, data: any) => {
    if (!resume) return

    setResume(prev => {
      const updated = {
        ...prev!,
        content: {
          ...prev!.content,
          [section]: data
        }
      }
      resumeRef.current = updated
      return updated
    })
    hasUnsavedChangesRef.current = true
    scheduleAutoSave()
  }

  // 更新简历标题
  const updateResumeTitle = (title: string) => {
    if (!resume) return

    setResume(prev => {
      const updated = {
        ...prev!,
        title: title
      }
      resumeRef.current = updated
      return updated
    })
    hasUnsavedChangesRef.current = true
    scheduleAutoSave()
  }

  // 聊天功能
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const sendMessage = async () => {
    if (!inputMessage.trim() || isSending || isStreaming) return

    try {
      await performAutoSave()
    } catch {
      setApiError('简历保存失败，未发送给 Agent')
      return
    }

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: inputMessage.trim(),
      timestamp: new Date()
    }

    appendMessageForAgent('resume', userMessage)
    if (agentType === 'resume' && resumeId) {
      chatHistoryApi.appendMessages(parseInt(resumeId), [
        { role: 'user', content: userMessage.content },
      ]).catch(console.error)
    }
    const currentMessage = inputMessage.trim()
    setInputMessage('')
    setIsSending(true)
    setApiError(null)

    try {
      // 使用流式聊天，传递当前的聊天历史
      await sendStreamingMessage(currentMessage, messages)
    } catch (error) {
      console.error('Streaming chat error:', error)
      setApiError('流式聊天发送失败，请重试')
    } finally {
      setIsSending(false)
    }
  }

  const handleClearMessages = async () => {
    if (!resume || isStreaming || isSending || isClearingMessages || messages.length === 0) {
      return
    }

    if (!window.confirm('确定清空当前聊天记录吗？此操作不可恢复。')) {
      return
    }

    try {
      setIsClearingMessages(true)
      if (agentType === 'resume') {
        await chatHistoryApi.clearMessages(resume.id)
      }
      replaceMessagesForAgent('resume', [])
      setApiError(null)
      toast.success('已清空消息记录')
    } catch (error) {
      console.error('Clear chat messages failed:', error)
      toast.error(error instanceof Error ? error.message : '清空消息失败')
    } finally {
      setIsClearingMessages(false)
    }
  }

  const updateMessageProposalStatus = (
    messageId: string,
    status: 'pending' | 'applied' | 'rejected'
  ) => {
    setMessageBuckets(prev => ({
      ...prev,
      resume: prev['resume'].map((message: ChatMessage) =>
        message.id === messageId && message.proposal
          ? { ...message, proposal: { ...message.proposal, proposalStatus: status } }
          : message
      )
    }))
  }

  const handleApplyProposal = async (message: ChatMessage) => {
    if (!resume || !message.proposal) return

    try {
      setProposalActionLoadingId(message.proposal.proposalId)
      const result = await resumeApi.applyResumeProposal(
        resume.id,
        message.proposal.proposalId
      )
      setResume(prev => {
        if (!prev) return prev
        const updated = {
          ...prev,
          content: result.proposed_content as Resume['content']
        }
        resumeRef.current = updated
        return updated
      })
      hasUnsavedChangesRef.current = false
      setAutoSaveStatus('idle')
      updateMessageProposalStatus(message.id, 'applied')
      toast.success('已应用这次修改')
    } catch (error) {
      console.error('Apply proposal failed:', error)
      toast.error(error instanceof Error ? error.message : '应用修改失败')
    } finally {
      setProposalActionLoadingId(null)
    }
  }

  const handleRejectProposal = (message: ChatMessage) => {
    if (!message.proposal || !resume) return
    setProposalActionLoadingId(message.proposal.proposalId)
    resumeApi.rejectResumeProposal(resume.id, message.proposal.proposalId)
      .then(() => {
        updateMessageProposalStatus(message.id, 'rejected')
        toast.success('已拒绝这次修改')
      })
      .catch((error) => {
        console.error('Reject proposal failed:', error)
        toast.error(error instanceof Error ? error.message : '拒绝修改失败')
      })
      .finally(() => {
        setProposalActionLoadingId(null)
      })
  }

  const renderProposalCard = (message: ChatMessage) => {
    if (!message.proposal) return null

    const status = message.proposal.proposalStatus
    const isPending = status === 'pending'
    const isLoadingProposal = proposalActionLoadingId === message.proposal.proposalId

    const statusColor = status === 'applied'
      ? 'border-green-200 bg-green-50'
      : status === 'rejected'
        ? 'border-gray-200 bg-gray-50'
        : 'border-primary-200 bg-primary-50'

    return (
      <div className={`mt-3 rounded-lg border overflow-hidden ${statusColor}`}>
        {/* 工具调用行 */}
        {message.toolCalls && message.toolCalls.length > 0 && (
          <div className="bg-white border-b border-gray-100 px-3 py-2 space-y-1">
            {message.toolCalls.map((tool, index) => (
              <div key={index} className="flex items-start gap-2 text-xs text-gray-600">
                <div className="mt-0.5 w-1.5 h-1.5 rounded-full bg-primary-500 flex-shrink-0" />
                <div className="min-w-0">
                  <span className="font-medium text-gray-700">{tool.name}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Proposal 头部 */}
        <div className="px-3 py-2 flex items-center justify-between gap-3">
          <div>
            <div className={`text-sm font-medium ${
              status === 'applied' ? 'text-green-900' : status === 'rejected' ? 'text-gray-500' : 'text-primary-900'
            }`}>
              {status === 'applied' ? '已接受修改' : status === 'rejected' ? '已拒绝修改' : '待确认修改'}
            </div>
            <div className="text-xs text-gray-400">Proposal #{message.proposal.proposalId}</div>
          </div>

          {isPending && (
            <div className="flex items-center gap-2 flex-shrink-0">
              <button
                onClick={() => handleApplyProposal(message)}
                disabled={isLoadingProposal}
                className="inline-flex items-center rounded-md bg-primary-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-primary-700 disabled:opacity-50"
              >
                {isLoadingProposal ? '应用中...' : '接受'}
              </button>
              <button
                onClick={() => handleRejectProposal(message)}
                disabled={isLoadingProposal}
                className="inline-flex items-center rounded-md border border-gray-300 bg-white px-3 py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50 disabled:opacity-50"
              >
                拒绝
              </button>
            </div>
          )}
        </div>

        {/* Diff */}
        {message.proposal.proposalPatch?.changes?.length ? (
          <div className="px-3 pb-3 space-y-2">
            {message.proposal.proposalPatch.changes.map((change, index) => (
              <div key={`${change.section}-${index}`} className="rounded-md border border-primary-100 bg-white p-2">
                <div className="mb-2 flex items-center justify-between gap-2">
                  <div className="text-xs font-semibold uppercase tracking-wide text-primary-700">
                    {change.section}
                    {change.item_label ? ` / ${change.item_label}` : ''}
                  </div>
                  <div className={`text-[10px] font-medium ${
                    change.op === 'add' ? 'text-green-700' : change.op === 'remove' ? 'text-red-700' : 'text-primary-700'
                  }`}>
                    {change.op === 'add' ? '新增' : change.op === 'remove' ? '删除' : '修改'}
                  </div>
                </div>
                <div className="space-y-1.5 text-xs">
                  <div>
                    <div className="mb-0.5 font-medium text-gray-400">改前</div>
                    <div className="rounded border border-gray-200 bg-gray-50 px-2 py-1 text-gray-600 leading-relaxed">
                      {change.before || '空'}
                    </div>
                  </div>
                  <div>
                    <div className="mb-0.5 font-medium text-gray-400">改后</div>
                    <div className="rounded border border-green-200 bg-green-50 px-2 py-1 text-gray-800 leading-relaxed">
                      {change.after || '空'}
                    </div>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    )
  }

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }



  // 自动滚动到底部（新消息 + 流式 token 更新时均触发）
  useEffect(() => {
    scrollToBottom()
  }, [messages, currentStreamingMessage])

  // 用于追踪登录成功是否已处理，避免重复触发
  const loginSuccessHandledRef = useRef(false)

  // 轮询 Boss 直聘扫码登录状态
  useEffect(() => {
    let intervalId: NodeJS.Timeout | null = null
    let isCleanedUp = false  // 追踪清理状态

    const checkLoginStatus = async () => {
      // 如果已经清理或已经处理过登录成功，直接返回
      if (isCleanedUp || loginSuccessHandledRef.current) return

      try {
        const token = localStorage.getItem('access_token')
        const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
        const response = await fetch(`${apiBaseUrl}/api/ai/boss/status`, {
          headers: {
            'Authorization': `Bearer ${token}`
          }
        })
        if (!response.ok) return

        const data = await response.json()

        // 双重检查：避免竞态条件
        if (data.is_logged_in && !loginSuccessHandledRef.current && !isCleanedUp) {
          // 立即标记为已处理，防止重复触发
          loginSuccessHandledRef.current = true

          // 立即清除定时器
          if (intervalId) {
            clearInterval(intervalId)
            intervalId = null
          }

          setIsQrModalOpen(false)
          toast.success('Boss直聘登录成功')

          // 登录成功后，自动让 Agent 继续（只触发一次）
          sendStreamingMessage('登录成功，请继续。', messages).catch(console.error)
        }
      } catch (e) {
        console.error('Check login status failed', e)
      }
    }

    if (isQrModalOpen) {
      // 当打开二维码弹窗时，重置登录成功处理标记
      loginSuccessHandledRef.current = false
      // 立即检查一次
      checkLoginStatus()
      // 然后定期轮询
      intervalId = setInterval(checkLoginStatus, 2000)
    }

    return () => {
      isCleanedUp = true  // 标记为已清理
      if (intervalId) {
        clearInterval(intervalId)
        intervalId = null
      }
    }
  }, [isQrModalOpen])

  if (!mounted || isLoading || resumeLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary-600 mx-auto mb-4"></div>
          <p className="text-gray-600">正在加载简历...</p>
        </div>
      </div>
    )
  }

  if (!resume) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600">简历不存在</p>
          <Link href="/dashboard" className="btn-primary mt-4">
            返回简历中心
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header - 现代化设计 */}
      <header className="bg-white border-b border-gray-100 print:hidden">
        <div className="w-full px-6">
          <div className="flex justify-between items-center py-3">
            <div className="flex items-center gap-3">
              <Link
                href="/dashboard"
                className="flex items-center p-2 rounded-lg text-gray-600 hover:text-gray-900 hover:bg-gray-50 transition-colors"
                title="返回仪表板"
              >
                <ArrowLeftIcon className="w-5 h-5" />
              </Link>
            </div>

            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-3">
                <div className="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-1">
                  <button
                    type="button"
                    onClick={() => setAgentType('resume')}
                    className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                      agentType === 'resume'
                        ? 'bg-white text-gray-900 shadow-sm'
                        : 'text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    简历 AGENT
                  </button>
                  <button
                    type="button"
                    onClick={() => { resetInterview(); setAgentType('interview') }}
                    className={`rounded-md px-3 py-1.5 text-xs font-medium transition-colors ${
                      agentType === 'interview'
                        ? 'bg-white text-gray-900 shadow-sm'
                        : 'text-gray-500 hover:text-gray-700'
                    }`}
                  >
                    面试 AGENT
                  </button>
                </div>
                <ResumeLayoutControls
                  config={layoutConfig}
                  onConfigChange={handleLayoutConfigChange}
                />
                <button
                  onClick={handleSmartFitHeaderClick}
                  disabled={isSmartFitting}
                  title="自动调整间距使简历恰好一页"
                  className={`inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium rounded-lg border transition-colors
                    ${isSmartFitting
                      ? 'border-gray-300 bg-white text-gray-500 cursor-wait'
                      : 'border-gray-300 bg-white text-gray-700 hover:bg-gray-50'
                    }`}
                >
                  {isSmartFitting ? (
                    <>
                      <svg className="animate-spin w-4 h-4" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"/>
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"/>
                      </svg>
                      计算中...
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path strokeLinecap="round" strokeLinejoin="round" d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"/>
                      </svg>
                      智能一页
                    </>
                  )}
                </button>
                <button
                  onClick={handleExportPDF}
                  disabled={exporting}
                  className="inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg border border-gray-300 text-gray-700 bg-white hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {exporting ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-600 mr-2"></div>
                      <span>生成中...</span>
                    </>
                  ) : (
                    <>
                      <ArrowDownTrayIcon className="w-4 h-4 mr-2" />
                      <span>导出 PDF</span>
                    </>
                  )}
                </button>
              </div>
              {AUTO_SAVE_STATUS_MESSAGE[autoSaveStatus].text && (
                <div className={`text-xs px-3 py-1 rounded-full ${autoSaveStatus === 'error' ? 'bg-error-50 text-error-600' : autoSaveStatus === 'success' ? 'bg-success-50 text-success-600' : 'bg-gray-50 text-gray-600'}`}>
                  {AUTO_SAVE_STATUS_MESSAGE[autoSaveStatus].text}
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content - 现代化三栏布局 */}
      <main className="max-w-full mx-auto px-6 py-3">
        <div
          ref={mainPanelsRef}
          className="flex gap-0 h-[calc(100vh-120px)]"
        >
          {/* Left Panel - Editor */}
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8 }}
            className="flex flex-col min-h-0 print:hidden"
            style={editorOpen ? { flex: `0 0 calc(${editorFlex}% - 8px)` } : undefined}
          >
            {!editorOpen ? (
              /* 折叠状态：现代化细条 */
              <div
                className="flex flex-col items-center justify-center h-full w-12 cursor-pointer bg-gray-50 hover:bg-gray-100 transition-colors group"
                onClick={() => setEditorOpen(true)}
                title="展开编辑区域"
              >
                <ChevronRightIcon className="w-5 h-5 text-gray-500 group-hover:text-gray-700" />
              </div>
            ) : (
            <div className="relative bg-white rounded-xl border border-gray-200 shadow-soft p-4 flex-1 overflow-hidden flex flex-col">
              <div className="flex-1 flex flex-col min-h-0">
                {/* Section Tabs - 现代化设计 */}
                <div className="flex items-center gap-2 mb-5 border-b border-gray-200 flex-shrink-0">
                  {editorSections.map(section => (
                    <button
                      key={section.key}
                      onClick={() => setActiveSection(section.key)}
                      className={`px-4 py-2.5 text-sm font-medium transition-colors relative ${activeSection === section.key
                        ? 'text-primary-600'
                        : 'text-gray-500 hover:text-gray-700'
                        }`}
                    >
                      <span>{section.label}</span>
                      {activeSection === section.key && (
                        <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary-600 rounded-t-full"></div>
                      )}
                    </button>
                  ))}
                </div>
                <button
                  onClick={() => setEditorOpen(false)}
                  className="absolute right-4 top-4 p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors"
                  title="折叠编辑器"
                >
                  <ChevronLeftIcon className="w-5 h-5" />
                </button>

                {/* Editor Content */}
                <div className="flex-1 overflow-y-auto min-h-0 hide-scrollbar">
                  {activeSection === 'job_application' && (
                    <JobApplicationEditor
                      data={resume.content.job_application || {}}
                      onChange={(data) => updateResumeContent('job_application', data)}
                      resumeTitle={resume.title}
                      onTitleChange={updateResumeTitle}
                    />
                  )}

                  {activeSection === 'personal' && (
                    <PersonalInfoEditor
                      data={resume.content.personal_info || {}}
                      onChange={(data) => updateResumeContent('personal_info', data)}
                    />
                  )}

                  {activeSection === 'education' && (
                    <EducationEditor
                      data={resume.content.education || []}
                      onChange={(data) => updateResumeContent('education', data)}
                    />
                  )}

                  {activeSection === 'work' && (
                    <WorkExperienceEditor
                      data={resume.content.work_experience || []}
                      onChange={(data) => updateResumeContent('work_experience', data)}
                    />
                  )}

                  {activeSection === 'skills' && (
                    <SkillsEditor
                      data={resume.content.skills || []}
                      onChange={(data) => updateResumeContent('skills', data)}
                    />
                  )}

                  {activeSection === 'projects' && (
                    <ProjectsEditor
                      data={resume.content.projects || []}
                      onChange={(data) => updateResumeContent('projects', data)}
                    />
                  )}
                </div>
              </div>
            </div>
            )}
          </motion.div>

          {editorOpen && (
            <div
              className="w-2 flex-shrink-0 cursor-col-resize flex items-center justify-center group select-none print:hidden"
              onPointerDown={handleEditorDividerPointerDown}
            >
              <div className="w-0.5 h-full bg-transparent group-hover:bg-primary-400 transition-colors rounded-full" />
            </div>
          )}

          {/* Middle Panel - Preview */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="preview-panel flex flex-col min-h-0 min-w-0 print:w-full print:h-auto print:absolute print:top-0 print:left-0 print:m-0 print:p-0"
            style={{ flex: `0 0 calc(${previewFlex}% - 16px)` }}
          >
            <div className="flex-1 overflow-y-auto min-h-0 hide-scrollbar print:overflow-visible print:h-auto">
              <ResumePreview
                key={JSON.stringify(moduleOrder.map(m => `${m.type}-${m.order}-${m.visible}`))}
                content={resume.content}
                moduleOrder={moduleOrder}
                spacingScale={layoutConfig.spacingScale}
                onSpacingScaleChange={(scale) =>
                  handleLayoutConfigChange({ ...layoutConfig, spacingScale: scale, density: 'custom' })
                }
                onTotalPagesChange={setPreviewTotalPages}
                smartFitTriggerRef={smartFitTriggerRef}
              />
            </div>
          </motion.div>

          {/* 拖拽分隔条 */}
          <div
            className="w-2 flex-shrink-0 cursor-col-resize flex items-center justify-center group select-none print:hidden"
            onPointerDown={handleAgentDividerPointerDown}
          >
            <div className="w-0.5 h-full bg-transparent group-hover:bg-primary-400 transition-colors rounded-full" />
          </div>

          {/* Right Panel - AI Chat */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.4 }}
            className="agent-panel flex flex-col min-h-0 min-w-0 print:hidden"
            style={{ flex: `0 0 calc(${editorOpen ? agentFlex : collapsedAgentFlex}% - 8px)` }}
          >
            <div className="bg-white rounded-xl border border-gray-200 shadow-soft p-4 flex-1 overflow-hidden flex flex-col">
              <div className="mb-3 flex items-center justify-end gap-3 flex-shrink-0">
                {agentType === 'resume' ? (
                  <button
                    onClick={handleClearMessages}
                    disabled={messages.length === 0 || isStreaming || isSending || isClearingMessages}
                    aria-label={isClearingMessages ? '清空中' : '清空消息'}
                    className="inline-flex items-center justify-center rounded-lg border border-gray-200 bg-white p-2 text-xs text-gray-600 transition-colors hover:bg-gray-50 hover:text-gray-900 disabled:cursor-not-allowed disabled:opacity-50"
                  >
                    <TrashIcon className="w-3.5 h-3.5" />
                  </button>
                ) : (
                  <button
                    onClick={endInterview}
                    disabled={!ivSession || ivSending || ivSession?.status === 'completed'}
                    className="inline-flex items-center gap-1.5 rounded-lg border border-gray-200 bg-white px-3 py-1.5 text-xs text-gray-600 transition-colors hover:bg-gray-50 disabled:opacity-50"
                  >
                    结束面试
                  </button>
                )}
              </div>
              {agentType === 'interview' ? (
              /* ── 面试模式 ── */
              <div className="flex-1 flex flex-col min-h-0">
                <div className="flex-1 overflow-y-auto mb-4 space-y-3 min-h-0 max-h-full hide-scrollbar">
                  {ivMessages.map((m) => (
                    <div key={m.id} className={`flex w-full ${m.type === 'user' ? 'justify-end' : 'justify-start'}`}>
                      <div className={`max-w-[88%] px-4 py-3 rounded-2xl ${
                        m.type === 'user'
                          ? 'bg-primary-600 text-white rounded-br-md text-[14px] shadow-sm'
                          : m.type === 'system'
                          ? 'bg-amber-50 text-amber-900 rounded-bl-md border border-amber-100 shadow-xs'
                          : 'bg-gray-50 text-gray-800 rounded-bl-md border border-gray-100 shadow-xs'
                      }`}>
                        {m.type === 'user'
                          ? <span className="text-[14px] whitespace-pre-wrap">{m.content}</span>
                          : <MarkdownMessage content={m.content} />
                        }
                      </div>
                    </div>
                  ))}
                  {ivSending && ivMessages.every((m) => !m.id.startsWith('ai-stream-') || m.content) && (
                    <div className="flex w-full justify-start">
                      <div className="max-w-[85%] rounded-2xl rounded-bl-md border border-gray-200 bg-white px-4 py-3 text-[14px] text-gray-500 shadow-sm">
                        <span className="inline-block animate-pulse">评估中...</span>
                      </div>
                    </div>
                  )}
                  {ivSession?.report_data && (
                    <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-sm text-emerald-950">
                      <p className="font-medium">面试报告</p>
                      {ivSession.report_data.summary && <p className="mt-2">{ivSession.report_data.summary}</p>}
                      {(ivSession.report_data.weaknesses ?? []).length > 0 && (
                        <p className="mt-2">主要问题：{(ivSession.report_data.weaknesses ?? []).join('；')}</p>
                      )}
                      {(ivSession.report_data.next_training_plan ?? []).length > 0 && (
                        <p className="mt-2">下一步：{(ivSession.report_data.next_training_plan ?? []).join('；')}</p>
                      )}
                    </div>
                  )}
                  {ivError && (
                    <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">{ivError}</div>
                  )}
                  <div ref={ivMessagesEndRef} />
                </div>
                <div className="pt-3 flex-shrink-0">
                  <div className="relative">
                    <textarea
                      value={ivInput}
                      onChange={(e) => setIvInput(e.target.value)}
                      onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); sendInterviewAnswer() } }}
                      placeholder={ivSession?.status === 'completed' ? '本场面试已结束' : '输入你的回答...'}
                      className="w-full p-3 pr-12 border border-gray-200 rounded-xl text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent shadow-inner"
                      rows={2}
                      disabled={ivSending || ivSession?.status === 'completed'}
                    />
                    <button
                      onClick={sendInterviewAnswer}
                      disabled={!ivInput.trim() || ivSending || ivSession?.status === 'completed'}
                      className={`absolute right-3 top-1/2 transform -translate-y-1/2 w-9 h-9 rounded-full transition-colors flex items-center justify-center ${
                        ivInput.trim() && !ivSending && ivSession?.status !== 'completed'
                          ? 'bg-primary-600 text-white hover:bg-primary-700 shadow-md'
                          : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                      }`}
                    >
                      <ArrowUpIcon className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
              ) : (
              /* ── 简历 AGENT 模式 ── */
              <>
              {/* API错误提示 */}
              {apiError && (
                <div className="mb-4 p-3 bg-error-50 border border-error-200 rounded-lg text-sm text-error-700 flex-shrink-0">
                  <div className="flex items-center">
                    <svg className="w-4 h-4 mr-2 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                    <span>{apiError}</span>
                  </div>
                </div>
              )}
              <div className="flex-1 flex flex-col min-h-0">
                {/* Messages Display Area */}
                <div className="flex-1 overflow-y-auto mb-4 space-y-3 min-h-0 max-h-full hide-scrollbar">
                  {messages.map((message: ChatMessage) => (
                    <div
                      key={message.id}
                      className={`flex w-full ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-[85%] px-4 py-3 rounded-2xl ${message.type === 'user'
                          ? 'bg-primary-600 text-white rounded-br-md text-[14px] shadow-sm'
                          : 'bg-gray-50 text-gray-800 rounded-bl-md border border-gray-100 shadow-xs'
                          }`}
                      >
                        {message.type === 'ai' ? (
                          <>
                            {/* 有 streamEvents 时按事件顺序交错渲染；否则直接渲染完整文本 */}
                            {message.streamEvents && message.streamEvents.length > 0 ? (
                              message.streamEvents!.map((event: StreamEvent, idx: number) => {
                                if (event.type === 'tool_confirmed' || event.type === 'tool_rejected') {
                                  const isConfirmed = event.type === 'tool_confirmed'
                                  const diffLines = parseDiffSummary(event.diffSummary)
                                  return (
                                    <div key={idx} className="mb-2 rounded-2xl border border-gray-200 bg-white overflow-hidden text-xs shadow-sm">
                                      <div className="px-4 py-3 flex items-center gap-2 bg-white border-b border-gray-200">
                                        <span className="font-medium text-gray-900">{event.toolName}</span>
                                        <span className="ml-auto" />
                                        {isConfirmed ? (
                                          <svg className="w-3.5 h-3.5 flex-shrink-0 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                                        ) : (
                                          <svg className="w-3.5 h-3.5 flex-shrink-0 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                                        )}
                                      </div>
                                      <div className="bg-white px-0 py-2 font-mono">
                                        {diffLines.map((l, i) => {
                                          if (l.type === 'remove') return (
                                            <div key={i} className="px-3 py-0.5 bg-red-50 text-red-600 whitespace-pre-wrap">{l.text}</div>
                                          )
                                          if (l.type === 'add') return (
                                            <div key={i} className={`px-3 py-0.5 whitespace-pre-wrap ${isConfirmed ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-400'}`}>{l.text}</div>
                                          )
                                          return null
                                        })}
                                      </div>
                                    </div>
                                  )
                                }
                                if (event.type === 'text') return (
                                  <div key={idx}>
                                    <MarkdownMessage content={event.content} />
                                  </div>
                                )
                                return null
                              })
                            ) : (
                              <MarkdownMessage content={message.content} />
                            )}
                            {renderProposalCard(message)}
                          </>
                        ) : (
                          <span className="text-[14px]">{message.content}</span>
                        )}
                      </div>
                    </div>
                  ))}
                  {/* 流式传输中的消息（按事件顺序渲染） */}
                  {isStreaming && streamEvents.length > 0 && (
                    <div className="flex w-full justify-start">
                      <div className="max-w-[85%] px-4 py-3 rounded-lg bg-gray-50 text-gray-800 rounded-bl-sm border border-gray-200">
                        {streamEvents.map((event: StreamEvent, idx: number) => {
                          if (event.type === 'tool_pending') {
                            const diffLines = parseDiffSummary(event.diffSummary)
                            return (
                              <div key={idx} className="mb-2 rounded-2xl border border-gray-200 bg-white overflow-hidden text-xs shadow-sm">
                                {/* 标题栏 */}
                                <div className="px-4 py-3 bg-white flex items-center gap-2 border-b border-gray-200">
                                  <span className="font-medium text-gray-900">{event.toolName}</span>
                                  <span className="ml-auto" />
                                  <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse flex-shrink-0" />
                                </div>
                                {/* diff 内容区 */}
                                <div className="bg-white px-0 py-2 font-mono">
                                  {diffLines.map((l, i) => {
                                    if (l.type === 'remove') return (
                                      <div key={i} className="px-3 py-0.5 bg-red-50 text-red-600 whitespace-pre-wrap">{l.text}</div>
                                    )
                                    if (l.type === 'add') return (
                                      <div key={i} className="px-3 py-0.5 bg-green-50 text-green-700 whitespace-pre-wrap">{l.text}</div>
                                    )
                                    return (
                                      <div key={i} className="px-3 py-0.5 text-primary-600 whitespace-pre-wrap">{l.text}</div>
                                    )
                                  })}
                                </div>
                                {/* 操作按钮 */}
                                <div className="px-4 py-3 bg-white border-t border-gray-200 flex gap-2">
                                  <button
                                    onClick={() => confirmTool(event.callId, true)}
                                    className="flex-1 rounded-md bg-primary-600 py-1.5 text-xs font-medium text-white hover:bg-primary-700"
                                  >
                                    确认修改
                                  </button>
                                  <button
                                    onClick={() => confirmTool(event.callId, false)}
                                    className="flex-1 rounded-md border border-gray-300 bg-white py-1.5 text-xs font-medium text-gray-700 hover:bg-gray-50"
                                  >
                                    拒绝
                                  </button>
                                </div>
                              </div>
                            )
                          }
                          if (event.type === 'tool_confirmed' || event.type === 'tool_rejected') {
                            const isConfirmed = event.type === 'tool_confirmed'
                            const diffLines = parseDiffSummary(event.diffSummary)
                            return (
                              <div key={idx} className="mb-2 rounded-2xl border border-gray-200 bg-white overflow-hidden text-xs shadow-sm">
                                {/* 标题栏 */}
                                <div className="px-4 py-3 flex items-center gap-2 bg-white border-b border-gray-200">
                                  <span className="font-medium text-gray-900">{event.toolName}</span>
                                  <span className="ml-auto" />
                                  {isConfirmed ? (
                                    <svg className="w-3.5 h-3.5 flex-shrink-0 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                                  ) : (
                                    <svg className="w-3.5 h-3.5 flex-shrink-0 text-red-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                                  )}
                                </div>
                                {/* diff 内容 */}
                                <div className="bg-white px-0 py-2 font-mono">
                                  {diffLines.map((l, i) => {
                                    if (l.type === 'remove') return (
                                      <div key={i} className="px-3 py-0.5 bg-red-50 text-red-600 whitespace-pre-wrap">{l.text}</div>
                                    )
                                    if (l.type === 'add') return (
                                      <div key={i} className={`px-3 py-0.5 whitespace-pre-wrap ${isConfirmed ? 'bg-green-50 text-green-700' : 'bg-gray-100 text-gray-400'}`}>{l.text}</div>
                                    )
                                    return (
                                      <div key={i} className="px-3 py-0.5 text-primary-600 whitespace-pre-wrap">{l.text}</div>
                                    )
                                  })}
                                </div>
                              </div>
                            )
                          }
                          if (event.type === 'tool') {
                            return (
                              <div key={idx} className="flex items-center gap-2 text-xs text-gray-500 mb-1">
                                <div className="w-1.5 h-1.5 rounded-full bg-primary-400 animate-pulse flex-shrink-0" />
                                <span>{event.name}</span>
                              </div>
                            )
                          }
                          // text event
                          const isLastEvent = idx === streamEvents.length - 1
                          return (
                            <div key={idx} className={idx > 0 ? 'mt-2' : ''}>
                              <StreamingMessage content={event.content} isComplete={!isLastEvent} />
                            </div>
                          )
                        })}
                        {!streamEvents.some((event) => event.type === 'text' && event.content.trim()) && (
                          <div className="mt-2 rounded-2xl rounded-bl-md border border-gray-200 bg-white px-4 py-3 text-[14px] text-gray-500 shadow-sm">
                            <span className="inline-block animate-pulse">Planning next moves</span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {/* 等待响应动画 */}
                  {(isSending || isStreaming) && streamEvents.length === 0 && (
                    <div className="flex w-full justify-start">
                      <div className="max-w-[85%] rounded-2xl rounded-bl-md border border-gray-200 bg-white px-4 py-3 text-[14px] text-gray-500 shadow-sm">
                        <span className="inline-block animate-pulse">Planning next moves</span>
                      </div>
                    </div>
                  )}
                  <div ref={messagesEndRef} />
                </div>

                {/* Input Area */}
                <div className="pt-3 flex-shrink-0">
                  <div className="relative">
                    <textarea
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      onKeyPress={handleKeyPress}
                      placeholder="输入消息..."
                      className="w-full p-3 pr-12 border border-gray-200 rounded-xl text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent shadow-inner"
                      rows={2}
                      disabled={isSending || isStreaming}
                    />
                    <button
                      onClick={sendMessage}
                      disabled={!inputMessage.trim() || isSending || isStreaming}
                      className={`absolute right-3 top-1/2 transform -translate-y-1/2 w-9 h-9 rounded-full transition-colors flex items-center justify-center ${inputMessage.trim()
                        ? 'bg-primary-600 text-white hover:bg-primary-700 shadow-md'
                        : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                        } disabled:cursor-not-allowed`}
                    >
                      <ArrowUpIcon className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
              </>
              )}
            </div>
          </motion.div>
        </div>
      </main>

      {/* Boss直聘二维码弹窗 */}
      {isQrModalOpen && qrImages.length > 0 && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50">
          <div className="bg-white rounded-xl shadow-2xl p-6 w-full max-w-md relative border border-gray-200">
            <button
              onClick={() => setIsQrModalOpen(false)}
              className="absolute top-3 right-3 text-gray-500 hover:text-gray-800"
            >
              <XMarkIcon className="w-5 h-5" />
            </button>
            <h3 className="text-lg font-semibold text-gray-900 mb-2">Boss直聘登录二维码</h3>
            <p className="text-sm text-gray-600 mb-4">
              请使用 Boss 直聘 App 扫描二维码完成登录。二维码将在登录完成前保持有效。
            </p>
            <div className="flex flex-col items-center space-y-4">
              {qrImages.map((img, index) => (
                <img
                  key={`${img}-${index}`}
                  src={`data:image/png;base64,${img}`}
                  alt="Boss直聘二维码"
                  className="w-48 h-48 object-contain border border-gray-200 rounded-lg shadow"
                />
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
