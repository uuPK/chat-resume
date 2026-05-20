'use client'
// 用于提供 app/[locale]/resumes/page.tsx 模块。

import { motion } from 'framer-motion'
import { useEffect, useState, useRef } from 'react'
import { useAuth } from '@/lib/auth'
import { useRouter } from '@/i18n/navigation'
import { resumeApi, type ResumeContent } from '@/lib/api'
import { formatApiErrorMessage } from '@/lib/apiErrors'
import toast from 'react-hot-toast'
import { Link } from '@/i18n/navigation'
import MainNavigation from '@/components/layout/MainNavigation'
import PaginatedResumePreview from '@/components/preview/PaginatedResumePreview'
import { useTranslations } from 'next-intl'
import {
  ArrowRightIcon,
  ArrowUpTrayIcon,
  ChatBubbleLeftRightIcon,
  ChevronDownIcon,
  DocumentTextIcon,
  ClockIcon,
  EllipsisVerticalIcon,
  LockClosedIcon,
  MagnifyingGlassIcon,
  PlusIcon,
  StarIcon,
  ClipboardDocumentListIcon,
} from '@heroicons/react/24/outline'

interface Resume {
  id: number
  title: string
  original_filename?: string
  owner_id?: number
  created_at: string
  updated_at?: string
  target_company?: string
  target_title?: string
  preview_content?: Partial<ResumeContent>
}

const UPLOAD_JOB_POLL_INTERVAL_MS = 1500
const UPLOAD_JOB_TIMEOUT_MS = 120000
const FREE_RESUME_LIMIT = 3

// 用于等待当前数据。
function sleep(ms: number) {
  return new Promise(resolve => window.setTimeout(resolve, ms))
}

// 简历预览加载器，展示简历内容缩略图
function ResumePreviewLoader({ content }: { content?: Partial<ResumeContent> }) {
  const t = useTranslations('resume.center')

  return (
    <div className="pointer-events-none select-none w-full h-full">
      {content ? (
        <PaginatedResumePreview content={content as any} />
      ) : (
        <div className="flex items-center justify-center h-full">
          <div className="animate-pulse flex flex-col items-center space-y-2 w-full px-6">
            <div className="h-4 rounded-lg w-1/2" style={{ backgroundColor: '#eef0f3' }} />
            <div className="h-3 rounded-lg w-3/4" style={{ backgroundColor: '#eef0f3' }} />
            <div className="h-3 rounded-lg w-2/3" style={{ backgroundColor: '#eef0f3' }} />
            <div className="h-3 rounded-lg w-3/4 mt-4" style={{ backgroundColor: '#eef0f3' }} />
            <div className="h-3 rounded-lg w-full" style={{ backgroundColor: '#eef0f3' }} />
            <p className="pt-4 text-xs" style={{ color: '#9ca3af' }}>{t('previewLoading')}</p>
          </div>
        </div>
      )}
    </div>
  )
}

// 用于生成简历列表卡片的状态标签。
function getResumeCardStatus(resume: Resume, index: number, t: ReturnType<typeof useTranslations>) {
  if (resume.target_company || resume.target_title) {
    return {
      label: index === 0 ? t('cardStatusActive') : t('cardStatusOptimized'),
      backgroundColor: index === 0 ? '#ecfdf5' : '#eef4ff',
      color: index === 0 ? '#059669' : '#0052ff',
    }
  }

  return {
    label: t('cardStatusDraft'),
    backgroundColor: '#ffffff',
    color: '#8b93a3',
  }
}

// 用于读取简历卡片副标题。
function getResumeSubtitle(resume: Resume, t: ReturnType<typeof useTranslations>) {
  const targetParts = [resume.target_company, resume.target_title].filter(Boolean)
  if (targetParts.length > 0) return targetParts.join(' · ')
  return resume.target_title || resume.original_filename || t('cardUntargeted')
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
  const [openResumeActionsId, setOpenResumeActionsId] = useState<number | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const t = useTranslations('resume.center')
  const common = useTranslations('common')
  const filteredResumes = resumes.filter(resume => resumeMatchesQuery(resume, resumeSearchQuery))
  const visibleResumes = filteredResumes.slice(0, FREE_RESUME_LIMIT)
  const hiddenResumeCount = Math.max(filteredResumes.length - FREE_RESUME_LIMIT, 0)

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
    } catch (error: any) {
      toast.error(error.response?.data?.detail || t('deleteFailed'), { id: 'delete' })
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
    } catch (error: any) {
      toast.error(error.response?.data?.detail || t('createFailed'), { id: 'create' })
    } finally {
      setCreating(false)
    }
  }

  // 用于打开简历editor。
  const openResumeEditor = (resumeId: number) => {
    router.push(`/resume/${resumeId}/edit`)
  }

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
      <input
        ref={fileInputRef}
        type="file"
        accept=".pdf,.doc,.docx,.txt"
        onChange={handleFileUpload}
        className="hidden"
      />
      <MainNavigation />
      <div className="flex min-h-[calc(100vh-56px)]">
        <aside
          className="hidden w-[238px] shrink-0 border-r bg-white px-3 py-6 md:flex md:flex-col"
          style={{ borderColor: 'rgba(91,97,110,0.14)' }}
        >
          <div className="space-y-6">
            <div>
              <p className="mb-2 px-2 text-xs font-medium" style={{ color: '#8b93a3' }}>{t('sidebarResume')}</p>
              <div className="space-y-1">
                <div className="flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm font-semibold" style={{ backgroundColor: '#eef4ff', color: '#0052ff' }}>
                  <DocumentTextIcon className="h-4 w-4" />
                  <span>{t('sidebarMyResumes')}</span>
                </div>
                <div className="flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm font-medium" style={{ color: '#8b93a3' }}>
                  <ClockIcon className="h-4 w-4" />
                  <span>{t('sidebarVersions')}</span>
                </div>
                <div className="flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm font-medium" style={{ color: '#8b93a3' }}>
                  <MagnifyingGlassIcon className="h-4 w-4" />
                  <span>{t('sidebarJdAnalysis')}</span>
                </div>
              </div>
            </div>

            <div>
              <p className="mb-2 px-2 text-xs font-medium" style={{ color: '#8b93a3' }}>{t('sidebarInterview')}</p>
              <div className="space-y-1">
                <Link href="/interviews" className="flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm font-medium" style={{ color: '#8b93a3' }}>
                  <ChatBubbleLeftRightIcon className="h-4 w-4" />
                  <span>{t('sidebarMockInterview')}</span>
                </Link>
                <div className="flex items-center gap-2 rounded-lg px-2.5 py-2 text-sm font-medium" style={{ color: '#8b93a3' }}>
                  <StarIcon className="h-4 w-4" />
                  <span>{t('sidebarInterviewReview')}</span>
                </div>
              </div>
            </div>
          </div>

          <div className="mt-auto rounded-xl border bg-white p-4" style={{ borderColor: 'rgba(91,97,110,0.18)' }}>
            <p className="text-base font-semibold" style={{ color: '#0a0b0d' }}>{t('upgradeTitle')}</p>
            <p className="mt-2 text-sm leading-5" style={{ color: '#5b616e' }}>{t('upgradeDescription')}</p>
            <Link
              href="/pricing"
              className="mt-4 inline-flex h-9 w-full items-center justify-center rounded-md text-sm font-semibold text-white"
              style={{ backgroundColor: '#0052ff' }}
            >
              {t('upgradeAction')}
            </Link>
          </div>
        </aside>

      <main className="flex-1 px-6 pb-10 pt-14" style={{ backgroundColor: '#f7f8fa' }}>
        {resumesLoading ? (
          <div className="flex justify-center items-center py-20">
            <div
              className="w-8 h-8 rounded-full border-2 border-transparent animate-spin"
              style={{ borderTopColor: '#0052ff', borderRightColor: '#0052ff' }}
            />
            <span className="ml-3 text-base" style={{ color: '#5b616e' }}>{t('loading')}</span>
          </div>
        ) : resumes.length === 0 ? (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="mx-auto max-w-[760px] py-8"
          >
            <div className="mb-9">
              <h1 className="text-2xl font-semibold tracking-tight" style={{ color: '#0a0b0d' }}>
                {t('emptyCreateHeading')}
              </h1>
              <p className="mt-3 text-base" style={{ color: '#5b616e' }}>
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
                onMouseEnter={e => { if (!uploadLoading) { e.currentTarget.style.borderColor = '#0052ff'; e.currentTarget.style.boxShadow = '0 16px 42px rgba(15,23,42,0.08)' } }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(91,97,110,0.2)'; e.currentTarget.style.boxShadow = 'none' }}
              >
                <span className="flex h-11 w-11 items-center justify-center rounded-lg" style={{ backgroundColor: '#f7f8fa', color: '#0052ff' }}>
                  <ArrowUpTrayIcon className="h-5 w-5" />
                </span>
                <span className="mt-6 block text-lg font-semibold" style={{ color: '#0a0b0d' }}>{t('emptyUploadTitle')}</span>
                <span className="mt-3 block text-sm leading-6" style={{ color: '#5b616e' }}>{t('emptyUploadDescription')}</span>
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
                onMouseEnter={e => { if (!creating) { e.currentTarget.style.borderColor = '#0052ff'; e.currentTarget.style.boxShadow = '0 16px 42px rgba(15,23,42,0.08)' } }}
                onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(91,97,110,0.2)'; e.currentTarget.style.boxShadow = 'none' }}
              >
                <span className="flex h-11 w-11 items-center justify-center rounded-lg" style={{ backgroundColor: '#f7f8fa', color: '#5b616e' }}>
                  <ClipboardDocumentListIcon className="h-5 w-5" />
                </span>
                <span className="mt-6 block text-lg font-semibold" style={{ color: '#0a0b0d' }}>{t('templateCreateTitle')}</span>
                <span className="mt-3 block text-sm leading-6" style={{ color: '#5b616e' }}>{t('templateCreateDescription')}</span>
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
          <div className="space-y-6">
            <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
              <div>
                <h1 className="text-2xl font-semibold tracking-tight" style={{ color: '#0a0b0d' }}>
                  {t('listTitle')}
                </h1>
                <p className="mt-2 text-sm" style={{ color: '#8b93a3' }}>
                  {t('listSummary', {
                    total: resumes.length,
                    limit: FREE_RESUME_LIMIT,
                    used: resumes.length,
                  })}
                </p>
              </div>
              <button
                type="button"
                onClick={handleConfirmCreate}
                disabled={creating}
                className="inline-flex h-10 items-center justify-center gap-2 rounded-lg px-5 text-sm font-semibold text-white transition-colors disabled:opacity-50"
                style={{ backgroundColor: '#0052ff' }}
              >
                <PlusIcon className="h-4 w-4" />
                <span>{creating ? t('creating') : t('create')}</span>
              </button>
            </div>

            <div className="flex flex-col gap-3 lg:flex-row lg:items-center">
              <label
                className="relative block w-full lg:max-w-[320px]"
                aria-label={t('searchPlaceholder')}
              >
                <MagnifyingGlassIcon className="pointer-events-none absolute left-3 top-1/2 h-5 w-5 -translate-y-1/2" style={{ color: '#b0b6c0' }} />
                <input
                  type="search"
                  value={resumeSearchQuery}
                  onChange={event => setResumeSearchQuery(event.target.value)}
                  placeholder={t('searchPlaceholder')}
                  className="h-10 w-full rounded-lg border bg-white pl-10 pr-3 text-sm outline-none"
                  style={{ borderColor: 'rgba(91,97,110,0.22)', color: '#0a0b0d' }}
                />
              </label>
              <button
                type="button"
                className="inline-flex h-10 items-center justify-between gap-3 rounded-lg border bg-white px-4 text-sm font-medium"
                style={{ borderColor: 'rgba(91,97,110,0.22)', color: '#5b616e' }}
              >
                <span>{t('filterAllStatus')}</span>
                <ChevronDownIcon className="h-4 w-4" />
              </button>
              <button
                type="button"
                className="inline-flex h-10 items-center justify-between gap-3 rounded-lg border bg-white px-4 text-sm font-medium"
                style={{ borderColor: 'rgba(91,97,110,0.22)', color: '#5b616e' }}
              >
                <span>{t('sortRecent')}</span>
                <ChevronDownIcon className="h-4 w-4" />
              </button>
            </div>

            <div className="grid grid-cols-1 gap-5 xl:grid-cols-5">
              {visibleResumes.map((resume, index) => {
                const status = getResumeCardStatus(resume, index, t)
                return (
                  <motion.div
                    key={resume.id}
                    initial={{ opacity: 0, y: 16 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.5, delay: index * 0.08 }}
                    className="group relative overflow-hidden rounded-2xl border bg-white"
                    style={{ borderColor: 'rgba(91,97,110,0.2)' }}
                  >
                    <div
                      role="link"
                      tabIndex={0}
                      aria-label={resume.title}
                      onClick={() => openResumeEditor(resume.id)}
                      onKeyDown={(event) => {
                        if (event.key === 'Enter' || event.key === ' ') {
                          event.preventDefault()
                          openResumeEditor(resume.id)
                        }
                      }}
                      className="relative block cursor-pointer"
                    >
                      <div className="h-[208px] overflow-hidden" style={{ backgroundColor: '#f4f6fa', borderBottom: '1px solid rgba(91,97,110,0.12)' }}>
                        {resume.preview_content ? (
                          <ResumePreviewLoader content={resume.preview_content} />
                        ) : (
                          <div className="px-5 py-5">
                            <div className="mb-4 text-center text-sm font-semibold" style={{ color: '#0a0b0d' }}>
                              {resume.title}
                            </div>
                            <div className="space-y-3">
                              <div className="h-2.5 rounded-full" style={{ backgroundColor: '#dfe3ea' }} />
                              <div className="h-2.5 w-4/5 rounded-full" style={{ backgroundColor: '#dfe3ea' }} />
                              <div className="h-2.5 w-full rounded-full" style={{ backgroundColor: '#e6e9ef' }} />
                              <div className="h-2.5 w-3/4 rounded-full" style={{ backgroundColor: '#e6e9ef' }} />
                            </div>
                            <div className="mt-7 flex gap-1.5">
                              <span className="h-4 w-10 rounded" style={{ backgroundColor: '#dfe3ea' }} />
                              <span className="h-4 w-14 rounded" style={{ backgroundColor: '#dfe3ea' }} />
                              <span className="h-4 w-8 rounded" style={{ backgroundColor: '#dfe3ea' }} />
                            </div>
                          </div>
                        )}
                      </div>
                      <span
                        className="absolute right-3 top-3 rounded-md px-2 py-1 text-xs font-semibold"
                        style={{ backgroundColor: status.backgroundColor, color: status.color, border: '1px solid rgba(91,97,110,0.12)' }}
                      >
                        {status.label}
                      </span>
                    </div>

                    <div className="p-4">
                      <div className="flex items-start justify-between gap-3">
                        <div className="min-w-0">
                          <h2 className="truncate text-base font-semibold" style={{ color: '#0a0b0d' }}>{resume.title}</h2>
                          <p className="mt-1 truncate text-sm" style={{ color: '#5b616e' }}>{getResumeSubtitle(resume, t)}</p>
                        </div>
                        <button
                          type="button"
                          onClick={() => setOpenResumeActionsId(current => current === resume.id ? null : resume.id)}
                          className="flex h-7 w-7 items-center justify-center rounded-full transition-colors"
                          style={{ color: '#9ca3af' }}
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
                              onClick={() => {
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
                      <div className="mt-4 flex flex-wrap items-center gap-3 text-xs" style={{ color: '#8b93a3' }}>
                        <span className="inline-flex items-center gap-1">
                          <ClockIcon className="h-3.5 w-3.5" />
                          {resume.updated_at ? t('modifiedAt', { value: new Date(resume.updated_at).toLocaleDateString() }) : t('recentlyModified')}
                        </span>
                        <span>{index === 0 ? t('submittedCount', { count: 3 }) : t('notSubmitted')}</span>
                      </div>
                      <div className="mt-4 grid grid-cols-3 gap-2 border-t pt-3" style={{ borderColor: 'rgba(91,97,110,0.12)' }}>
                        <Link
                          href={`/resume/${resume.id}/edit`}
                          className="inline-flex h-9 items-center justify-center rounded-lg border text-sm font-semibold"
                          style={{ borderColor: 'rgba(91,97,110,0.22)', color: '#5b616e' }}
                        >
                          {t('editAction')}
                        </Link>
                        <button
                          type="button"
                          className="h-9 rounded-lg border text-sm font-semibold"
                          style={{ borderColor: 'rgba(91,97,110,0.22)', color: '#5b616e' }}
                        >
                          {t('exportAction')}
                        </button>
                        <Link
                          href={`/resume/${resume.id}/edit`}
                          className="inline-flex h-9 items-center justify-center rounded-lg text-sm font-semibold text-white"
                          style={{ backgroundColor: '#0052ff' }}
                        >
                          {t('aiOptimizeAction')}
                        </Link>
                      </div>
                    </div>
                  </motion.div>
                )
              })}

              {hiddenResumeCount > 0 && (
                <div className="flex min-h-[368px] flex-col items-center justify-center rounded-2xl border bg-white px-6 text-center opacity-60" style={{ borderColor: 'rgba(91,97,110,0.18)' }}>
                  <LockClosedIcon className="h-7 w-7" style={{ color: '#8b93a3' }} />
                  <p className="mt-4 text-base font-semibold" style={{ color: '#8b93a3' }}>{t('freeLimitReached')}</p>
                  <p className="mt-2 text-sm" style={{ color: '#a0a7b3' }}>{t('upgradeToSaveMore')}</p>
                  <Link href="/pricing" className="mt-5 inline-flex h-9 items-center justify-center rounded-lg px-5 text-sm font-semibold text-white" style={{ backgroundColor: '#0052ff' }}>
                    {t('upgradeProAction')}
                  </Link>
                </div>
              )}

              <button
                type="button"
                onClick={handleConfirmCreate}
                disabled={creating}
                className="flex min-h-[368px] flex-col items-center justify-center rounded-2xl border border-dashed bg-white px-6 text-center disabled:opacity-50"
                style={{ borderColor: 'rgba(91,97,110,0.28)' }}
              >
                <PlusIcon className="h-7 w-7" style={{ color: '#8b93a3' }} />
                <span className="mt-6 text-base font-semibold" style={{ color: '#5b616e' }}>{creating ? t('creating') : t('create')}</span>
                <span className="mt-3 text-sm" style={{ color: '#8b93a3' }}>{t('createCardHint')}</span>
              </button>
            </div>
          </div>
        )}
      </main>
      </div>
    </div>
  )
}
