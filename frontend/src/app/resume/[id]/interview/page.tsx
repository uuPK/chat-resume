'use client'

import { useEffect, useRef, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { motion } from 'framer-motion'
import { ArrowLeftIcon, ArrowUpIcon, StopIcon } from '@heroicons/react/24/outline'
import { useAuth } from '@/lib/auth'
import { resumeApi, type InterviewSession } from '@/lib/api'
import ResumePreview from '@/components/preview/ResumePreview'
import MarkdownMessage from '@/components/ui/MarkdownMessage'

type UIMessage = {
  id: string
  type: 'user' | 'ai' | 'system'
  content: string
}

function buildMessagesFromSession(session: InterviewSession): UIMessage[] {
  const messages: UIMessage[] = []
  for (const turn of session.turns || []) {
    messages.push({
      id: `q-${turn.id}`,
      type: 'ai',
      content: turn.question,
    })
    if (turn.answer) {
      messages.push({
        id: `a-${turn.id}`,
        type: 'user',
        content: turn.answer,
      })
    }
    if (turn.evaluation) {
      const gaps = turn.evaluation.gaps || []
      const evidence = turn.evaluation.evidence || []
      const scores = turn.evaluation.dimension_scores || {}
      const scoreLine = Object.keys(scores).length > 0
        ? `评分：${Object.entries(scores).map(([key, value]) => `${key} ${value}`).join(' / ')}`
        : ''
      const detailLine = gaps.length > 0
        ? `问题：${gaps.join('；')}`
        : evidence.length > 0
        ? `亮点：${evidence.join('；')}`
        : ''
      messages.push({
        id: `e-${turn.id}`,
        type: 'system',
        content: [turn.evaluation.summary, scoreLine, detailLine].filter(Boolean).join('\n'),
      })
    }
  }
  return messages
}

export default function InterviewPage() {
  const params = useParams()
  const router = useRouter()
  const resumeId = Number(params?.id as string)

  const { isAuthenticated, isLoading } = useAuth()
  const [mounted, setMounted] = useState(false)
  const [resume, setResume] = useState<Awaited<ReturnType<typeof resumeApi.getResume>> | null>(null)
  const [resumeLoading, setResumeLoading] = useState(true)
  const [session, setSession] = useState<InterviewSession | null>(null)
  const [messages, setMessages] = useState<UIMessage[]>([])
  const [inputMessage, setInputMessage] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    setMounted(true)
  }, [])

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
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, session])

  useEffect(() => {
    if (!resume || session || isSending) return
    const jobApplication = resume.content?.job_application || {}
    setIsSending(true)
    resumeApi.createInterviewSession({
      resume_id: resume.id,
      target_title: jobApplication.target_title,
      target_company: jobApplication.target_company,
      jd_text: jobApplication.jd_text,
      interview_type: 'general',
      difficulty: 'medium',
      language: 'zh-CN',
      mode: 'text',
    })
      .then((created) => resumeApi.startInterviewSession(created.session.id))
      .then((started) => {
        setSession(started.session)
        setMessages(buildMessagesFromSession(started.session))
      })
      .catch((err) => setError(err instanceof Error ? err.message : '启动面试失败'))
      .finally(() => setIsSending(false))
  }, [resume, session, isSending])

  const sendAnswer = async () => {
    const text = inputMessage.trim()
    if (!text || !session || isSending || session.status === 'completed') return
    setIsSending(true)
    setError(null)
    setInputMessage('')

    // 立即把用户回答追加到 UI
    const userMsgId = `user-${Date.now()}`
    setMessages((prev) => [...prev, { id: userMsgId, type: 'user', content: text }])

    // 占位 AI 气泡，流式 token 追加进来
    const aiMsgId = `ai-stream-${Date.now()}`
    setMessages((prev) => [...prev, { id: aiMsgId, type: 'ai', content: '' }])

    try {
      for await (const event of resumeApi.answerInterviewSessionStream(session.id, text)) {
        if (event.type === 'token') {
          setMessages((prev) =>
            prev.map((m) => m.id === aiMsgId ? { ...m, content: m.content + event.content } : m)
          )
        } else if (event.type === 'done') {
          // 流结束：用完整 session 状态重建消息列表（含评估气泡）
          setSession(event.session)
          setMessages(buildMessagesFromSession(event.session))
        }
      }
    } catch (err) {
      // 移除占位气泡，显示错误
      setMessages((prev) => prev.filter((m) => m.id !== aiMsgId))
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
      setMessages(buildMessagesFromSession(result.session))
    } catch (err) {
      setError(err instanceof Error ? err.message : '结束面试失败')
    } finally {
      setIsSending(false)
    }
  }

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
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

  const report = session?.report_data

  return (
    <div className="min-h-screen bg-gray-50">
      <header className="bg-white border-b border-gray-100 print:hidden">
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
                  第 {session.current_turn_index} 题 · {session.status === 'completed' ? '已结束' : '进行中'}
                </span>
              )}
            </div>
            <button
              onClick={endInterview}
              disabled={!session || isSending || session.status === 'completed'}
              className="inline-flex items-center gap-2 rounded-lg border border-gray-200 bg-white px-3 py-2 text-xs text-gray-700 disabled:opacity-50"
            >
              <StopIcon className="w-4 h-4" />
              结束面试
            </button>
          </div>
        </div>
      </header>

      <main className="max-w-full mx-auto px-6 py-3">
        <div className="flex gap-0 h-[calc(100vh-120px)]">
          <motion.div
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ duration: 0.8 }}
            className="flex flex-col min-h-0 min-w-0 overflow-hidden"
            style={{ flex: '0 0 calc(37% - 8px)' }}
          >
            <div className="flex-1 overflow-y-auto min-h-0 min-w-0 hide-scrollbar">
              <ResumePreview content={resume.content} />
            </div>
          </motion.div>

          <div className="w-2 flex-shrink-0 flex items-center justify-center group select-none">
            <div className="w-0.5 h-full bg-transparent group-hover:bg-primary-400 transition-colors rounded-full" />
          </div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="flex flex-col min-h-0 min-w-0"
            style={{ flex: '0 0 calc(63% - 8px)' }}
          >
            <div className="bg-white rounded-xl border border-gray-200 shadow-soft p-4 flex-1 overflow-hidden flex flex-col">
              <div className="mb-3 flex items-center justify-between gap-3 flex-shrink-0">
                <div className="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-1">
                  <span className="rounded-md px-3 py-1.5 text-xs font-medium bg-white text-gray-900 shadow-sm">
                    面试 Session
                  </span>
                </div>
                {session?.overall_score != null && (
                  <span className="text-xs text-gray-500">总分 {session.overall_score}</span>
                )}
              </div>

              <div className="flex-1 overflow-y-auto mb-4 space-y-3 min-h-0 max-h-full hide-scrollbar">
                {messages.map((message) => (
                  <div
                    key={message.id}
                    className={`flex w-full ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                  >
                    <div
                      className={`max-w-[88%] px-4 py-3 rounded-2xl ${
                        message.type === 'user'
                          ? 'bg-primary-600 text-white rounded-br-md text-[14px] shadow-sm'
                          : message.type === 'system'
                          ? 'bg-amber-50 text-amber-900 rounded-bl-md border border-amber-100 shadow-xs'
                          : 'bg-gray-50 text-gray-800 rounded-bl-md border border-gray-100 shadow-xs'
                      }`}
                    >
                      {message.type === 'user' ? (
                        <span className="text-[14px] whitespace-pre-wrap">{message.content}</span>
                      ) : (
                        <MarkdownMessage content={message.content} />
                      )}
                    </div>
                  </div>
                ))}

                {isSending && messages.every((m) => !m.id.startsWith('ai-stream-') || m.content) && (
                  <div className="flex w-full justify-start">
                    <div className="max-w-[85%] rounded-2xl rounded-bl-md border border-gray-200 bg-white px-4 py-3 text-[14px] text-gray-500 shadow-sm">
                      <span className="inline-block animate-pulse">评估中...</span>
                    </div>
                  </div>
                )}

                {report && (
                  <div className="rounded-2xl border border-emerald-200 bg-emerald-50 px-4 py-4 text-sm text-emerald-950">
                    <p className="font-medium">面试报告</p>
                    {report.summary && <p className="mt-2">{report.summary}</p>}
                    {report.weaknesses && report.weaknesses.length > 0 && (
                      <p className="mt-2">主要问题：{report.weaknesses.join('；')}</p>
                    )}
                    {report.next_training_plan && report.next_training_plan.length > 0 && (
                      <p className="mt-2">下一步：{report.next_training_plan.join('；')}</p>
                    )}
                  </div>
                )}

                {error && (
                  <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
                    {error}
                  </div>
                )}

                <div ref={messagesEndRef} />
              </div>

              <div className="pt-3 flex-shrink-0">
                <div className="relative">
                  <textarea
                    value={inputMessage}
                    onChange={(e) => setInputMessage(e.target.value)}
                    onKeyPress={handleKeyPress}
                    placeholder={session?.status === 'completed' ? '本场面试已结束' : '输入你的回答...'}
                    className="w-full p-3 pr-12 border border-gray-200 rounded-xl text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent shadow-inner"
                    rows={3}
                    disabled={isSending || session?.status === 'completed'}
                  />
                  <button
                    onClick={sendAnswer}
                    disabled={!inputMessage.trim() || isSending || session?.status === 'completed'}
                    className={`absolute right-3 top-1/2 transform -translate-y-1/2 w-9 h-9 rounded-full transition-colors flex items-center justify-center ${
                      inputMessage.trim() && !isSending && session?.status !== 'completed'
                        ? 'bg-primary-600 text-white hover:bg-primary-700 shadow-md'
                        : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                    }`}
                  >
                    <ArrowUpIcon className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>
          </motion.div>
        </div>
      </main>
    </div>
  )
}
