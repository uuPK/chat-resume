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
  CheckCircleIcon,
  ClockIcon,
  MicrophoneIcon,
  PlayCircleIcon,
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
  if (status === 'completed') return { text: '已完成', bg: '#ecfdf5', color: '#059669' }
  if (status === 'waiting_user_answer') return { text: '进行中', bg: '#eef0ff', color: '#0052ff' }
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
              <p className="mt-3 text-lg" style={{ color: '#5b616e' }}>
                先选择一份简历，再补充岗位和 JD，上下文准备好后再进入统一面试流程。
              </p>
            </div>
            <button
              type="button"
              onClick={openCreateInterviewModal}
              className="inline-flex items-center justify-center px-6 py-3 text-sm font-semibold text-white transition-colors"
              style={{ borderRadius: '999px', backgroundColor: '#0052ff', border: '1px solid #0052ff' }}
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
              className="w-full max-w-3xl max-h-[calc(100vh-2rem)] overflow-y-auto p-6 md:p-8"
              style={{
                border: '1px solid rgba(91,97,110,0.16)',
                borderRadius: '24px',
                background: 'linear-gradient(180deg, rgba(238,240,255,0.96) 0%, rgba(255,255,255,1) 100%)',
                boxShadow: '0 24px 80px rgba(10,11,13,0.22)',
              }}
              onClick={(event) => event.stopPropagation()}
            >
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div>
                  <p className="text-sm font-semibold tracking-[0.16em] uppercase" style={{ color: '#0052ff' }}>
                    Start Interview
                  </p>
                  <h2 className="mt-2 text-3xl font-semibold" style={{ color: '#0a0b0d' }}>
                    新建模拟面试
                  </h2>
                  <p className="mt-2 text-sm" style={{ color: '#5b616e' }}>
                    先选模式，再选择简历和岗位上下文。练习模式会提供提示和题后反馈，拟真模式不会。
                  </p>
                </div>
                <div className="flex items-center gap-3">
                  {selectedResumeLoading && (
                    <span className="text-sm font-medium" style={{ color: '#0052ff' }}>
                      正在读取简历中的岗位信息...
                    </span>
                  )}
                  <button
                    type="button"
                    onClick={() => setShowCreateInterviewPanel(false)}
                    className="inline-flex h-10 w-10 items-center justify-center rounded-full transition-colors"
                    style={{ backgroundColor: '#ffffff', color: '#5b616e', border: '1px solid rgba(91,97,110,0.12)' }}
                    aria-label="关闭创建面试弹层"
                  >
                    <XMarkIcon className="w-5 h-5" />
                  </button>
                </div>
              </div>

              {pageError && (
                <div
                  className="mt-6 rounded-2xl px-4 py-3 text-sm"
                  style={{ backgroundColor: '#fef2f2', color: '#dc2626', border: '1px solid rgba(220,38,38,0.12)' }}
                >
                  {pageError}
                </div>
              )}

              {resumes.length === 0 && !loading ? (
                <div
                  className="mt-6 rounded-3xl px-6 py-10 text-center"
                  style={{ backgroundColor: '#ffffff', border: '1px solid rgba(91,97,110,0.12)' }}
                >
                  <div
                    className="w-16 h-16 rounded-3xl flex items-center justify-center mx-auto mb-5"
                    style={{ backgroundColor: '#eef0f3' }}
                  >
                    <MicrophoneIcon className="w-8 h-8" style={{ color: '#0052ff' }} />
                  </div>
                  <h3 className="text-xl font-semibold" style={{ color: '#0a0b0d' }}>
                    还没有可用于面试的简历
                  </h3>
                  <p className="mt-2 text-sm" style={{ color: '#5b616e' }}>
                    先去简历中心上传或整理一份简历，再回来开始模拟面试。
                  </p>
                  <Link href="/resumes" className="btn-primary btn-lg inline-flex items-center gap-2 mt-6">
                    前往简历中心
                  </Link>
                </div>
              ) : (
                <div className="mt-6 grid gap-5">
                  <div>
                    <label className="block text-sm font-medium mb-2" style={{ color: '#0a0b0d' }}>
                      面试模式
                    </label>
                    <div className="grid gap-3 md:grid-cols-2">
                      {INTERVIEW_MODE_OPTIONS.map((option) => {
                        const isSelected = interviewMode === option.value
                        return (
                          <button
                            key={option.value}
                            type="button"
                            onClick={() => setInterviewMode(option.value)}
                            className="rounded-3xl px-4 py-4 text-left transition-colors"
                            style={{
                              border: isSelected ? '1px solid #0052ff' : '1px solid rgba(91,97,110,0.16)',
                              backgroundColor: isSelected ? '#eef0ff' : '#ffffff',
                              boxShadow: isSelected ? '0 0 0 3px rgba(0,82,255,0.08)' : 'none',
                            }}
                          >
                            <p className="text-sm font-semibold" style={{ color: '#0a0b0d' }}>
                              {option.label}
                            </p>
                            <p className="mt-1 text-xs leading-5" style={{ color: '#5b616e' }}>
                              {option.description}
                            </p>
                          </button>
                        )
                      })}
                    </div>
                  </div>

                  <div className="grid gap-5 md:grid-cols-[1.2fr,0.8fr]">
                    <div>
                      <label className="block text-sm font-medium mb-2" style={{ color: '#0a0b0d' }}>
                        选择简历
                      </label>
                      <select
                        value={selectedResumeId}
                        onChange={(event) => setSelectedResumeId(event.target.value)}
                        className="w-full rounded-2xl px-4 py-3 text-sm outline-none transition-shadow"
                        style={{
                          border: '1px solid rgba(91,97,110,0.2)',
                          backgroundColor: '#ffffff',
                          color: '#0a0b0d',
                          boxShadow: selectedResumeId ? '0 0 0 4px rgba(0,82,255,0.04)' : 'none',
                        }}
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
                      <label className="block text-sm font-medium mb-2" style={{ color: '#0a0b0d' }}>
                        目标岗位
                      </label>
                      <input
                        type="text"
                        value={targetTitle}
                        onChange={(event) => setTargetTitle(event.target.value)}
                        placeholder="例如：前端工程师 / 产品经理"
                        className="w-full rounded-2xl px-4 py-3 text-sm outline-none"
                        style={{
                          border: '1px solid rgba(91,97,110,0.2)',
                          backgroundColor: '#ffffff',
                          color: '#0a0b0d',
                        }}
                      />
                    </div>
                  </div>

                  <div>
                    <div className="flex items-center justify-between gap-3 mb-2">
                      <label className="block text-sm font-medium" style={{ color: '#0a0b0d' }}>
                        职位描述（JD）
                      </label>
                      {selectedResumeId && (
                        <span className="text-xs" style={{ color: '#9ca3af' }}>
                          选择简历后会自动回填该简历已保存的 JD
                        </span>
                      )}
                    </div>
                    <textarea
                      value={jdText}
                      onChange={(event) => setJdText(event.target.value)}
                      placeholder="粘贴职位描述，或先在简历编辑页保存 JD 后再自动带入"
                      rows={12}
                      className="w-full rounded-3xl px-4 py-4 text-sm resize-none outline-none"
                      style={{
                        border: '1px solid rgba(91,97,110,0.2)',
                        backgroundColor: '#ffffff',
                        color: '#0a0b0d',
                      }}
                    />
                  </div>

                  {selectedResumeId && (
                    <div
                      className="rounded-2xl px-4 py-3 text-sm"
                      style={{ backgroundColor: '#ffffff', border: '1px solid rgba(91,97,110,0.12)', color: '#5b616e' }}
                    >
                      当前简历关联信息：{targetCompany || '未设置目标公司'} · {targetTitle || '未设置目标岗位'}
                    </div>
                  )}

                  {formError && (
                    <div
                      className="rounded-2xl px-4 py-3 text-sm"
                      style={{ backgroundColor: '#fef2f2', color: '#dc2626', border: '1px solid rgba(220,38,38,0.12)' }}
                    >
                      {formError}
                    </div>
                  )}

                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <p className="text-sm" style={{ color: '#5b616e' }}>
                      创建后会直接进入统一的结构化面试流程，并从第 1 题开始。
                    </p>
                    <button
                      type="button"
                      onClick={handleCreateInterview}
                      disabled={!selectedResumeId || creatingSession}
                      className="inline-flex items-center justify-center px-6 py-3 text-sm font-semibold text-white transition-colors disabled:cursor-not-allowed disabled:opacity-60"
                      style={{ borderRadius: '999px', backgroundColor: '#0052ff', border: '1px solid #0052ff' }}
                    >
                      {creatingSession ? '正在创建面试...' : '开始面试'}
                    </button>
                  </div>
                </div>
              )}
            </motion.section>
          </div>
        )}

        <motion.section
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, delay: 0.05 }}
        >
          <div className="flex items-center justify-between gap-3 mb-4">
            <div>
              <h2 className="text-2xl font-semibold" style={{ color: '#0a0b0d' }}>
                历史记录
              </h2>
              <p className="mt-1 text-sm" style={{ color: '#5b616e' }}>
                查看未完成的面试，或回看已生成的报告。
              </p>
            </div>
          </div>

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
            <div className="space-y-4">
              {sessions.map((session, index) => {
                const { text, bg, color } = statusLabel(session.status)
                const started = session.started_at ? formatDate(session.started_at) : null
                return (
                  <motion.div
                    key={session.id}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4, delay: index * 0.05 }}
                    className="flex items-center justify-between gap-4 p-5 transition-shadow"
                    style={{
                      border: '1px solid rgba(91,97,110,0.2)',
                      borderRadius: '16px',
                      backgroundColor: '#ffffff',
                    }}
                  >
                    <div className="flex items-center gap-4 min-w-0">
                      <div
                        className="w-10 h-10 rounded-2xl flex items-center justify-center flex-shrink-0"
                        style={{ backgroundColor: session.status === 'completed' ? '#ecfdf5' : '#eef0f3' }}
                      >
                        {session.status === 'completed'
                          ? <CheckCircleIcon className="w-5 h-5" style={{ color: '#059669' }} />
                          : <PlayCircleIcon className="w-5 h-5" style={{ color: '#0052ff' }} />
                        }
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                          <span className="font-semibold truncate" style={{ color: '#0a0b0d' }}>
                            {session.target_title || '未设置岗位'}
                          </span>
                          {session.target_company && (
                            <span className="text-sm truncate" style={{ color: '#5b616e' }}>
                              @ {session.target_company}
                            </span>
                          )}
                          <span
                            className="text-xs font-semibold px-2.5 py-0.5"
                            style={{ borderRadius: '100000px', backgroundColor: '#eef0ff', color: '#0052ff' }}
                          >
                            {session.mode === 'simulation' ? '拟真模式' : '练习模式'}
                          </span>
                          <span
                            className="text-xs font-semibold px-2.5 py-0.5"
                            style={{ borderRadius: '100000px', backgroundColor: bg, color }}
                          >
                            {text}
                          </span>
                        </div>
                        <div className="flex items-center gap-3 text-xs flex-wrap" style={{ color: '#9ca3af' }}>
                          {started && (
                            <span className="flex items-center gap-1">
                              <ClockIcon className="w-3.5 h-3.5" />{started}
                            </span>
                          )}
                          <span>{session.answered_turn_count} 题已回答</span>
                        </div>
                      </div>
                    </div>
                    <Link
                      href={`/resume/${session.resume_id}/interview?session=${session.id}`}
                      className="flex-shrink-0 inline-flex items-center px-4 py-2 text-sm font-semibold text-white transition-colors"
                      style={{ borderRadius: '56px', backgroundColor: '#0052ff', border: '1px solid #0052ff' }}
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
