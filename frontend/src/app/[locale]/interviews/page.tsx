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
import CandidateSidebar from '@/components/layout/CandidateSidebar'
import toast from 'react-hot-toast'
import { resumeApi, type InterviewSessionSummary, type Resume, type ResumeListItem } from '@/lib/api'
import { formatApiErrorMessage } from '@/lib/apiErrors'
import { useLocale, useTranslations } from 'next-intl'
import { toInterviewLanguage, type AppLocale } from '@/i18n/routing'
import {
  ArrowPathIcon,
  ArrowRightIcon,
  ChevronDownIcon,
  ChatBubbleLeftRightIcon,
  DocumentCheckIcon,
  DocumentTextIcon,
  ExclamationCircleIcon,
  MagnifyingGlassIcon,
  MicrophoneIcon,
  TrashIcon,
  XMarkIcon,
  SparklesIcon,
  BriefcaseIcon,
  AcademicCapIcon,
} from '@heroicons/react/24/outline'

/**
 * 用于从简历列表和详情中提取岗位与 JD 的默认值。
 */
// 用于读取面试默认值。
function readInterviewDefaults(resumeItem?: ResumeListItem, resumeDetail?: Resume | null) {
  const jobApplication = resumeDetail?.content?.job_application || {}
  return {
    targetCompany: jobApplication.target_company || resumeItem?.target_company || '',
    targetTitle: jobApplication.target_title || resumeItem?.target_title || '',
    jdText: jobApplication.jd_text || '',
  }
}

const LIST_BLUE = '#2563eb'
const LIST_BLUE_HOVER = '#1d4ed8'
const LIST_BLUE_BG = '#eff6ff'
const LIST_TEXT = '#111827'
const LIST_MUTED = '#6b7280'
const LIST_FAINT = '#9ca3af'
const LIST_BORDER = 'rgba(0,0,0,0.14)'
const LIST_SOFT_BORDER = 'rgba(0,0,0,0.08)'

type SessionStatusFilter = 'all' | 'completed' | 'active' | 'not_started'
type SessionSortOrder = 'recent' | 'oldest'

// 用于生成面试记录卡片的完整开始时间。
function formatInterviewStartTime(dateString: string | undefined, locale: string) {
  if (!dateString) return '--'
  const timestamp = new Date(dateString.includes('Z') || dateString.includes('+') ? dateString : `${dateString}Z`).getTime()
  if (Number.isNaN(timestamp)) return '--'

  return new Intl.DateTimeFormat(locale === 'zh' ? 'zh-CN' : 'en-US', {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
    timeZone: 'Asia/Shanghai',
  }).format(new Date(timestamp)).replace(/\//g, '-')
}

// 用于生成面试记录卡片的面试时长。
function formatInterviewDuration(
  startedAt: string | undefined,
  endedAt: string | undefined,
  locale: string,
) {
  if (!startedAt) return '--'
  const started = new Date(startedAt.includes('Z') || startedAt.includes('+') ? startedAt : `${startedAt}Z`).getTime()
  const ended = endedAt
    ? new Date(endedAt.includes('Z') || endedAt.includes('+') ? endedAt : `${endedAt}Z`).getTime()
    : Date.now()
  if (Number.isNaN(started) || Number.isNaN(ended)) return '--'

  const totalMinutes = Math.max(1, Math.round((ended - started) / 60000))
  const hours = Math.floor(totalMinutes / 60)
  const minutes = totalMinutes % 60
  if (locale === 'zh') {
    if (hours > 0 && minutes > 0) return `${hours}小时${minutes}分钟`
    if (hours > 0) return `${hours}小时`
    return `${minutes}分钟`
  }
  if (hours > 0 && minutes > 0) return `${hours}h ${minutes}m`
  if (hours > 0) return `${hours}h`
  return `${minutes}m`
}

// 用于把面试难度枚举转换成记录卡片展示文案。
function formatInterviewDifficulty(difficulty: string, t: ReturnType<typeof useTranslations>) {
  if (difficulty === 'easy' || difficulty === 'beginner') return t('center.difficultyEasy')
  if (difficulty === 'hard' || difficulty === 'advanced' || difficulty === 'senior') return t('center.difficultyHard')
  return t('center.difficultyMedium')
}

// 用于渲染面试记录卡片信息行。
function InterviewInfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="grid grid-cols-[72px_minmax(0,1fr)] items-center gap-3 text-[13px] leading-5">
      <span className="font-medium" style={{ color: LIST_FAINT }}>{label}</span>
      <span className="min-w-0 truncate font-semibold" style={{ color: LIST_TEXT }}>{value}</span>
    </div>
  )
}

// 无简历时的面试入口说明页。
function NoResumeInterviewState({
  hasResumes,
  onStart,
  t,
  pageError,
}: {
  hasResumes: boolean
  onStart: () => void
  t: ReturnType<typeof useTranslations>
  pageError: string | null
}) {
  const prereqCopy = t('center.needResumePrefix')

  return (
    <div className="mx-auto w-full max-w-[640px] py-6">
      <h1 className="text-[22px] font-medium leading-tight" style={{ color: LIST_TEXT }}>{t('center.practiceHeading')}</h1>
      <p className="mt-1.5 text-[13.5px] leading-6" style={{ color: LIST_MUTED }}>{t('center.practiceSubheading')}</p>

      {pageError && (
        <div className="mt-6 rounded-lg border px-4 py-3 text-sm" style={{ backgroundColor: '#fef2f2', borderColor: 'rgba(220,38,38,0.14)', color: '#dc2626' }}>
          {pageError}
        </div>
      )}

      {!hasResumes && (
        <div className="mt-8 flex items-start gap-2.5 rounded-xl border px-4 py-3.5" style={{ backgroundColor: '#fffbeb', borderColor: 'rgba(180,130,0,0.2)' }}>
          <ExclamationCircleIcon className="mt-0.5 h-4 w-4 shrink-0" style={{ color: '#d97706' }} />
          <p className="text-[13px] leading-6" style={{ color: '#92400e' }}>
            {prereqCopy}
            <Link href="/resumes" className="font-medium underline underline-offset-2" style={{ color: '#b45309' }}>{t('center.needResumeLink')}</Link>
            {t('center.needResumeSuffix')}
          </p>
        </div>
      )}

      <div className={`${hasResumes ? 'mt-8' : 'mt-7'} grid gap-3.5 md:grid-cols-2`}>
        <button type="button" onClick={onStart} className="flex min-h-[210px] flex-col rounded-2xl border bg-white p-6 text-left transition-all" style={{ borderColor: LIST_BORDER }}>
          <span className="mb-4 flex h-10 w-10 items-center justify-center rounded-lg" style={{ backgroundColor: '#f9fafb', color: LIST_BLUE }}>
            <DocumentCheckIcon className="h-5 w-5" />
          </span>
          <span className="text-[15px] font-medium" style={{ color: LIST_TEXT }}>{t('center.targetPracticeTitle')}</span>
          <span className="mt-1.5 flex-1 text-[13px] leading-6" style={{ color: LIST_MUTED }}>{t('center.targetPracticeDescription')}</span>
          <span className="mt-4 flex items-center justify-between">
            <span className="text-xs" style={{ color: LIST_FAINT }}>{t('center.generalPracticeEta')}</span>
            <span className="flex h-7 w-7 items-center justify-center rounded-full border" style={{ borderColor: LIST_BORDER, color: LIST_MUTED }}>
              <ArrowRightIcon className="h-3.5 w-3.5" />
            </span>
          </span>
        </button>
      </div>

      <div className="mt-8">
        <div className="mb-3 text-[11px] font-medium uppercase tracking-wider" style={{ color: LIST_FAINT }}>{t('center.practiceAboutTitle')}</div>
        <div className="grid gap-2.5">
          {[t('center.practiceTipFeedback'), t('center.practiceTipReview')].map((tip) => (
            <div key={tip} className="flex items-start gap-2.5 text-[13px] leading-6" style={{ color: LIST_MUTED }}>
              <span className="mt-[9px] h-1.5 w-1.5 shrink-0 rounded-full" style={{ backgroundColor: LIST_BORDER }} />
              <span>{tip}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

// 用于判断面试卡片视觉状态。
function getInterviewVisualState(status: string, t: ReturnType<typeof useTranslations>) {
  if (status === 'completed') {
    return { label: t('status.completed'), badgeBg: LIST_BLUE_BG, badgeColor: '#1e40af', kind: 'done' as const }
  }
  if (status === 'waiting_user_answer') {
    return { label: t('status.active'), badgeBg: '#ecfdf5', badgeColor: '#047857', kind: 'ongoing' as const }
  }
  return { label: t('status.notStarted'), badgeBg: '#f9fafb', badgeColor: LIST_FAINT, kind: 'draft' as const }
}

// 用于给列表摘要生成稳定得分。
function getInterviewScore(session: InterviewSessionSummary) {
  if (session.status !== 'completed') return null
  return Math.min(92, 58 + session.answered_turn_count * 3)
}

// 用于搜索过滤面试记录。
function sessionMatchesQuery(session: InterviewSessionSummary, query: string) {
  const normalizedQuery = query.trim().toLowerCase()
  if (!normalizedQuery) return true
  return [session.target_title, session.target_company]
    .some(value => value?.toLowerCase().includes(normalizedQuery))
}

// 用于判断面试记录是否符合状态筛选。
function sessionMatchesStatus(session: InterviewSessionSummary, filter: SessionStatusFilter) {
  if (filter === 'all') return true
  if (filter === 'completed') return session.status === 'completed'
  if (filter === 'active') return session.status === 'waiting_user_answer' || session.status === 'in_progress'
  return session.status !== 'completed' && session.status !== 'waiting_user_answer' && session.status !== 'in_progress'
}

// 用于给面试记录排序提供稳定时间戳。
function getSessionSortTimestamp(session: InterviewSessionSummary) {
  const dateString = session.started_at || session.ended_at
  if (!dateString) return session.id
  const normalizedDate = dateString.includes('Z') || dateString.includes('+') ? dateString : `${dateString}Z`
  const timestamp = new Date(normalizedDate).getTime()
  return Number.isNaN(timestamp) ? session.id : timestamp
}

// 用于组合搜索、状态筛选和时间排序。
function getVisibleInterviewSessions(
  sessions: InterviewSessionSummary[],
  query: string,
  statusFilter: SessionStatusFilter,
  sortOrder: SessionSortOrder,
) {
  return sessions
    .filter(session => sessionMatchesQuery(session, query))
    .filter(session => sessionMatchesStatus(session, statusFilter))
    .sort((left, right) => {
      const leftTime = getSessionSortTimestamp(left)
      const rightTime = getSessionSortTimestamp(right)
      return sortOrder === 'recent' ? rightTime - leftTime : leftTime - rightTime
    })
}

// 面试记录卡片。
function InterviewCard({
  session,
  locale,
  index,
  deletingSessionId,
  onDelete,
  onPracticeAgain,
  onGenerateReport,
  retryingSessionId,
  generatingReportSessionId,
  t,
}: {
  session: InterviewSessionSummary
  locale: string
  index: number
  deletingSessionId: number | null
  onDelete: (sessionId: number) => void
  onPracticeAgain: (sessionId: number) => void
  onGenerateReport: (sessionId: number) => void
  retryingSessionId: number | null
  generatingReportSessionId: number | null
  t: ReturnType<typeof useTranslations>
}) {
  const visual = getInterviewVisualState(session.status, t)
  const score = getInterviewScore(session)
  const isCompleted = session.status === 'completed'
  const scoreValue = `${score || 0}${t('center.scoreSuffix')}`
  const isGeneratingReport = generatingReportSessionId === session.id
  const isRetrying = retryingSessionId === session.id
  const hasReport = Boolean(session.has_report)

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.04 }}
      className="group flex min-h-[240px] cursor-pointer flex-col overflow-hidden rounded-2xl border bg-white transition-all"
      style={{ borderColor: LIST_BORDER }}
      onMouseEnter={event => {
        event.currentTarget.style.borderColor = LIST_BLUE
        event.currentTarget.style.boxShadow = '0 0 0 3px rgba(37,99,235,0.07)'
      }}
      onMouseLeave={event => {
        event.currentTarget.style.borderColor = LIST_BORDER
        event.currentTarget.style.boxShadow = 'none'
      }}
    >
      <div className="flex flex-1 flex-col gap-3 px-4 py-3.5">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <h2 className="truncate text-sm font-medium" style={{ color: LIST_TEXT }}>{session.target_company || t('center.noTargetCompany')}</h2>
            <p className="mt-0.5 truncate text-xs" style={{ color: LIST_MUTED }}>
              {session.target_title || t('session.untitledRole')}
            </p>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="shrink-0 rounded px-1.5 py-0.5 text-[10px] font-medium" style={{ backgroundColor: visual.badgeBg, color: visual.badgeColor, border: visual.kind === 'draft' ? `1px solid ${LIST_BORDER}` : 'none' }}>
              {visual.label}
            </span>
            <button
              type="button"
              onClick={() => onDelete(session.id)}
              disabled={deletingSessionId === session.id}
              className="flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-lg transition-colors"
              style={{ color: deletingSessionId === session.id ? '#dc2626' : LIST_FAINT }}
              title={t('session.deleteTitle')}
              aria-label={t('session.deleteTitle')}
            >
              <TrashIcon className={`h-3.5 w-3.5 ${deletingSessionId === session.id ? 'animate-pulse' : ''}`} />
            </button>
          </div>
        </div>

        <div className="grid gap-2 px-1 py-2">
          <InterviewInfoRow label={t('center.interviewScoreLabel')} value={scoreValue} />
          <InterviewInfoRow label={t('center.difficultyLabel')} value={formatInterviewDifficulty(session.difficulty, t)} />
          <InterviewInfoRow label={t('center.companyLabel')} value={session.target_company || '--'} />
          <InterviewInfoRow label={t('center.roleLabel')} value={session.target_title || '--'} />
          <InterviewInfoRow label={t('center.durationLabel')} value={formatInterviewDuration(session.started_at, session.ended_at, locale)} />
          <InterviewInfoRow label={t('center.startedAtLabel')} value={formatInterviewStartTime(session.started_at, locale)} />
        </div>

        <div className="mt-auto flex flex-wrap items-center gap-3.5 border-t pt-2.5" style={{ borderColor: LIST_SOFT_BORDER }}>
          <span className="flex items-center gap-1 text-xs" style={{ color: LIST_FAINT }}>
            <ChatBubbleLeftRightIcon className="h-3 w-3" />
            {isCompleted ? t('center.totalQuestions', { count: session.answered_turn_count }) : t('center.answeredQuestions', { count: session.answered_turn_count, total: 8 })}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-1.5 px-[18px] pb-4">
        {isCompleted ? (
          <>
            {hasReport ? (
              <Link href={`/resume/${session.resume_id}/interview?session=${session.id}`} aria-label={t('session.viewReport')} className="inline-flex h-[30px] items-center justify-center rounded-lg border text-xs transition-colors" style={{ borderColor: LIST_BORDER, color: LIST_MUTED }}>
                {t('center.reviewAction')}
              </Link>
            ) : (
              <button
                type="button"
                onClick={() => onGenerateReport(session.id)}
                disabled={isGeneratingReport}
                className="inline-flex h-[30px] items-center justify-center gap-1.5 rounded-lg border text-xs font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-70"
                style={{ borderColor: LIST_BORDER, color: LIST_BLUE }}
              >
                {isGeneratingReport && <ArrowPathIcon className="h-3 w-3 animate-spin" />}
                {isGeneratingReport ? t('session.generatingReport') : t('session.generateReport')}
              </button>
            )}
            <button
              type="button"
              onClick={() => onPracticeAgain(session.id)}
              disabled={isRetrying}
              className="inline-flex h-[30px] items-center justify-center gap-1.5 rounded-lg text-xs font-medium text-white disabled:cursor-not-allowed disabled:opacity-70"
              style={{ backgroundColor: LIST_BLUE }}
            >
              {isRetrying && <ArrowPathIcon className="h-3 w-3 animate-spin" />}
              {t('center.practiceAgain')}
            </button>
          </>
        ) : (
          <>
            <button type="button" onClick={() => onDelete(session.id)} className="inline-flex h-[30px] items-center justify-center rounded-lg border text-xs transition-colors" style={{ borderColor: LIST_BORDER, color: LIST_MUTED }}>
              {t('center.abandonAction')}
            </button>
            <Link href={`/resume/${session.resume_id}/interview?session=${session.id}`} className="inline-flex h-[30px] items-center justify-center rounded-lg text-xs font-medium text-white" style={{ backgroundColor: LIST_BLUE }}>
              {t('session.continue')}
            </Link>
          </>
        )}
      </div>
    </motion.div>
  )
}

/**
 * 面试中心页组件
 *
 * 用于承接新建面试和查看历史面试这两个核心入口。
 */
// 用于渲染 InterviewsPage 组件。
export default function InterviewsPage() {
  const { isAuthenticated, isLoading } = useAuth()
  const router = useRouter()
  const locale = useLocale() as AppLocale
  const t = useTranslations('interview')
  const common = useTranslations('common')
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
  const [generatingReportSessionId, setGeneratingReportSessionId] = useState<number | null>(null)
  const [retryingSessionId, setRetryingSessionId] = useState<number | null>(null)
  const [sessionSearchQuery, setSessionSearchQuery] = useState('')
  const [sessionStatusFilter, setSessionStatusFilter] = useState<SessionStatusFilter>('all')
  const [sessionSortOrder, setSessionSortOrder] = useState<SessionSortOrder>('recent')
  const [formError, setFormError] = useState<string | null>(null)
  const [targetCompany, setTargetCompany] = useState('')
  const [targetTitle, setTargetTitle] = useState('')
  const [jdText, setJdText] = useState('')
  const hasResumes = resumes.length > 0
  const filteredSessions = getVisibleInterviewSessions(sessions, sessionSearchQuery, sessionStatusFilter, sessionSortOrder)

  const getSidebarUrl = (type: 'edit' | 'jobs' | 'learning-path') => {
    if (resumes.length === 0) return '/resumes'
    return `/resume/${resumes[0].id}/${type}`
  }

  const handleSidebarClick = (e: React.MouseEvent, type: 'edit' | 'jobs' | 'learning-path') => {
    if (resumes.length === 0) {
      e.preventDefault()
      toast('请先新建或上传一份简历！', { icon: '📝' })
    }
  }

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

    // 用于应用简历默认值。
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
  // 用于处理create面试。
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
      setFormError(formatApiErrorMessage(
        error,
        { activeSubscriptionRequired: common('errors.activeSubscriptionRequired') },
        t('center.createError'),
      ))
    } finally {
      setCreatingSession(false)
    }
  }

  /**
   * 用于删除一条历史面试记录，并在成功后同步更新列表状态。
   */
  // 用于处理delete面试。
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
   * 用于在面试列表卡片上直接生成报告。
   */
  // 用于处理生成报告。
  const handleGenerateReport = async (sessionId: number) => {
    if (generatingReportSessionId) return

    setGeneratingReportSessionId(sessionId)
    setPageError(null)
    try {
      const result = await resumeApi.generateInterviewReportStream(sessionId, () => {})
      if (result.next_action === 'report_skipped') {
        setPageError(t('errors.reportSkipped'))
        return
      }
      setSessions((currentSessions) => currentSessions.map((session) => (
        session.id === sessionId ? { ...session, has_report: true } : session
      )))
    } catch (error) {
      setPageError(error instanceof Error ? error.message : t('errors.reportFailed'))
    } finally {
      setGeneratingReportSessionId(null)
    }
  }


  /**
   * 用于基于历史面试记录创建一场新的复练面试并进入房间。
   */
  // 用于处理历史面试复练。
  const handlePracticeAgain = async (sessionId: number) => {
    if (retryingSessionId) return

    setRetryingSessionId(sessionId)
    setPageError(null)
    try {
      const result = await resumeApi.retryInterviewSession(sessionId)
      router.push(`/resume/${result.session.resume_id}/interview?session=${result.session.id}`)
    } catch (error) {
      setPageError(formatApiErrorMessage(
        error,
        { activeSubscriptionRequired: common('errors.activeSubscriptionRequired') },
        t('center.createError'),
      ))
    } finally {
      setRetryingSessionId(null)
    }
  }


  /**
   * 用于打开创建面试弹层，让用户在不离开当前页面布局的情况下完成配置。
   */
  // 用于打开create面试modal。
  const openCreateInterviewModal = () => {
    setShowCreateInterviewPanel(true)
  }

  // 用于处理通用面试练习入口。
  const handlePracticeCardClick = () => {
    if (!hasResumes) {
      router.push('/resumes')
      return
    }
    openCreateInterviewModal()
  }

  /**
   * 用于在弹层打开时锁定页面滚动，并支持按下 Esc 关闭弹层。
   */
  useEffect(() => {
    if (!showCreateInterviewPanel) return

    const originalOverflow = document.body.style.overflow
    document.body.style.overflow = 'hidden'

    // 用于处理键down。
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
    <div className="min-h-screen" style={{ backgroundColor: '#f9fafb' }}>
      <MainNavigation />
      <div className="flex min-h-[calc(100vh-56px)]">
          <CandidateSidebar hasResumes={hasResumes} firstResumeId={resumes[0]?.id} />

      <main className="flex-1 overflow-y-auto px-8 py-7" style={{ backgroundColor: '#f9fafb' }}>
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
                        <div className="relative">
                          <select
                            value={selectedResumeId}
                            onChange={(event) => setSelectedResumeId(event.target.value)}
                            className="input h-[52px] appearance-none px-5 pr-12"
                            style={{ color: selectedResumeId ? '#0a0b0d' : '#9ca3af' }}
                          >
                            <option value="">{t('form.selectResumePlaceholder')}</option>
                            {resumes.map((resume) => (
                              <option key={resume.id} value={resume.id}>
                                {resume.title}
                              </option>
                            ))}
                          </select>
                          <ChevronDownIcon
                            aria-hidden="true"
                            className="pointer-events-none absolute right-5 top-1/2 h-5 w-5 -translate-y-1/2"
                            style={{ color: '#9ca3af' }}
                          />
                        </div>
                      </div>

                      <div>
                        <label className="label">{t('form.targetCompany')}</label>
                        <input
                          type="text"
                          value={targetCompany}
                          onChange={(event) => setTargetCompany(event.target.value)}
                          placeholder={t('form.targetCompanyPlaceholder')}
                          className="input h-[52px] px-5"
                        />
                      </div>

                      <div>
                        <label className="label">{t('form.targetTitle')}</label>
                        <input
                          type="text"
                          value={targetTitle}
                          onChange={(event) => setTargetTitle(event.target.value)}
                          placeholder={t('form.targetTitlePlaceholder')}
                          className="input h-[52px] px-5"
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
                        className="btn-primary btn-sm"
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
                style={{ borderTopColor: LIST_BLUE, borderRightColor: LIST_BLUE }}
              />
              <span className="ml-3 text-base" style={{ color: LIST_MUTED }}>{t('center.loading')}</span>
            </div>
          ) : !hasResumes || sessions.length === 0 ? (
            <NoResumeInterviewState hasResumes={hasResumes} onStart={handlePracticeCardClick} t={t} pageError={pageError} />
          ) : (
            <div>
              <div className="mb-5 flex items-center justify-between gap-4">
                <div>
                  <h1 className="text-xl font-medium" style={{ color: LIST_TEXT }}>{t('center.mockTitle')}</h1>
                  <p className="mt-0.5 text-[13px]" style={{ color: LIST_FAINT }}>
                    {t('center.listSummary', { total: sessions.length, used: sessions.length, limit: '∞' })}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={handlePracticeCardClick}
                  aria-label={t('center.create')}
                  className="inline-flex h-9 shrink-0 items-center justify-center gap-1.5 rounded-lg px-4 text-[13px] font-medium text-white transition-colors"
                  style={{ backgroundColor: LIST_BLUE }}
                  onMouseEnter={event => { event.currentTarget.style.backgroundColor = LIST_BLUE_HOVER }}
                  onMouseLeave={event => { event.currentTarget.style.backgroundColor = LIST_BLUE }}
                >
                  <span className="text-lg leading-none">+</span>
                  <span>{t('center.startNewInterview')}</span>
                </button>
              </div>

              {pageError && (
                <div className="mb-5 rounded-lg border px-4 py-3 text-sm" style={{ backgroundColor: '#fef2f2', borderColor: 'rgba(220,38,38,0.14)', color: '#dc2626' }}>
                  {pageError}
                </div>
              )}

              <div className="mb-5 flex flex-col gap-2 lg:flex-row lg:items-center">
                <label className="relative block w-full lg:max-w-[280px]" aria-label={t('center.searchPlaceholder')}>
                  <MagnifyingGlassIcon className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2" style={{ color: LIST_FAINT }} />
                  <input
                    type="search"
                    value={sessionSearchQuery}
                    onChange={event => setSessionSearchQuery(event.target.value)}
                    placeholder={t('center.searchPlaceholder')}
                    className="h-[34px] w-full rounded-lg border bg-white pl-8 pr-3 text-[13px] outline-none"
                    style={{ borderColor: LIST_BORDER, color: LIST_TEXT }}
                  />
                </label>
                <label className="relative block w-full sm:w-[150px]" aria-label={t('center.filterStatusLabel')}>
                  <select
                    value={sessionStatusFilter}
                    onChange={event => setSessionStatusFilter(event.target.value as SessionStatusFilter)}
                    className="h-[34px] w-full appearance-none rounded-lg border bg-white pl-3 pr-9 text-[13px] outline-none"
                    style={{ borderColor: LIST_BORDER, color: LIST_MUTED }}
                  >
                    <option value="all">{t('center.filterAllStatus')}</option>
                    <option value="completed">{t('status.completed')}</option>
                    <option value="active">{t('status.active')}</option>
                    <option value="not_started">{t('status.notStarted')}</option>
                  </select>
                  <ChevronDownIcon className="pointer-events-none absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2" style={{ color: LIST_MUTED }} />
                </label>
                <label className="relative block w-full sm:w-[150px]" aria-label={t('center.sortTimeLabel')}>
                  <select
                    value={sessionSortOrder}
                    onChange={event => setSessionSortOrder(event.target.value as SessionSortOrder)}
                    className="h-[34px] w-full appearance-none rounded-lg border bg-white pl-3 pr-9 text-[13px] outline-none"
                    style={{ borderColor: LIST_BORDER, color: LIST_MUTED }}
                  >
                    <option value="recent">{t('center.sortRecent')}</option>
                    <option value="oldest">{t('center.sortOldest')}</option>
                  </select>
                  <ChevronDownIcon className="pointer-events-none absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2" style={{ color: LIST_MUTED }} />
                </label>
              </div>

              <div className="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-4">
                {filteredSessions.map((session, index) => (
                  <InterviewCard
                    key={session.id}
                    session={session}
                    locale={locale}
                    index={index}
                    deletingSessionId={deletingSessionId}
                    onDelete={handleDeleteInterview}
                    onPracticeAgain={handlePracticeAgain}
                    onGenerateReport={handleGenerateReport}
                    retryingSessionId={retryingSessionId}
                    generatingReportSessionId={generatingReportSessionId}
                    t={t}
                  />
                ))}
                <button
                  type="button"
                  onClick={handlePracticeCardClick}
                  aria-label={t('center.create')}
                  className="flex min-h-[240px] flex-col items-center justify-center gap-2.5 rounded-2xl border border-dashed bg-transparent px-5 text-center transition-colors"
                  style={{ borderColor: LIST_BORDER }}
                  onMouseEnter={event => {
                    event.currentTarget.style.borderColor = LIST_BLUE
                    event.currentTarget.style.backgroundColor = LIST_BLUE_BG
                  }}
                  onMouseLeave={event => {
                    event.currentTarget.style.borderColor = LIST_BORDER
                    event.currentTarget.style.backgroundColor = 'transparent'
                  }}
                >
                  <span className="flex h-10 w-10 items-center justify-center rounded-full" style={{ backgroundColor: '#f9fafb', color: LIST_FAINT }}>
                    <span className="text-2xl leading-none">+</span>
                  </span>
                  <span className="text-[13.5px] font-medium" style={{ color: LIST_MUTED }}>{t('center.startNewInterview')}</span>
                  <span className="text-xs leading-5" style={{ color: LIST_FAINT }}>{t('center.startNewInterviewHint')}</span>
                </button>
              </div>
            </div>
          )}
        </motion.section>
      </main>
      </div>
    </div>
  )
}
