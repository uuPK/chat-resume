/**
 * 结构化面试面板组件
 *
 * 用于按 DESIGN.md 的 Coinbase 风格统一展示问答、反馈和报告。
 */

'use client'

import { useEffect, useRef } from 'react'

import { motion } from 'framer-motion'
import { ArrowUpIcon, LightBulbIcon } from '@heroicons/react/24/outline'

import type { InterviewSession } from '@/lib/api'
import MarkdownMessage from '@/components/ui/MarkdownMessage'

const ROUND_LABELS: Record<string, string> = {
  warmup: '热身',
  resume_deep_dive: '项目深挖',
  behavioral: '行为面试',
  technical: '技术考察',
  closing: '收尾',
}

interface StructuredInterviewPanelProps {
  session: InterviewSession | null
  inputMessage: string
  pendingAnswer: string | null
  pendingEvaluationTurnId?: number | null
  isSending: boolean
  isRequestingHint?: boolean
  error: string | null
  hintItems?: string[]
  onInputChange: (value: string) => void
  onSendAnswer: () => void
  onRequestHint?: () => void
  onEndInterview: () => void
  className?: string
}

/**
 * 统一处理回答输入框里的回车发送交互。
 */
function handleInputKeyDown(
  event: React.KeyboardEvent<HTMLTextAreaElement>,
  onSendAnswer: () => void,
) {
  if (event.key === 'Enter' && !event.shiftKey) {
    event.preventDefault()
    onSendAnswer()
  }
}

/**
 * 将阶段标签转成统一的小尺寸 badge。
 */
function RoundBadge({ questionType }: { questionType?: string }) {
  if (!questionType) return null
  return (
    <span
      className="inline-flex items-center px-3 py-1 text-[11px] font-semibold"
      style={{
        borderRadius: '100000px',
        backgroundColor: '#eef0f3',
        color: '#0052ff',
      }}
    >
      {ROUND_LABELS[questionType] || questionType}
    </span>
  )
}

/**
 * 用统一的蓝色圆点承载面试官身份标识。
 */
function InterviewerAvatar() {
  return (
    <div
      className="flex h-10 w-10 flex-shrink-0 items-center justify-center"
      style={{
        borderRadius: '100000px',
        backgroundColor: '#0052ff',
      }}
    >
      <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="h-5 w-5 text-white">
        <path fillRule="evenodd" d="M7.5 6a4.5 4.5 0 1 1 9 0 4.5 4.5 0 0 1-9 0ZM3.751 20.105a8.25 8.25 0 0 1 16.498 0 .75.75 0 0 1-.437.695A18.683 18.683 0 0 1 12 22.5c-2.786 0-5.433-.608-7.812-1.7a.75.75 0 0 1-.437-.695Z" clipRule="evenodd" />
      </svg>
    </div>
  )
}

/**
 * 统一渲染结构化面试的核心时间线。
 */
export default function StructuredInterviewPanel({
  session,
  inputMessage,
  pendingAnswer,
  pendingEvaluationTurnId = null,
  isSending,
  isRequestingHint = false,
  error,
  hintItems = [],
  onInputChange,
  onSendAnswer,
  onRequestHint,
  className = '',
}: StructuredInterviewPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const turns = session?.turns || []
  const report = session?.report_data
  const isComplete = session?.status === 'completed'
  const isPracticeMode = session?.mode === 'practice'

  /**
   * 在会话更新后自动滚动到当前底部，保证答题体验连续。
   */
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [pendingAnswer, session])

  return (
    <div className={`flex min-h-0 flex-col ${className}`}>
      <div className="hide-scrollbar flex-1 space-y-5 overflow-y-auto min-h-0">
        {turns.map((turn) => {
          const hasAnswer = !!turn.answer
          const isActive = !hasAnswer && !pendingAnswer
          const isPendingEval = !hasAnswer && !!pendingAnswer
          const displayAnswer = turn.answer || (isPendingEval ? pendingAnswer : null)
          const isGeneratingEvaluation = turn.id === pendingEvaluationTurnId && !turn.evaluation

          return (
            <motion.div
              key={turn.id}
              initial={{ opacity: 0, y: 20, scale: 0.985 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.32 }}
              style={{
                borderRadius: '32px',
                border: isActive ? '1px solid #0052ff' : '1px solid rgba(91, 97, 110, 0.2)',
                backgroundColor: '#ffffff',
              }}
            >
              <div className="px-6 py-6">
                <div className="flex items-start gap-4">
                  <InterviewerAvatar />
                  <div className="min-w-0 flex-1">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="text-sm font-semibold" style={{ color: '#0a0b0d' }}>
                        面试官
                      </span>
                      <RoundBadge questionType={turn.question_type} />
                      <span
                        className="ml-auto inline-flex h-7 min-w-7 items-center justify-center px-2 text-xs font-semibold"
                        style={{
                          borderRadius: '100000px',
                          backgroundColor: hasAnswer || isPendingEval ? '#eef0f3' : '#0052ff',
                          color: hasAnswer || isPendingEval ? '#0a0b0d' : '#ffffff',
                        }}
                      >
                        {turn.turn_index}
                      </span>
                    </div>
                    <div
                      className="mt-4 text-base"
                      style={{ color: '#0a0b0d', lineHeight: '1.56' }}
                    >
                      <MarkdownMessage content={turn.question} />
                    </div>
                  </div>
                </div>
              </div>

              {displayAnswer && (
                <div className="px-6 pb-4">
                  <div
                    className="rounded-[24px] border px-5 py-4 text-[15px] whitespace-pre-wrap"
                    style={{
                      borderColor: 'rgba(91, 97, 110, 0.15)',
                      backgroundColor: 'rgba(247,247,247,0.88)',
                      color: '#0a0b0d',
                      lineHeight: '1.56',
                    }}
                  >
                    {displayAnswer}
                  </div>
                </div>
              )}

              {isPracticeMode && turn.evaluation && (
                <div className="px-6 pb-5">
                  <div
                    className="rounded-[24px] border px-5 py-4"
                    style={{
                      borderColor: 'rgba(0, 82, 255, 0.18)',
                      backgroundColor: '#eef0f3',
                    }}
                  >
                    <p className="text-xs font-semibold tracking-[0.16em] lowercase" style={{ color: '#0052ff' }}>
                      system feedback
                    </p>
                    <p
                      className="mt-3 whitespace-pre-wrap text-[15px]"
                      style={{ color: '#0a0b0d', lineHeight: '1.56' }}
                    >
                      {turn.evaluation}
                    </p>
                  </div>
                </div>
              )}

              {isPracticeMode && isGeneratingEvaluation && (
                <div className="px-6 pb-5">
                  <div
                    className="flex items-center gap-3 rounded-[24px] border px-5 py-4 text-sm"
                    style={{
                      borderColor: 'rgba(0, 82, 255, 0.18)',
                      backgroundColor: '#eef0f3',
                      color: '#0052ff',
                    }}
                  >
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#b8ccff] border-t-[#0052ff]" />
                    评估生成中...
                  </div>
                </div>
              )}

              {isPendingEval && (
                <div className="px-6 pb-5">
                  <div
                    className="flex items-center gap-3 rounded-[24px] border px-5 py-4 text-sm"
                    style={{
                      borderColor: 'rgba(91, 97, 110, 0.15)',
                      backgroundColor: 'rgba(247,247,247,0.88)',
                      color: '#5b616e',
                    }}
                  >
                    <div className="h-4 w-4 animate-spin rounded-full border-2 border-[#d6dae0] border-t-[#0052ff]" />
                    正在生成下一题...
                  </div>
                </div>
              )}

              {isActive && !isComplete && (
                <div
                  className="px-6 pb-6 pt-2"
                  style={{ borderTop: '1px solid rgba(91, 97, 110, 0.12)' }}
                >
                  {isPracticeMode && (
                    <div className="mb-4 flex justify-start">
                      <button
                        type="button"
                        onClick={onRequestHint}
                        disabled={isRequestingHint || !onRequestHint}
                        className="btn-outline btn-sm gap-2"
                      >
                        <LightBulbIcon className="h-4 w-4" />
                        {isRequestingHint ? '提示生成中...' : '给我提示'}
                      </button>
                    </div>
                  )}

                  {isPracticeMode && hintItems.length > 0 && (
                    <div
                      className="mb-4 rounded-[24px] border px-5 py-4"
                      style={{
                        borderColor: 'rgba(0, 82, 255, 0.18)',
                        backgroundColor: '#eef0f3',
                      }}
                    >
                      <p className="text-xs font-semibold tracking-[0.16em] lowercase" style={{ color: '#0052ff' }}>
                        response guide
                      </p>
                      <ul className="mt-3 space-y-2">
                        {hintItems.map((hint, index) => (
                          <li
                            key={`${turn.id}-hint-${index}`}
                            className="flex items-start gap-3 text-sm"
                            style={{ color: '#0a0b0d', lineHeight: '1.5' }}
                          >
                            <span
                              className="mt-[7px] h-1.5 w-1.5 flex-shrink-0"
                              style={{ borderRadius: '100000px', backgroundColor: '#0052ff' }}
                            />
                            <span>{hint}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}

                  <div
                    className="rounded-[28px] border p-4"
                    style={{
                      borderColor: 'rgba(91, 97, 110, 0.2)',
                      backgroundColor: '#ffffff',
                    }}
                  >
                    <textarea
                      value={inputMessage}
                      onChange={(event) => onInputChange(event.target.value)}
                      onKeyDown={(event) => handleInputKeyDown(event, onSendAnswer)}
                      placeholder="输入你的回答..."
                      className="input min-h-[124px] resize-none border-0 px-0 py-0 shadow-none focus:shadow-none"
                      rows={4}
                      disabled={isSending}
                    />
                    <div className="mt-4 flex justify-end">
                      <button
                        onClick={onSendAnswer}
                        disabled={!inputMessage.trim() || isSending}
                        className="btn-primary btn-sm gap-2"
                      >
                        提交回答
                        <ArrowUpIcon className="h-4 w-4" />
                      </button>
                    </div>
                  </div>
                </div>
              )}
            </motion.div>
          )
        })}

        {isSending && pendingAnswer && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.32 }}
            className="px-6 py-6"
            style={{
              borderRadius: '32px',
              border: '1px solid rgba(91, 97, 110, 0.2)',
              backgroundColor: '#eef0f3',
            }}
          >
            <div className="flex items-center gap-4">
              <InterviewerAvatar />
              <div>
                <p className="text-sm font-semibold" style={{ color: '#0a0b0d' }}>
                  面试官
                </p>
                <p className="mt-1 text-sm" style={{ color: '#5b616e' }}>
                  正在准备下一题...
                </p>
              </div>
            </div>
          </motion.div>
        )}

        {report && (
          <motion.div
            initial={{ opacity: 0, y: 20, scale: 0.985 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.32 }}
            className="overflow-hidden"
            style={{
              borderRadius: '32px',
              backgroundColor: '#0a0b0d',
              color: '#ffffff',
            }}
          >
            <div className="px-6 py-6">
              <p className="text-xs font-semibold tracking-[0.18em] lowercase" style={{ color: '#7ea6ff' }}>
                interview report
              </p>
              <h3 className="mt-3 text-[32px] font-semibold" style={{ lineHeight: '1.13' }}>
                面试报告
              </h3>

              {report.summary && (
                <p className="mt-4 text-[15px]" style={{ color: 'rgba(255,255,255,0.84)', lineHeight: '1.56' }}>
                  {report.summary}
                </p>
              )}

              {report.weaknesses && report.weaknesses.length > 0 && (
                <div className="mt-6">
                  <p className="text-xs font-semibold tracking-[0.16em] lowercase" style={{ color: '#7ea6ff' }}>
                    gaps to close
                  </p>
                  <ul className="mt-3 space-y-2">
                    {report.weaknesses.map((weakness, index) => (
                      <li key={index} className="flex items-start gap-3 text-sm" style={{ color: '#ffffff' }}>
                        <span
                          className="mt-[7px] h-1.5 w-1.5 flex-shrink-0"
                          style={{ borderRadius: '100000px', backgroundColor: '#0052ff' }}
                        />
                        <span>{weakness}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}

              {report.next_training_plan && report.next_training_plan.length > 0 && (
                <div className="mt-6">
                  <p className="text-xs font-semibold tracking-[0.16em] lowercase" style={{ color: '#7ea6ff' }}>
                    next training plan
                  </p>
                  <ul className="mt-3 space-y-2">
                    {report.next_training_plan.map((plan, index) => (
                      <li key={index} className="flex items-start gap-3 text-sm" style={{ color: '#ffffff' }}>
                        <span
                          className="mt-[7px] h-1.5 w-1.5 flex-shrink-0"
                          style={{ borderRadius: '100000px', backgroundColor: '#0052ff' }}
                        />
                        <span>{plan}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </motion.div>
        )}

        {error && (
          <div
            className="rounded-[24px] border px-5 py-4 text-sm"
            style={{
              borderColor: 'rgba(220, 38, 38, 0.2)',
              backgroundColor: '#fef2f2',
              color: '#b91c1c',
            }}
          >
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}
