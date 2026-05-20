'use client'

/**
 * 面试中心页模块
 *
 * 用于让用户在进入面试前选择简历、补充岗位上下文，并查看历史面试记录。
 */

import { useEffect, useMemo, useRef, useState } from 'react'
import { useAuth } from '@/lib/auth'
import { useRouter } from '@/i18n/navigation'
import { motion } from 'framer-motion'
import { Link } from '@/i18n/navigation'
import MainNavigation from '@/components/layout/MainNavigation'
import { resumeApi, type InterviewSessionSummary, type Resume, type ResumeListItem } from '@/lib/api'
import { formatApiErrorMessage } from '@/lib/apiErrors'
import { useLocale, useTranslations } from 'next-intl'
import { toInterviewLanguage, type AppLocale } from '@/i18n/routing'
import {
  ChevronDownIcon,
  ClockIcon,
  ChatBubbleLeftRightIcon,
  DocumentTextIcon,
  ExclamationCircleIcon,
  MagnifyingGlassIcon,
  MicrophoneIcon,
  StarIcon,
  XMarkIcon,
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

const LIST_BLUE = '#5457e8'
const LIST_BLUE_HOVER = '#4447d6'
const LIST_BLUE_BG = '#eef2ff'
const LIST_TEXT = '#111827'
const LIST_MUTED = '#6b7280'
const LIST_FAINT = '#9ca3af'
const LIST_BORDER = 'rgba(0,0,0,0.14)'
const LIST_SOFT_BORDER = 'rgba(0,0,0,0.08)'
const LIST_GREEN = '#10b981'
const LIST_YELLOW = '#f59e0b'

// 用于生成列表页的紧凑时间文案。
function formatCompactDate(dateString: string | undefined, locale: string, t: ReturnType<typeof useTranslations>) {
  if (!dateString) return t('center.dateUnknown')
  const timestamp = new Date(dateString.includes('Z') || dateString.includes('+') ? dateString : `${dateString}Z`).getTime()
  if (Number.isNaN(timestamp)) return t('center.dateUnknown')

  const elapsedHours = Math.floor((Date.now() - timestamp) / 3600000)
  if (elapsedHours < 24) {
    return new Intl.DateTimeFormat(locale === 'zh' ? 'zh-CN' : 'en-US', {
      hour: '2-digit',
      minute: '2-digit',
      timeZone: 'Asia/Shanghai',
      hour12: false,
    }).format(new Date(timestamp))
  }
  if (elapsedHours < 48) return t('center.dateYesterday')
  if (elapsedHours < 24 * 7) return t('center.dateDaysAgo', { count: Math.floor(elapsedHours / 24) })
  return t('center.dateLastWeek')
}

// 用于判断面试卡片视觉状态。
function getInterviewVisualState(status: string, t: ReturnType<typeof useTranslations>) {
  if (status === 'completed') {
    return { label: t('status.completed'), badgeBg: '#ecfdf5', badgeColor: '#065f46', band: LIST_GREEN, kind: 'done' as const }
  }
  if (status === 'in_progress' || status === 'waiting_user_answer') {
    return { label: t('status.active'), badgeBg: '#fffbeb', badgeColor: '#92400e', band: LIST_YELLOW, kind: 'ongoing' as const }
  }
  return { label: t('status.notStarted'), badgeBg: '#f9fafb', badgeColor: LIST_FAINT, band: LIST_SOFT_BORDER, kind: 'draft' as const }
}

// 用于给列表摘要生成稳定得分。
function getInterviewScore(session: InterviewSessionSummary) {
  if (session.status !== 'completed') return null
  return Math.min(92, 58 + session.answered_turn_count * 3)
}

type InterviewPracticeGroup = {
  key: string
  title: string
  company: string
  sessions: InterviewSessionSummary[]
  completedSessions: InterviewSessionSummary[]
  activeSession?: InterviewSessionSummary
  bestScore: number | null
  averageScore: number | null
  answeredQuestionCount: number
}

// 用于生成岗位练习分组的稳定键。
function getPracticeGroupKey(session: InterviewSessionSummary) {
  const title = session.target_title?.trim().toLowerCase() || 'general'
  const company = session.target_company?.trim().toLowerCase() || 'none'
  return `${title}::${company}::${session.resume_id}`
}

// 用于对面试记录按最近练习排序。
function compareSessionsByRecentTime(a: InterviewSessionSummary, b: InterviewSessionSummary) {
  const left = new Date(a.started_at || a.ended_at || '').getTime() || 0
  const right = new Date(b.started_at || b.ended_at || '').getTime() || 0
  return right - left
}

// 用于按目标岗位聚合面试记录。
function buildPracticeGroups(sessions: InterviewSessionSummary[], t: ReturnType<typeof useTranslations>) {
  const grouped = new Map<string, InterviewSessionSummary[]>()
  for (const session of sessions) {
    const key = getPracticeGroupKey(session)
    grouped.set(key, [...(grouped.get(key) || []), session])
  }

  return Array.from(grouped.entries())
    .map(([key, groupSessions]) => {
      const sortedSessions = [...groupSessions].sort(compareSessionsByRecentTime)
      const completedSessions = sortedSessions.filter(session => session.status === 'completed')
      const scores = completedSessions.map(getInterviewScore).filter(score => score !== null)
      const scoreTotal = scores.reduce((sum, score) => sum + score, 0)

      return {
        key,
        sessions: sortedSessions,
        completedSessions,
        activeSession: sortedSessions.find(session => session.status !== 'completed'),
        title: sortedSessions[0]?.target_title || t('session.untitledRole'),
        company: sortedSessions[0]?.target_company || t('center.noTargetCompany'),
        bestScore: scores.length ? Math.max(...scores) : null,
        averageScore: scores.length ? Math.round(scoreTotal / scores.length) : null,
        answeredQuestionCount: sortedSessions.reduce((sum, session) => sum + session.answered_turn_count, 0),
      }
    })
    .sort((a, b) => compareSessionsByRecentTime(a.sessions[0], b.sessions[0]))
}

// 面试得分环。
function ScoreRing({ score }: { score: number }) {
  const circumference = 131.9
  const offset = circumference * (1 - score / 100)
  const color = score >= 75 ? LIST_GREEN : LIST_YELLOW

  return (
    <div className="relative h-12 w-12 shrink-0">
      <svg width="48" height="48" viewBox="0 0 52 52" className="-rotate-90">
        <circle cx="26" cy="26" r="21" fill="none" stroke="#f3f4f6" strokeWidth="5" />
        <circle cx="26" cy="26" r="21" fill="none" stroke={color} strokeWidth="5" strokeDasharray={circumference} strokeDashoffset={offset} strokeLinecap="round" />
      </svg>
      <div className="absolute inset-0 flex items-center justify-center text-sm font-medium" style={{ color: LIST_TEXT }}>
        {score}
      </div>
    </div>
  )
}

// 面试得分明细条。
function ScoreBar({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center gap-2 text-[11px]" style={{ color: LIST_FAINT }}>
      <span className="w-[52px] shrink-0">{label}</span>
      <span className="h-[3px] min-w-[84px] flex-1 overflow-hidden rounded-sm" style={{ backgroundColor: '#f3f4f6' }}>
        <span className="block h-full rounded-sm" style={{ width: `${value}%`, backgroundColor: value >= 75 ? LIST_GREEN : LIST_YELLOW }} />
      </span>
    </div>
  )
}

// 面试详情页顶部统计项。
function InterviewStat({ value, suffix = '', label, trend }: { value: string; suffix?: string; label: string; trend?: string }) {
  return (
    <div className="border-r pr-5 last:border-r-0" style={{ borderColor: LIST_SOFT_BORDER }}>
      <div className="text-xl font-medium leading-none" style={{ color: LIST_TEXT }}>
        {value}
        {suffix && <span className="ml-1 text-xs font-normal" style={{ color: LIST_MUTED }}>{suffix}</span>}
      </div>
      <div className="mt-1 text-xs" style={{ color: LIST_FAINT }}>{label}</div>
      {trend && <div className="mt-1 text-[11.5px]" style={{ color: LIST_GREEN }}>{trend}</div>}
    </div>
  )
}

// 岗位练习列表项。
function PracticeGroupRow({
  group,
  selected,
  onSelect,
  t,
}: {
  group: InterviewPracticeGroup
  selected: boolean
  onSelect: () => void
  t: ReturnType<typeof useTranslations>
}) {
  return (
    <button
      type="button"
      onClick={onSelect}
      className="w-full rounded-xl border px-3.5 py-3 text-left transition-colors"
      style={{ borderColor: selected ? LIST_BLUE : LIST_BORDER, backgroundColor: selected ? LIST_BLUE_BG : '#ffffff' }}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="truncate text-[13px] font-medium" style={{ color: LIST_TEXT }}>{group.title}</div>
          <div className="mt-1 truncate text-[11.5px]" style={{ color: LIST_MUTED }}>{group.company}</div>
        </div>
        {group.activeSession && (
          <span className="mt-0.5 flex shrink-0 items-center gap-1 text-[10.5px]" style={{ color: '#92400e' }}>
            <span className="h-1.5 w-1.5 rounded-full" style={{ backgroundColor: LIST_YELLOW }} />
            {t('status.active')}
          </span>
        )}
      </div>
      <div className="mt-2 flex items-center gap-3 text-[11.5px]" style={{ color: LIST_FAINT }}>
        <span className="flex items-center gap-1">
          <ChatBubbleLeftRightIcon className="h-3 w-3" />
          {t('center.practiceCount', { count: group.sessions.length })}
        </span>
        <span>
          {t('center.bestScorePrefix')}
          <span className="ml-1 text-sm font-medium" style={{ color: group.bestScore && group.bestScore >= 75 ? LIST_GREEN : LIST_YELLOW }}>
            {group.bestScore || '-'}
          </span>
        </span>
      </div>
    </button>
  )
}

// 面试记录卡片。
function InterviewCard({
  session,
  locale,
  index,
  totalCount,
  deletingSessionId,
  onDelete,
  t,
}: {
  session: InterviewSessionSummary
  locale: string
  index: number
  totalCount: number
  deletingSessionId: number | null
  onDelete: (sessionId: number) => void
  t: ReturnType<typeof useTranslations>
}) {
  const visual = getInterviewVisualState(session.status, t)
  const score = getInterviewScore(session)
  const started = formatCompactDate(session.started_at, locale, t)
  const isCompleted = session.status === 'completed'
  const scoreBase = score || 0
  const attemptNumber = totalCount - index

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, delay: index * 0.04 }}
      className="group flex min-h-[214px] w-full cursor-pointer flex-col overflow-hidden rounded-xl border bg-white transition-all"
      style={{ borderColor: visual.kind === 'ongoing' ? LIST_YELLOW : LIST_BORDER, backgroundColor: visual.kind === 'ongoing' ? '#fffbeb' : '#ffffff' }}
      onMouseEnter={event => {
        event.currentTarget.style.borderColor = visual.kind === 'ongoing' ? LIST_YELLOW : LIST_BLUE
        event.currentTarget.style.boxShadow = visual.kind === 'ongoing' ? '0 0 0 3px rgba(245,158,11,0.1)' : '0 0 0 3px rgba(84,87,232,0.07)'
      }}
      onMouseLeave={event => {
        event.currentTarget.style.borderColor = visual.kind === 'ongoing' ? LIST_YELLOW : LIST_BORDER
        event.currentTarget.style.boxShadow = 'none'
      }}
    >
      <div className="flex flex-1 flex-col gap-3 px-3.5 py-4">
        <div className="flex items-start justify-between gap-2">
          <div className="text-[13.5px] font-medium" style={{ color: LIST_TEXT }}>
            {t('center.practiceAttempt', { count: attemptNumber })}
          </div>
          <div className="flex items-center gap-1.5">
            <span className="shrink-0 rounded px-2 py-1 text-[10.5px] font-medium" style={{ backgroundColor: visual.badgeBg, color: visual.badgeColor, border: visual.kind === 'draft' ? `1px solid ${LIST_BORDER}` : 'none' }}>
              {visual.label}
            </span>
          </div>
        </div>

        {score ? (
          <div className="flex min-h-[58px] items-center gap-3.5">
            <ScoreRing score={score} />
            <div className="flex flex-1 flex-col gap-1">
              <ScoreBar label={t('center.scoreClarity')} value={Math.min(96, scoreBase + 6)} />
              <ScoreBar label={t('center.scoreCompleteness')} value={scoreBase} />
              <ScoreBar label={t('center.scoreMatch')} value={Math.max(52, scoreBase - 8)} />
            </div>
          </div>
        ) : (
          <div className="flex flex-col gap-3">
            <span className="h-1 overflow-hidden rounded-sm" style={{ backgroundColor: 'rgba(245,158,11,0.18)' }}>
              <span className="block h-full rounded-sm" style={{ width: `${Math.min(100, (session.answered_turn_count / 8) * 100)}%`, backgroundColor: LIST_YELLOW }} />
            </span>
            <div className="text-[12px]" style={{ color: '#92400e' }}>
              {t('center.answeredQuestions', { count: session.answered_turn_count, total: 8 })}
            </div>
          </div>
        )}

        <div className="mt-auto flex flex-wrap items-center gap-3.5 border-t pt-2.5" style={{ borderColor: LIST_SOFT_BORDER }}>
          <span className="flex items-center gap-1 text-xs" style={{ color: LIST_FAINT }}>
            <ClockIcon className="h-3 w-3" />
            {started}
          </span>
          <span className="flex items-center gap-1 text-xs" style={{ color: LIST_FAINT }}>
            <ChatBubbleLeftRightIcon className="h-3 w-3" />
            {isCompleted ? t('center.totalQuestions', { count: session.answered_turn_count }) : t('center.answeredQuestions', { count: session.answered_turn_count, total: 8 })}
          </span>
        </div>
      </div>

      <div className="grid grid-cols-2 gap-2 px-3.5 pb-3">
        {isCompleted ? (
          <Link href={`/resume/${session.resume_id}/interview?session=${session.id}`} aria-label={t('session.viewReport')} className="col-span-2 inline-flex h-[30px] items-center justify-center rounded-lg border text-xs transition-colors" style={{ borderColor: LIST_BORDER, color: LIST_MUTED }}>
              {t('center.reviewAction')}
          </Link>
        ) : (
          <>
            <Link href={`/resume/${session.resume_id}/interview?session=${session.id}`} className="inline-flex h-[30px] items-center justify-center rounded-lg text-xs font-medium text-white" style={{ backgroundColor: LIST_BLUE }}>
              {t('session.continue')}
            </Link>
            <button type="button" onClick={() => onDelete(session.id)} disabled={deletingSessionId === session.id} className="inline-flex h-[30px] items-center justify-center rounded-lg border text-xs transition-colors disabled:opacity-60" style={{ borderColor: 'rgba(245,158,11,0.35)', color: '#92400e' }}>
              {deletingSessionId === session.id ? t('session.deletingTitle') : t('center.abandonAction')}
            </button>
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
  const [selectedPracticeKey, setSelectedPracticeKey] = useState('')
  const [formError, setFormError] = useState<string | null>(null)
  const [targetCompany, setTargetCompany] = useState('')
  const [targetTitle, setTargetTitle] = useState('')
  const [jdText, setJdText] = useState('')
  const hasResumes = resumes.length > 0
  const practiceGroups = useMemo(() => buildPracticeGroups(sessions, t), [sessions, t])
  const selectedPracticeGroup = practiceGroups.find(group => group.key === selectedPracticeKey) || practiceGroups[0]
  const selectedBestScore = selectedPracticeGroup?.bestScore
  const selectedAverageScore = selectedPracticeGroup?.averageScore
  const selectedAnsweredCount = selectedPracticeGroup?.answeredQuestionCount || 0
  const selectedFirstScore = selectedPracticeGroup?.completedSessions
    .slice()
    .sort((a, b) => compareSessionsByRecentTime(b, a))
    .map(getInterviewScore)
    .find(score => score !== null)
  const selectedScoreDelta = selectedBestScore && selectedFirstScore ? selectedBestScore - selectedFirstScore : 0

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
        <aside
          className="hidden w-[220px] shrink-0 border-r bg-white px-3 py-5 md:flex md:flex-col"
          style={{ borderColor: LIST_SOFT_BORDER }}
        >
          <div className="space-y-5">
            <div>
              <p className="mb-1 px-2 text-[11px] font-medium uppercase tracking-wider" style={{ color: LIST_FAINT }}>{t('center.sidebarResume')}</p>
              <div className="space-y-1">
                <Link href="/resumes" className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-[13.5px] font-medium" style={{ color: LIST_MUTED }}>
                  <DocumentTextIcon className="h-4 w-4" />
                  <span>{t('center.sidebarMyResumes')}</span>
                </Link>
                <div className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-[13.5px] font-medium" style={{ color: LIST_MUTED }}>
                  <ClockIcon className="h-4 w-4" />
                  <span>{t('center.sidebarVersions')}</span>
                </div>
                <div className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-[13.5px] font-medium" style={{ color: LIST_MUTED }}>
                  <MagnifyingGlassIcon className="h-4 w-4" />
                  <span>{t('center.sidebarJdAnalysis')}</span>
                </div>
              </div>
            </div>

            <div>
              <p className="mb-1 px-2 text-[11px] font-medium uppercase tracking-wider" style={{ color: LIST_FAINT }}>{t('center.sidebarInterview')}</p>
              <div className="space-y-1">
                <div className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-[13.5px] font-medium" style={{ backgroundColor: LIST_BLUE_BG, color: '#1e40af' }}>
                  <ChatBubbleLeftRightIcon className="h-4 w-4" />
                  <span>{t('center.sidebarMockInterview')}</span>
                </div>
                <div className="flex items-center gap-2 rounded-lg px-2 py-1.5 text-[13.5px] font-medium" style={{ color: LIST_MUTED }}>
                  <StarIcon className="h-4 w-4" />
                  <span>{t('center.sidebarInterviewReview')}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-auto rounded-xl border p-3.5" style={{ borderColor: LIST_BORDER, backgroundColor: '#f9fafb' }}>
            <p className="text-[13px] font-medium" style={{ color: LIST_TEXT }}>{t('center.upgradeTitle')}</p>
            <p className="mt-1 text-xs leading-5" style={{ color: LIST_MUTED }}>{t('center.upgradeDescription')}</p>
            <Link
              href="/pricing"
              className="mt-2.5 inline-flex h-8 w-full items-center justify-center rounded-lg text-xs font-medium text-white"
              style={{ backgroundColor: LIST_BLUE }}
            >
              {t('center.upgradeAction')}
            </Link>
          </div>
        </aside>

      <main className="flex-1 overflow-y-auto" style={{ backgroundColor: '#f9fafb' }}>
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
          ) : (
            <div className="flex min-h-[calc(100vh-112px)] border bg-white" style={{ borderColor: LIST_SOFT_BORDER }}>
              <section className="w-[300px] shrink-0 border-r bg-white" style={{ borderColor: LIST_SOFT_BORDER }}>
                <div className="border-b px-4 py-4" style={{ borderColor: LIST_SOFT_BORDER }}>
                  <h1 className="text-[15px] font-medium" style={{ color: LIST_TEXT }}>{t('center.practiceRoles')}</h1>
                  <button
                    type="button"
                    onClick={handlePracticeCardClick}
                    aria-label={t('center.create')}
                    className="mt-3 inline-flex h-9 w-full items-center justify-center gap-1.5 rounded-lg text-[13px] font-medium text-white transition-colors"
                    style={{ backgroundColor: LIST_BLUE }}
                    onMouseEnter={event => { event.currentTarget.style.backgroundColor = LIST_BLUE_HOVER }}
                    onMouseLeave={event => { event.currentTarget.style.backgroundColor = LIST_BLUE }}
                  >
                    <span className="text-lg leading-none">+</span>
                    <span>{t('center.addPracticeRole')}</span>
                  </button>
                </div>

                <div className="flex flex-col gap-1.5 p-3">
                  {practiceGroups.map(group => (
                    <PracticeGroupRow
                      key={group.key}
                      group={group}
                      selected={group.key === selectedPracticeGroup?.key}
                      onSelect={() => setSelectedPracticeKey(group.key)}
                      t={t}
                    />
                  ))}
                </div>
              </section>

              <section className="min-w-0 flex-1 bg-[#f9fafb]">
                {pageError && (
                  <div className="m-6 rounded-lg border px-4 py-3 text-sm" style={{ backgroundColor: '#fef2f2', borderColor: 'rgba(220,38,38,0.14)', color: '#dc2626' }}>
                    {pageError}
                  </div>
                )}

                {!hasResumes && (
                  <div className="m-6 flex items-start gap-3 rounded-lg border px-4 py-3 text-sm" style={{ backgroundColor: '#fffbeb', borderColor: '#fde68a', color: '#b45309' }}>
                    <ExclamationCircleIcon className="mt-0.5 h-5 w-5 shrink-0" />
                    <span>
                      {t('center.needResumePrefix')}
                      <Link href="/resumes" className="font-semibold underline underline-offset-2">{t('center.needResumeLink')}</Link>
                      {t('center.needResumeSuffix')}
                    </span>
                  </div>
                )}

                {selectedPracticeGroup ? (
                  <>
                    <div className="border-b bg-white px-6 py-5" style={{ borderColor: LIST_SOFT_BORDER }}>
                      <div className="mb-4 flex items-start justify-between gap-4">
                        <div>
                          <h2 className="text-lg font-medium" style={{ color: LIST_TEXT }}>
                            {selectedPracticeGroup.title} · {selectedPracticeGroup.company}
                          </h2>
                          <p className="mt-1 text-[13px]" style={{ color: LIST_MUTED }}>
                            {t('center.selectedPracticeSummary', { total: selectedPracticeGroup.sessions.length })}
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
                          <span>{t('center.practiceAgain')}</span>
                        </button>
                      </div>

                      <div className="flex gap-5">
                        <InterviewStat value={String(selectedPracticeGroup.sessions.length)} label={t('center.statTotal')} />
                        <InterviewStat value={selectedBestScore ? String(selectedBestScore) : '-'} suffix={selectedBestScore ? t('center.scoreSuffix') : ''} label={t('center.statBestScore')} />
                        <InterviewStat
                          value={selectedAverageScore ? String(selectedAverageScore) : '-'}
                          suffix={selectedAverageScore ? t('center.scoreSuffix') : ''}
                          label={t('center.statAverageScore')}
                          trend={selectedScoreDelta > 0 ? t('center.scoreTrendFromFirst', { delta: selectedScoreDelta }) : undefined}
                        />
                        <InterviewStat value={String(selectedAnsweredCount)} suffix={t('center.questionSuffix')} label={t('center.statAnswered')} />
                      </div>
                    </div>

                    <div className="px-6 py-5">
                      <div className="mb-4 text-[11px] font-medium uppercase tracking-wider" style={{ color: LIST_FAINT }}>
                        {t('center.practiceRecords')}
                      </div>
                      <div className="grid grid-cols-[repeat(auto-fit,minmax(260px,280px))] gap-3.5">
                        {selectedPracticeGroup.sessions.map((session, index) => (
                          <InterviewCard
                            key={session.id}
                            session={session}
                            locale={locale}
                            index={index}
                            totalCount={selectedPracticeGroup.sessions.length}
                            deletingSessionId={deletingSessionId}
                            onDelete={handleDeleteInterview}
                            t={t}
                          />
                        ))}
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="flex min-h-[420px] flex-col items-center justify-center px-6 text-center">
                    <h2 className="text-lg font-medium" style={{ color: LIST_TEXT }}>{t('center.emptyTitle')}</h2>
                    <p className="mt-2 max-w-md text-sm leading-6" style={{ color: LIST_MUTED }}>{t('center.emptyDescription')}</p>
                    <button
                      type="button"
                      onClick={handlePracticeCardClick}
                      className="mt-5 inline-flex h-9 items-center justify-center rounded-lg px-4 text-[13px] font-medium text-white"
                      style={{ backgroundColor: LIST_BLUE }}
                    >
                      {t('center.startNewInterview')}
                    </button>
                  </div>
                )}
              </section>
            </div>
          )}
        </motion.section>
      </main>
      </div>
    </div>
  )
}
