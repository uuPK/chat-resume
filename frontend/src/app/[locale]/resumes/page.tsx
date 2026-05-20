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
  TrashIcon,
  CloudArrowUpIcon,
  ChatBubbleLeftRightIcon,
  DocumentTextIcon,
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

// 简历中心主页，展示用户所有简历
export default function ResumesPage() {
  const { isAuthenticated, isLoading } = useAuth()
  const router = useRouter()
  const [mounted, setMounted] = useState(false)
  const [uploadLoading, setUploadLoading] = useState(false)
  const [resumes, setResumes] = useState<Resume[]>([])
  const [resumesLoading, setResumesLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const t = useTranslations('resume.center')
  const common = useTranslations('common')

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
      <div className="border-b px-6 py-3" style={{ borderColor: 'rgba(91,97,110,0.12)' }}>
        <div className="mx-auto flex max-w-7xl items-center justify-end gap-3">
          <button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploadLoading}
            className="inline-flex flex-1 items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold transition-colors disabled:opacity-50"
            style={{
              borderRadius: '56px',
              backgroundColor: '#ffffff',
              color: '#0a0b0d',
              border: '1px solid rgba(91,97,110,0.3)',
            }}
          >
            {uploadLoading ? t('uploading') : t('upload')}
          </button>
          <button
            onClick={handleConfirmCreate}
            disabled={creating}
            className="inline-flex flex-1 items-center justify-center gap-2 px-4 py-2.5 text-sm font-semibold text-white transition-colors disabled:opacity-50"
            style={{
              borderRadius: '56px',
              backgroundColor: '#0052ff',
              border: '1px solid #0052ff',
            }}
          >
            {creating ? t('creating') : t('create')}
          </button>
        </div>
      </div>

      {/* Content section — white */}
      <main className="max-w-7xl mx-auto px-6 pb-10 pt-14">
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
            className="mx-auto max-w-4xl py-10"
          >
            <div
              className="overflow-hidden rounded-[28px] border"
              style={{
                background: 'linear-gradient(135deg, #ffffff 0%, #f7f8fb 100%)',
                borderColor: 'rgba(91,97,110,0.16)',
                boxShadow: '0 24px 80px rgba(15,23,42,0.08)',
              }}
            >
              <div className="px-6 py-8 sm:px-10 sm:py-10">
                <div className="mx-auto mb-6 flex h-14 w-14 items-center justify-center rounded-2xl" style={{ backgroundColor: 'rgba(0,82,255,0.08)' }}>
                  <DocumentTextIcon className="h-7 w-7" style={{ color: '#0052ff' }} />
                </div>
                <div className="mx-auto max-w-2xl text-center">
                  <h3 className="text-2xl font-semibold sm:text-3xl" style={{ color: '#0a0b0d', letterSpacing: '-0.03em' }}>{t('emptyTitle')}</h3>
                </div>

                <div className="mt-8 grid gap-4 md:grid-cols-2">
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploadLoading}
                    className="group rounded-3xl border p-5 text-left transition-all disabled:opacity-50"
                    style={{ backgroundColor: '#ffffff', borderColor: 'rgba(0,82,255,0.22)' }}
                    onMouseEnter={e => { if (!uploadLoading) { e.currentTarget.style.borderColor = '#0052ff'; e.currentTarget.style.boxShadow = '0 16px 40px rgba(0,82,255,0.12)' } }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(0,82,255,0.22)'; e.currentTarget.style.boxShadow = 'none' }}
                  >
                    <span className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-2xl" style={{ backgroundColor: '#0052ff', color: '#ffffff' }}>
                      <CloudArrowUpIcon className="h-5 w-5" />
                    </span>
                    <span className="block text-lg font-semibold" style={{ color: '#0a0b0d' }}>{t('emptyUploadTitle')}</span>
                    <span className="mt-2 block text-sm leading-6" style={{ color: '#5b616e' }}>{t('emptyUploadDescription')}</span>
                    <span className="mt-5 inline-flex rounded-full px-4 py-2 text-sm font-semibold text-white" style={{ backgroundColor: '#0052ff' }}>
                      {uploadLoading ? t('uploading') : t('emptyUploadAction')}
                    </span>
                  </button>

                  <button
                    type="button"
                    onClick={handleConfirmCreate}
                    disabled={creating}
                    className="rounded-3xl border p-5 text-left transition-all disabled:opacity-50"
                    style={{ backgroundColor: '#ffffff', borderColor: 'rgba(91,97,110,0.2)' }}
                    onMouseEnter={e => { if (!creating) { e.currentTarget.style.borderColor = '#0a0b0d'; e.currentTarget.style.boxShadow = '0 16px 40px rgba(15,23,42,0.08)' } }}
                    onMouseLeave={e => { e.currentTarget.style.borderColor = 'rgba(91,97,110,0.2)'; e.currentTarget.style.boxShadow = 'none' }}
                  >
                    <span className="mb-4 inline-flex h-10 w-10 items-center justify-center rounded-2xl" style={{ backgroundColor: '#eef0f3', color: '#0a0b0d' }}>
                      <DocumentTextIcon className="h-5 w-5" />
                    </span>
                    <span className="block text-lg font-semibold" style={{ color: '#0a0b0d' }}>{t('emptyCreateTitle')}</span>
                    <span className="mt-2 block text-sm leading-6" style={{ color: '#5b616e' }}>{t('emptyCreateDescription')}</span>
                    <span className="mt-5 inline-flex rounded-full border px-4 py-2 text-sm font-semibold" style={{ borderColor: 'rgba(91,97,110,0.24)', color: '#0a0b0d' }}>
                      {creating ? t('creating') : t('emptyCreateAction')}
                    </span>
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
            {resumes.map((resume, index) => (
              <motion.div
                key={resume.id}
                initial={{ opacity: 0, y: 16 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.5, delay: index * 0.08 }}
                className="group overflow-hidden flex flex-col"
                style={{
                  border: '1px solid rgba(91,97,110,0.2)',
                  borderRadius: '16px',
                  backgroundColor: '#ffffff',
                }}
              >
                {/* Preview area */}
                <div className="relative">
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
                    className="block cursor-pointer"
                  >
                    <div
                      className="overflow-hidden"
                      style={{ height: '220px', backgroundColor: '#eef0f3', borderBottom: '1px solid rgba(91,97,110,0.1)' }}
                    >
                      <ResumePreviewLoader content={resume.preview_content} />
                    </div>
                  </div>
                  <button
                    onClick={() => handleDeleteResume(resume.id, resume.title)}
                    className="absolute top-2.5 right-2.5 w-8 h-8 flex items-center justify-center rounded-full bg-white opacity-0 group-hover:opacity-100 transition-opacity"
                    style={{ boxShadow: '0 1px 6px rgba(0,0,0,0.12)', color: '#9ca3af' }}
                    title={t('deleteTitle')}
                    onMouseEnter={e => (e.currentTarget.style.color = '#dc2626')}
                    onMouseLeave={e => (e.currentTarget.style.color = '#9ca3af')}
                  >
                    <TrashIcon className="w-4 h-4" />
                  </button>
                </div>

                {/* Footer */}
                <div className="px-4 py-3 flex items-center justify-between gap-2" style={{ minHeight: '60px' }}>
                  <div className="flex-1 min-w-0">
                    {(resume.target_company || resume.target_title) && (
                      <div className="truncate text-sm font-medium text-[#0a0b0d]">
                        {[resume.target_company, resume.target_title].filter(Boolean).join(' · ')}
                      </div>
                    )}
                  </div>
                  <Link
                    href={`/resume/${resume.id}/edit`}
                    className="inline-flex items-center gap-1.5 px-4 py-2 text-xs font-semibold text-white transition-colors flex-shrink-0"
                    style={{ borderRadius: '56px', backgroundColor: '#0052ff', border: '1px solid #0052ff' }}
                    onMouseEnter={e => { (e.currentTarget as HTMLAnchorElement).style.backgroundColor = '#578bfa'; (e.currentTarget as HTMLAnchorElement).style.borderColor = '#578bfa' }}
                    onMouseLeave={e => { (e.currentTarget as HTMLAnchorElement).style.backgroundColor = '#0052ff'; (e.currentTarget as HTMLAnchorElement).style.borderColor = '#0052ff' }}
                  >
                    <ChatBubbleLeftRightIcon className="w-3.5 h-3.5" />
                    <span>{t('chat')}</span>
                  </Link>
                </div>
              </motion.div>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
