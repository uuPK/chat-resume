'use client'

import { motion, AnimatePresence } from 'framer-motion'
import { useEffect, useState, useRef, useMemo, useCallback, useLayoutEffect } from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import { useAuth } from '@/lib/auth'
import { resumeApi } from '@/lib/api'
import toast from 'react-hot-toast'
import Link from 'next/link'
import {
  ArrowLeftIcon,
  ArrowUpIcon,
  ArrowDownTrayIcon,
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
import StructuredInterviewPanel from '@/components/interview/StructuredInterviewPanel'
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
import { chatHistoryApi } from '@/lib/api'
import { useInterviewSession } from '@/hooks/useInterviewSession'

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
function parseDiffSummary(raw: string): Array<{ type: 'remove' | 'add' | 'reason' | 'meta'; text: string }> {
  const lines = raw.split('\n')
  const result: Array<{ type: 'remove' | 'add' | 'reason' | 'meta'; text: string }> = []
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
    } else if (line.startsWith('改动理由：') || line.startsWith('  改动理由：')) {
      const text = line.replace(/^\s*改动理由：/, '').trim()
      if (text) result.push({ type: 'reason', text })
    }
  }
  return result
}

interface DiffGroup { remove?: string; add?: string; reason?: string }

/** 将 parseDiffSummary 返回的平铺行分组，每对"改前/改后/理由"为一组 */
function groupDiffLines(lines: Array<{ type: 'remove' | 'add' | 'reason' | 'meta'; text: string }>): DiffGroup[] {
  const groups: DiffGroup[] = []
  let current: DiffGroup | null = null
  for (const line of lines) {
    if (line.type === 'remove') {
      if (current) groups.push(current)
      current = { remove: line.text }
    } else if (line.type === 'add') {
      if (!current) current = {}
      current.add = line.text
    } else if (line.type === 'reason') {
      if (!current) current = {}
      current.reason = line.text
    }
  }
  if (current) groups.push(current)
  return groups
}

/** 将文本中的数字/百分比/量化表达高亮为绿色粗体，让用户一眼看到量化改写成果 */
const NUMBER_SPLIT_RE = /(\d[\d,，]*(?:\.\d+)?(?:%|％|万|亿|千|百|倍|x|X|次|人|个|项|天|月|年|ms|GB|MB|TB|KB)?)/

function HighlightNumbers({ text, active }: { text: string; active: boolean }) {
  if (!active) return <>{text}</>
  // split with a capturing group: even indices = plain text, odd indices = matched numbers
  const parts = text.split(NUMBER_SPLIT_RE)
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <span key={i} className="font-bold text-emerald-600 bg-emerald-100 rounded px-0.5">{part}</span>
        ) : (
          part
        )
      )}
    </>
  )
}

/** 渲染一组 diff 改动（改前 → 改后 + 理由），用于 tool_pending/confirmed/rejected */
function DiffGroupCards({ diffSummary, isConfirmed }: { diffSummary: string; isConfirmed?: boolean }) {
  const groups = groupDiffLines(parseDiffSummary(diffSummary))
  if (groups.length === 0) return null
  const addActive = isConfirmed !== false
  return (
    <div className="divide-y divide-gray-100">
      {groups.map((g, i) => (
        <div key={i} className="px-3 py-2 space-y-0.5 font-mono text-xs">
          {g.remove && (
            <div className="px-2 py-1 rounded bg-red-50 text-red-600 whitespace-pre-wrap">{g.remove}</div>
          )}
          {g.add && (
            <div className={`px-2 py-1 rounded whitespace-pre-wrap ${isConfirmed === false ? 'bg-gray-100 text-gray-400' : 'bg-green-50 text-green-700'}`}>
              <HighlightNumbers text={g.add} active={addActive} />
            </div>
          )}
          {g.reason && (
            <div className="px-2 py-1 rounded bg-amber-50 flex items-start gap-1 font-sans not-italic">
              <span className="flex-shrink-0">💡</span>
              <span className="italic text-amber-700">{g.reason}</span>
            </div>
          )}
        </div>
      ))}
    </div>
  )
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
  const [apiError, setApiError] = useState<string | null>(null)
  const [agentType, setAgentType] = useState<'resume' | 'interview'>('resume')

  const messagesEndRef = useRef<HTMLDivElement>(null)
  const messagesContainerRef = useRef<HTMLDivElement>(null)
  const shouldStickToBottomRef = useRef(true)
  const previousMessageCountRef = useRef(0)

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
  const editorAnimateWidth = editorOpen ? `calc(${editorFlex}% - 8px)` : '48px'
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
    if (agentType === 'interview') {
      setEditorOpen(false)
    } else {
      setEditorOpen(true)
    }
  }, [agentType])

  const {
    session: ivSession,
    inputMessage: ivInput,
    setInputMessage: setIvInput,
    isSending: ivSending,
    error: ivError,
    pendingAnswer: ivPendingAnswer,
    sendAnswer: sendInterviewAnswer,
    endInterview,
  } = useInterviewSession({
    resume,
    enabled: agentType === 'interview',
  })

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
  const updateStickToBottom = useCallback(() => {
    const container = messagesContainerRef.current
    if (!container) return

    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight
    shouldStickToBottomRef.current = distanceFromBottom <= 48
  }, [])

  const scrollToBottom = useCallback((behavior: ScrollBehavior = 'auto') => {
    const container = messagesContainerRef.current
    if (container) {
      container.scrollTo({ top: container.scrollHeight, behavior })
      return
    }
    messagesEndRef.current?.scrollIntoView({ behavior })
  }, [])

  const handleMessagesScroll = useCallback(() => {
    updateStickToBottom()
  }, [updateStickToBottom])

  useEffect(() => {
    updateStickToBottom()
  }, [updateStickToBottom, editorOpen, agentType])

  useLayoutEffect(() => {
    const hasNewMessage = messages.length > previousMessageCountRef.current
    previousMessageCountRef.current = messages.length

    if (!shouldStickToBottomRef.current && !hasNewMessage) {
      return
    }

    const behavior: ScrollBehavior = isStreaming ? 'auto' : (hasNewMessage ? 'smooth' : 'auto')
    scrollToBottom(behavior)
  }, [messages.length, currentStreamingMessage, isStreaming, scrollToBottom])

  useEffect(() => {
    previousMessageCountRef.current = messages.length
  }, [messages.length])

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

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }
  if (!mounted || isLoading || resumeLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#ffffff' }}>
        <div className="text-center">
          <div
            className="w-16 h-16 rounded-full border-2 border-transparent animate-spin mx-auto mb-4"
            style={{ borderTopColor: '#0052ff', borderRightColor: '#0052ff' }}
          />
          <p style={{ color: '#5b616e' }}>正在加载简历...</p>
        </div>
      </div>
    )
  }

  if (!resume) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#ffffff' }}>
        <div className="text-center">
          <p style={{ color: '#5b616e' }}>简历不存在</p>
          <Link href="/dashboard" className="btn-primary mt-4">
            返回简历中心
          </Link>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#ffffff' }}>
      {/* Header — Coinbase 风格 */}
      <header className="bg-white print:hidden" style={{ borderBottom: '1px solid rgba(91,97,110,0.15)' }}>
        <div className="w-full px-6">
          <div className="flex justify-between items-center py-3">
            <div className="flex items-center gap-3">
              <Link
                href="/dashboard"
                className="flex items-center p-2 transition-colors"
                style={{ borderRadius: '56px', color: '#0a0b0d' }}
                title="返回仪表板"
              >
                <ArrowLeftIcon className="w-5 h-5" />
              </Link>
            </div>

            <div className="flex items-center gap-3">
              <ResumeLayoutControls
                config={layoutConfig}
                onConfigChange={handleLayoutConfigChange}
              />
              <button
                onClick={handleSmartFitHeaderClick}
                disabled={isSmartFitting}
                title="自动调整间距使简历恰好一页"
                className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold transition-colors disabled:opacity-50"
                style={{
                  borderRadius: '56px',
                  backgroundColor: '#ffffff',
                  border: '1px solid rgba(91,97,110,0.25)',
                  color: '#0a0b0d',
                  cursor: isSmartFitting ? 'wait' : 'pointer',
                }}
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
                className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold text-white transition-colors disabled:opacity-50"
                style={{
                  borderRadius: '56px',
                  backgroundColor: '#0052ff',
                  border: '1px solid #0052ff',
                }}
              >
                {exporting ? (
                  <>
                    <div className="w-4 h-4 rounded-full border-2 border-transparent animate-spin" style={{ borderTopColor: '#fff' }} />
                    <span>生成中...</span>
                  </>
                ) : (
                  <>
                    <ArrowDownTrayIcon className="w-4 h-4" />
                    <span>导出 PDF</span>
                  </>
                )}
              </button>
              {AUTO_SAVE_STATUS_MESSAGE[autoSaveStatus].text && (
                <div
                  className="text-xs px-3 py-1"
                  style={{
                    borderRadius: '100000px',
                    backgroundColor: autoSaveStatus === 'error' ? '#fef2f2' : autoSaveStatus === 'success' ? '#ecfdf5' : '#eef0f3',
                    color: autoSaveStatus === 'error' ? '#dc2626' : autoSaveStatus === 'success' ? '#059669' : '#5b616e',
                  }}
                >
                  {AUTO_SAVE_STATUS_MESSAGE[autoSaveStatus].text}
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content — 三栏布局 */}
      <main className="max-w-full mx-auto px-6 py-3">
        <div
          ref={mainPanelsRef}
          className="flex gap-0 h-[calc(100vh-120px)]"
        >
          {/* Left Panel - Editor */}
          <AnimatePresence initial={false}>
          {agentType !== 'interview' && (
          <motion.div
            initial={{ opacity: 0, width: 0 }}
            animate={{ opacity: 1, width: editorAnimateWidth }}
            exit={{ opacity: 0, width: 0 }}
            transition={{ duration: 0.35, ease: 'easeInOut' }}
            className="flex flex-col min-h-0 print:hidden overflow-hidden"
            style={{ flexShrink: 0, flexGrow: 0 }}
          >
            {!editorOpen ? (
              <div
                className="flex flex-col items-center justify-center h-full w-12 cursor-pointer transition-colors group"
                style={{ backgroundColor: '#eef0f3' }}
                onClick={() => setEditorOpen(true)}
                title="展开编辑区域"
                onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#dde0e8')}
                onMouseLeave={e => (e.currentTarget.style.backgroundColor = '#eef0f3')}
              >
                <ChevronRightIcon className="w-5 h-5" style={{ color: '#5b616e' }} />
              </div>
            ) : (
            <div
              className="relative p-4 flex-1 overflow-hidden flex flex-col"
              style={{
                backgroundColor: '#ffffff',
                border: '1px solid rgba(91,97,110,0.2)',
                borderRadius: '16px',
              }}
            >
              <div className="flex-1 flex flex-col min-h-0">
                {/* Section Tabs */}
                <div
                  className="flex items-center gap-1 mb-5 flex-shrink-0 pb-0"
                  style={{ borderBottom: '1px solid rgba(91,97,110,0.15)' }}
                >
                  {editorSections.map(section => (
                    <button
                      key={section.key}
                      onClick={() => setActiveSection(section.key)}
                      className="px-4 py-2.5 text-sm font-semibold transition-colors relative"
                      style={{
                        color: activeSection === section.key ? '#0052ff' : '#5b616e',
                      }}
                    >
                      <span>{section.label}</span>
                      {activeSection === section.key && (
                        <div
                          className="absolute bottom-0 left-0 right-0 h-0.5"
                          style={{ backgroundColor: '#0052ff', borderRadius: '2px 2px 0 0' }}
                        />
                      )}
                    </button>
                  ))}
                </div>
                <button
                  onClick={() => setEditorOpen(false)}
                  className="absolute right-4 top-4 p-1.5 transition-colors"
                  style={{ borderRadius: '8px', color: '#9ca3af' }}
                  title="折叠编辑器"
                  onMouseEnter={e => { e.currentTarget.style.backgroundColor = '#eef0f3'; e.currentTarget.style.color = '#5b616e' }}
                  onMouseLeave={e => { e.currentTarget.style.backgroundColor = 'transparent'; e.currentTarget.style.color = '#9ca3af' }}
                >
                  <ChevronLeftIcon className="w-5 h-5" />
                </button>

                {/* Editor Content */}
                <div className="flex-1 overflow-y-auto min-h-0 hide-scrollbar">
                  {activeSection === 'job_application' && (
                    <JobApplicationEditor
                      data={resume.content.job_application || {}}
                      onChange={(data) => updateResumeContent('job_application', data)}
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
          )}
          </AnimatePresence>

          {agentType !== 'interview' && editorOpen && (
            <div
              className="w-2 flex-shrink-0 cursor-col-resize flex items-center justify-center group select-none print:hidden"
              onPointerDown={handleEditorDividerPointerDown}
            >
              <div
                className="w-0.5 h-full transition-colors rounded-full"
                style={{ backgroundColor: 'transparent' }}
                onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#578bfa')}
                onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
              />
            </div>
          )}

          {/* Middle Panel - Preview */}
          <motion.div
            layout
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ layout: { duration: 0.35, ease: 'easeInOut' }, opacity: { duration: 0.8, delay: 0.2 }, x: { duration: 0.8, delay: 0.2 } }}
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
            <div className="w-0.5 h-full transition-colors rounded-full" style={{ backgroundColor: 'transparent' }} />
          </div>

          {/* Right Panel - AI Chat */}
          <motion.div
            layout
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ layout: { duration: 0.35, ease: 'easeInOut' }, opacity: { duration: 0.8, delay: 0.4 }, y: { duration: 0.8, delay: 0.4 } }}
            className="agent-panel flex flex-col min-h-0 min-w-0 print:hidden"
            style={{ flex: `0 0 calc(${editorOpen ? agentFlex : collapsedAgentFlex}% - 8px)` }}
          >
            <div
              className="p-4 flex-1 overflow-hidden flex flex-col"
              style={{
                backgroundColor: '#ffffff',
                border: '1px solid rgba(91,97,110,0.2)',
                borderRadius: '16px',
              }}
            >
              <div className="mb-3 flex items-center justify-between gap-3 flex-shrink-0">
                {agentType === 'resume' && (resume.content.job_application?.target_company || resume.content.job_application?.target_title) ? (
                  <button
                    onClick={() => { setEditorOpen(true); setActiveSection('job_application') }}
                    title="点击编辑目标岗位"
                    className="flex items-center gap-1.5 text-xs font-semibold px-3 py-1 transition-colors truncate max-w-[60%]"
                    style={{
                      borderRadius: '100000px',
                      backgroundColor: '#eef0f3',
                      color: '#0052ff',
                      border: '1px solid rgba(0,82,255,0.15)',
                    }}
                  >
                    <svg className="w-3 h-3 flex-shrink-0" viewBox="0 0 20 20" fill="currentColor"><path fillRule="evenodd" d="M10 2a8 8 0 100 16A8 8 0 0010 2zm0 14a6 6 0 110-12 6 6 0 010 12zm1-9a1 1 0 10-2 0v3.586l-1.707 1.707a1 1 0 101.414 1.414l2-2A1 1 0 0011 11V7z" clipRule="evenodd"/></svg>
                    <span className="truncate">
                      {[resume.content.job_application?.target_company, resume.content.job_application?.target_title].filter(Boolean).join(' · ')}
                    </span>
                  </button>
                ) : <div />}
                {agentType === 'resume' ? (
                  <button
                    onClick={handleClearMessages}
                    disabled={messages.length === 0 || isStreaming || isSending || isClearingMessages}
                    aria-label={isClearingMessages ? '清空中' : '清空消息'}
                    className="inline-flex items-center justify-center p-2 transition-colors disabled:opacity-50"
                    style={{
                      borderRadius: '8px',
                      border: '1px solid rgba(91,97,110,0.2)',
                      backgroundColor: '#ffffff',
                      color: '#5b616e',
                    }}
                  >
                    <TrashIcon className="w-3.5 h-3.5" />
                  </button>
                ) : (
                  <div />
                )}
              </div>
              <AnimatePresence mode="wait">
              {agentType === 'interview' ? (
              /* ── 面试模式 ── */
              <motion.div
                key="interview"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="flex-1 flex flex-col min-h-0"
              >
                <StructuredInterviewPanel
                  session={ivSession}
                  inputMessage={ivInput}
                  pendingAnswer={ivPendingAnswer}
                  isSending={ivSending}
                  error={ivError}
                  onInputChange={setIvInput}
                  onSendAnswer={sendInterviewAnswer}
                  onEndInterview={endInterview}
                />
              </motion.div>
              ) : (
              /* ── 简历 AGENT 模式 ── */
              <motion.div
                key="resume"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="flex-1 flex flex-col min-h-0"
              >
              {/* API错误提示 */}
              {apiError && (
                <div
                  className="mb-4 p-3 text-sm flex-shrink-0"
                  style={{
                    borderRadius: '12px',
                    backgroundColor: '#fef2f2',
                    border: '1px solid rgba(220,38,38,0.2)',
                    color: '#dc2626',
                  }}
                >
                  <div className="flex items-center gap-2">
                    <svg className="w-4 h-4 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                      <path fillRule="evenodd" d="M10 18a8 8 0 100-16 8 8 0 000 16zM8.707 7.293a1 1 0 00-1.414 1.414L8.586 10l-1.293 1.293a1 1 0 101.414 1.414L10 11.414l1.293 1.293a1 1 0 001.414-1.414L11.414 10l1.293-1.293a1 1 0 00-1.414-1.414L10 8.586 8.707 7.293z" clipRule="evenodd" />
                    </svg>
                    <span>{apiError}</span>
                  </div>
                </div>
              )}
              <div className="flex-1 flex flex-col min-h-0">
                {/* Messages Display Area */}
                <div
                  ref={messagesContainerRef}
                  onScroll={handleMessagesScroll}
                  className="flex-1 overflow-y-auto mb-4 space-y-3 min-h-0 max-h-full hide-scrollbar"
                >
                  {messages.map((message: ChatMessage) => (
                    <div
                      key={message.id}
                      className={`flex w-full ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className="max-w-[85%] px-4 py-3"
                        style={{
                          borderRadius: message.type === 'user' ? '20px 20px 6px 20px' : '20px 20px 20px 6px',
                          backgroundColor: message.type === 'user' ? '#0052ff' : '#eef0f3',
                          color: message.type === 'user' ? '#ffffff' : '#0a0b0d',
                          border: message.type === 'user' ? 'none' : '1px solid rgba(91,97,110,0.15)',
                        }}
                      >
                        {message.type === 'ai' ? (
                          <>
                            {/* 有 streamEvents 时按事件顺序交错渲染；否则直接渲染完整文本 */}
                            {message.streamEvents && message.streamEvents.length > 0 ? (
                              message.streamEvents!.map((event: StreamEvent, idx: number) => {
                                if (event.type === 'tool_confirmed' || event.type === 'tool_rejected') {
                                  const isConfirmed = event.type === 'tool_confirmed'
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
                                      <DiffGroupCards diffSummary={event.diffSummary} isConfirmed={isConfirmed} />
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
                          </>
                        ) : (
                          <span className="text-[14px]">{message.content}</span>
                        )}
                      </div>
                    </div>
                  ))}
                  {isStreaming && streamEvents.length > 0 && (
                    <div className="flex w-full justify-start">
                      <div
                        className="max-w-[85%] px-4 py-3"
                        style={{
                          borderRadius: '20px 20px 20px 6px',
                          backgroundColor: '#eef0f3',
                          border: '1px solid rgba(91,97,110,0.15)',
                          color: '#0a0b0d',
                        }}
                      >
                        {streamEvents.map((event: StreamEvent, idx: number) => {
                          if (event.type === 'tool_pending') {
                            return (
                              <div key={idx} className="mb-2 rounded-2xl border border-gray-200 bg-white overflow-hidden text-xs shadow-sm">
                                {/* 标题栏 */}
                                <div className="px-4 py-3 bg-white flex items-center gap-2 border-b border-gray-200">
                                  <span className="font-medium text-gray-900">{event.toolName}</span>
                                  <span className="ml-auto" />
                                  <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse flex-shrink-0" />
                                </div>
                                {/* diff 内容区 */}
                                <DiffGroupCards diffSummary={event.diffSummary} isConfirmed={true} />
                                {/* 操作按钮 */}
                                <div className="px-4 py-3 bg-white border-t border-gray-200 flex gap-2">
                                  <button
                                    onClick={() => confirmTool(event.callId, true)}
                                    className="flex-1 py-1.5 text-xs font-semibold text-white transition-colors"
                                    style={{ borderRadius: '56px', backgroundColor: '#0052ff' }}
                                  >
                                    确认修改
                                  </button>
                                  <button
                                    onClick={() => confirmTool(event.callId, false)}
                                    className="flex-1 py-1.5 text-xs font-semibold transition-colors"
                                    style={{
                                      borderRadius: '56px',
                                      border: '1px solid rgba(91,97,110,0.2)',
                                      backgroundColor: '#ffffff',
                                      color: '#0a0b0d',
                                    }}
                                  >
                                    拒绝
                                  </button>
                                </div>
                              </div>
                            )
                          }
                          if (event.type === 'tool_confirmed' || event.type === 'tool_rejected') {
                            const isConfirmed = event.type === 'tool_confirmed'
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
                                <DiffGroupCards diffSummary={event.diffSummary} isConfirmed={isConfirmed} />
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
                          <div className="mt-2 px-4 py-3 text-sm" style={{ color: '#5b616e' }}>
                            <span className="inline-block animate-pulse">Planning next moves</span>
                          </div>
                        )}
                      </div>
                    </div>
                  )}

                  {(isSending || isStreaming) && streamEvents.length === 0 && (
                    <div className="flex w-full justify-start">
                      <div
                        className="max-w-[85%] px-4 py-3 text-sm"
                        style={{
                          borderRadius: '20px 20px 20px 6px',
                          backgroundColor: '#eef0f3',
                          border: '1px solid rgba(91,97,110,0.15)',
                          color: '#5b616e',
                        }}
                      >
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
                      className="w-full p-3 pr-12 text-sm resize-none focus:outline-none"
                      style={{
                        border: '1px solid rgba(91,97,110,0.25)',
                        borderRadius: '12px',
                        color: '#0a0b0d',
                      }}
                      rows={2}
                      disabled={isSending || isStreaming}
                    />
                    <button
                      onClick={sendMessage}
                      disabled={!inputMessage.trim() || isSending || isStreaming}
                      className="absolute right-3 top-1/2 -translate-y-1/2 w-9 h-9 rounded-full transition-colors flex items-center justify-center disabled:cursor-not-allowed"
                      style={{
                        backgroundColor: inputMessage.trim() ? '#0052ff' : '#eef0f3',
                        color: inputMessage.trim() ? '#ffffff' : '#9ca3af',
                      }}
                    >
                      <ArrowUpIcon className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>
              </motion.div>
              )}
              </AnimatePresence>
            </div>
          </motion.div>
        </div>
      </main>

    </div>
  )
}
