'use client'

/**
 * 面试中心页模块
 *
 * 用于让用户在进入面试前选择简历、补充岗位上下文，并查看历史面试记录。
 */

import { useEffect, useRef, useState } from 'react'
import { useAuth } from '@/lib/auth'
import { useRouter } from '@/i18n/navigation'
import { motion } from 'framer-motion'
import { Link } from '@/i18n/navigation'
import MainNavigation from '@/components/layout/MainNavigation'
import { resumeApi, type InterviewSessionSummary, type Resume, type ResumeListItem } from '@/lib/api'
import { useLocale, useTranslations } from 'next-intl'
import { toInterviewLanguage, type AppLocale } from '@/i18n/routing'
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
function formatDate(dateString: string, locale: string) {
  const d = new Date(dateString.includes('Z') || dateString.includes('+') ? dateString : `${dateString}Z`)
  return new Intl.DateTimeFormat(locale === 'zh' ? 'zh-CN' : 'en-US', {
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
function statusLabel(status: string, t: ReturnType<typeof useTranslations>) {
  if (status === 'completed') return { text: t('status.completed'), bg: '#eef0f3', color: '#0a0b0d' }
  if (status === 'waiting_user_answer') return { text: t('status.active'), bg: '#eef0f3', color: '#0052ff' }
  return { text: t('status.notStarted'), bg: '#eef0f3', color: '#5b616e' }
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

/**
 * 面试中心页组件
 *
 * 用于承接新建面试和查看历史面试这两个核心入口。
 */
export default function InterviewsPage() {
  const { isAuthenticated, isLoading } = useAuth()
  const router = useRouter()
  const locale = useLocale() as AppLocale
  const t = useTranslations('interview')
  const resumeCacheRef = useRef<Record<number, Resume>>({})

  const [mounted, setMounted] = useState(false)
  const [loading, setLoading] = useState(true)
  const [pageError, setPageError] = useState<string | null>(null)
  const [sessions, setSessions] = useState<InterviewSessionSummary[]>([])
  const [resumes, setResumes] = useState<ResumeListItem[]>([])
  const [showCreateInterviewPanel, setShowCreateInterviewPanel] = useState(false)
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
        setPageError(error instanceof Error ? error.message : t('center.loadError'))
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
        setFormError(error instanceof Error ? error.message : t('center.readResumeError'))
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
      setFormError(t('center.selectResumeFirst'))
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
        language: toInterviewLanguage(locale),
        mode: 'practice',
      })
      router.push(`/resume/${resumeId}/interview?session=${result.session.id}`)
    } catch (error) {
      setFormError(error instanceof Error ? error.message : t('center.createError'))
    } finally {
      setCreatingSession(false)
    }
  }

  /**
   * 用于删除一条历史面试记录，并在成功后同步更新列表状态。
   */
  const handleDeleteInterview = async (sessionId: number) => {
    const confirmed = window.confirm(t('center.deleteConfirm'))
    if (!confirmed) return

    setDeletingSessionId(sessionId)
    setPageError(null)
    try {
      await resumeApi.deleteInterviewSession(sessionId)
      setSessions((currentSessions) => currentSessions.filter((session) => session.id !== sessionId))
    } catch (error) {
      setPageError(error instanceof Error ? error.message : t('center.deleteError'))
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
                {t('center.title')}
              </h1>
            </div>
            <button
              type="button"
              onClick={openCreateInterviewModal}
              className="btn-primary btn-sm"
            >
              {t('center.create')}
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
              aria-label={t('center.create')}
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
                    {t('center.create')}
                  </h2>
                </div>
                  <div className="flex items-center gap-3">
                    {selectedResumeLoading && (
                      <span
                        className="inline-flex items-center px-3 py-1 text-xs font-semibold"
                        style={{ borderRadius: '100000px', backgroundColor: '#eef0f3', color: '#0052ff' }}
                      >
                        {t('center.readingResume')}
                      </span>
                    )}
                    <button
                      type="button"
                      onClick={() => setShowCreateInterviewPanel(false)}
                      className="btn-secondary btn-sm h-11 w-11 p-0"
                      aria-label={t('form.close')}
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
                      {t('center.emptyTitle')}
                    </h3>
                    <p className="mt-3 text-base" style={{ color: '#5b616e', lineHeight: '1.5' }}>
                      {t('center.emptyDescription')}
                    </p>
                    <Link href="/resumes" className="btn-primary btn-lg mt-7 inline-flex items-center gap-2">
                      {t('center.title')}
                    </Link>
                  </div>
                ) : (
                  <div className="grid gap-7">
                    <div className="grid gap-5 md:grid-cols-3">
                      <div>
                        <label className="label">{t('form.selectResume')}</label>
                        <select
                          value={selectedResumeId}
                          onChange={(event) => setSelectedResumeId(event.target.value)}
                          className="input"
                        >
                          <option value="">{t('form.selectResumePlaceholder')}</option>
                          {resumes.map((resume) => (
                            <option key={resume.id} value={resume.id}>
                              {resume.title}
                            </option>
                          ))}
                        </select>
                      </div>

                      <div>
                        <label className="label">{t('form.targetCompany')}</label>
                        <input
                          type="text"
                          value={targetCompany}
                          onChange={(event) => setTargetCompany(event.target.value)}
                          placeholder={t('form.targetCompanyPlaceholder')}
                          className="input"
                        />
                      </div>

                      <div>
                        <label className="label">{t('form.targetTitle')}</label>
                        <input
                          type="text"
                          value={targetTitle}
                          onChange={(event) => setTargetTitle(event.target.value)}
                          placeholder={t('form.targetTitlePlaceholder')}
                          className="input"
                        />
                      </div>
                    </div>

                    <div>
                      <label className="label">{t('form.jd')}</label>
                      <textarea
                        value={jdText}
                        onChange={(event) => setJdText(event.target.value)}
                        placeholder={t('form.jdPlaceholder')}
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
                        {creatingSession ? t('form.creating') : t('form.start')}
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
              <span className="ml-3 text-base" style={{ color: '#5b616e' }}>{t('center.loading')}</span>
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
                {t('center.emptyTitle')}
              </h3>
              <p className="mt-2 text-sm" style={{ color: '#5b616e' }}>
                {t('center.emptyDescription')}
              </p>
            </div>
          ) : (
            <div className="space-y-5">
              {sessions.map((session, index) => {
                const { text, bg, color } = statusLabel(session.status, t)
                const started = session.started_at ? formatDate(session.started_at, locale) : null
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
                      title={deletingSessionId === session.id ? t('session.deletingTitle') : t('session.deleteTitle')}
                      aria-label={t('session.deleteTitle')}
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
                            {session.target_title || t('session.untitledRole')}
                          </span>
                          {session.target_company && (
                            <span className="text-base truncate" style={{ color: '#5b616e' }}>
                              @ {session.target_company}
                            </span>
                          )}
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
                          <span>{session.answered_turn_count}</span>
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
                        {session.status === 'completed' ? t('session.viewReport') : t('session.continue')}
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
