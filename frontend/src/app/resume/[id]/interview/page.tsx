'use client'

import { useEffect, useRef, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { motion } from 'framer-motion'
import { ArrowLeftIcon, ArrowUpIcon, TrashIcon } from '@heroicons/react/24/outline'
import { useAuth } from '@/lib/auth'
import { resumeApi } from '@/lib/api'
import ResumePreview from '@/components/preview/ResumePreview'
import StreamingMessage from '@/components/ui/StreamingMessage'
import MarkdownMessage from '@/components/ui/MarkdownMessage'
import { useStreamingChat, ChatMessage } from '@/hooks/useStreamingChat'

export default function InterviewPage() {
  const params = useParams()
  const router = useRouter()
  const resumeId = params?.id as string

  const { isAuthenticated, isLoading } = useAuth()
  const [mounted, setMounted] = useState(false)
  const [resume, setResume] = useState<Awaited<ReturnType<typeof resumeApi.getResume>> | null>(null)
  const [resumeLoading, setResumeLoading] = useState(true)

  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputMessage, setInputMessage] = useState('')
  const [isSending, setIsSending] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const {
    isStreaming,
    currentStreamingMessage,
    sendStreamingMessage,
    stopStreaming,
  } = useStreamingChat(parseInt(resumeId), {
    agentType: 'interview',
    onMessage: (message) => {
      setMessages(prev => [...prev, message])
      setIsSending(false)
    },
    onError: (error) => {
      setMessages(prev => [
        ...prev,
        {
          id: Date.now().toString(),
          type: 'ai',
          content: `抱歉，发生了错误：${error}`,
          timestamp: new Date(),
        },
      ])
      setIsSending(false)
    },
  })

  useEffect(() => { setMounted(true) }, [])

  useEffect(() => {
    if (mounted && !isLoading && !isAuthenticated) router.push('/login')
  }, [mounted, isLoading, isAuthenticated, router])

  useEffect(() => {
    if (!resumeId || !isAuthenticated) return
    resumeApi.getResume(parseInt(resumeId))
      .then(setResume)
      .catch(console.error)
      .finally(() => setResumeLoading(false))
  }, [resumeId, isAuthenticated])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, currentStreamingMessage])

  const sendMessage = async () => {
    const text = inputMessage.trim()
    if (!text || isStreaming || isSending) return

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: text,
      timestamp: new Date(),
    }
    setMessages(prev => [...prev, userMessage])
    setInputMessage('')
    setIsSending(true)
    await sendStreamingMessage(text, [...messages, userMessage])
  }

  const handleKeyPress = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage()
    }
  }

  const handleClearMessages = () => {
    if (isStreaming || isSending) return
    setMessages([])
  }

  if (!mounted || isLoading || resumeLoading) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-32 w-32 border-b-2 border-primary-600 mx-auto mb-4" />
          <p className="text-gray-600">正在加载简历...</p>
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

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
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
              {(resume.content?.job_application?.target_company || resume.content?.job_application?.target_title) && (
                <span className="text-xs text-gray-400">
                  {[
                    resume.content.job_application?.target_company,
                    resume.content.job_application?.target_title,
                  ].filter(Boolean).join(' · ')}
                </span>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="max-w-full mx-auto px-6 py-3">
        <div className="flex gap-0 h-[calc(100vh-120px)]">

          {/* Left Panel - Resume Preview */}
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

          {/* Divider */}
          <div className="w-2 flex-shrink-0 flex items-center justify-center group select-none">
            <div className="w-0.5 h-full bg-transparent group-hover:bg-primary-400 transition-colors rounded-full" />
          </div>

          {/* Right Panel - Interview Chat */}
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.8, delay: 0.2 }}
            className="flex flex-col min-h-0 min-w-0"
            style={{ flex: '0 0 calc(63% - 8px)' }}
          >
            <div className="bg-white rounded-xl border border-gray-200 shadow-soft p-4 flex-1 overflow-hidden flex flex-col">
              {/* Panel header */}
              <div className="mb-3 flex items-center justify-between gap-3 flex-shrink-0">
                <div className="inline-flex rounded-lg border border-gray-200 bg-gray-50 p-1">
                  <span className="rounded-md px-3 py-1.5 text-xs font-medium bg-white text-gray-900 shadow-sm">
                    面试 AGENT
                  </span>
                </div>
                <button
                  onClick={handleClearMessages}
                  disabled={messages.length === 0 || isStreaming || isSending}
                  aria-label="清空消息"
                  className="inline-flex items-center justify-center rounded-lg border border-gray-200 bg-white p-2 text-xs text-gray-600 transition-colors hover:bg-gray-50 hover:text-gray-900 disabled:cursor-not-allowed disabled:opacity-50"
                >
                  <TrashIcon className="w-3.5 h-3.5" />
                </button>
              </div>

              <div className="flex-1 flex flex-col min-h-0">
                {/* Messages */}
                <div className="flex-1 overflow-y-auto mb-4 space-y-3 min-h-0 max-h-full hide-scrollbar">
                  {messages.length === 0 && !isStreaming && (
                    <div className="flex flex-col items-center justify-center h-full text-center text-gray-400 gap-2 py-12">
                      <p className="text-sm">发送一条消息开始模拟面试</p>
                      <p className="text-xs text-gray-300">面试官会基于你的简历提问</p>
                    </div>
                  )}

                  {messages.map((message) => (
                    <div
                      key={message.id}
                      className={`flex w-full ${message.type === 'user' ? 'justify-end' : 'justify-start'}`}
                    >
                      <div
                        className={`max-w-[85%] px-4 py-3 rounded-2xl ${
                          message.type === 'user'
                            ? 'bg-primary-600 text-white rounded-br-md text-[14px] shadow-sm'
                            : 'bg-gray-50 text-gray-800 rounded-bl-md border border-gray-100 shadow-xs'
                        }`}
                      >
                        {message.type === 'ai' ? (
                          <MarkdownMessage content={message.content} />
                        ) : (
                          <span className="text-[14px]">{message.content}</span>
                        )}
                      </div>
                    </div>
                  ))}

                  {/* Streaming */}
                  {isStreaming && currentStreamingMessage && (
                    <div className="flex w-full justify-start">
                      <div className="max-w-[85%] px-4 py-3 rounded-2xl rounded-bl-md bg-gray-50 text-gray-800 border border-gray-100 shadow-xs">
                        <StreamingMessage content={currentStreamingMessage} isComplete={false} />
                      </div>
                    </div>
                  )}

                  {/* Thinking */}
                  {(isSending || isStreaming) && !currentStreamingMessage && (
                    <div className="flex w-full justify-start">
                      <div className="max-w-[85%] rounded-2xl rounded-bl-md border border-gray-200 bg-white px-4 py-3 text-[14px] text-gray-500 shadow-sm">
                        <span className="inline-block animate-pulse">思考中...</span>
                      </div>
                    </div>
                  )}

                  <div ref={messagesEndRef} />
                </div>

                {/* Input */}
                <div className="pt-3 flex-shrink-0">
                  <div className="relative">
                    <textarea
                      value={inputMessage}
                      onChange={(e) => setInputMessage(e.target.value)}
                      onKeyPress={handleKeyPress}
                      placeholder="输入你的回答，或让面试官开始提问..."
                      className="w-full p-3 pr-12 border border-gray-200 rounded-xl text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent shadow-inner"
                      rows={2}
                      disabled={isSending || isStreaming}
                    />
                    <button
                      onClick={isStreaming ? stopStreaming : sendMessage}
                      disabled={isStreaming ? false : (!inputMessage.trim() || isSending)}
                      className={`absolute right-3 top-1/2 transform -translate-y-1/2 w-9 h-9 rounded-full transition-colors flex items-center justify-center ${
                        isStreaming
                          ? 'bg-red-500 text-white hover:bg-red-600 shadow-md'
                          : inputMessage.trim()
                          ? 'bg-primary-600 text-white hover:bg-primary-700 shadow-md'
                          : 'bg-gray-200 text-gray-400 cursor-not-allowed'
                      } disabled:cursor-not-allowed`}
                    >
                      {isStreaming ? (
                        <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                          <rect x="4" y="4" width="12" height="12" rx="1" />
                        </svg>
                      ) : (
                        <ArrowUpIcon className="w-4 h-4" />
                      )}
                    </button>
                  </div>
                </div>
              </div>
            </div>
          </motion.div>

        </div>
      </main>
    </div>
  )
}
