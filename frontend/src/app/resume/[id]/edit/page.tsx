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
import { useStreamingChat, ChatMessage } from '@/hooks/useStreamingChat'
// 已移除错误的前端Gemini集成

interface Resume {
  id: number
  title: string
  content: {
    job_application?: {
      company?: string
      position?: string
      jd?: string
    }
    personal_info?: {
      name?: string
      email?: string
      phone?: string
      position?: string
      github?: string
    }
    education?: Array<{
      id?: number
      school: string
      major: string
      degree: string
      duration: string
      description?: string
    }>
    work_experience?: Array<{
      id?: number
      company: string
      position: string
      duration: string
      description: string
    }>
    skills?: Array<{
      id?: number
      name: string
      level: string
      category: string
    }>
    projects?: Array<{
      id?: number
      name: string
      description: string
      technologies: string[]
      role: string
      duration: string
      github_url?: string
      demo_url?: string
      achievements: string[]
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
  saving: { text: '自动保存中…', className: 'text-blue-600' },
  success: { text: '已自动保存', className: 'text-green-600' },
  error: { text: '自动保存失败，请检查网络或手动保存', className: 'text-red-600' }
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
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      id: '1',
      type: 'ai',
      content: `您好！我是您的简历优化Agent，我能提供以下服务：

1. **岗位定向优化**：根据目标职位的JD，提出针对性修改建议

2. **内容精炼与结构优化**：帮您梳理项目描述、强化个人亮点

3. **量化成果与关键词增强**：引导您将抽象描述转化为具体成就

4. **句子优化与润色建议**：对语句进行逻辑性、表达清晰度与专业度优化

请输入您需要的服务的数字编号。`,
      timestamp: new Date()
    }
  ])
  const [inputMessage, setInputMessage] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [apiError, setApiError] = useState<string | null>(null)
  const [qrImages, setQrImages] = useState<string[]>([])
  const [isQrModalOpen, setIsQrModalOpen] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  // 布局配置状态
  const [layoutConfig, setLayoutConfig] = useState<ResumeLayoutConfig>(DEFAULT_LAYOUT_CONFIG)

  const resumeId = params?.id as string

  // 调试信息
  console.log('Resume ID from params:', resumeId)
  console.log('Parsed Resume ID:', parseInt(resumeId))
  console.log('Current user:', user)

  // 流式聊天Hook
  const {
    isStreaming,
    currentStreamingMessage,
    currentToolCalls,
    sendStreamingMessage,
    stopStreaming
  } = useStreamingChat(parseInt(resumeId), {
    onMessage: (message) => {
      setMessages(prev => [...prev, message])
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
    onResumeUpdate: (resumeContent) => {
      // AI 修改简历后，更新本地状态
      setResume(prev => {
        if (!prev) return prev
        const updated = {
          ...prev,
          content: resumeContent as Resume['content']
        }
        resumeRef.current = updated
        return updated
      })
    }
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
    }
  }, [mounted, isAuthenticated, resumeId])

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

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }



  // 自动滚动到底部
  useEffect(() => {
    scrollToBottom()
  }, [messages])

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
      {/* Header */}
      <header className="bg-white shadow-sm border-b print:hidden">
        <div className="w-full px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center py-4">
            <div className="flex items-center space-x-4">
              <Link
                href="/dashboard"
                className="flex items-center space-x-2 text-gray-600 hover:text-gray-900"
              >
                <ArrowLeftIcon className="w-5 h-5 ml-9" />
              </Link>
            </div>

            <div className="flex items-center space-x-3">
              <ResumeLayoutControls
                config={layoutConfig}
                onConfigChange={handleLayoutConfigChange}
              />
              <button
                onClick={handleExportPDF}
                disabled={exporting}
                className="btn-secondary flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {exporting ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-gray-600"></div>
                    <span>生成中...</span>
                  </>
                ) : (
                  <>
                    <ArrowDownTrayIcon className="w-4 h-4" />
                    <span>导出 PDF</span>
                  </>
                )}
              </button>
              <button
                onClick={handleSave}
                disabled={saving}
                className="btn-primary flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {saving ? (
                  <>
                    <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white"></div>
                    <span>保存中...</span>
                  </>
                ) : (
                  <>
                    <CheckIcon className="w-4 h-4" />
                    <span>保存</span>
                  </>
                )}
              </button>
              {AUTO_SAVE_STATUS_MESSAGE[autoSaveStatus].text && (
                <div className={`text-xs ${AUTO_SAVE_STATUS_MESSAGE[autoSaveStatus].className}`}>
                  {AUTO_SAVE_STATUS_MESSAGE[autoSaveStatus].text}
                </div>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-full mx-auto px-4 sm:px-6 lg:px-8 py-4">
        <div
          ref={mainPanelsRef}
          className={`flex gap-0 h-[calc(100vh-140px)] ${editorOpen ? '' : 'lg:[&_.preview-panel]:flex-1 lg:[&_.agent-panel]:flex-1'}`}
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
              /* 折叠状态：细条 */
              <div
                className="card flex flex-col items-center justify-center h-full w-10 cursor-pointer hover:bg-gray-50 transition-colors"
                onClick={() => setEditorOpen(true)}
                title="展开编辑区域"
              >
                <ChevronRightIcon className="w-4 h-4 text-gray-500" />
              </div>
            ) : (
            <div className="card p-4 flex-1 overflow-hidden flex flex-col">
              <div className="mb-4 flex justify-end flex-shrink-0">
                <button
                  onClick={() => setEditorOpen(false)}
                  className="text-gray-400 hover:text-gray-600 transition-colors"
                  title="折叠"
                >
                  <ChevronLeftIcon className="w-5 h-5" />
                </button>
              </div>
              <div className="flex-1 flex flex-col min-h-0">
                {/* Section Tabs */}
                <div className="flex space-x-1 mb-4 bg-gray-100 p-1 rounded-lg flex-shrink-0">
                  {[
                    { key: 'job_application', label: '投递岗位' },
                    { key: 'personal', label: '个人信息' },
                    { key: 'education', label: '教育经历' },
                    { key: 'work', label: '工作经验' },
                    { key: 'skills', label: '技能' },
                    { key: 'projects', label: '项目' }
                  ].map(section => (
                    <button
                      key={section.key}
                      onClick={() => setActiveSection(section.key)}
                      className={`flex-1 flex items-center justify-center px-3 py-2 rounded-md text-sm font-medium transition-colors ${activeSection === section.key
                        ? 'bg-white text-primary-600 shadow-sm'
                        : 'text-gray-600 hover:text-gray-900'
                        }`}
                    >
                      <span>{section.label}</span>
                    </button>
                  ))}
                </div>

                {/* Editor Content */}
                <div className="flex-1 overflow-y-auto min-h-0 pr-2">
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
              className="w-3 flex-shrink-0 cursor-col-resize flex items-center justify-center group select-none print:hidden"
              onPointerDown={handleEditorDividerPointerDown}
            >
              <div className="w-1 h-full bg-gray-200 group-hover:bg-blue-400 transition-colors rounded-full" />
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
            <div className="card p-4 flex-1 overflow-hidden flex flex-col print:shadow-none print:border-none print:p-0">
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
            className="w-3 flex-shrink-0 cursor-col-resize flex items-center justify-center group select-none print:hidden"
            onPointerDown={handleAgentDividerPointerDown}
          >
            <div className="w-1 h-full bg-gray-200 group-hover:bg-blue-400 transition-colors rounded-full" />
          </div>

          {/* Right Panel - AI Chat */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.4 }}
            className="agent-panel flex flex-col min-h-0 min-w-0 print:hidden"
            style={{ flex: `0 0 calc(${agentFlex}% - 8px)` }}
          >
            <div className="card p-4 flex-1 overflow-hidden flex flex-col">
              {/* API错误提示 */}
              {apiError && (
                <div className="mb-3 p-2 bg-orange-50 border border-orange-200 rounded-lg text-sm text-orange-700 flex-shrink-0">
                  ⚠️ {apiError}
                </div>
              )}
              <div className="flex-1 flex flex-col min-h-0">
                {/* Messages Display Area */}
                <div className="flex-1 overflow-y-auto mb-4 space-y-3 pr-2 min-h-0 max-h-full">
                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex w-full ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-[85%] px-4 py-3 rounded-lg ${message.type === 'user'
                          ? 'bg-blue-600 text-white rounded-br-sm text-sm'
                          : 'bg-gray-50 text-gray-800 rounded-bl-sm border border-gray-200'
                          }`}
                      >
                        {message.type === 'ai' ? (
                          <>
                            {message.toolCalls && message.toolCalls.length > 0 && (
                              <div className="mb-3 space-y-2">
                                {message.toolCalls.map((tool, index) => (
                                  <div key={index} className="bg-white border text-xs rounded-md overflow-hidden shadow-sm">
                                    <div className="px-3 py-2 bg-gray-50 border-b flex items-center justify-between">
                                      <div className="flex items-center gap-2">
                                        <div className="w-1.5 h-1.5 rounded-full bg-blue-500"></div>
                                        <span className="font-medium text-gray-700">工具调用: {tool.name}</span>
                                      </div>
                                    </div>
                                    <div className="px-3 py-2 text-gray-600 bg-white font-mono break-all whitespace-pre-wrap max-h-40 overflow-y-auto">
                                      {tool.result}
                                    </div>
                                  </div>
                                ))}
                              </div>
                            )}
                            <MarkdownMessage content={message.content} />
                          </>
                        ) : (
                          <span className="text-sm">{message.content}</span>
                        )}
                      </div>
                    </div>
                  ))}
                  {/* 流式传输中的消息 */}
                  {isStreaming && (currentStreamingMessage || (currentToolCalls && currentToolCalls.length > 0)) && (
                    <div className="flex w-full justify-start">
                      <div className="max-w-[85%] px-4 py-3 rounded-lg bg-gray-50 text-gray-800 rounded-bl-sm border border-gray-200">
                        {currentToolCalls && currentToolCalls.length > 0 && (
                          <div className="mb-3 space-y-2">
                            {currentToolCalls.map((tool, index) => (
                              <div key={index} className="bg-white border text-xs rounded-md overflow-hidden shadow-sm">
                                <div className="px-3 py-2 bg-gray-50 border-b flex items-center justify-between">
                                  <div className="flex items-center gap-2">
                                    <div className="w-1.5 h-1.5 rounded-full bg-blue-500"></div>
                                    <span className="font-medium text-gray-700">工具调用: {tool.name}</span>
                                  </div>
                                </div>
                                <div className="px-3 py-2 text-gray-600 bg-white font-mono break-all whitespace-pre-wrap max-h-40 overflow-y-auto">
                                  {tool.result}
                                </div>
                              </div>
                            ))}
                          </div>
                        )}
                        <StreamingMessage content={currentStreamingMessage} isComplete={false} />
                      </div>
                    </div>
                  )}

                  {/* 等待响应动画 */}
                  {(isSending || isStreaming) && !currentStreamingMessage && (
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
                      className="w-full p-2 pr-12 border border-gray-300 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                      rows={2}
                      disabled={isSending || isStreaming}
                    />
                    <button
                      onClick={sendMessage}
                      disabled={!inputMessage.trim() || isSending || isStreaming}
                      className={`absolute right-2 top-1/2 transform -translate-y-1/2 w-8 h-8 rounded-full transition-colors flex items-center justify-center ${inputMessage.trim()
                        ? 'bg-blue-600 text-white hover:bg-blue-700'
                        : 'bg-gray-300 text-gray-500 cursor-not-allowed'
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
