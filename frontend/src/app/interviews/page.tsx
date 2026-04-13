'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@/lib/auth'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import Link from 'next/link'
import MainNavigation from '@/components/layout/MainNavigation'
import { resumeApi, type InterviewSession } from '@/lib/api'
import { MicrophoneIcon, ClockIcon, CheckCircleIcon, PlayCircleIcon } from '@heroicons/react/24/outline'

function formatDate(dateString: string) {
  const d = new Date(dateString.includes('Z') || dateString.includes('+') ? dateString : dateString + 'Z')
  return new Intl.DateTimeFormat('zh-CN', {
    year: 'numeric', month: 'long', day: 'numeric',
    hour: '2-digit', minute: '2-digit',
    timeZone: 'Asia/Shanghai', hour12: false,
  }).format(d)
}

function statusLabel(status: string) {
  if (status === 'completed') return { text: '已完成', color: 'text-green-600 bg-green-50' }
  if (status === 'waiting_user_answer') return { text: '进行中', color: 'text-blue-600 bg-blue-50' }
  return { text: '未开始', color: 'text-gray-500 bg-gray-100' }
}

export default function InterviewsPage() {
  const { isAuthenticated, isLoading } = useAuth()
  const router = useRouter()
  const [mounted, setMounted] = useState(false)
  const [sessions, setSessions] = useState<InterviewSession[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => { setMounted(true) }, [])

  useEffect(() => {
    if (mounted && !isLoading && !isAuthenticated) router.push('/login')
  }, [mounted, isLoading, isAuthenticated, router])

  useEffect(() => {
    if (!mounted || !isAuthenticated) return
    resumeApi.listInterviewSessions()
      .then(setSessions)
      .catch(() => {})
      .finally(() => setLoading(false))
  }, [mounted, isAuthenticated])

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
      <main className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <motion.div initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.6 }}>
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900 mb-1">面试中心</h1>
            <p className="text-gray-500">查看所有面试记录和报告</p>
          </div>

          {loading ? (
            <div className="flex justify-center items-center py-16">
              <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary-600" />
              <span className="ml-3 text-gray-500">加载中...</span>
            </div>
          ) : sessions.length === 0 ? (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center py-20">
              <MicrophoneIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 mb-2">还没有面试记录</h3>
              <p className="text-gray-500 mb-6">去简历中心选一份简历，开始模拟面试吧</p>
              <Link href="/resumes" className="btn-primary inline-flex items-center gap-2">
                前往简历中心
              </Link>
            </motion.div>
          ) : (
            <div className="space-y-4">
              {sessions.map((session, index) => {
                const { text, color } = statusLabel(session.status)
                const turns = session.turns || []
                const answered = turns.filter(t => t.answer).length
                const started = session.started_at ? formatDate(session.started_at) : null
                return (
                  <motion.div
                    key={session.id}
                    initial={{ opacity: 0, y: 12 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ duration: 0.4, delay: index * 0.05 }}
                    className="bg-white rounded-xl border border-gray-200 shadow-sm hover:shadow-md transition-shadow p-5 flex items-center justify-between gap-4"
                  >
                    <div className="flex items-center gap-4 min-w-0">
                      <div className="w-10 h-10 bg-green-50 rounded-xl flex items-center justify-center flex-shrink-0">
                        {session.status === 'completed'
                          ? <CheckCircleIcon className="w-5 h-5 text-green-600" />
                          : <PlayCircleIcon className="w-5 h-5 text-blue-500" />
                        }
                      </div>
                      <div className="min-w-0">
                        <div className="flex items-center gap-2 mb-0.5 flex-wrap">
                          <span className="font-semibold text-gray-900 truncate">
                            {session.target_title || '未设置岗位'}
                          </span>
                          {session.target_company && (
                            <span className="text-gray-400 text-sm truncate">@ {session.target_company}</span>
                          )}
                          <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${color}`}>{text}</span>
                        </div>
                        <div className="flex items-center gap-3 text-xs text-gray-400 flex-wrap">
                          {started && (
                            <span className="flex items-center gap-1">
                              <ClockIcon className="w-3.5 h-3.5" />{started}
                            </span>
                          )}
                          <span>{answered} 题已回答</span>
                          {session.overall_score != null && (
                            <span className="text-green-600 font-medium">综合评分 {session.overall_score}/10</span>
                          )}
                        </div>
                      </div>
                    </div>
                    <Link
                      href={`/resume/${session.resume_id}/interview?session=${session.id}`}
                      className="flex-shrink-0 px-4 py-2 bg-green-600 hover:bg-green-700 text-white text-sm font-medium rounded-lg transition-colors"
                    >
                      {session.status === 'completed' ? '查看报告' : '继续面试'}
                    </Link>
                  </motion.div>
                )
              })}
            </div>
          )}
        </motion.div>
      </main>
    </div>
  )
}
