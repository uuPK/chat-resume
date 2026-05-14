'use client'
// 用于提供 app/[locale]/resumes/page.tsx 模块。

import { motion } from 'framer-motion'
import { useEffect, useState, useRef } from 'react'
import { useAuth } from '@/lib/auth'
import { useRouter } from '@/i18n/navigation'
import { resumeApi, type ResumeContent } from '@/lib/api'
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
      router.push(`/resume/${resumeId}/edit`)
    } catch (error: any) {
      toast.error(error.response?.data?.detail || error.message || t('uploadFailed'), { id: 'upload' })
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
      <MainNavigation />

      {/* Header */}
      <div className="py-10 px-6" style={{ borderBottom: '1px solid rgba(91,97,110,0.12)' }}>
        <div className="max-w-7xl mx-auto">
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
            className="flex flex-col sm:flex-row sm:items-end justify-between gap-6"
          >
            <div>
              <h1
                className="text-5xl font-semibold"
                style={{ lineHeight: '1.00', color: '#0a0b0d' }}
              >
                {t('title')}
              </h1>
            </div>
            <div className="flex items-center gap-3">
              <input
                ref={fileInputRef}
                type="file"
                accept=".pdf,.doc,.docx,.txt"
                onChange={handleFileUpload}
                className="hidden"
              />
              <button
                onClick={() => fileInputRef.current?.click()}
                disabled={uploadLoading}
                className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold transition-colors disabled:opacity-50"
                style={{
                  borderRadius: '56px',
                  backgroundColor: '#ffffff',
                  color: '#0a0b0d',
                  border: '1px solid rgba(91,97,110,0.3)',
                }}
                onMouseEnter={e => { if (!uploadLoading) { e.currentTarget.style.backgroundColor = '#eef0f3' } }}
                onMouseLeave={e => { e.currentTarget.style.backgroundColor = '#ffffff' }}
              >
                {uploadLoading ? (
                  <>
                    <div className="w-4 h-4 rounded-full border-2 border-transparent animate-spin" style={{ borderTopColor: 'currentColor' }} />
                    <span>{t('uploading')}</span>
                  </>
                ) : (
                  <span>{t('upload')}</span>
                )}
              </button>
              <button
                onClick={handleConfirmCreate}
                disabled={creating}
                className="inline-flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white transition-colors disabled:opacity-50"
                style={{
                  borderRadius: '56px',
                  backgroundColor: '#0052ff',
                  border: '1px solid #0052ff',
                }}
                onMouseEnter={e => { if (!creating) { e.currentTarget.style.backgroundColor = '#578bfa'; e.currentTarget.style.borderColor = '#578bfa' } }}
                onMouseLeave={e => { e.currentTarget.style.backgroundColor = '#0052ff'; e.currentTarget.style.borderColor = '#0052ff' }}
              >
                {creating ? (
                  <>
                    <div className="w-4 h-4 rounded-full border-2 border-transparent animate-spin" style={{ borderTopColor: '#fff' }} />
                    <span>{t('creating')}</span>
                  </>
                ) : (
                  <span>{t('create')}</span>
                )}
              </button>
            </div>
          </motion.div>
        </div>
      </div>

      {/* Content section — white */}
      <main className="max-w-7xl mx-auto px-6 py-10">
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
            className="text-center py-16"
          >
            <div
              className="w-16 h-16 rounded-2xl flex items-center justify-center mx-auto mb-5"
              style={{ backgroundColor: '#eef0f3' }}
            >
              <DocumentTextIcon className="w-8 h-8" style={{ color: '#0052ff' }} />
            </div>
            <h3 className="text-xl font-semibold mb-2" style={{ color: '#0a0b0d' }}>{t('emptyTitle')}</h3>
            <p className="text-base mb-6" style={{ color: '#5b616e' }}>
              {t('emptyDescription')}
            </p>
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploadLoading}
              className="btn-primary inline-flex items-center gap-2 px-7 py-3 text-base"
            >
              <CloudArrowUpIcon className="w-4 h-4" />
              <span>{t('upload')}</span>
            </button>
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
