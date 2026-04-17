'use client'

import { motion } from 'framer-motion'
import { useEffect, useState, useRef } from 'react'
import { useAuth } from '@/lib/auth'
import { useRouter } from 'next/navigation'
import { resumeApi, type ResumeContent } from '@/lib/api'
import toast from 'react-hot-toast'
import Link from 'next/link'
import MainNavigation from '@/components/layout/MainNavigation'
import PaginatedResumePreview from '@/components/preview/PaginatedResumePreview'
import {
  DocumentIcon,
  PlusIcon,
  TrashIcon,
  CloudArrowUpIcon,
  ChatBubbleLeftRightIcon,
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

function ResumePreviewLoader({
  content,
}: {
  content?: Partial<ResumeContent>
}) {
  return (
    <div className="pointer-events-none select-none w-full h-full">
      {content ? (
        <PaginatedResumePreview content={content as any} />
      ) : (
        <div className="flex items-center justify-center h-full">
          <div className="animate-pulse flex flex-col items-center space-y-2 w-full px-6">
            <div className="h-4 bg-gray-200 rounded w-1/2" />
            <div className="h-3 bg-gray-200 rounded w-3/4" />
            <div className="h-3 bg-gray-200 rounded w-2/3" />
            <div className="h-3 bg-gray-200 rounded w-3/4 mt-4" />
            <div className="h-3 bg-gray-200 rounded w-full" />
            <div className="h-3 bg-gray-200 rounded w-full" />
            <p className="pt-4 text-xs text-gray-400">正在准备预览...</p>
          </div>
        </div>
      )}
    </div>
  )
}

export default function ResumesPage() {
  const { isAuthenticated, isLoading } = useAuth()
  const router = useRouter()
  const [mounted, setMounted] = useState(false)
  const [uploadLoading, setUploadLoading] = useState(false)
  const [resumes, setResumes] = useState<Resume[]>([])
  const [resumesLoading, setResumesLoading] = useState(true)
  const [creating, setCreating] = useState(false)
  const fileInputRef = useRef<HTMLInputElement>(null)

  useEffect(() => { setMounted(true) }, [])

  useEffect(() => {
    if (mounted && !isLoading && !isAuthenticated) {
      router.push('/login')
    }
  }, [mounted, isLoading, isAuthenticated, router])

  const fetchResumes = async () => {
    if (!isAuthenticated) return
    try {
      setResumesLoading(true)
      const data = await resumeApi.getResumes()
      setResumes(data)
    } catch {
      toast.error('获取简历列表失败')
    } finally {
      setResumesLoading(false)
    }
  }

  useEffect(() => {
    if (mounted && isAuthenticated) fetchResumes()
  }, [mounted, isAuthenticated])

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return
    const allowedTypes = ['application/pdf', 'application/msword', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'text/plain']
    if (!allowedTypes.includes(file.type)) {
      toast.error('请上传 PDF、Word 或 TXT 格式的文件')
      return
    }
    if (file.size > 5 * 1024 * 1024) {
      toast.error('文件大小不能超过 5MB')
      return
    }
    setUploadLoading(true)
    try {
      toast.loading('正在上传和解析简历...', { id: 'upload' })
      const result = await resumeApi.uploadResume(file)
      const parsingQuality = result.content?.parsing_quality || 0
      const parsingMethod = result.content?.parsing_method || 'unknown'
      if (parsingMethod === 'fallback' || parsingQuality === 0) {
        toast.success('简历上传成功，AI解析失败，已提取基本信息，请检查并补充', { id: 'upload', duration: 4000 })
        router.push(`/resume/${result.id}/edit`)
        return
      } else if (parsingQuality < 0.3) {
        toast.success(`简历上传成功，解析质量较低(${Math.round(parsingQuality * 100)}%)，建议检查并完善信息`, { id: 'upload', duration: 5000 })
      } else {
        toast.success(`简历上传并解析成功！解析质量: ${Math.round(parsingQuality * 100)}%`, { id: 'upload' })
      }
      await fetchResumes()
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '上传失败，请重试', { id: 'upload' })
    } finally {
      setUploadLoading(false)
      if (fileInputRef.current) fileInputRef.current.value = ''
    }
  }

  const handleDeleteResume = async (resumeId: number, title: string) => {
    if (!confirm(`确定要删除简历 "${title}" 吗？此操作无法撤销。`)) return
    try {
      toast.loading('正在删除简历...', { id: 'delete' })
      await resumeApi.deleteResume(resumeId)
      setResumes(prev => prev.filter(r => r.id !== resumeId))
      toast.success('简历已删除', { id: 'delete' })
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '删除失败，请重试', { id: 'delete' })
    }
  }

  const handleConfirmCreate = async () => {
    setCreating(true)
    try {
      toast.loading('正在创建简历...', { id: 'create' })
      const emptyResumeContent = {
        job_application: { target_company: '', target_title: '', jd_text: '', strategy: '' },
        personal_info: { name: '', email: '', phone: '', position: '', github: '' },
        education: [], work_experience: [], skills: [], projects: []
      }
      const newResume = await resumeApi.createResume({ title: '未命名简历', content: emptyResumeContent })
      toast.success('简历创建成功！', { id: 'create' })
      router.push(`/resume/${newResume.id}/edit`)
    } catch (error: any) {
      toast.error(error.response?.data?.detail || '创建失败，请重试', { id: 'create' })
    } finally {
      setCreating(false)
    }
  }

  if (!mounted || isLoading || !isAuthenticated) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="animate-spin rounded-full h-16 w-16 border-b-2 border-primary-600" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <MainNavigation />
      <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
          <div className="flex justify-between items-center mb-8">
            <div>
              <h1 className="text-3xl font-bold text-gray-900 mb-1">简历中心</h1>
              <p className="text-gray-500">管理你的简历，使用 AI 进行优化</p>
            </div>
            <div className="flex space-x-3">
              <input ref={fileInputRef} type="file" accept=".pdf,.doc,.docx,.txt" onChange={handleFileUpload} className="hidden" />
              <button onClick={() => fileInputRef.current?.click()} disabled={uploadLoading} className="btn-primary flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed">
                {uploadLoading ? <><div className="animate-spin rounded-full h-5 w-5 border-b-2 border-white" /><span>上传中...</span></> : <><CloudArrowUpIcon className="w-5 h-5" /><span>上传简历</span></>}
              </button>
              <button onClick={handleConfirmCreate} disabled={creating} className="btn-secondary flex items-center space-x-2 disabled:opacity-50 disabled:cursor-not-allowed">
                {creating ? <><div className="animate-spin rounded-full h-5 w-5 border-b-2 border-gray-700" /><span>创建中...</span></> : <><PlusIcon className="w-5 h-5" /><span>新建简历</span></>}
              </button>
            </div>
          </div>

          {resumesLoading ? (
            <div className="flex justify-center items-center py-12">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
              <span className="ml-3 text-gray-600">加载简历列表...</span>
            </div>
          ) : resumes.length === 0 ? (
            <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6, delay: 0.2 }} className="text-center py-12">
              <DocumentIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">还没有简历</h3>
              <p className="text-gray-500 mb-6">上传你的第一份简历，开始使用 AI 优化功能</p>
              <button onClick={() => fileInputRef.current?.click()} disabled={uploadLoading} className="btn-primary flex items-center space-x-2 mx-auto disabled:opacity-50">
                <CloudArrowUpIcon className="w-5 h-5" /><span>上传简历文件</span>
              </button>
            </motion.div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
              {resumes.map((resume, index) => (
                <motion.div
                  key={resume.id}
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.6, delay: index * 0.1 }}
                  className="card overflow-hidden hover:shadow-lg transition-shadow flex flex-col group"
                >
                  <div className="relative">
                    <Link href={`/resume/${resume.id}/edit`} className="block">
                      <div className="overflow-hidden bg-gray-50 border-b border-gray-100" style={{ height: '220px' }}>
                        <ResumePreviewLoader
                          content={resume.preview_content}
                        />
                      </div>
                    </Link>
                    <button onClick={() => handleDeleteResume(resume.id, resume.title)} className="absolute top-2 right-2 p-1.5 bg-white bg-opacity-90 text-gray-400 hover:text-red-500 rounded-full shadow opacity-0 group-hover:opacity-100 transition-opacity" title="删除简历">
                      <TrashIcon className="w-4 h-4" />
                    </button>
                  </div>
                  <div className="px-4 flex items-center justify-between gap-2" style={{ minHeight: '60px' }}>
                    <div className="flex-1 min-w-0">
                      {([resume.target_company, resume.target_title].filter(Boolean).length > 0) && (
                        <h3 className="text-sm font-semibold text-gray-900 truncate">
                          {[resume.target_company, resume.target_title].filter(Boolean).join(' · ')}
                        </h3>
                      )}
                    </div>
                    <Link href={`/resume/${resume.id}/edit`} className="flex items-center gap-1 px-2.5 py-1.5 bg-blue-600 hover:bg-blue-700 text-white rounded-md text-xs font-medium transition-colors flex-shrink-0">
                      <ChatBubbleLeftRightIcon className="w-3 h-3" /><span>Chat</span>
                    </Link>
                  </div>
                </motion.div>
              ))}
            </div>
          )}
        </motion.div>
      </main>
    </div>
  )
}
