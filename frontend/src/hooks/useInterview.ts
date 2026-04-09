import { useCallback, useEffect, useState } from 'react'
import { interviewApi, type InterviewSession, type InterviewTurn } from '@/lib/api'

interface ChatMessage {
  id: string
  type: 'user' | 'ai'
  content: string
  timestamp: Date
}

interface InterviewHookOptions {
  onMessage?: (message: ChatMessage) => void
  onError?: (error: string) => void
  jobPosition?: string
  jdContent?: string
  existingSessionId?: number | null
}

function createMessage(type: 'user' | 'ai', content: string): ChatMessage {
  return {
    id: `${type}_${Date.now()}_${Math.random().toString(36).slice(2, 9)}`,
    type,
    content,
    timestamp: new Date(),
  }
}

function getCurrentTurn(session: InterviewSession | null): InterviewTurn | null {
  return session?.current_turn || session?.turns?.find(turn => turn.status !== 'answered') || null
}

/**
 * 从流式 JSON 字节流中尽力抽取 `question` 字段的当前已生成文本。
 * 用于边出题边做打字机效果。支持常见转义字符。
 */
function extractQuestionProgress(buffer: string): string {
  const key = '"question"'
  const keyIdx = buffer.indexOf(key)
  if (keyIdx < 0) return ''
  let i = keyIdx + key.length
  while (i < buffer.length && buffer[i] !== '"') i++
  if (i >= buffer.length) return ''
  i++ // 跳过开始引号
  let out = ''
  while (i < buffer.length) {
    const ch = buffer[i]
    if (ch === '\\' && i + 1 < buffer.length) {
      const nx = buffer[i + 1]
      if (nx === 'n') out += '\n'
      else if (nx === 't') out += '\t'
      else if (nx === 'r') out += ''
      else if (nx === '"') out += '"'
      else if (nx === '\\') out += '\\'
      else if (nx === '/') out += '/'
      else out += nx
      i += 2
      continue
    }
    if (ch === '"') break
    out += ch
    i++
  }
  return out
}

export function useInterview(resumeId: number, options: InterviewHookOptions = {}) {
  const [isInterviewActive, setIsInterviewActive] = useState(false)
  const [currentSession, setCurrentSession] = useState<InterviewSession | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState('')
  const [hasAutoLoaded, setHasAutoLoaded] = useState(false)

  const {
    onMessage,
    onError,
    jobPosition,
    jdContent,
    existingSessionId,
  } = options

  const stableOnMessage = useCallback((message: ChatMessage) => {
    onMessage?.(message)
  }, [onMessage])

  const stableOnError = useCallback((error: string) => {
    onError?.(error)
  }, [onError])

  const applySession = useCallback((session: InterviewSession, mode: 'start' | 'resume') => {
    setCurrentSession(session)
    setIsInterviewActive(session.status !== 'completed')

    const currentTurn = getCurrentTurn(session)
    if (!currentTurn) {
      if (mode === 'resume') {
        stableOnMessage(createMessage('ai', '这场面试已经完成。你可以查看报告，或重新开始一场新的面试。'))
      }
      return session
    }

    if (mode === 'resume') {
      const intro = `欢迎回到面试。当前进度 ${session.answered_questions || 0}/${session.total_questions || session.turns?.length || 0}。\n\n**当前问题：**\n${currentTurn.question}`
      stableOnMessage(createMessage('ai', intro))
    } else {
      stableOnMessage(createMessage('ai', currentTurn.question))
    }

    return session
  }, [stableOnMessage])

  const loadExistingSession = useCallback(async (sessionId: number) => {
    setIsLoading(true)
    try {
      const session = await interviewApi.getInterviewSession(resumeId, sessionId)
      return applySession(session, 'resume')
    } catch (error) {
      const message = error instanceof Error ? error.message : '加载面试会话失败'
      stableOnError(message)
      return null
    } finally {
      setIsLoading(false)
    }
  }, [applySession, resumeId, stableOnError])

  useEffect(() => {
    if (existingSessionId) {
      setHasAutoLoaded(false)
    }
  }, [existingSessionId])

  useEffect(() => {
    if (existingSessionId && !hasAutoLoaded && !isLoading && resumeId) {
      setHasAutoLoaded(true)
      loadExistingSession(existingSessionId)
    }
  }, [existingSessionId, hasAutoLoaded, isLoading, loadExistingSession, resumeId])

  const startInterview = async (nextJdContent?: string) => {
    if (isInterviewActive && currentSession) {
      return currentSession
    }

    if (existingSessionId) {
      return loadExistingSession(existingSessionId)
    }

    setIsLoading(true)
    try {
      const session = await interviewApi.startInterview(resumeId, {
        job_position: jobPosition || '未指定职位',
        jd_content: nextJdContent || jdContent || '',
      })
      return applySession(session, 'start')
    } catch (error) {
      const message = error instanceof Error ? error.message : '开始面试失败'
      stableOnError(message)
      return null
    } finally {
      setIsLoading(false)
    }
  }

  const sendAnswer = async (message: string) => {
    if (!currentSession || !isInterviewActive || isLoading) {
      return
    }

    const currentTurn = getCurrentTurn(currentSession)
    if (!currentTurn) {
      stableOnError('当前没有可回答的问题')
      return
    }

    setIsLoading(true)
    setCurrentStreamingMessage('')
    try {
      stableOnMessage(createMessage('user', message))

      let rawBuffer = ''
      let lastQuestion = ''
      let doneEvent:
        | { type: 'done'; completed: boolean; next_turn: InterviewTurn | null }
        | null = null
      let errorMessage: string | null = null

      for await (const evt of interviewApi.submitInterviewAnswerStream(
        resumeId,
        currentSession.id,
        message,
        currentTurn.turn_index,
      )) {
        if (evt.type === 'delta') {
          rawBuffer += evt.content
          const q = extractQuestionProgress(rawBuffer)
          if (q && q !== lastQuestion) {
            lastQuestion = q
            setCurrentStreamingMessage(q)
          }
        } else if (evt.type === 'done') {
          doneEvent = evt
        } else if (evt.type === 'error') {
          errorMessage = evt.message
        }
      }

      setCurrentStreamingMessage('')

      if (errorMessage) {
        throw new Error(errorMessage)
      }

      const refreshedSession = await interviewApi.getInterviewSession(resumeId, currentSession.id)
      setCurrentSession(refreshedSession)
      setIsInterviewActive(refreshedSession.status !== 'completed')

      const nextTurn =
        refreshedSession.current_turn || doneEvent?.next_turn || null
      if (nextTurn && refreshedSession.status !== 'completed') {
        stableOnMessage(createMessage('ai', nextTurn.question))
      } else {
        stableOnMessage(createMessage('ai', '本场模拟面试已完成。你可以结束面试并查看报告。'))
      }
    } catch (error) {
      const messageText = error instanceof Error ? error.message : '提交回答失败'
      stableOnError(messageText)
    } finally {
      setIsLoading(false)
      setCurrentStreamingMessage('')
    }
  }

  const endInterview = async () => {
    if (!currentSession) {
      return
    }

    try {
      await interviewApi.endInterview(resumeId, currentSession.id)
      const latestSession = await interviewApi.getInterviewSession(resumeId, currentSession.id)
      setCurrentSession(latestSession)
      setIsInterviewActive(false)
      stableOnMessage(
        createMessage(
          'ai',
          `面试结束。\n\n已完成 ${latestSession.answered_questions || 0} 轮问答。你现在可以查看报告。`
        )
      )
    } catch (error) {
      const message = error instanceof Error ? error.message : '结束面试失败'
      stableOnError(message)
    }
  }

  const stopCurrentRequest = () => {
    setCurrentStreamingMessage('')
  }

  return {
    isInterviewActive,
    currentSession,
    isLoading,
    currentStreamingMessage,
    startInterview,
    sendAnswer,
    endInterview,
    stopCurrentRequest,
  }
}
