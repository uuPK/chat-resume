'use client'

import { useEffect, useRef, useState } from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import { motion } from 'framer-motion'
import { ArrowLeftIcon, ArrowUpIcon, StopIcon } from '@heroicons/react/24/outline'
import { useAuth } from '@/lib/auth'
import { resumeApi, type InterviewSession } from '@/lib/api'
import MarkdownMessage from '@/components/ui/MarkdownMessage'

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
  const [session, setSession] = useState<InterviewSession | null>(null)
  const [inputMessage, setInputMessage] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pendingAnswer, setPendingAnswer] = useState<string | null>(null)
  const bottomRef = useRef<HTMLDivElement>(null)

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

  useEffect(() => {
    if (!resume || session || isSending) return
    const jobApplication = resume.content?.job_application || {}
    setIsSending(true)

    const loadSession = requestedSessionId
      ? resumeApi.getInterviewSession(requestedSessionId).then((result) => {
          if (result.session.resume_id !== resume.id) {
            throw new Error('面试记录与当前简历不匹配')
          }
          if ((result.session.turns?.length ?? 0) === 0 && result.session.status !== 'completed') {
            return resumeApi.startInterviewSession(result.session.id)
          }
          return result
        })
      : resumeApi.createInterviewSession({
          resume_id: resume.id,
          target_title: jobApplication.target_title,
          target_company: jobApplication.target_company,
          jd_text: jobApplication.jd_text,
          interview_type: 'general',
          difficulty: 'medium',
          language: 'zh-CN',
          mode: 'text',
        }).then((created) => resumeApi.startInterviewSession(created.session.id))

    loadSession
      .then((started) => setSession(started.session))
      .catch((err) => setError(err instanceof Error ? err.message : '启动面试失败'))
      .finally(() => setIsSending(false))
  }, [resume, session, isSending, requestedSessionId])

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [session, pendingAnswer])

  const sendAnswer = async () => {
    const text = inputMessage.trim()
    if (!text || !session || isSending || session.status === 'completed') return
    setIsSending(true)
    setError(null)
    setInputMessage('')
    setPendingAnswer(text)

    try {
      for await (const _event of resumeApi.answerInterviewSessionStream(session.id, text)) {
        if (_event.type === 'done') {
          setSession(_event.session)
          setPendingAnswer(null)
        }
      }
    } catch (err) {
      setPendingAnswer(null)
      setError(err instanceof Error ? err.message : '提交回答失败')
    } finally {
      setIsSending(false)
    }
  }

  const endInterview = async () => {
    if (!session || isSending || session.status === 'completed') return
    setIsSending(true)
    setError(null)
    try {
      const result = await resumeApi.endInterviewSession(session.id)
      setSession(result.session)
    } catch (err) {
      setError(err instanceof Error ? err.message : '结束面试失败')
    } finally {
      setIsSending(false)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendAnswer()
    }
  }

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

  const turns = session?.turns || []
  const report = session?.report_data
  const isComplete = session?.status === 'completed'
  const rounds: Array<{ type: string; goal: string }> = session?.plan?.rounds || []
  const currentRoundIndex: number = session?.current_round_index ?? -1

  const ROUND_LABEL: Record<string, string> = {
    warmup: '热身',
    resume_deep_dive: '项目深挖',
    behavioral: '行为面试',
    technical: '技术考察',
    closing: '收尾',
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-100 sticky top-0 z-10 print:hidden">
        <div className="w-full px-6">
          <div className="flex justify-between items-center py-3">
            <div className="flex items-center gap-3">
              <Link
                href={`/resume/${resumeId}/edit`}
                className="flex items-center p-2 rounded-lg text-gray-600 hover:text-gray-900 hover:bg-gray-50 transition-colors"
                title="返回编辑"
              >
                <ArrowLeftIcon className="w-5 h-5" />
              </Link>
              <span className="text-sm font-medium text-gray-900">
                {resume.content?.personal_info?.name
                  ? `${resume.content.personal_info.name} · 模拟面试`
                  : resume.title}
              </span>
              {session && (
                <span className="text-xs text-gray-400">
                  第 {session.current_turn_index} 题 · {isComplete ? '已结束' : '进行中'}
                </span>
              )}
            </div>
            <button
              onClick={endInterview}
              disabled={!session || isSending || isComplete}
              className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-gray-700 disabled:opacity-50"
            >
              <StopIcon className="w-4 h-4" />
              结束面试
            </button>
          </div>
        </div>
      </header>

      <main className="w-full py-6">
        <div className="flex items-start min-h-0">

          {/* Left column: phase sidebar — horizontally + vertically centered in viewport */}
          <div className="hidden md:flex flex-1 items-center justify-center sticky top-0 h-screen self-start">
            <aside>
              <div className="relative">
                {rounds.length > 1 && (
                  <div className="absolute left-[6px] top-3 bottom-3 w-px bg-gray-200" />
                )}
                <div className="space-y-[7.5rem]">
                  {rounds.map((round, idx) => {
                    const isCurrent = !isComplete && idx === currentRoundIndex
                    const isDone = isComplete || idx < currentRoundIndex
                    return (
                      <div key={idx} className="flex items-center gap-3">
                        <span className={`flex-shrink-0 w-3 h-3 rounded-full border-2 transition-colors ${
                          isCurrent
                            ? 'bg-indigo-500 border-indigo-500'
                            : isDone
                            ? 'bg-emerald-400 border-emerald-400'
                            : 'bg-white border-gray-300'
                        }`} />
                        <span className={`text-xs transition-colors ${
                          isCurrent ? 'text-indigo-600 font-semibold' : 'text-gray-400'
                        }`}>
                          {ROUND_LABEL[round.type] || round.type}
                        </span>
                      </div>
                    )
                  })}
                </div>
              </div>
            </aside>
          </div>

          {/* Center: question cards */}
          <div className="w-full max-w-2xl flex-shrink-0 space-y-5 px-4">
          {turns.map((turn) => {
            const hasAnswer = !!turn.answer
            const isActive = !hasAnswer && !pendingAnswer
            const isPendingEval = !hasAnswer && !!pendingAnswer
            const displayAnswer = turn.answer || (isPendingEval ? pendingAnswer : null)

            return (
              <motion.div
                key={turn.id}
                initial={{ opacity: 0, y: 24, scale: 0.97 }}
                animate={{ opacity: 1, y: 0, scale: 1 }}
                transition={{ duration: 0.4 }}
                className={`bg-white rounded-2xl shadow-sm overflow-hidden ${
                  isActive ? 'border-2 border-primary-200' : 'border border-gray-200'
                }`}
              >
                {/* Question */}
                <div className="px-6 pt-5 pb-3">
                  <div className="flex items-center gap-2 mb-3">
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-sm">
                      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 text-white">
                        <path fillRule="evenodd" d="M7.5 6a4.5 4.5 0 1 1 9 0 4.5 4.5 0 0 1-9 0ZM3.751 20.105a8.25 8.25 0 0 1 16.498 0 .75.75 0 0 1-.437.695A18.683 18.683 0 0 1 12 22.5c-2.786 0-5.433-.608-7.812-1.7a.75.75 0 0 1-.437-.695Z" clipRule="evenodd" />
                      </svg>
                    </div>
                    <span className="text-xs font-medium text-gray-500">面试官</span>
                    <span className={`ml-auto flex-shrink-0 inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-semibold ${
                      hasAnswer || isPendingEval
                        ? 'bg-emerald-100 text-emerald-700'
                        : 'bg-primary-100 text-primary-700'
                    }`}>
                      {turn.turn_index}
                    </span>
                  </div>
                  <div className="text-[15px] text-gray-900 leading-relaxed pl-10">
                    <MarkdownMessage content={turn.question} />
                  </div>
                </div>

                {/* User answer */}
                {displayAnswer && (
                  <div className="px-6 pb-3">
                    <div className="bg-gray-50 rounded-xl px-4 py-3 text-[14px] text-gray-700 leading-relaxed whitespace-pre-wrap border border-gray-100">
                      {displayAnswer}
                    </div>
                  </div>
                )}

                {/* Evaluation */}
                {turn.evaluation && (
                  <div className="px-6 pb-4">
                    <div className="bg-amber-50 rounded-xl px-4 py-3 border border-amber-100 text-sm">
                      {turn.evaluation.summary && (
                        <p className="text-amber-900">{turn.evaluation.summary}</p>
                      )}
                      {Object.keys(turn.evaluation.dimension_scores || {}).length > 0 && (
                        <div className="flex flex-wrap gap-2 mt-2">
                          {Object.entries(turn.evaluation.dimension_scores!).map(([key, value]) => (
                            <span key={key} className="inline-flex items-center px-2 py-0.5 rounded-md bg-amber-100 text-amber-800 text-xs">
                              {key} {value}
                            </span>
                          ))}
                        </div>
                      )}
                      {(turn.evaluation.gaps?.length ?? 0) > 0 && (
                        <p className="mt-2 text-amber-700 text-xs">问题：{turn.evaluation.gaps!.join('；')}</p>
                      )}
                      {(turn.evaluation.evidence?.length ?? 0) > 0 && (
                        <p className="mt-1 text-amber-700 text-xs">亮点：{turn.evaluation.evidence!.join('；')}</p>
                      )}
                    </div>
                  </div>
                )}

                {/* Pending evaluation indicator */}
                {isPendingEval && (
                  <div className="px-6 pb-4 flex items-center gap-2 text-sm text-gray-400">
                    <div className="animate-spin h-4 w-4 border-2 border-gray-300 border-t-primary-600 rounded-full" />
                    评估中...
                  </div>
                )}

                {/* Active input */}
                {isActive && !isComplete && (
                  <div className="px-6 pb-5 pt-1">
                    <div className="relative">
                      <textarea
                        value={inputMessage}
                        onChange={(e) => setInputMessage(e.target.value)}
                        onKeyDown={handleKeyDown}
                        placeholder="输入你的回答..."
                        className="w-full p-3 pr-12 border border-gray-200 rounded-xl text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                        rows={3}
                        disabled={isSending}
                      />
                      <button
                        onClick={sendAnswer}
                        disabled={!inputMessage.trim() || isSending}
                        className={`absolute right-3 top-1/2 -translate-y-1/2 w-8 h-8 rounded-full flex items-center justify-center transition-colors ${
                          inputMessage.trim() && !isSending
                            ? 'bg-primary-600 text-white hover:bg-primary-700'
                            : 'bg-gray-200 text-gray-400'
                        }`}
                      >
                        <ArrowUpIcon className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                )}
              </motion.div>
            )
          })}

          {/* Waiting for next question */}
          {isSending && pendingAnswer && (
            <motion.div
              initial={{ opacity: 0, y: 24, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.4 }}
              className="bg-white rounded-2xl border border-gray-200 shadow-sm overflow-hidden"
            >
              <div className="px-6 py-5 flex items-center gap-3">
                <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-sm animate-pulse">
                  <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 text-white">
                    <path fillRule="evenodd" d="M7.5 6a4.5 4.5 0 1 1 9 0 4.5 4.5 0 0 1-9 0ZM3.751 20.105a8.25 8.25 0 0 1 16.498 0 .75.75 0 0 1-.437.695A18.683 18.683 0 0 1 12 22.5c-2.786 0-5.433-.608-7.812-1.7a.75.75 0 0 1-.437-.695Z" clipRule="evenodd" />
                  </svg>
                </div>
                <span className="text-xs font-medium text-gray-500">面试官</span>
                <span className="text-sm text-gray-400 ml-1">正在准备下一题...</span>
              </div>
            </motion.div>
          )}

          {/* Report */}
          {report && (
            <motion.div
              initial={{ opacity: 0, y: 24, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.4 }}
              className="bg-white rounded-2xl border border-emerald-200 shadow-sm overflow-hidden"
            >
              <div className="px-6 py-5">
                <h3 className="font-semibold text-emerald-900 mb-3">面试报告</h3>
                {report.summary && <p className="text-sm text-emerald-800 leading-relaxed">{report.summary}</p>}
                {report.weaknesses && report.weaknesses.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs font-medium text-emerald-700 mb-1">待改进</p>
                    <ul className="space-y-1">
                      {report.weaknesses.map((w, i) => (
                        <li key={i} className="text-sm text-emerald-700 flex items-start gap-2">
                          <span className="mt-1.5 w-1 h-1 rounded-full bg-emerald-400 flex-shrink-0" />
                          {w}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {report.next_training_plan && report.next_training_plan.length > 0 && (
                  <div className="mt-3">
                    <p className="text-xs font-medium text-emerald-700 mb-1">下一步建议</p>
                    <ul className="space-y-1">
                      {report.next_training_plan.map((p, i) => (
                        <li key={i} className="text-sm text-emerald-700 flex items-start gap-2">
                          <span className="mt-1.5 w-1 h-1 rounded-full bg-emerald-400 flex-shrink-0" />
                          {p}
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
                {session?.overall_score != null && (
                  <div className="mt-4 pt-3 border-t border-emerald-100 flex items-center gap-2">
                    <span className="text-sm text-emerald-600">综合评分</span>
                    <span className="text-lg font-semibold text-emerald-800">{session.overall_score}</span>
                  </div>
                )}
              </div>
            </motion.div>
          )}

          {/* Error */}
          {error && (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
              {error}
            </div>
          )}

          <div ref={bottomRef} />
          </div>{/* end center column */}

          {/* Right balance column */}
          <div className="hidden md:block flex-1" />
        </div>
      </main>
    </div>
  )
}
