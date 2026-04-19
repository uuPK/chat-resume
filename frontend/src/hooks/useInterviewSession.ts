/**
 * 结构化面试会话 Hook 模块
 *
 * 用于在不同页面复用统一的面试创建、开始、作答和结束流程。
 */

'use client'

import { useCallback, useEffect, useState } from 'react'

import { resumeApi, type InterviewSession } from '@/lib/api'

type InterviewResumeSource = {
  id: number
  content?: {
    job_application?: {
      target_title?: string
      target_company?: string
      jd_text?: string
    }
  }
}

interface UseInterviewSessionOptions {
  resume: InterviewResumeSource | null
  enabled: boolean
  requestedSessionId?: number
  defaultMode?: 'practice' | 'simulation'
}

/**
 * 等待指定毫秒数，供轮询评估结果时复用。
 */
function delay(ms: number) {
  return new Promise((resolve) => window.setTimeout(resolve, ms))
}

/**
 * 读取求职目标，用于创建结构化面试上下文。
 */
function getJobApplicationPayload(resume: InterviewResumeSource) {
  const jobApplication = resume.content?.job_application || {}
  return {
    target_title: jobApplication.target_title,
    target_company: jobApplication.target_company,
    jd_text: jobApplication.jd_text,
  }
}

/**
 * 统一加载已有 session 或创建新 session。
 */
async function loadStructuredInterviewSession(
  resume: InterviewResumeSource,
  defaultMode: 'practice' | 'simulation',
  requestedSessionId?: number,
) {
  if (requestedSessionId) {
    const result = await resumeApi.getInterviewSession(requestedSessionId)
    if (result.session.resume_id !== resume.id) {
      throw new Error('面试记录与当前简历不匹配')
    }
    if ((result.session.turns?.length ?? 0) === 0 && result.session.status !== 'completed') {
      const started = await resumeApi.startInterviewSession(result.session.id)
      return started.session
    }
    return result.session
  }

  const created = await resumeApi.createInterviewSession({
    resume_id: resume.id,
    ...getJobApplicationPayload(resume),
    interview_type: 'general',
    difficulty: 'medium',
    language: 'zh-CN',
    mode: defaultMode,
  })
  const started = await resumeApi.startInterviewSession(created.session.id)
  return started.session
}

/**
 * 提供统一的结构化面试状态和操作方法。
 */
export function useInterviewSession({
  resume,
  enabled,
  requestedSessionId,
  defaultMode = 'practice',
}: UseInterviewSessionOptions) {
  const [session, setSession] = useState<InterviewSession | null>(null)
  const [inputMessage, setInputMessage] = useState('')
  const [isSending, setIsSending] = useState(false)
  const [isRequestingHint, setIsRequestingHint] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [pendingAnswer, setPendingAnswer] = useState<string | null>(null)
  const [pendingEvaluationTurnId, setPendingEvaluationTurnId] = useState<number | null>(null)
  const [hintItems, setHintItems] = useState<string[]>([])

  /**
   * 当简历或 session 参数变化时重置局部会话状态。
   */
  useEffect(() => {
    setSession(null)
    setInputMessage('')
    setError(null)
    setPendingAnswer(null)
    setPendingEvaluationTurnId(null)
    setIsSending(false)
    setHintItems([])
    setIsRequestingHint(false)
  }, [defaultMode, resume?.id, requestedSessionId])

  /**
   * 在下一题已展示后补拉当前题评估，避免和下一题同时出现。
   */
  const waitForEvaluation = useCallback(async (sessionId: number, turnId: number) => {
    for (let attempt = 0; attempt < 12; attempt += 1) {
      await delay(300)
      try {
        const result = await resumeApi.getInterviewSession(sessionId)
        const targetTurn = result.session.turns.find((turn) => turn.id === turnId)
        if (!targetTurn?.evaluation) continue
        setSession((currentSession) => {
          if (!currentSession) return currentSession
          return {
            ...currentSession,
            turns: currentSession.turns.map((turn) => (
              turn.id === turnId
                ? { ...turn, evaluation: targetTurn.evaluation }
                : turn
            )),
          }
        })
        setPendingEvaluationTurnId((currentTurnId) => (currentTurnId === turnId ? null : currentTurnId))
        return
      } catch {
        // 轮询失败时继续重试，避免短暂网络波动直接打断体验。
      }
    }
    setPendingEvaluationTurnId((currentTurnId) => (currentTurnId === turnId ? null : currentTurnId))
  }, [])

  /**
   * 在页面进入面试模式后自动准备好当前 session。
   */
  const ensureSessionReady = useCallback(async () => {
    if (!resume) return
    setIsSending(true)
    setError(null)
    try {
      const nextSession = await loadStructuredInterviewSession(resume, defaultMode, requestedSessionId)
      setSession(nextSession)
    } catch (err) {
      setError(err instanceof Error ? err.message : '启动面试失败')
    } finally {
      setIsSending(false)
    }
  }, [defaultMode, resume, requestedSessionId])

  /**
   * 在启用面试模式后按需自动初始化会话。
   */
  useEffect(() => {
    if (!enabled || !resume || session || isSending) return
    ensureSessionReady().catch(() => {
      // 错误已在 ensureSessionReady 内写入状态。
    })
  }, [enabled, ensureSessionReady, isSending, resume, session])

  /**
   * 在题目切换或模式变化后清空上一题的提示内容。
   */
  useEffect(() => {
    setHintItems([])
    setIsRequestingHint(false)
  }, [session?.current_turn?.id, session?.mode])

  /**
   * 提交当前回答并等待结构化面试返回下一题。
   */
  const sendAnswer = useCallback(async () => {
    const text = inputMessage.trim()
    if (!text || !session || isSending || session.status === 'completed') return

    setIsSending(true)
    setError(null)
    setInputMessage('')
    setPendingAnswer(text)
    setHintItems([])

    try {
      for await (const event of resumeApi.answerInterviewSessionStream(session.id, text)) {
        if (event.type === 'done') {
          setSession(event.session)
          setPendingAnswer(null)
          const answeredTurn = [...event.session.turns].reverse().find((turn) => !!turn.answer)
          if (event.session.mode === 'practice' && answeredTurn && !answeredTurn.evaluation) {
            setPendingEvaluationTurnId(answeredTurn.id)
            void waitForEvaluation(event.session.id, answeredTurn.id)
          } else {
            setPendingEvaluationTurnId(null)
          }
        }
      }
    } catch (err) {
      setPendingAnswer(null)
      setPendingEvaluationTurnId(null)
      setError(err instanceof Error ? err.message : '提交回答失败')
    } finally {
      setIsSending(false)
    }
  }, [inputMessage, isSending, session])

  /**
   * 在练习模式下为当前题目请求答题提示。
   */
  const requestHint = useCallback(async () => {
    if (!session || isRequestingHint || session.mode !== 'practice') return

    setIsRequestingHint(true)
    setError(null)
    try {
      const result = await resumeApi.getInterviewHint(session.id)
      setHintItems(result.hints)
    } catch (err) {
      setError(err instanceof Error ? err.message : '获取提示失败')
    } finally {
      setIsRequestingHint(false)
    }
  }, [isRequestingHint, session])

  /**
   * 主动结束当前面试并返回最终报告。
   */
  const endInterview = useCallback(async () => {
    if (!session || isSending || session.status === 'completed') return

    setIsSending(true)
    setError(null)
    try {
      const result = await resumeApi.endInterviewSession(session.id)
      setSession(result.session)
      setPendingAnswer(null)
    } catch (err) {
      setError(err instanceof Error ? err.message : '结束面试失败')
    } finally {
      setIsSending(false)
    }
  }, [isSending, session])

  return {
    session,
    inputMessage,
    setInputMessage,
    isSending,
    isRequestingHint,
    error,
    pendingAnswer,
    pendingEvaluationTurnId,
    hintItems,
    sendAnswer,
    requestHint,
    endInterview,
  }
}
