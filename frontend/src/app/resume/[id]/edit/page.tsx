'use client'

import { motion } from 'framer-motion'
import { useEffect, useState, useRef, useMemo, useCallback } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth'
import { resumeApi } from '@/lib/api'
import toast from 'react-hot-toast'
import Link from 'next/link'
import {
  ArrowLeftIcon,
  CheckIcon,
  ArrowUpIcon,
  ArrowDownTrayIcon,
  XMarkIcon,
  ChevronLeftIcon,
  ChevronRightIcon
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
  loadLayoutConfig,
  saveLayoutConfig,
  MODULE_LABELS,
  DEFAULT_LAYOUT_CONFIG
} from '@/lib/resumeLayoutConfig'
import MarkdownMessage from '@/components/ui/MarkdownMessage'
import StreamingMessage from '@/components/ui/StreamingMessage'
import { useStreamingChat, ChatMessage, StreamEvent } from '@/hooks/useStreamingChat'
import { chatHistoryApi } from '@/lib/api'

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
      name: string
      level: string
      category: string
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
      result.push({ type: 'remove', text: '- ' + line.replace(/^\s*改前：/, '') })
    } else if (line.startsWith('改后：') || line.startsWith('  改后：')) {
      result.push({ type: 'add', text: '+ ' + line.replace(/^\s*改后：/, '') })
    }
  }
  return result
}

export default function ResumeEditPage() {
  const params = useParams()
  const router = useRouter()
  const { user, isAuthenticated, isLoading } = useAuth()
  const [mounted, setMounted] = useState(false)
  const [resume, setResume] = useState<Resume | null>(null)
  const [resumeLoading, setResumeLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [autoSaveStatus, setAutoSaveStatus] = useState<AutoSaveStatus>('idle')
  const [activeSection, setActiveSection] = useState('job_application')
  const [editorOpen, setEditorOpen] = useState(false)
  const [editorFlex, setEditorFlex] = useState(30)
  const [agentFlex, setAgentFlex] = useState(30)
  const mainPanelsRef = useRef<HTMLDivElement>(null)
  const autoSaveTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const statusResetTimeoutRef = useRef<NodeJS.Timeout | null>(null)
  const resumeRef = useRef<Resume | null>(null)

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
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputMessage, setInputMessage] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [proposalActionLoadingId, setProposalActionLoadingId] = useState<number | null>(null)
  const [apiError, setApiError] = useState<string | null>(null)
  const [qrImages, setQrImages] = useState<string[]>([])
  const [isQrModalOpen, setIsQrModalOpen] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // 布局配置状态
  const [layoutConfig, setLayoutConfig] = useState<ResumeLayoutConfig>(DEFAULT_LAYOUT_CONFIG)

  const resumeId = params?.id as string

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
    onMessage: (message) => {
      setMessages(prev => {
        const next = [...prev, message]
        // 找到最后一条用户消息和刚收到的 AI 消息，一起持久化
        const lastUser = [...next].reverse().find(m => m.type === 'user')
        if (lastUser && resumeId) {
          chatHistoryApi.appendMessages(parseInt(resumeId), [
            { role: 'user', content: lastUser.content },
            {
              role: 'assistant',
              content: message.content,
              stream_events: message.streamEvents || null,
            },
          ]).catch(console.error)
        }
        return next
      })
    },
    onError: (error) => {
      setApiError(error)
      const errorMessage: ChatMessage = {
        id: Date.now().toString(),
        type: 'ai',
        content: `抱歉，发生了错误：${error}`,
        timestamp: new Date()
      }
      setMessages(prev => [...prev, errorMessage])
    },
    onQrImages: (images) => {
      if (images && images.length > 0) {
        setQrImages(images)
        setIsQrModalOpen(true)
      }
    },
    onResumeUpdate: (content) => {
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
        setMessages(loaded)
      }
    } catch (e) {
      console.error('Failed to load chat history:', e)
    }
  }

  // 加载布局配置
  useEffect(() => {
    if (resumeId) {
      const config = loadLayoutConfig(parseInt(resumeId))
      setLayoutConfig(config)
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
    }
  }, [])

  // 处理布局配置变化
  const handleLayoutConfigChange = (newConfig: ResumeLayoutConfig) => {
    setLayoutConfig(newConfig)
    if (resumeId) {
      saveLayoutConfig(parseInt(resumeId), newConfig)
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

      if (autoSaveTimeoutRef.current) {
        clearTimeout(autoSaveTimeoutRef.current)
        autoSaveTimeoutRef.current = null
      }

      setAutoSaveStatus('saving')
      try {
        await resumeApi.updateResume(resumeRef.current.id, {
          title: resumeRef.current.title,
          content: resumeRef.current.content
        })
        setAutoSaveStatus('success')
        if (showSuccessToast) {
          toast.success('简历保存成功')
        }
        scheduleStatusReset()
      } catch (error) {
        console.error('Auto save error:', error)
        setAutoSaveStatus('error')
        toast.error('自动保存失败，请检查网络或手动保存')
        throw error
      }
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

  // 保存简历
  const handleSave = async () => {
    if (!resume) return

    try {
      setSaving(true)
      await performAutoSave({ showSuccessToast: true })
    } catch (error) {
      console.error('Save error:', error)
    } finally {
      setSaving(false)
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
    scheduleAutoSave()
  }

  // 聊天功能
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }

  const sendMessage = async () => {
    if (!inputMessage.trim() || isSending || isStreaming) return

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: inputMessage.trim(),
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
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

  const updateMessageProposalStatus = (
    messageId: string,
    status: 'pending' | 'applied' | 'rejected'
  ) => {
    setMessages(prev =>
      prev.map(message =>
        message.id === messageId && message.proposal
          ? { ...message, proposal: { ...message.proposal, proposalStatus: status } }
          : message
      )
    )
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
            <div className="flex items-center">
              <Link
                href="/dashboard"
                className="flex items-center p-2 rounded-lg text-gray-600 hover:text-gray-900 hover:bg-gray-50 transition-colors"
                title="返回仪表板"
              >
                <ArrowLeftIcon className="w-5 h-5" />
                <span className="ml-2 text-sm font-medium">返回</span>
              </Link>
            </div>

            <div className="flex items-center space-x-4">
              <div className="flex items-center space-x-3">
                <ResumeLayoutControls
                  config={layoutConfig}
                  onConfigChange={handleLayoutConfigChange}
                />
                <div className="h-6 w-px bg-gray-200"></div>
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
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="inline-flex items-center px-4 py-2 text-sm font-medium rounded-lg bg-primary-600 text-white hover:bg-primary-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-primary-500 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                >
                  {saving ? (
                    <>
                      <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                      <span>保存中...</span>
                    </>
                  ) : (
                    <>
                      <CheckIcon className="w-4 h-4 mr-2" />
                      <span>保存</span>
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
          className={`flex gap-0 h-[calc(100vh-120px)] ${editorOpen ? '' : 'lg:[&_.preview-panel]:flex-1 lg:[&_.agent-panel]:flex-1'}`}
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
                className="flex flex-col items-center justify-center h-full w-12 cursor-pointer bg-gray-50 hover:bg-gray-100 border-r border-gray-200 transition-colors group"
                onClick={() => setEditorOpen(true)}
                title="展开编辑区域"
              >
                <ChevronRightIcon className="w-5 h-5 text-gray-500 group-hover:text-gray-700" />
                <span className="mt-2 text-xs text-gray-500 group-hover:text-gray-700 writing-mode-vertical-rl">编辑器</span>
              </div>
            ) : (
            <div className="bg-white rounded-xl border border-gray-200 shadow-soft p-4 flex-1 overflow-hidden flex flex-col">
              <div className="mb-4 flex justify-between items-center flex-shrink-0">
                <h3 className="text-sm font-semibold text-gray-900">简历编辑器</h3>
                <button
                  onClick={() => setEditorOpen(false)}
                  className="p-1.5 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors"
                  title="折叠编辑器"
                >
                  <ChevronLeftIcon className="w-5 h-5" />
                </button>
              </div>
              <div className="flex-1 flex flex-col min-h-0">
                {/* Section Tabs - 现代化设计 */}
                <div className="flex space-x-2 mb-5 border-b border-gray-200 flex-shrink-0">
                  {[
                    { key: 'job_application', label: '投递岗位' },
                    { key: 'personal', label: '个人信息' },
                    { key: 'education', label: '教育经历' },
                    { key: 'work', label: '工作经验' },
                    { key: 'projects', label: '项目' },
                    { key: 'skills', label: '技能' }
                  ].map(section => (
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
              <div className="w-0.5 h-full bg-gray-300 group-hover:bg-primary-400 transition-colors rounded-full" />
            </div>
          )}

          {/* Middle Panel - Preview */}
          <motion.div
            initial={{ opacity: 0, x: 20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="preview-panel flex flex-col min-h-0 min-w-0 print:w-full print:h-auto print:absolute print:top-0 print:left-0 print:m-0 print:p-0"
            style={{ flex: `1 1 calc(${100 - editorFlex - agentFlex}% - 16px)` }}
          >
            <div className="bg-white rounded-xl border border-gray-200 shadow-soft p-5 flex-1 overflow-hidden flex flex-col print:shadow-none print:border-none print:p-0">
              <div className="mb-4 flex-shrink-0">
                <h3 className="text-sm font-semibold text-gray-900">简历预览</h3>
                <p className="text-xs text-gray-500 mt-1">实时预览您的简历效果</p>
              </div>
              <div className="flex-1 overflow-hidden min-h-0 print:overflow-visible print:h-auto">
                <ResumePreview
                  key={JSON.stringify(moduleOrder.map(m => `${m.type}-${m.order}-${m.visible}`))}
                  content={resume.content}
                  moduleOrder={moduleOrder}
                />
              </div>
            </div>
          </motion.div>

          {/* 拖拽分隔条 */}
          <div
            className="w-2 flex-shrink-0 cursor-col-resize flex items-center justify-center group select-none print:hidden"
            onPointerDown={handleAgentDividerPointerDown}
          >
            <div className="w-0.5 h-full bg-gray-300 group-hover:bg-primary-400 transition-colors rounded-full" />
          </div>

          {/* Right Panel - AI Chat */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.4 }}
            className="agent-panel flex flex-col min-h-0 min-w-0 print:hidden"
            style={{ flex: `0 0 calc(${agentFlex}% - 8px)` }}
          >
            <div className="bg-white rounded-xl border border-gray-200 shadow-soft p-4 flex-1 overflow-hidden flex flex-col">
              {/* 顶栏：标题 + 清空按钮 */}
              <div className="flex items-center justify-between mb-4 flex-shrink-0">
                <div>
                  <h3 className="text-sm font-semibold text-gray-900">AI简历优化助手</h3>
                  <p className="text-xs text-gray-500 mt-0.5">智能优化您的简历内容</p>
                </div>
                {messages.length > 0 && (
                  <button
                    onClick={async () => {
                      if (!resumeId) return
                      await chatHistoryApi.clearMessages(parseInt(resumeId)).catch(console.error)
                      setMessages([])
                    }}
                    className="text-xs px-3 py-1.5 rounded-lg border border-gray-200 text-gray-600 hover:text-red-600 hover:border-red-200 hover:bg-red-50 transition-colors"
                  >
                    清空记录
                  </button>
                )}
              </div>
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
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex w-full ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-[85%] px-4 py-3 rounded-2xl ${message.type === 'user'
                          ? 'bg-primary-600 text-white rounded-br-md text-sm shadow-sm'
                          : 'bg-gray-50 text-gray-800 rounded-bl-md border border-gray-100 shadow-xs'
                          }`}
                      >
                        {message.type === 'ai' ? (
                          <>
                            {/* 有 streamEvents 时按事件顺序交错渲染；否则直接渲染完整文本 */}
                            {message.streamEvents && message.streamEvents.length > 0 ? (
                              message.streamEvents.map((event, idx) => {
                                if (event.type === 'tool_confirmed' || event.type === 'tool_rejected') {
                                  const isConfirmed = event.type === 'tool_confirmed'
                                  const diffLines = parseDiffSummary(event.diffSummary)
                                  return (
                                    <div key={idx} className={`mb-2 rounded-lg border overflow-hidden text-xs ${isConfirmed ? 'border-green-200' : 'border-gray-300'}`}>
                                      <div className={`px-3 py-2 flex items-center gap-2 ${isConfirmed ? 'bg-green-50' : 'bg-gray-50'}`}>
                                        {isConfirmed ? (
                                          <svg className="w-3.5 h-3.5 flex-shrink-0 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                                        ) : (
                                          <svg className="w-3.5 h-3.5 flex-shrink-0 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                                        )}
                                        <span className={`font-medium ${isConfirmed ? 'text-green-800' : 'text-gray-500'}`}>{event.toolName}</span>
                                        <span className={`ml-auto ${isConfirmed ? 'text-green-500' : 'text-gray-400'}`}>{isConfirmed ? '已应用' : '已拒绝'}</span>
                                      </div>
                                      <div className="bg-white px-0 py-1 font-mono">
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
                          <span className="text-sm">{message.content}</span>
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
                              <div key={idx} className="mb-2 rounded-lg border border-amber-200 overflow-hidden text-xs">
                                {/* 标题栏 */}
                                <div className="px-3 py-2 bg-amber-50 flex items-center gap-2">
                                  <div className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse flex-shrink-0" />
                                  <span className="font-medium text-amber-800">{event.toolName}</span>
                                  <span className="text-amber-500 ml-auto">待确认</span>
                                </div>
                                {/* diff 内容区 */}
                                <div className="bg-white px-0 py-1 font-mono">
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
                                <div className="px-3 py-2 bg-gray-50 border-t border-gray-200 flex gap-2">
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
                              <div key={idx} className={`mb-2 rounded-lg border overflow-hidden text-xs ${isConfirmed ? 'border-green-200' : 'border-gray-300'}`}>
                                {/* 标题栏 */}
                                <div className={`px-3 py-2 flex items-center gap-2 ${isConfirmed ? 'bg-green-50' : 'bg-gray-50'}`}>
                                  {isConfirmed ? (
                                    <svg className="w-3.5 h-3.5 flex-shrink-0 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" /></svg>
                                  ) : (
                                    <svg className="w-3.5 h-3.5 flex-shrink-0 text-gray-400" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" /></svg>
                                  )}
                                  <span className={`font-medium ${isConfirmed ? 'text-green-800' : 'text-gray-500'}`}>{event.toolName}</span>
                                  <span className={`ml-auto ${isConfirmed ? 'text-green-500' : 'text-gray-400'}`}>{isConfirmed ? '已应用' : '已拒绝'}</span>
                                </div>
                                {/* diff 内容 */}
                                <div className="bg-white px-0 py-1 font-mono">
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
                      </div>
                    </div>
                  )}

                  {/* 等待响应动画 */}
                  {(isSending || isStreaming) && streamEvents.length === 0 && (
                    <div className="flex w-full justify-start">
                      <div className="bg-gray-100 text-gray-800 px-4 py-2 rounded-lg rounded-bl-sm text-sm">
                        <div className="flex items-center space-x-1">
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"></div>
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.1s' }}></div>
                          <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0.2s' }}></div>
                        </div>
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
