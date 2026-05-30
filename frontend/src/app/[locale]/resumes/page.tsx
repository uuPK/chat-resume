'use client'
// 用于提供 app/[locale]/resumes/page.tsx 模块。

import { motion } from 'framer-motion'
import { useEffect, useState, useRef } from 'react'
import { useAuth } from '@/lib/auth'
import { useRouter } from '@/i18n/navigation'
import { resumeApi, type ResumeContent } from '@/lib/api'
import { formatApiErrorMessage } from '@/lib/apiErrors'
import { buildModuleConfig, deserializeLayoutConfig } from '@/lib/resumeLayoutConfig'
import toast from 'react-hot-toast'
import { Link } from '@/i18n/navigation'
import MainNavigation from '@/components/layout/MainNavigation'
import CandidateSidebar from '@/components/layout/CandidateSidebar'
import PaginatedResumePreview from '@/components/preview/PaginatedResumePreview'
import { useTranslations } from 'next-intl'
import {
  ArrowRightIcon,
  ArrowUpTrayIcon,
  ArrowDownTrayIcon,
  ChatBubbleLeftRightIcon,
  ChevronDownIcon,
  DocumentTextIcon,
  ClockIcon,
  EllipsisVerticalIcon,
  LockClosedIcon,
  MagnifyingGlassIcon,
  PlusIcon,
  ClipboardDocumentListIcon,
  SparklesIcon,
  BriefcaseIcon,
  AcademicCapIcon,
} from '@heroicons/react/24/solid'

interface Resume {
  id: number
  title: string
  original_filename?: string
  owner_id?: number
  created_at: string
  updated_at?: string
  target_company?: string
  target_title?: string
  layout_config?: Record<string, unknown> | null
  preview_content?: Partial<ResumeContent>
}

const UPLOAD_JOB_POLL_INTERVAL_MS = 1500
const UPLOAD_JOB_TIMEOUT_MS = 120000
const FREE_RESUME_LIMIT = 3
const LIST_BLUE = '#7c3aed'
const LIST_BLUE_HOVER = '#6d28d9'
const LIST_BLUE_BG = '#f5f3ff'
const LIST_TEXT = '#111827'
const LIST_MUTED = '#6b7280'
const LIST_FAINT = '#9ca3af'
const LIST_BORDER = 'rgba(0,0,0,0.14)'
const LIST_SOFT_BORDER = 'rgba(0,0,0,0.08)'

type ResumeStatusFilter = 'all' | 'optimized' | 'draft'
type ResumeSortOrder = 'recent' | 'oldest'

// 用于等待当前数据。
function sleep(ms: number) {
  return new Promise(resolve => window.setTimeout(resolve, ms))
}

// 用于生成简历列表卡片的状态标签。
function getResumeCardStatus(resume: Resume, t: ReturnType<typeof useTranslations>) {
  if (resume.target_company || resume.target_title) {
    return {
      label: t('cardStatusOptimized'),
      backgroundColor: LIST_BLUE_BG,
      color: '#1e40af',
    }
  }

  return {
    label: t('cardStatusDraft'),
    backgroundColor: '#fafafa',
    color: LIST_FAINT,
  }
}

// 用于读取简历卡片副标题。
function getResumeSubtitle(resume: Resume, t: ReturnType<typeof useTranslations>) {
  const targetParts = [resume.target_company, resume.target_title].filter(Boolean)
  if (targetParts.length > 0) return targetParts.join(' · ')
  return resume.target_title || resume.original_filename || t('cardUntargeted')
}

// 用于渲染简历卡片的主标题和副标题。
function ResumeCardTitleBlock({ resume, t }: { resume: Resume; t: ReturnType<typeof useTranslations> }) {
  return (
    <div className="min-w-0">
      <h2 className="truncate text-sm font-medium" style={{ color: LIST_TEXT }}>{getResumeSubtitle(resume, t)}</h2>
      <p className="mt-0.5 truncate text-xs" style={{ color: LIST_MUTED }}>{resume.title}</p>
    </div>
  )
}

// 用于格式化列表卡片的修改时间。
function formatResumeModifiedAt(dateString: string | undefined, t: ReturnType<typeof useTranslations>) {
  if (!dateString) return t('recentlyModified')
  const modifiedAt = new Date(dateString).getTime()
  if (Number.isNaN(modifiedAt)) return t('recentlyModified')

  const elapsedHours = Math.max(1, Math.floor((Date.now() - modifiedAt) / 3600000))
  if (elapsedHours < 24) return t('modifiedHoursAgo', { count: elapsedHours })
  if (elapsedHours < 48) return t('modifiedYesterday')
  return t('modifiedDaysAgo', { count: Math.floor(elapsedHours / 24) })
}

// 简历卡片预览，优先展示真实简历内容。
function ResumeCardPreview({
  resume,
  status,
  t,
}: {
  resume: Resume
  status: { label: string; backgroundColor: string; color: string }
  t: ReturnType<typeof useTranslations>
}) {
  const layoutConfig = deserializeLayoutConfig(resume.layout_config)
  const moduleOrder = buildModuleConfig(layoutConfig.moduleOrder, layoutConfig.visibleModules)

  return (
    <div className="relative h-[192px] overflow-hidden border-b" style={{ backgroundColor: '#fafbff', borderColor: LIST_SOFT_BORDER }}>
      <span
        className="absolute right-2.5 top-2.5 z-10 rounded px-1.5 py-0.5 text-[10px] font-medium"
        style={{ backgroundColor: status.backgroundColor, color: status.color, border: status.color === LIST_FAINT ? `1px solid ${LIST_BORDER}` : 'none' }}
      >
        {status.label}
      </span>
      {resume.preview_content ? (
        <div className="pointer-events-none h-full select-none">
          <PaginatedResumePreview
            content={resume.preview_content as ResumeContent}
            moduleOrder={moduleOrder}
            spacingScale={layoutConfig.spacingScale}
            templateStyle={layoutConfig.templateStyle}
            viewportPadding={0}
          />
        </div>
      ) : (
        <FallbackResumePreview t={t} />
      )}
    </div>
  )
}

// 无预览内容时展示轻量占位。
function FallbackResumePreview({ t }: { t: ReturnType<typeof useTranslations> }) {
  const skillWidths = ['36px', '48px', '28px', '40px']
  return (
    <div className="px-4 pb-3 pt-4">
      <div className="mb-0.5 truncate text-center text-[13px] font-medium" style={{ color: LIST_TEXT }}>
        {t('previewLoading')}
      </div>
      <FallbackSection label={t('previewEducation')} lineWidths={['80%', '60%']} />
      <FallbackSection label={t('previewExperience')} lineWidths={['100%', '80%', '100%']} />
      <div className="mt-2 text-[9px] font-medium uppercase tracking-wide" style={{ color: LIST_FAINT }}>
        {t('previewSkills')}
      </div>
      <div className="mt-1.5 flex flex-wrap gap-1">
        {skillWidths.map(width => (
          <span key={width} className="h-3.5 rounded-[3px]" style={{ width, backgroundColor: LIST_SOFT_BORDER }} />
        ))}
      </div>
    </div>
  )
}

// 用于渲染无预览内容时的小节线条。
function FallbackSection({ label, lineWidths }: { label: string; lineWidths: string[] }) {
  return (
    <div className="mt-2">
      <div className="mb-1.5 text-[9px] font-medium uppercase tracking-wide" style={{ color: LIST_FAINT }}>{label}</div>
      <div className="space-y-1">
        {lineWidths.map((width, index) => (
          <div key={`${label}-${width}-${index}`} className={index === 0 ? 'h-1 rounded-sm' : 'h-[3px] rounded-sm'} style={{ width, backgroundColor: LIST_SOFT_BORDER }} />
        ))}
      </div>
    </div>
  )
}

// 用于判断简历是否匹配搜索词。
function resumeMatchesQuery(resume: Resume, query: string) {
  const normalizedQuery = query.trim().toLowerCase()
  if (!normalizedQuery) return true

  return [
    resume.title,
    resume.target_title,
    resume.target_company,
    resume.original_filename,
  ].some(value => value?.toLowerCase().includes(normalizedQuery))
}

// 用于判断简历是否符合状态筛选。
function resumeMatchesStatus(resume: Resume, filter: ResumeStatusFilter) {
  if (filter === 'all') return true
  const hasTarget = Boolean(resume.target_company || resume.target_title)
  return filter === 'optimized' ? hasTarget : !hasTarget
}

// 用于给简历排序提供稳定修改时间。
function getResumeSortTimestamp(resume: Resume) {
  const timestamp = new Date(resume.updated_at || resume.created_at).getTime()
  return Number.isNaN(timestamp) ? resume.id : timestamp
}

// 用于组合搜索、状态筛选和修改时间排序。
function getVisibleResumes(
  resumes: Resume[],
  query: string,
  statusFilter: ResumeStatusFilter,
  sortOrder: ResumeSortOrder,
) {
  return resumes
    .filter(resume => resumeMatchesQuery(resume, query))
    .filter(resume => resumeMatchesStatus(resume, statusFilter))
    .sort((left, right) => {
      const leftTime = getResumeSortTimestamp(left)
      const rightTime = getResumeSortTimestamp(right)
      return sortOrder === 'recent' ? rightTime - leftTime : leftTime - rightTime
    })
}

// 简历中心主页，展示用户所有简历
export default function ResumesPage() {
  const { isAuthenticated, isLoading } = useAuth()
  const router = useRouter()
  const [mounted, setMounted] = useState(false)
  const [uploadLoading, setUploadLoading] = useState(false)
  const [resumes, setResumes] = useState<Resume[]>([])
  const [resumesLoading, setResumesLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const [resumeSearchQuery, setResumeSearchQuery] = useState('')
  const [resumeStatusFilter, setResumeStatusFilter] = useState<ResumeStatusFilter>('all')
  const [resumeSortOrder, setResumeSortOrder] = useState<ResumeSortOrder>('recent')
  const [openResumeActionsId, setOpenResumeActionsId] = useState<number | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const t = useTranslations('resume.center')
  const common = useTranslations('common')
  const filteredResumes = resumes.filter(resume => resumeMatchesQuery(resume, resumeSearchQuery))
  const visibleResumes = filteredResumes
  const hiddenResumeCount = 0

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

  const [exportingIds, setExportingIds] = useState<Record<number, boolean>>({})

  const handleExportPDF = async (id: number, title: string) => {
    if (exportingIds[id]) return
    setExportingIds(prev => ({ ...prev, [id]: true }))
    const toastId = toast.loading('正在准备 PDF 并下载...')
    try {
      const data = await resumeApi.getResume(id)
      const template = (data.layout_config as any)?.templateStyle || 'classic'
      const result = await resumeApi.exportResume(id, 'pdf', template as string)
      const apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
      const downloadUrl = `${apiBaseUrl}${result.download_url}`
      const link = document.createElement('a')
      link.href = downloadUrl
      link.download = result.filename
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
      toast.success('PDF 导出并下载成功！', { id: toastId })
    } catch (error) {
      toast.error('导出失败，请稍后重试', { id: toastId })
    } finally {
      setExportingIds(prev => ({ ...prev, [id]: false }))
    }
  }

  useEffect(() => { setMounted(true) }, [])

  useEffect(() => {
    if (mounted && !isLoading && !isAuthenticated) router.push('/login')
  }, [mounted, isLoading, isAuthenticated, router])

  // 用于请求简历。
  const fetchResumes = async () => {
    if (!isAuthenticated) return
    try {
      setResumesLoading(true)
      const data = await resumeApi.getResumes()
      setResumes(data)
    } catch {
      toast.error(t('fetchError'))
    } finally {
      setResumesLoading(false)
    }
  }

  useEffect(() => {
    if (mounted && isAuthenticated) fetchResumes()
  }, [mounted, isAuthenticated])

  // 用于等待foruploadjob。
  const waitForUploadJob = async (jobId: string) => {
    const startedAt = Date.now()
    while (Date.now() - startedAt < UPLOAD_JOB_TIMEOUT_MS) {
      const job = await resumeApi.getResumeUploadJob(jobId)
      if (job.status === 'completed') {
        if (!job.resume_id) {
          throw new Error(t('parseMissingId'))
        }
        return job.resume_id
      }
      if (job.status === 'failed') {
        throw new Error(job.error || t('parseFailed'))
      }
      await sleep(UPLOAD_JOB_POLL_INTERVAL_MS)
    }
    throw new Error(t('parseTimeout'))
  }

  // 用于处理fileupload。
  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    const allowedTypes = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain']
    if (!allowedTypes.includes(file.type)) {
      toast.error(t('uploadTypeError'))
      return
    }
    if (file.size > 5 * 1024 * 1024) {
      toast.error(t('uploadSizeError'))
      return
    }
    setUploadLoading(true)
    try {
      toast.loading(t('uploadStart'), { id: 'upload' })
      const job = await resumeApi.uploadResume(file)
      toast.loading(t('uploadParsing'), { id: 'upload' })
      const resumeId = await waitForUploadJob(job.job_id)
      toast.success(t('uploadDone'), { id: 'upload' })
      router.push(`/resume/${resumeId}/edit?firstRun=1`)
    } catch (error) {
      toast.error(formatApiErrorMessage(
        error,
        { activeSubscriptionRequired: common('errors.activeSubscriptionRequired') },
        t('uploadFailed'),
      ), { id: 'upload' })
    } finally {
      setUploadLoading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  // 用于处理delete简历。
  const handleDeleteResume = async (resumeId: number, title: string) => {
    if (!confirm(t('deleteConfirm', { title }))) return
    try {
      toast.loading(t('deleteStart'), { id: 'delete' })
      await resumeApi.deleteResume(resumeId)
      setResumes(prev => prev.filter(r => r.id !== resumeId))
      toast.success(t('deleteDone'), { id: 'delete' })
    } catch (error) {
      toast.error(formatApiErrorMessage(error, {}, t('deleteFailed')), { id: 'delete' })
    }
  }

  // 用于处理confirmcreate。
  const handleConfirmCreate = async () => {
    setCreating(true)
    try {
      toast.loading(t('createStart'), { id: 'create' })
      const emptyResumeContent = {
        job_application: { target_company: '', target_title: '', jd_text: '', strategy: '' },
        personal_info: { name: '', email: '', phone: '', position: '', github: '' },
        education: [], work_experience: [], skills: [], projects: []
      }
      const newResume = await resumeApi.createResume({ title: t('untitled'), content: emptyResumeContent })
      toast.success(t('createDone'), { id: 'create' })
      router.push(`/resume/${newResume.id}/edit`)
    } catch (error) {
      toast.error(formatApiErrorMessage(error, {}, t('createFailed')), { id: 'create' })
    } finally {
      setCreating(false)
    }
  }

  if (!mounted || isLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#ffffff' }}>
        <div
          className="w-12 h-12 rounded-full border-2 border-transparent animate-spin"
          style={{ borderTopColor: '#7c3aed', borderRightColor: '#7c3aed' }}
        />
      </div>
    )
  }

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#fafafa' }}>
      {openResumeActionsId !== null && (
        <div className="fixed inset-0 z-[9]" onClick={() => setOpenResumeActionsId(null)} />
      )}
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.doc,.docx,.txt"
        onChange={handleFileUpload}
        className="hidden"
      />
      <MainNavigation />
      <div className="flex min-h-[calc(100vh-56px)]">
          <CandidateSidebar hasResumes={resumes.length > 0} firstResumeId={resumes[0]?.id} />

      <main className="flex-1 overflow-y-auto px-8 py-7" style={{ backgroundColor: '#fafafa' }}>
        {resumesLoading ? (
          <div className="flex justify-center items-center py-20">
            <div
              className="w-8 h-8 rounded-full border-2 border-transparent animate-spin"
              style={{ borderTopColor: '#7c3aed', borderRightColor: '#7c3aed' }}
            />
            <span className="ml-3 text-base" style={{ color: '#52525b' }}>{t('loading')}</span>
          </div>
        ) : resumes.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="mx-auto max-w-[760px] py-8"
          >
            <div className="mb-9">
              <h1 className="text-2xl font-semibold tracking-tight" style={{ color: '#18181b' }}>
                {t('emptyCreateHeading')}
              </h1>
              <p className="mt-3 text-base" style={{ color: '#52525b' }}>
                {t('emptyCreateSubheading')}
              </p>
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <button
                type="button"
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadLoading}
                aria-label={t('upload')}
                className="group flex min-h-[240px] flex-col rounded-2xl border bg-white p-7 text-left transition-all disabled:opacity-50"
                style={{ borderColor: 'rgba(91,97,110,0.2)' }}
                onMouseEnter={e => { if (!uploadLoading) { e.currentTarget.style.borderColor = '#7c3aed'; e.currentTarget.style.boxShadow = '0 16px 42px rgba(15,23,42,0.08)' } }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(91,97,110,0.2)'; e.currentTarget.style.boxShadow = 'none' }}
              >
                <span className="flex h-11 w-11 items-center justify-center rounded-lg" style={{ backgroundColor: '#f7f8fa', color: '#7c3aed' }}>
                  <ArrowUpTrayIcon className="h-5 w-5" />
                </span>
                <span className="mt-6 block text-lg font-semibold" style={{ color: '#18181b' }}>{t('emptyUploadTitle')}</span>
                <span className="mt-3 block text-sm leading-6" style={{ color: '#52525b' }}>{t('emptyUploadDescription')}</span>
                <span className="mt-auto flex items-end justify-between gap-4 pt-6">
                  <span className="flex gap-1.5">
                    {['PDF', 'Word', 'TXT'].map(label => (
                      <span key={label} className="rounded-md border px-2 py-1 text-xs font-medium" style={{ borderColor: 'rgba(91,97,110,0.22)', color: '#8b93a3' }}>
                        {label}
                      </span>
                    ))}
                  </span>
                  <span className="flex h-8 w-8 items-center justify-center rounded-full border" style={{ borderColor: 'rgba(91,97,110,0.2)', color: '#8b93a3' }}>
                    <ArrowRightIcon className="h-4 w-4" />
                  </span>
                </span>
              </button>

              <button
                type="button"
                onClick={handleConfirmCreate}
                disabled={creating}
                aria-label={t('create')}
                className="group flex min-h-[240px] flex-col rounded-2xl border bg-white p-7 text-left transition-all disabled:opacity-50"
                style={{ borderColor: 'rgba(91,97,110,0.2)' }}
                onMouseEnter={e => { if (!creating) { e.currentTarget.style.borderColor = '#7c3aed'; e.currentTarget.style.boxShadow = '0 16px 42px rgba(15,23,42,0.08)' } }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(91,97,110,0.2)'; e.currentTarget.style.boxShadow = 'none' }}
              >
                <span className="flex h-11 w-11 items-center justify-center rounded-lg" style={{ backgroundColor: '#f7f8fa', color: '#52525b' }}>
                  <ClipboardDocumentListIcon className="h-5 w-5" />
                </span>
                <span className="mt-6 block text-lg font-semibold" style={{ color: '#18181b' }}>{t('templateCreateTitle')}</span>
                <span className="mt-3 block text-sm leading-6" style={{ color: '#52525b' }}>{t('templateCreateDescription')}</span>
                <span className="mt-auto flex items-end justify-between gap-4 pt-6">
                  <span className="text-sm font-medium" style={{ color: '#b0b6c0' }}>
                    {creating ? t('creating') : t('templateCreateEta')}
                  </span>
                  <span className="flex h-8 w-8 items-center justify-center rounded-full border" style={{ borderColor: 'rgba(91,97,110,0.2)', color: '#8b93a3' }}>
                    <ArrowRightIcon className="h-4 w-4" />
                  </span>
                </span>
              </button>
            </div>

            <div className="mt-10">
              <p className="text-sm font-semibold" style={{ color: '#a0a7b3' }}>{t('usageTipsTitle')}</p>
              <ul className="mt-4 space-y-3 text-sm leading-6" style={{ color: '#8b93a3' }}>
                <li className="flex gap-3">
                  <span aria-hidden="true">•</span>
                  <span>{t('usageTipUpload')}</span>
                </li>
                <li className="flex gap-3">
                  <span aria-hidden="true">•</span>
                  <span>{t('usageTipVersions')}</span>
                </li>
                <li className="flex gap-3">
                  <span aria-hidden="true">•</span>
                  <span>{t('usageTipInterview')}</span>
                </li>
              </ul>
            </div>
          </motion.div>
        ) : (
          <div>
            <div className="mb-6 flex items-center justify-between gap-4">
              <div>
                <h1 className="text-xl font-medium" style={{ color: LIST_TEXT }}>
                  {t('listTitle')}
                </h1>
                <p className="mt-0.5 text-[13px]" style={{ color: LIST_FAINT }}>
                  {t('listSummary', {
                    total: resumes.length,
                    limit: '\u221e',
                    used: resumes.length,
                  })}
                </p>
              </div>
              <button
                type="button"
                onClick={handleConfirmCreate}
                disabled={creating}
                className="inline-flex h-9 shrink-0 items-center justify-center gap-1.5 rounded-lg px-4 text-[13px] font-medium text-white transition-colors disabled:opacity-50"
                style={{ backgroundColor: LIST_BLUE }}
                onMouseEnter={event => { if (!creating) event.currentTarget.style.backgroundColor = LIST_BLUE_HOVER }}
                onMouseLeave={event => { event.currentTarget.style.backgroundColor = LIST_BLUE }}
              >
                <PlusIcon className="h-4 w-4" />
                <span>{creating ? t('creating') : t('create')}</span>
              </button>
            </div>

            <div className="mb-5 flex flex-col gap-2 lg:flex-row lg:items-center">
              <label
                className="relative block w-full lg:max-w-[280px]"
                aria-label={t('searchPlaceholder')}
              >
                <MagnifyingGlassIcon className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2" style={{ color: LIST_FAINT }} />
                <input
                  type="search"
                  value={resumeSearchQuery}
                  onChange={event => setResumeSearchQuery(event.target.value)}
                  placeholder={t('searchPlaceholder')}
                  className="h-[34px] w-full rounded-lg border bg-white pl-8 pr-3 text-[13px] outline-none"
                  style={{ borderColor: LIST_BORDER, color: LIST_TEXT }}
                />
              </label>
              <label className="relative block w-full sm:w-[150px]" aria-label={t('filterStatusLabel')}>
                <select
                  value={resumeStatusFilter}
                  onChange={event => setResumeStatusFilter(event.target.value as ResumeStatusFilter)}
                  className="h-[34px] w-full appearance-none rounded-lg border bg-white pl-3 pr-9 text-[13px] outline-none"
                  style={{ borderColor: LIST_BORDER, color: LIST_MUTED }}
                >
                  <option value="all">{t('filterAllStatus')}</option>
                  <option value="optimized">{t('cardStatusOptimized')}</option>
                  <option value="draft">{t('cardStatusDraft')}</option>
                </select>
                <ChevronDownIcon className="pointer-events-none absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2" style={{ color: LIST_MUTED }} />
              </label>
              <label className="relative block w-full sm:w-[150px]" aria-label={t('sortModifiedLabel')}>
                <select
                  value={resumeSortOrder}
                  onChange={event => setResumeSortOrder(event.target.value as ResumeSortOrder)}
                  className="h-[34px] w-full appearance-none rounded-lg border bg-white pl-3 pr-9 text-[13px] outline-none"
                  style={{ borderColor: LIST_BORDER, color: LIST_MUTED }}
                >
                  <option value="recent">{t('sortRecent')}</option>
                  <option value="oldest">{t('sortOldest')}</option>
                </select>
                <ChevronDownIcon className="pointer-events-none absolute right-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2" style={{ color: LIST_MUTED }} />
              </label>
            </div>

            <div className="grid grid-cols-[repeat(auto-fill,minmax(260px,1fr))] gap-4">
              {visibleResumes.map((resume, index) => {
                const status = getResumeCardStatus(resume, t)
                return (
                  <motion.div
                    key={resume.id}
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: index * 0.08 }}
                    className="group relative flex cursor-pointer flex-col overflow-hidden rounded-2xl border bg-white transition-all"
                    style={{ borderColor: LIST_BORDER }}
                    onMouseEnter={event => {
                      event.currentTarget.style.borderColor = LIST_BLUE
                      event.currentTarget.style.boxShadow = '0 0 0 3px rgba(124,58,237,0.07)'
                    }}
                    onMouseLeave={event => {
                      event.currentTarget.style.borderColor = LIST_BORDER
                      event.currentTarget.style.boxShadow = 'none'
                    }}
                  >
                    <div
                      role="link"
                      tabIndex={0}
                      aria-label={resume.title}
                      onClick={() => router.push(`/resume/${resume.id}/edit`)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          router.push(`/resume/${resume.id}/edit`)
                        }
                      }}
                      className="relative block cursor-pointer"
                    >
                      <ResumeCardPreview resume={resume} status={status} t={t} />
                    </div>

                    <div className="flex flex-1 flex-col gap-2.5 px-4 py-3.5">
                      <div className="flex items-start justify-between gap-3">
                        <ResumeCardTitleBlock resume={resume} t={t} />
                        <button
                          type="button"
                          onClick={event => {
                            event.stopPropagation()
                            setOpenResumeActionsId(current => current === resume.id ? null : resume.id)
                          }}
                          className="flex h-[26px] w-[26px] shrink-0 items-center justify-center rounded-lg transition-colors"
                          style={{ color: LIST_FAINT }}
                          title={t('moreActions')}
                        >
                          <EllipsisVerticalIcon className="h-4 w-4" />
                        </button>
                        {openResumeActionsId === resume.id && (
                          <div
                            className="absolute right-4 top-[248px] z-10 rounded-lg border bg-white p-1 shadow-lg"
                            style={{ borderColor: 'rgba(91,97,110,0.16)' }}
                          >
                            <button
                              type="button"
                              onClick={event => {
                                event.stopPropagation()
                                setOpenResumeActionsId(null)
                                handleDeleteResume(resume.id, resume.title)
                              }}
                              className="rounded-md px-3 py-2 text-sm font-medium"
                              style={{ color: '#dc2626' }}
                            >
                              {t('deleteTitle')}
                            </button>
                          </div>
                        )}
                      </div>
                      <div className="flex flex-wrap items-center gap-3 text-xs" style={{ color: LIST_FAINT }}>
                        <span className="inline-flex items-center gap-1">
                          <ClockIcon className="h-3 w-3" />
                          {formatResumeModifiedAt(resume.updated_at || resume.created_at, t)}
                        </span>
                      </div>
                      <div className="mt-auto flex flex-col gap-2 border-t pt-3" style={{ borderColor: LIST_SOFT_BORDER }}>
                        {/* Row 1: Primary AI Edit + Export PDF */}
                        <div className="flex gap-2">
                          <Link
                            href={`/resume/${resume.id}/edit`}
                            className="flex-1 inline-flex h-[34px] items-center justify-center rounded-xl text-xs font-semibold text-white transition-all shadow-sm"
                            style={{ 
                              background: `linear-gradient(135deg, ${LIST_BLUE} 0%, #a78bfa 100%)`,
                            }}
                            onMouseEnter={e => {
                              e.currentTarget.style.filter = 'brightness(1.08)'
                            }}
                            onMouseLeave={e => {
                              e.currentTarget.style.filter = 'none'
                            }}
                          >
                            <svg className="mr-1.5 h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 12c0-1.232-.046-2.453-.138-3.662a4.006 4.006 0 00-3.7-3.7 48.678 48.678 0 00-7.324 0 4.006 4.006 0 00-3.7 3.7C4.547 9.547 4.5 10.768 4.5 12s.047 2.453.138 3.662a4.006 4.006 0 003.7 3.7 48.656 48.656 0 007.324 0 4.006 4.006 0 003.7-3.7c.092-1.209.138-2.43.138-3.662z" />
                              <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 9.75c0 .414-.168.75-.375.75S9 10.164 9 9.75 9.168 9 9.375 9s.375.336.375.75zm-.375 0h.008v.015h-.008V9.75zm5.625 0c0 .414-.168.75-.375.75s-.375-.336-.375-.75.168-.75.375-.75.375.336.375.75zm-.375 0h.008v.015h-.008V9.75z" />
                            </svg>
                            {t('aiOptimizeAction')}
                          </Link>
                          
                          <button
                            type="button"
                            onClick={event => {
                              event.stopPropagation()
                              handleExportPDF(resume.id, resume.title)
                            }}
                            disabled={exportingIds[resume.id]}
                            className="inline-flex h-[34px] w-[80px] items-center justify-center rounded-xl border text-xs font-medium transition-colors"
                            style={{ borderColor: LIST_BORDER, color: LIST_MUTED, backgroundColor: 'white' }}
                            onMouseEnter={e => {
                              e.currentTarget.style.backgroundColor = '#fafafa'
                              e.currentTarget.style.borderColor = LIST_BLUE
                            }}
                            onMouseLeave={e => {
                              e.currentTarget.style.backgroundColor = 'white'
                              e.currentTarget.style.borderColor = LIST_BORDER
                            }}
                          >
                            {exportingIds[resume.id] ? (
                              <div className="h-3 w-3 animate-spin rounded-full border-2" style={{ borderColor: '#eef0f3', borderTopColor: LIST_BLUE }} />
                            ) : (
                              <>
                                <svg className="mr-1 h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                                  <path strokeLinecap="round" strokeLinejoin="round" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                                </svg>
                                {t('exportAction')}
                              </>
                            )}
                          </button>
                        </div>

                        {/* Row 2: Ancillary Tools - 3 equal columns */}
                        <div className="grid grid-cols-3 gap-1.5">
                          <Link
                            href={`/resume/${resume.id}/jobs`}
                            className="inline-flex h-[30px] items-center justify-center rounded-xl border text-[11px] font-medium transition-colors"
                            style={{ backgroundColor: '#f5f3ff', borderColor: '#c4b5fd', color: '#6d28d9' }}
                            onMouseEnter={e => {
                              e.currentTarget.style.backgroundColor = '#ede9fe'
                            }}
                            onMouseLeave={e => {
                              e.currentTarget.style.backgroundColor = '#f5f3ff'
                            }}
                          >
                            <svg className="mr-1 h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                            </svg>
                            岗位匹配
                          </Link>

                          <Link
                            href={`/resume/${resume.id}/interview`}
                            className="inline-flex h-[30px] items-center justify-center rounded-xl border text-[11px] font-medium transition-colors"
                            style={{ borderColor: LIST_BORDER, color: LIST_MUTED, backgroundColor: 'white' }}
                            onMouseEnter={e => {
                              e.currentTarget.style.backgroundColor = '#fafafa'
                              e.currentTarget.style.borderColor = LIST_BORDER
                            }}
                            onMouseLeave={e => {
                              e.currentTarget.style.backgroundColor = 'white'
                              e.currentTarget.style.borderColor = LIST_BORDER
                            }}
                          >
                            <svg className="mr-1 h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
                            </svg>
                            {t('editAction')}
                          </Link>

                          <Link
                            href={`/resume/${resume.id}/learning-path`}
                            className="inline-flex h-[30px] items-center justify-center rounded-xl border text-[11px] font-medium transition-colors"
                            style={{ borderColor: LIST_BORDER, color: LIST_MUTED, backgroundColor: 'white' }}
                            onMouseEnter={e => {
                              e.currentTarget.style.backgroundColor = '#fafafa'
                              e.currentTarget.style.borderColor = LIST_BORDER
                            }}
                            onMouseLeave={e => {
                              e.currentTarget.style.backgroundColor = 'white'
                              e.currentTarget.style.borderColor = LIST_BORDER
                            }}
                          >
                            <svg className="mr-1 h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                              <path strokeLinecap="round" strokeLinejoin="round" d="M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" />
                            </svg>
                            成长路线
                          </Link>
                        </div>
                      </div>
                    </div>
                  </motion.div>
                )
              })}




              <button
                type="button"
                onClick={handleConfirmCreate}
                disabled={creating}
                className="flex min-h-[280px] flex-col items-center justify-center gap-2.5 rounded-2xl border border-dashed bg-transparent px-5 text-center transition-colors disabled:opacity-50"
                style={{ borderColor: LIST_BORDER }}
                onMouseEnter={event => {
                  if (creating) return
                  event.currentTarget.style.borderColor = LIST_BLUE
                  event.currentTarget.style.backgroundColor = LIST_BLUE_BG
                }}
                onMouseLeave={event => {
                  event.currentTarget.style.borderColor = LIST_BORDER
                  event.currentTarget.style.backgroundColor = 'transparent'
                }}
              >
                <span className="flex h-10 w-10 items-center justify-center rounded-full" style={{ backgroundColor: '#fafafa', color: LIST_FAINT }}>
                  <PlusIcon className="h-5 w-5" />
                </span>
                <span className="text-[13.5px] font-medium" style={{ color: LIST_MUTED }}>{creating ? t('creating') : t('create')}</span>
                <span className="text-xs leading-5" style={{ color: LIST_FAINT }}>{t('createCardHint')}</span>
              </button>
            </div>
          </div>
        )}
      </main>
      </div>
    </div>
  )
}
