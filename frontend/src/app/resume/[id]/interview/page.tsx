'use client'

import { useEffect, useState } from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { ArrowLeftIcon, ChevronLeftIcon, ChevronRightIcon } from '@heroicons/react/24/outline'
import { useAuth } from '@/lib/auth'
import { resumeApi } from '@/lib/api'
import StructuredInterviewPanel from '@/components/interview/StructuredInterviewPanel'
import ResumePreview from '@/components/preview/ResumePreview'
import { useInterviewSession } from '@/hooks/useInterviewSession'

export default function InterviewPage() {
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()
  const resumeId = Number(params?.id as string)
  const requestedSessionId = Number(searchParams?.get('session') || 0)

  const { isAuthenticated, isLoading } = useAuth()
  const [mounted, setMounted] = useState(false)
  const [resume, setResume] = useState<Awaited<ReturnType<typeof resumeApi.getResume>> | null>(null)
  const [resumeLoading, setResumeLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [resumeExpanded, setResumeExpanded] = useState(true)

  useEffect(() => { setMounted(true) }, [])

  useEffect(() => {
    if (mounted && !isLoading && !isAuthenticated) router.push('/login')
  }, [mounted, isLoading, isAuthenticated, router])

  useEffect(() => {
    if (!resumeId || !isAuthenticated) return
    resumeApi.getResume(resumeId)
      .then(setResume)
      .catch((err) => setError(err instanceof Error ? err.message : '加载简历失败'))
      .finally(() => setResumeLoading(false))
  }, [resumeId, isAuthenticated])

  const {
    session,
    inputMessage,
    setInputMessage,
    isSending,
    isRequestingHint,
    pendingAnswer,
    pendingEvaluationTurnId,
    error: sessionError,
    hintItems,
    sendAnswer,
    requestHint,
    endInterview,
  } = useInterviewSession({
    resume,
    enabled: mounted && isAuthenticated && !!resume,
    requestedSessionId: requestedSessionId || undefined,
    defaultMode: 'practice',
  })

  if (!mounted || isLoading || resumeLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary-600 mx-auto mb-4" />
          <p className="text-gray-600">正在加载面试工作台...</p>
        </div>
      </div>
    )
  }

  if (!resume) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <p className="text-gray-600">简历不存在</p>
          <Link href="/dashboard" className="btn-primary mt-4">返回简历中心</Link>
        </div>
      </div>
    )
  }

  const isComplete = session?.status === 'completed'

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-100 sticky top-0 z-10 print:hidden">
        <div className="w-full px-6">
          <div className="flex justify-between items-center py-3">
            <div className="flex items-center gap-3">
              <Link
                href="/interviews"
                className="flex items-center p-2 rounded-lg text-gray-600 hover:text-gray-900 hover:bg-gray-50 transition-colors"
                title="返回面试中心"
              >
                <ArrowLeftIcon className="w-5 h-5" />
              </Link>
              <span className="text-sm font-medium text-gray-900">
                模拟面试
              </span>
              {session && (
                <span className="text-xs text-gray-400">
                  第 {session.current_turn_index} 题 · {isComplete ? '已结束' : '进行中'}
                </span>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Left panel */}
      <div
        className="fixed left-0 top-[57px] bottom-0 z-30 bg-white border-r border-gray-100 shadow-sm flex flex-col overflow-hidden transition-all duration-[350ms] ease-in-out"
        style={{ width: drawerOpen ? 'calc((100vw - 42rem) / 2 - 1.5rem)' : '48px' }}
      >
        {!drawerOpen ? (
          /* collapsed strip — same as edit page */
          <div
            className="flex flex-col items-center justify-center h-full w-12 cursor-pointer bg-gray-50 hover:bg-gray-100 transition-colors group"
            onClick={() => setDrawerOpen(true)}
          >
            <ChevronRightIcon className="w-5 h-5 text-gray-500 group-hover:text-gray-700" />
          </div>
        ) : (
          <div className="w-full flex flex-col h-full">
            <div className="px-4 py-3 border-b border-gray-100 flex-shrink-0 flex items-center justify-between">
              <div className="flex gap-3">
                <button
                  onClick={() => setResumeExpanded(false)}
                  className={`text-xs font-medium pb-0.5 border-b-2 transition-colors ${!resumeExpanded ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-gray-400 hover:text-gray-600'}`}
                >
                  岗位 JD
                </button>
                <button
                  onClick={() => setResumeExpanded(true)}
                  className={`text-xs font-medium pb-0.5 border-b-2 transition-colors ${resumeExpanded ? 'border-indigo-500 text-indigo-600' : 'border-transparent text-gray-400 hover:text-gray-600'}`}
                >
                  简历预览
                </button>
              </div>
              <button
                onClick={() => setDrawerOpen(false)}
                className="p-1 rounded-lg text-gray-400 hover:text-gray-600 hover:bg-gray-50 transition-colors"
              >
                <ChevronLeftIcon className="w-4 h-4" />
              </button>
            </div>

            {/* JD tab */}
            {!resumeExpanded && (
              <div className="flex-1 overflow-y-auto px-4 py-4">
                {session?.jd_text
                  ? <p className="text-[13px] text-gray-600 leading-relaxed whitespace-pre-wrap">{session.jd_text}</p>
                  : <p className="text-sm text-gray-300 text-center mt-10">暂无 JD 信息</p>
                }
              </div>
            )}

            {/* Resume preview tab */}
            {resumeExpanded && (
              <div className="flex-1 overflow-y-auto hide-scrollbar">
                {resume?.content
                  ? <ResumePreview content={resume.content} />
                  : <p className="text-sm text-gray-300 text-center mt-10">暂无简历内容</p>
                }
              </div>
            )}
          </div>
        )}
      </div>

      <main className="w-full py-6">
        <div className="max-w-2xl mx-auto space-y-5 px-4">
          <StructuredInterviewPanel
            session={session}
            inputMessage={inputMessage}
            pendingAnswer={pendingAnswer}
            pendingEvaluationTurnId={pendingEvaluationTurnId}
            isSending={isSending}
            isRequestingHint={isRequestingHint}
            error={error || sessionError}
            hintItems={hintItems}
            onInputChange={setInputMessage}
            onSendAnswer={sendAnswer}
            onRequestHint={requestHint}
            onEndInterview={endInterview}
          />
        </div>
      </main>
    </div>
  )
}
