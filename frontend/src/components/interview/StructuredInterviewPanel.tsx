/**
 * 结构化面试面板组件
 *
 * 用于统一展示按轮次推进的提问、回答、评估和最终报告。
 */

'use client'

import { useEffect, useMemo, useRef } from 'react'

import { motion } from 'framer-motion'
import { ArrowUpIcon, LightBulbIcon, StopIcon } from '@heroicons/react/24/outline'

import type { InterviewSession } from '@/lib/api'
import MarkdownMessage from '@/components/ui/MarkdownMessage'

const ROUND_LABELS: Record<string, string> = {
  warmup: '热身',
  resume_deep_dive: '项目深挖',
  behavioral: '行为面试',
  technical: '技术考察',
  closing: '收尾',
}

const MODE_LABELS: Record<string, string> = {
  practice: '练习模式',
  simulation: '拟真模式',
}

interface StructuredInterviewPanelProps {
  session: InterviewSession | null
  inputMessage: string
  pendingAnswer: string | null
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
 * 读取当前待回答轮次，供顶部状态区展示。
 */
function getActiveTurn(session: InterviewSession | null) {
  const turns = session?.turns || []
  return turns.find((turn) => turn.status === 'asked') || turns[turns.length - 1] || null
}

/**
 * 读取当前轮次的人类可读阶段名称。
 */
function getCurrentRoundLabel(session: InterviewSession | null) {
  const activeTurn = getActiveTurn(session)
  if (!activeTurn?.question_type) return '准备中'
  return ROUND_LABELS[activeTurn.question_type] || activeTurn.question_type
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
 * 兼容历史结构化评估和新文本评估，统一转成可展示的文字。
 */
function getEvaluationDisplayText(evaluation: InterviewSession['turns'][number]['evaluation']) {
  if (!evaluation) return ''
  if (typeof evaluation === 'string') return evaluation

  const parts: string[] = []
  if (evaluation.summary) {
    parts.push(evaluation.summary)
  }
  if ((evaluation.gaps?.length ?? 0) > 0) {
    parts.push(`问题：${evaluation.gaps!.join('；')}`)
  }
  if ((evaluation.evidence?.length ?? 0) > 0) {
    parts.push(`亮点：${evaluation.evidence!.join('；')}`)
  }
  if (Object.keys(evaluation.dimension_scores || {}).length > 0) {
    const scoreText = Object.entries(evaluation.dimension_scores || {})
      .map(([key, value]) => `${key} ${value}`)
      .join('，')
    parts.push(`评分：${scoreText}`)
  }

  return parts.join('\n')
}

/**
 * 统一渲染结构化面试的核心时间线。
 */
export default function StructuredInterviewPanel({
  session,
  inputMessage,
  pendingAnswer,
  isSending,
  isRequestingHint = false,
  error,
  hintItems = [],
  onInputChange,
  onSendAnswer,
  onRequestHint,
  onEndInterview,
  className = '',
}: StructuredInterviewPanelProps) {
  const bottomRef = useRef<HTMLDivElement>(null)
  const turns = session?.turns || []
  const report = session?.report_data
  const isComplete = session?.status === 'completed'
  const isPracticeMode = session?.mode === 'practice'
  const currentRoundLabel = useMemo(() => getCurrentRoundLabel(session), [session])
  const answeredTurnCount = useMemo(
    () => turns.filter((turn) => !!turn.answer).length,
    [turns],
  )

  /**
   * 在会话更新后自动滚动到当前底部，保证答题体验连续。
   */
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [pendingAnswer, session])

  return (
    <div className={`flex flex-col min-h-0 ${className}`}>
      <div className="rounded-2xl border border-gray-200 bg-white px-4 py-4 shadow-sm mb-4">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <div className="min-w-0">
            <p className="text-xs font-semibold uppercase tracking-[0.08em] text-gray-400">
              Structured Interview
            </p>
            <div className="mt-1 flex items-center gap-2 flex-wrap">
              <span className="text-lg font-semibold text-gray-900">{currentRoundLabel}</span>
              <span className="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
                第 {session?.current_turn_index || 0} 题
              </span>
              <span className="inline-flex items-center rounded-full bg-gray-100 px-2.5 py-0.5 text-xs font-medium text-gray-600">
                已回答 {answeredTurnCount} 题
              </span>
              {session?.mode && (
                <span className="inline-flex items-center rounded-full bg-indigo-50 px-2.5 py-0.5 text-xs font-medium text-indigo-700">
                  {MODE_LABELS[session.mode] || session.mode}
                </span>
              )}
              {session?.overall_score != null && (isPracticeMode || isComplete) && (
                <span className="inline-flex items-center rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-medium text-emerald-700">
                  综合评分 {session.overall_score}/10
                </span>
              )}
            </div>
          </div>
          <button
            onClick={onEndInterview}
            disabled={!session || isSending || isComplete}
            className="inline-flex items-center gap-2 rounded-xl border border-gray-200 bg-white px-3 py-2 text-xs font-semibold text-gray-700 transition-colors disabled:opacity-50"
          >
            <StopIcon className="w-4 h-4" />
            结束面试
          </button>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto space-y-4 min-h-0 hide-scrollbar">
        {turns.map((turn) => {
          const hasAnswer = !!turn.answer
          const isActive = !hasAnswer && !pendingAnswer
          const isPendingEval = !hasAnswer && !!pendingAnswer
          const displayAnswer = turn.answer || (isPendingEval ? pendingAnswer : null)
          const evaluationDisplayText = getEvaluationDisplayText(turn.evaluation)

          return (
            <motion.div
              key={turn.id}
              initial={{ opacity: 0, y: 24, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              transition={{ duration: 0.35 }}
              className={`bg-white rounded-2xl shadow-sm overflow-hidden ${
                isActive ? 'border-2 border-primary-200' : 'border border-gray-200'
              }`}
            >
              <div className="px-6 pt-5 pb-3">
                <div className="flex items-center gap-2 mb-3">
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-sm">
                    <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" className="w-4 h-4 text-white">
                      <path fillRule="evenodd" d="M7.5 6a4.5 4.5 0 1 1 9 0 4.5 4.5 0 0 1-9 0ZM3.751 20.105a8.25 8.25 0 0 1 16.498 0 .75.75 0 0 1-.437.695A18.683 18.683 0 0 1 12 22.5c-2.786 0-5.433-.608-7.812-1.7a.75.75 0 0 1-.437-.695Z" clipRule="evenodd" />
                    </svg>
                  </div>
                  <span className="text-xs font-medium text-gray-500">面试官</span>
                  {turn.question_type && (
                    <span className="text-[11px] px-2 py-0.5 rounded-full bg-indigo-50 text-indigo-500 font-medium">
                      {ROUND_LABELS[turn.question_type] || turn.question_type}
                    </span>
                  )}
                  <span className={`ml-auto inline-flex items-center justify-center w-6 h-6 rounded-full text-xs font-semibold ${
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

              {displayAnswer && (
                <div className="px-6 pb-3">
                  <div className="bg-gray-50 rounded-xl px-4 py-3 text-[14px] text-gray-700 leading-relaxed whitespace-pre-wrap border border-gray-100">
                    {displayAnswer}
                  </div>
                </div>
              )}

              {isPracticeMode && evaluationDisplayText && (
                <div className="px-6 pb-4">
                  <div className="bg-amber-50 rounded-xl px-4 py-3 border border-amber-100 text-sm">
                    <p className="text-amber-900 whitespace-pre-wrap leading-relaxed">{evaluationDisplayText}</p>
                  </div>
                </div>
              )}

              {isPendingEval && (
                <div className="px-6 pb-4 flex items-center gap-2 text-sm text-gray-400">
                  <div className="animate-spin h-4 w-4 border-2 border-gray-300 border-t-primary-600 rounded-full" />
                  评估中...
                </div>
              )}

              {isActive && !isComplete && (
                <div className="px-6 pb-5 pt-1">
                  {isPracticeMode && (
                    <div className="mb-3 rounded-xl border border-indigo-100 bg-indigo-50/70 px-4 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <p className="text-xs font-semibold text-indigo-700">练习辅助</p>
                          <p className="mt-1 text-xs text-indigo-600">
                            可以先拿提示再组织答案，题后也会给你即时反馈。
                          </p>
                        </div>
                        <button
                          type="button"
                          onClick={onRequestHint}
                          disabled={isRequestingHint || !onRequestHint}
                          className="inline-flex items-center gap-1.5 rounded-full border border-indigo-200 bg-white px-3 py-2 text-xs font-semibold text-indigo-700 transition-colors disabled:opacity-60"
                        >
                          <LightBulbIcon className="w-4 h-4" />
                          {isRequestingHint ? '提示生成中...' : '给我提示'}
                        </button>
                      </div>
                      {hintItems.length > 0 && (
                        <ul className="mt-3 space-y-1.5">
                          {hintItems.map((hint, index) => (
                            <li key={`${turn.id}-hint-${index}`} className="flex items-start gap-2 text-xs text-indigo-700">
                              <span className="mt-1 h-1.5 w-1.5 rounded-full bg-indigo-400 flex-shrink-0" />
                              <span>{hint}</span>
                            </li>
                          ))}
                        </ul>
                      )}
                    </div>
                  )}
                  <div className="relative">
                    <textarea
                      value={inputMessage}
                      onChange={(event) => onInputChange(event.target.value)}
                      onKeyDown={(event) => handleInputKeyDown(event, onSendAnswer)}
                      placeholder="输入你的回答..."
                      className="w-full p-3 pr-12 border border-gray-200 rounded-xl text-sm resize-none focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      rows={3}
                      disabled={isSending}
                    />
                    <button
                      onClick={onSendAnswer}
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

        {isSending && pendingAnswer && (
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.35 }}
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

        {report && (
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            transition={{ duration: 0.35 }}
            className="bg-white rounded-2xl border border-emerald-200 shadow-sm overflow-hidden"
          >
            <div className="px-6 py-5">
              <h3 className="font-semibold text-emerald-900 mb-3">面试报告</h3>
              {report.summary && <p className="text-sm text-emerald-800 leading-relaxed">{report.summary}</p>}
              {report.weaknesses && report.weaknesses.length > 0 && (
                <div className="mt-3">
                  <p className="text-xs font-medium text-emerald-700 mb-1">待改进</p>
                  <ul className="space-y-1">
                    {report.weaknesses.map((weakness, index) => (
                      <li key={index} className="text-sm text-emerald-700 flex items-start gap-2">
                        <span className="mt-1.5 w-1 h-1 rounded-full bg-emerald-400 flex-shrink-0" />
                        {weakness}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              {report.next_training_plan && report.next_training_plan.length > 0 && (
                <div className="mt-3">
                  <p className="text-xs font-medium text-emerald-700 mb-1">下一步建议</p>
                  <ul className="space-y-1">
                    {report.next_training_plan.map((plan, index) => (
                      <li key={index} className="text-sm text-emerald-700 flex items-start gap-2">
                        <span className="mt-1.5 w-1 h-1 rounded-full bg-emerald-400 flex-shrink-0" />
                        {plan}
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </motion.div>
        )}

        {error && (
          <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700">
            {error}
          </div>
        )}

        <div ref={bottomRef} />
      </div>
    </div>
  )
}
