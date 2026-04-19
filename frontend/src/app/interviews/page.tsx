'use client'

/**
 * 面试中心页模块
 *
 * 用于让用户在进入面试前选择简历、补充岗位上下文，并查看历史面试记录。
 */

import { useEffect, useRef, useState } from 'react'
import { useAuth } from '@/lib/auth'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import Link from 'next/link'
import MainNavigation from '@/components/layout/MainNavigation'
import { resumeApi, type InterviewSessionSummary, type Resume, type ResumeListItem } from '@/lib/api'
import {
  ClockIcon,
  MicrophoneIcon,
  PlayCircleIcon,
  TrashIcon,
  XMarkIcon,
} from '@heroicons/react/24/outline'

/**
 * 用于把服务端时间格式化成北京时间展示。
 */
function formatDate(dateString: string) {
  const d = new Date(dateString.includes('Z') || dateString.includes('+') ? dateString : `${dateString}Z`)
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
    timeZone: 'Asia/Shanghai',
    hour12: false,
  }).format(d)
}

/**
 * 用于把面试状态映射成界面上的标签文案和颜色。
 */
function statusLabel(status: string) {
  if (status === 'completed') return { text: '已完成', bg: '#eef0f3', color: '#0a0b0d' }
  if (status === 'waiting_user_answer') return { text: '进行中', bg: '#eef0f3', color: '#0052ff' }
  return { text: '未开始', bg: '#eef0f3', color: '#5b616e' }
}

/**
 * 用于从简历列表和详情中提取岗位与 JD 的默认值。
 */
function readInterviewDefaults(resumeItem?: ResumeListItem, resumeDetail?: Resume | null) {
  const jobApplication = resumeDetail?.content?.job_application || {}
  return {
    targetCompany: jobApplication.target_company || resumeItem?.target_company || '',
    targetTitle: jobApplication.target_title || resumeItem?.target_title || '',
    jdText: jobApplication.jd_text || '',
  }
}

const INTERVIEW_MODE_OPTIONS = [
  {
    value: 'practice',
    label: '练习模式',
    description: '题后即时反馈，可随时获取答题提示。',
  },
  {
    value: 'simulation',
    label: '拟真模式',
    description: '不展示题后反馈和提示，更接近真实面试节奏。',
  },
] as const

/**
 * 面试中心页组件
 *
 * 用于承接新建面试和查看历史面试这两个核心入口。
 */
export default function InterviewsPage() {
  const { isAuthenticated, isLoading } = useAuth()
  const router = useRouter()
  const resumeCacheRef = useRef<Record<number, Resume>>({})

  const [mounted, setMounted] = useState(false)
  const [loading, setLoading] = useState(true)
  const [pageError, setPageError] = useState<string | null>(null)
  const [sessions, setSessions] = useState<InterviewSessionSummary[]>([])
  const [resumes, setResumes] = useState<ResumeListItem[]>([])
  const [showCreateInterviewPanel, setShowCreateInterviewPanel] = useState(false)
  const [interviewMode, setInterviewMode] = useState<'practice' | 'simulation'>('practice')
  const [selectedResumeId, setSelectedResumeId] = useState('')
  const [selectedResumeLoading, setSelectedResumeLoading] = useState(false)
  const [creatingSession, setCreatingSession] = useState(false)
  const [deletingSessionId, setDeletingSessionId] = useState<number | null>(null)
  const [formError, setFormError] = useState<string | null>(null)
  const [targetCompany, setTargetCompany] = useState('')
  const [targetTitle, setTargetTitle] = useState('')
  const [jdText, setJdText] = useState('')

  /**
   * 用于在客户端挂载后再读取鉴权状态和本地缓存。
   */
  useEffect(() => {
    setMounted(true)
  }, [])

  /**
   * 用于在用户未登录时把面试中心重定向到登录页。
   */
  useEffect(() => {
    if (mounted && !isLoading && !isAuthenticated) router.push('/login')
  }, [mounted, isLoading, isAuthenticated, router])

  /**
   * 用于首次进入页面时并行加载简历列表和历史面试记录。
   */
  useEffect(() => {
    if (!mounted || !isAuthenticated) return

    let active = true
    setLoading(true)
    setPageError(null)

    Promise.all([resumeApi.getResumes(), resumeApi.listInterviewSessions()])
      .then(([loadedResumes, loadedSessions]) => {
        if (!active) return
        setResumes(loadedResumes)
        setSessions(loadedSessions)
      })
      .catch((error) => {
        if (!active) return
        setPageError(error instanceof Error ? error.message : '加载面试中心失败')
      })
      .finally(() => {
        if (!active) return
        setLoading(false)
      })

    return () => {
      active = false
    }
  }, [mounted, isAuthenticated])

  /**
   * 用于在用户切换简历后读取该简历已保存的岗位和 JD。
   */
  useEffect(() => {
    if (!mounted || !isAuthenticated || !selectedResumeId) {
      setTargetCompany('')
      setTargetTitle('')
      setJdText('')
      setFormError(null)
      return
    }

    const resumeId = Number(selectedResumeId)
    const resumeItem = resumes.find((item) => item.id === resumeId)
    const cachedResume = resumeCacheRef.current[resumeId]
    const initialDefaults = readInterviewDefaults(resumeItem, cachedResume)

    let active = true
    setSelectedResumeLoading(true)
    setFormError(null)
    setTargetCompany(initialDefaults.targetCompany)
    setTargetTitle(initialDefaults.targetTitle)
    setJdText(initialDefaults.jdText)

    const applyResumeDefaults = (resumeDetail?: Resume | null) => {
      if (!active) return
      const defaults = readInterviewDefaults(resumeItem, resumeDetail)
      setTargetCompany(defaults.targetCompany)
      setTargetTitle(defaults.targetTitle)
      setJdText(defaults.jdText)
    }

    if (cachedResume) {
      applyResumeDefaults(cachedResume)
      setSelectedResumeLoading(false)
      return () => {
        active = false
      }
    }

    resumeApi.getResume(resumeId)
      .then((resumeDetail) => {
        if (!active) return
        resumeCacheRef.current[resumeId] = resumeDetail
        applyResumeDefaults(resumeDetail)
      })
      .catch((error) => {
        if (!active) return
        setFormError(error instanceof Error ? error.message : '读取简历中的岗位信息失败，请手动填写')
      })
      .finally(() => {
        if (!active) return
        setSelectedResumeLoading(false)
      })

    return () => {
      active = false
    }
  }, [mounted, isAuthenticated, resumes, selectedResumeId])

  /**
   * 用于根据当前配置创建新的结构化面试 session 并跳转到面试页。
   */
  const handleCreateInterview = async () => {
    if (!selectedResumeId) {
      setFormError('请先选择一份简历')
      return
    }

    setCreatingSession(true)
    setFormError(null)

    try {
      const resumeId = Number(selectedResumeId)
      const result = await resumeApi.createInterviewSession({
        resume_id: resumeId,
        target_company: targetCompany.trim() || undefined,
        target_title: targetTitle.trim() || undefined,
        jd_text: jdText.trim() || undefined,
        interview_type: 'general',
        difficulty: 'medium',
        language: 'zh-CN',
        mode: interviewMode,
      })
      router.push(`/resume/${resumeId}/interview?session=${result.session.id}`)
    } catch (error) {
      setFormError(error instanceof Error ? error.message : '创建面试失败，请稍后重试')
    } finally {
      setCreatingSession(false)
    }
  }

  /**
   * 用于删除一条历史面试记录，并在成功后同步更新列表状态。
   */
  const handleDeleteInterview = async (sessionId: number) => {
    const confirmed = window.confirm('确认删除这条面试记录吗？删除后无法恢复。')
    if (!confirmed) return

    setDeletingSessionId(sessionId)
    setPageError(null)
    try {
      await resumeApi.deleteInterviewSession(sessionId)
      setSessions((currentSessions) => currentSessions.filter((session) => session.id !== sessionId))
    } catch (error) {
      setPageError(error instanceof Error ? error.message : '删除面试记录失败')
    } finally {
      setDeletingSessionId(null)
    }
  }

  /**
   * 用于打开创建面试弹层，让用户在不离开当前页面布局的情况下完成配置。
   */
  const openCreateInterviewModal = () => {
    setShowCreateInterviewPanel(true)
  }

  /**
   * 用于在弹层打开时锁定页面滚动，并支持按下 Esc 关闭弹层。
   */
  useEffect(() => {
    if (!showCreateInterviewPanel) return

    const originalOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setShowCreateInterviewPanel(false)
      }
    }

    window.addEventListener('keydown', handleKeyDown)

    return () => {
      document.body.style.overflow = originalOverflow
      window.removeEventListener('keydown', handleKeyDown)
    }
  }, [showCreateInterviewPanel])

  if (!mounted || isLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#ffffff' }}>
        <div
          className="w-12 h-12 rounded-full border-2 border-transparent animate-spin"
          style={{ borderTopColor: '#0052ff', borderRightColor: '#0052ff' }}
        />
      </div>
    )
  }

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#ffffff' }}>
      <MainNavigation />

      <div className="py-10 px-6" style={{ borderBottom: '1px solid rgba(91,97,110,0.12)' }}>
        <div className="max-w-5xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="flex flex-col gap-5 md:flex-row md:items-end md:justify-between"
          >
            <div>
              <h1 className="text-5xl font-semibold" style={{ lineHeight: '1.00', color: '#0a0b0d' }}>
                面试中心
              </h1>
            </div>
            <button
              type="button"
              onClick={openCreateInterviewModal}
              className="btn-primary btn-sm"
            >
              创建面试
            </button>
          </motion.div>
        </div>
      </div>

      <main className="max-w-5xl mx-auto px-6 py-10 space-y-8">
        {showCreateInterviewPanel && (
          <div
            className="fixed inset-0 z-40 flex items-center justify-center p-4 md:p-6"
            style={{ backgroundColor: 'rgba(10,11,13,0.48)' }}
            onClick={() => setShowCreateInterviewPanel(false)}
          >
            <motion.section
              initial={{ opacity: 0, y: 16, scale: 0.98 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.22 }}
              role="dialog"
              aria-modal="true"
              aria-label="创建面试"
              className="w-full max-w-4xl"
              style={{
                border: '1px solid rgba(91,97,110,0.2)',
                borderRadius: '40px',
                backgroundColor: '#ffffff',
                boxShadow: '0 32px 96px rgba(10,11,13,0.24)',
              }}
              onClick={(event) => event.stopPropagation()}
            >
              <div className="border-b px-7 py-7 md:px-9 md:py-8" style={{ borderColor: 'rgba(91,97,110,0.12)' }}>
                <div className="flex flex-col gap-4 md:flex-row md:items-start md:justify-between">
                  <div className="max-w-2xl">
                  <p className="text-sm font-semibold tracking-[0.16em] lowercase" style={{ color: '#0052ff' }}>
                    start interview
                  </p>
                  <h2 className="mt-3 text-5xl font-semibold" style={{ color: '#0a0b0d', lineHeight: '1.00' }}>
                    新建模拟面试
                  </h2>
                </div>
                  <div className="flex items-center gap-3">
                    {selectedResumeLoading && (
                      <span
                        className="inline-flex items-center px-3 py-1 text-xs font-semibold"
                        style={{ borderRadius: '100000px', backgroundColor: '#eef0f3', color: '#0052ff' }}
                      >
                        正在读取简历中的岗位信息...
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => setShowCreateInterviewPanel(false)}
                      className="btn-secondary btn-sm h-11 w-11 p-0"
                      aria-label="关闭创建面试弹层"
                    >
                      <XMarkIcon className="w-5 h-5" />
                    </button>
                  </div>
                </div>
              </div>

              <div className="px-7 py-7 md:px-9 md:py-8">
                {pageError && (
                  <div
                    className="mb-6 rounded-[24px] px-5 py-4 text-sm"
                    style={{ backgroundColor: '#fef2f2', color: '#dc2626', border: '1px solid rgba(220,38,38,0.12)' }}
                  >
                    {pageError}
                  </div>
                )}

                {resumes.length === 0 && !loading ? (
                  <div
                    className="rounded-[32px] px-6 py-12 text-center"
                    style={{ backgroundColor: '#ffffff', border: '1px solid rgba(91,97,110,0.2)' }}
                  >
                    <div
                      className="mx-auto mb-5 flex h-16 w-16 items-center justify-center"
                      style={{ borderRadius: '24px', backgroundColor: '#eef0f3' }}
                    >
                      <MicrophoneIcon className="h-8 w-8" style={{ color: '#0052ff' }} />
                    </div>
                    <h3 className="text-[32px] font-semibold" style={{ color: '#0a0b0d', lineHeight: '1.13' }}>
                      还没有可用于面试的简历
                    </h3>
                    <p className="mt-3 text-base" style={{ color: '#5b616e', lineHeight: '1.5' }}>
                      先去简历中心上传或整理一份简历，再回来开始模拟面试。
                    </p>
                    <Link href="/resumes" className="btn-primary btn-lg mt-7 inline-flex items-center gap-2">
                      前往简历中心
                    </Link>
                  </div>
                ) : (
                  <div className="grid gap-7">
                    <div>
                      <label className="label">面试模式</label>
                      <div className="grid gap-4 md:grid-cols-2">
                        {INTERVIEW_MODE_OPTIONS.map((option) => {
                          const isSelected = interviewMode === option.value
                          return (
                            <button
                              key={option.value}
                              type="button"
                              onClick={() => setInterviewMode(option.value)}
                              className="text-left transition-colors"
                              style={{
                                borderRadius: '32px',
                                border: isSelected ? '1px solid #0052ff' : '1px solid rgba(91,97,110,0.2)',
                                backgroundColor: isSelected ? '#eef0f3' : '#ffffff',
                                boxShadow: isSelected ? '0 0 0 2px rgba(0,82,255,0.08)' : 'none',
                                padding: '24px',
                              }}
                            >
                              <div className="flex items-start justify-between gap-3">
                                <div>
                                  <p className="text-[18px] font-semibold" style={{ color: '#0a0b0d', lineHeight: '1.33' }}>
                                    {option.label}
                                  </p>
                                  <p className="mt-2 text-sm" style={{ color: '#5b616e', lineHeight: '1.5' }}>
                                    {option.description}
                                  </p>
                                </div>
                              </div>
                            </button>
                          )
                        })}
                      </div>
                    </div>

                    <div className="grid gap-5 md:grid-cols-3">
                      <div>
                        <label className="label">选择简历</label>
                        <select
                          value={selectedResumeId}
                          onChange={(event) => setSelectedResumeId(event.target.value)}
                          className="input"
                        >
                          <option value="">请选择一份简历</option>
                          {resumes.map((resume) => (
                            <option key={resume.id} value={resume.id}>
                              {resume.title}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="label">目标公司</label>
                        <input
                          type="text"
                          value={targetCompany}
                          onChange={(event) => setTargetCompany(event.target.value)}
                          placeholder="例如：腾讯 / 字节跳动"
                          className="input"
                        />
                      </div>

                      <div>
                        <label className="label">目标岗位</label>
                        <input
                          type="text"
                          value={targetTitle}
                          onChange={(event) => setTargetTitle(event.target.value)}
                          placeholder="例如：前端工程师 / 产品经理"
                          className="input"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="label">职位描述（JD）</label>
                      <textarea
                        value={jdText}
                        onChange={(event) => setJdText(event.target.value)}
                        placeholder="粘贴职位描述，或先在简历编辑页保存 JD 后再自动带入"
                        rows={11}
                        className="input resize-none px-5 py-4"
                        style={{ borderRadius: '24px' }}
                      />
                    </div>

                    {formError && (
                      <div
                        className="rounded-[24px] px-5 py-4 text-sm"
                        style={{ backgroundColor: '#fef2f2', color: '#dc2626', border: '1px solid rgba(220,38,38,0.12)' }}
                      >
                        {formError}
                      </div>
                    )}

                    <div className="flex justify-end">
                      <button
                        type="button"
                        onClick={handleCreateInterview}
                        disabled={!selectedResumeId || creatingSession}
                        className="btn-secondary btn-sm"
                      >
                        {creatingSession ? '正在创建面试...' : '开始面试'}
                      </button>
                    </div>
                  </div>
                )}
              </div>
            </motion.section>
          </div>
        )}

        <motion.section
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.05 }}
        >
          {loading ? (
            <div className="flex justify-center items-center py-16">
              <div
                className="w-8 h-8 rounded-full border-2 border-transparent animate-spin"
                style={{ borderTopColor: '#0052ff', borderRightColor: '#0052ff' }}
              />
              <span className="ml-3 text-base" style={{ color: '#5b616e' }}>加载中...</span>
            </div>
          ) : sessions.length === 0 ? (
            <div
              className="text-center py-16 px-6"
              style={{
                border: '1px dashed rgba(91,97,110,0.18)',
                borderRadius: '24px',
                backgroundColor: '#fcfcfd',
              }}
            >
              <div
                className="w-16 h-16 rounded-3xl flex items-center justify-center mx-auto mb-5"
                style={{ backgroundColor: '#eef0f3' }}
              >
                <MicrophoneIcon className="w-8 h-8" style={{ color: '#0052ff' }} />
              </div>
              <h3 className="text-xl font-semibold" style={{ color: '#0a0b0d' }}>
                还没有历史面试记录
              </h3>
              <p className="mt-2 text-sm" style={{ color: '#5b616e' }}>
                点击右上角的创建面试按钮，开始第一次模拟面试。
              </p>
            </div>
          ) : (
            <div className="space-y-5">
              {sessions.map((session, index) => {
                const { text, bg, color } = statusLabel(session.status)
                const started = session.started_at ? formatDate(session.started_at) : null
                return (
                  <motion.div
                    key={session.id}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4, delay: index * 0.05 }}
                    className="group relative flex items-center justify-between gap-5 p-6 transition-shadow"
                    style={{
                      border: '1px solid rgba(91,97,110,0.2)',
                      borderRadius: '32px',
                      backgroundColor: '#ffffff',
                    }}
                  >
                    <button
                      type="button"
                      onClick={() => handleDeleteInterview(session.id)}
                      disabled={deletingSessionId === session.id}
                      className={`absolute right-2.5 top-2.5 flex h-8 w-8 items-center justify-center rounded-full bg-white transition-opacity ${
                        deletingSessionId === session.id ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'
                      }`}
                      style={{
                        boxShadow: '0 1px 6px rgba(0,0,0,0.12)',
                        color: deletingSessionId === session.id ? '#dc2626' : '#9ca3af',
                      }}
                      title={deletingSessionId === session.id ? '正在删除...' : '删除面试记录'}
                      aria-label={`删除面试记录 ${session.target_title || session.id}`}
                      onMouseEnter={(event) => {
                        event.currentTarget.style.color = '#dc2626'
                      }}
                      onMouseLeave={(event) => {
                        if (deletingSessionId === session.id) return
                        event.currentTarget.style.color = '#9ca3af'
                      }}
                    >
                      <TrashIcon
                        className={`h-4 w-4 ${deletingSessionId === session.id ? 'animate-pulse' : ''}`}
                      />
                    </button>
                    <div className="flex items-center gap-4 min-w-0">
                      <div
                        className="w-14 h-14 flex items-center justify-center flex-shrink-0"
                        style={{ borderRadius: '24px', backgroundColor: '#eef0f3' }}
                      >
                        <PlayCircleIcon className="w-7 h-7" style={{ color: '#0052ff' }} />
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2.5 mb-1 flex-wrap">
                          <span className="truncate text-[18px] font-semibold" style={{ color: '#0a0b0d', lineHeight: '1.33' }}>
                            {session.target_title || '未设置岗位'}
                          </span>
                          {session.target_company && (
                            <span className="text-base truncate" style={{ color: '#5b616e' }}>
                              @ {session.target_company}
                            </span>
                          )}
                          <span
                            className="px-3 py-1 text-xs font-semibold"
                            style={{ borderRadius: '100000px', backgroundColor: '#eef0f3', color: '#0052ff' }}
                          >
                            {session.mode === 'simulation' ? '拟真模式' : '练习模式'}
                          </span>
                          <span
                            className="px-3 py-1 text-xs font-semibold"
                            style={{ borderRadius: '100000px', backgroundColor: bg, color }}
                          >
                            {text}
                          </span>
                        </div>
                        <div className="flex items-center gap-4 text-sm flex-wrap" style={{ color: '#5b616e' }}>
                          {started && (
                            <span className="flex items-center gap-1">
                              <ClockIcon className="w-3.5 h-3.5" />{started}
                            </span>
                          )}
                          <span>{session.answered_turn_count} 题已回答</span>
                        </div>
                      </div>
                    </div>
                    <div className="flex flex-shrink-0 items-center gap-3">
                      <Link
                        href={`/resume/${session.resume_id}/interview?session=${session.id}`}
                        className="btn-primary btn-sm"
                        onMouseEnter={(event) => {
                          event.currentTarget.style.backgroundColor = '#578bfa'
                          event.currentTarget.style.borderColor = '#578bfa'
                        }}
                        onMouseLeave={(event) => {
                          event.currentTarget.style.backgroundColor = '#0052ff'
                          event.currentTarget.style.borderColor = '#0052ff'
                        }}
                      >
                        {session.status === 'completed' ? '查看报告' : '继续面试'}
                      </Link>
                    </div>
                  </motion.div>
                )
              })}
            </div>
          )}
        </motion.section>
      </main>
    </div>
  )
}
