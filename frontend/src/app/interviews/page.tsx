'use client'

import { useEffect, useState } from 'react'
import { useAuth } from '@/lib/auth'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import Link from 'next/link'
import MainNavigation from '@/components/layout/MainNavigation'
import { resumeApi, type InterviewSessionSummary } from '@/lib/api'
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
  if (status === 'completed') return { text: '已完成', bg: '#ecfdf5', color: '#059669' }
  if (status === 'waiting_user_answer') return { text: '进行中', bg: '#eef0ff', color: '#0052ff' }
  return { text: '未开始', bg: '#eef0f3', color: '#5b616e' }
}

// 面试中心页，展示所有面试记录
export default function InterviewsPage() {
  const { isAuthenticated, isLoading } = useAuth()
  const router = useRouter()
  const [mounted, setMounted] = useState(false)
  const [sessions, setSessions] = useState<InterviewSessionSummary[]>([])
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
        <div className="max-w-4xl mx-auto">
          <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
            <h1 className="text-5xl font-semibold" style={{ lineHeight: '1.00', color: '#0a0b0d' }}>
              面试中心
            </h1>
          </motion.div>
        </div>
      </div>

      <main className="max-w-4xl mx-auto px-6 py-10">
        <motion.div initial={{ opacity: 0, y: 16 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.5 }}>
          {loading ? (
            <div className="flex justify-center items-center py-20">
              <div
                className="w-8 h-8 rounded-full border-2 border-transparent animate-spin"
                style={{ borderTopColor: '#0052ff', borderRightColor: '#0052ff' }}
              />
              <span className="ml-3 text-base" style={{ color: '#5b616e' }}>加载中...</span>
            </div>
          ) : sessions.length === 0 ? (
            <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="text-center py-24">
              <div
                className="w-20 h-20 rounded-3xl flex items-center justify-center mx-auto mb-6"
                style={{ backgroundColor: '#eef0f3' }}
              >
                <MicrophoneIcon className="w-10 h-10" style={{ color: '#0052ff' }} />
              </div>
              <h3 className="text-2xl font-semibold mb-2" style={{ color: '#0a0b0d' }}>
                还没有面试记录
              </h3>
              <p className="text-lg mb-8" style={{ color: '#5b616e' }}>
                去简历中心选一份简历，开始模拟面试吧
              </p>
              <Link href="/resumes" className="btn-primary btn-lg inline-flex items-center gap-2">
                前往简历中心
              </Link>
            </motion.div>
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
                          {session.overall_score != null && (
                            <span className="font-semibold" style={{ color: '#059669' }}>
                              综合评分 {session.overall_score}/10
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                    <Link
                      href={`/resume/${session.resume_id}/interview?session=${session.id}`}
                      className="flex-shrink-0 inline-flex items-center px-4 py-2 text-sm font-semibold text-white transition-colors"
                      style={{ borderRadius: '56px', backgroundColor: '#0052ff', border: '1px solid #0052ff' }}
                      onMouseEnter={e => { (e.currentTarget as HTMLAnchorElement).style.backgroundColor = '#578bfa'; (e.currentTarget as HTMLAnchorElement).style.borderColor = '#578bfa' }}
                      onMouseLeave={e => { (e.currentTarget as HTMLAnchorElement).style.backgroundColor = '#0052ff'; (e.currentTarget as HTMLAnchorElement).style.borderColor = '#0052ff' }}
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
