import { useState, useRef } from 'react'

export type DiffItem = {
  before?: string
  after?: string
  reason?: string
}

export type StreamEvent =
  | { type: 'tool'; name: string }
  | { type: 'text'; content: string }
  | {
      type: 'tool_call'
      callId: string
      toolName: string
      displayMessage?: string
    }
  | {
      type: 'tool_result'
      callId?: string
      toolName: string
      displayMessage?: string
    }
  | {
      type: 'tool_pending'
      callId: string
      toolName: string
      diffSummary: string
      diffItems?: DiffItem[]
    }
  | {
      type: 'tool_confirmed'
      callId: string
      toolName: string
      diffSummary: string
      diffItems?: DiffItem[]
    }
  | {
      type: 'tool_rejected'
      callId: string
      toolName: string
      diffSummary: string
      diffItems?: DiffItem[]
    }

export interface ChatMessage {
  id: string
  type: 'user' | 'ai'
  content: string
  timestamp: Date
  streamEvents?: StreamEvent[]
}

interface StreamingChatOptions {
  onMessage?: (message: ChatMessage) => void
  onError?: (error: string) => void
  apiBaseUrl?: string
  onQrImages?: (images: string[]) => void
  onResumeUpdate?: (resumeContent: Record<string, unknown>) => void
  visibleModules?: string[]
  agentType?: 'resume'
}

function normalizeDiffItems(value: unknown): DiffItem[] {
  if (!Array.isArray(value)) return []
  return value.flatMap((item) => {
    if (!item || typeof item !== 'object') return []
    const record = item as Record<string, unknown>
    const diffItem: DiffItem = {}
    if (record.before !== undefined && record.before !== null) {
      diffItem.before = String(record.before)
    }
    if (record.after !== undefined && record.after !== null) {
      diffItem.after = String(record.after)
    }
    if (record.reason !== undefined && record.reason !== null) {
      diffItem.reason = String(record.reason)
    }
    return Object.keys(diffItem).length > 0 ? [diffItem] : []
  })
}

const TOOL_NAME_ALIASES: Record<string, string> = {
  update_highlight: 'update_bullet',
  add_highlight: 'add_bullet',
  remove_highlight: 'remove_bullet',
}

function normalizeToolName(name: string): string {
  return TOOL_NAME_ALIASES[name] || name
}

function resolveToolName(data: Record<string, unknown>): string {
  if (data.tool_display_name) return normalizeToolName(String(data.tool_display_name))
  if (data.tool_name) return normalizeToolName(String(data.tool_name))
  const calls = Array.isArray(data.tool_calls) ? data.tool_calls : []
  const lastCall = calls[calls.length - 1]
  if (lastCall && typeof lastCall === 'object' && 'name' in lastCall) {
    return normalizeToolName(String((lastCall as { name?: unknown }).name || ''))
  }
  return '工具调用'
}

export function useStreamingChat(resumeId: number, options: StreamingChatOptions = {}) {
  const [isStreaming, setIsStreaming] = useState(false)
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState('')
  const [streamEvents, setStreamEvents] = useState<StreamEvent[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  // 使用 ref 作为立即生效的锁，因为 useState 更新是异步的
  const isStreamingLockRef = useRef(false)
  // 用 ref 跟踪当前 sessionId，以便在异步回调中读取最新值
  const sessionIdRef = useRef<string | null>(null)
  // tool_pending 超时计时器：key=callId, value=timerId
  const pendingToolTimersRef = useRef<Record<string, ReturnType<typeof setTimeout>>>({})
  const confirmingToolCallsRef = useRef<Set<string>>(new Set())

  const {
    onMessage,
    onError,
    apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    onQrImages,
    onResumeUpdate,
    visibleModules = [],
    agentType = 'resume'
  } = options

  const sendStreamingMessage = async (message: string, chatHistory: ChatMessage[] = []) => {
    // 使用 ref 做立即检查，防止并发调用
    if (isStreamingLockRef.current) {
      console.log('[useStreamingChat] 已有流式请求进行中，跳过重复调用')
      return
    }
    // 立即加锁
    isStreamingLockRef.current = true

    setIsStreaming(true)
    setCurrentStreamingMessage('')

    // 创建中止控制器
    abortControllerRef.current = new AbortController()

    try {
      // 转换聊天记录格式为后端需要的 OpenAI 格式
      const historyToSend = chatHistory.map((msg) => ({
        role: msg.type === 'ai' ? 'assistant' : 'user',
        content: msg.content
      }))

      const response = await fetch(`${apiBaseUrl}/api/ai/chat/stream`, {
        method: 'POST',
        credentials: 'include',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          message,
          resume_id: resumeId,
          chat_history: historyToSend,
          visible_modules: visibleModules,
          agent_type: agentType,
        }),
        signal: abortControllerRef.current.signal
      })

      if (!response.ok) {
        if (response.status === 401) {
          throw new Error('认证已过期，请重新登录')
        }
        throw new Error(`HTTP error! status: ${response.status}`)
      }

      if (!response.body) {
        throw new Error('Response body is null')
      }

      const reader = response.body.getReader()
      const decoder = new TextDecoder()
      let buffer = ''
      let streamingContent = ''
      let eventsBuffer: StreamEvent[] = []

      try {
        while (true) {
          const { done, value } = await reader.read()

          if (done) break

          // 解码数据
          buffer += decoder.decode(value, { stream: true })

          // 处理完整的SSE消息
          const lines = buffer.split('\n')
          buffer = lines.pop() || '' // 保留不完整的行

          for (const line of lines) {
            if (line.startsWith('data: ')) {
              try {
                const data = JSON.parse(line.slice(6))

                if (data.error) {
                  onError?.(data.error)
                  return
                }

                if (data.done) {
                  // done 事件携带最终 resume_content 用于刷新预览
                  if (data.resume_content) {
                    console.log('[useStreamingChat] done 事件收到 resume_content', Object.keys(data.resume_content))
                    onResumeUpdate?.(data.resume_content)
                  }
                  // 流式传输完成，创建完整的AI消息（携带工具事件快照，用于历史渲染）
                  const aiMessage: ChatMessage = {
                    id: Date.now().toString(),
                    type: 'ai',
                    content: streamingContent,
                    timestamp: new Date(),
                    streamEvents: eventsBuffer.length > 0 ? [...eventsBuffer] : undefined,
                  }
                  // 先清掉流式展示态，再把最终消息并入历史，避免同一条消息短暂重复渲染。
                  setIsStreaming(false)
                  setCurrentStreamingMessage('')
                  setStreamEvents([])
                  setTimeout(() => {
                    onMessage?.(aiMessage)
                  }, 0)
                  return
                }

                // 首个事件携带 session_id
                if (data.session_id) {
                  sessionIdRef.current = data.session_id
                  setSessionId(data.session_id)
                }

                if (data.qr_images && Array.isArray(data.qr_images) && data.qr_images.length > 0) {
                  onQrImages?.(data.qr_images)
                }

                if (data.event_type === 'tool_call' && data.call_id) {
                  const callId = data.call_id as string
                  eventsBuffer = [...eventsBuffer, {
                    type: 'tool_call',
                    callId,
                    toolName: resolveToolName(data),
                    displayMessage: data.display_message ? String(data.display_message) : undefined,
                  }]
                  setStreamEvents([...eventsBuffer])
                }

                if (data.event_type === 'tool_result') {
                  eventsBuffer = [...eventsBuffer, {
                    type: 'tool_result',
                    callId: data.call_id ? String(data.call_id) : undefined,
                    toolName: resolveToolName(data),
                    displayMessage: data.display_message ? String(data.display_message) : undefined,
                  }]
                  setStreamEvents([...eventsBuffer])
                }

                // tool_pending: agent 暂停，等待用户确认
                if (data.tool_pending && data.call_id) {
                  const callId = data.call_id as string
                  eventsBuffer = [...eventsBuffer, {
                    type: 'tool_pending',
                    callId,
                    toolName: data.tool_display_name || data.tool_name || '',
                    diffSummary: data.diff_summary || '',
                    diffItems: normalizeDiffItems(data.diff_items),
                  }]
                  setStreamEvents([...eventsBuffer])

                  // 5 分钟无操作自动标记为 rejected，避免永久卡在确认按钮
                  pendingToolTimersRef.current[callId] = setTimeout(() => {
                    eventsBuffer = eventsBuffer.map(e =>
                      e.type === 'tool_pending' && e.callId === callId
                        ? {
                            type: 'tool_rejected' as const,
                            callId: e.callId,
                            toolName: e.toolName,
                            diffSummary: e.diffSummary,
                            diffItems: e.diffItems,
                          }
                        : e
                    )
                    setStreamEvents([...eventsBuffer])
                    delete pendingToolTimersRef.current[callId]
                  }, 5 * 60 * 1000)
                }

                // tool_confirmed / tool_rejected: 清除超时计时器，更新对应的 pending 事件状态
                if ((data.tool_confirmed || data.tool_rejected) && data.call_id) {
                  const callId = data.call_id as string
                  if (pendingToolTimersRef.current[callId]) {
                    clearTimeout(pendingToolTimersRef.current[callId])
                    delete pendingToolTimersRef.current[callId]
                  }
                  const newType: 'tool_confirmed' | 'tool_rejected' = data.tool_confirmed
                    ? 'tool_confirmed'
                    : 'tool_rejected'
                  eventsBuffer = eventsBuffer.map(e => {
                    if (e.type === 'tool_pending' && e.callId === callId) {
                      return {
                        type: newType,
                        callId: e.callId,
                        toolName: e.toolName,
                        diffSummary: e.diffSummary,
                        diffItems: e.diffItems,
                      }
                    }
                    return e
                  })
                  setStreamEvents([...eventsBuffer])
                }

                // 处理简历更新
                if (data.resume_content) {
                  console.log('[useStreamingChat] 收到 resume_content，触发预览更新', Object.keys(data.resume_content))
                  onResumeUpdate?.(data.resume_content)
                }

                if (data.content) {
                  streamingContent += data.content
                  setCurrentStreamingMessage(streamingContent)
                  const last = eventsBuffer[eventsBuffer.length - 1]
                  if (last?.type === 'text') {
                    eventsBuffer = [...eventsBuffer.slice(0, -1), { type: 'text', content: last.content + data.content }]
                  } else {
                    eventsBuffer = [...eventsBuffer, { type: 'text', content: data.content }]
                  }
                  setStreamEvents([...eventsBuffer])
                }
              } catch {
                console.warn('Failed to parse SSE data:', line)
              }
            }
          }
        }
      } finally {
        reader.releaseLock()
      }

    } catch (error) {
      if (error instanceof Error && error.name === 'AbortError') {
        console.log('Streaming aborted')
      } else {
        console.error('Streaming error:', error)
        const errorMessage = error instanceof Error ? error.message : 'Unknown streaming error'
        onError?.(errorMessage)
      }
    } finally {
      // 清理所有 tool_pending 超时计时器
      Object.values(pendingToolTimersRef.current).forEach(clearTimeout)
      pendingToolTimersRef.current = {}
      confirmingToolCallsRef.current.clear()
      // 释放锁
      isStreamingLockRef.current = false
      setIsStreaming(false)
      setCurrentStreamingMessage('')
      setStreamEvents([])
      setSessionId(null)
      sessionIdRef.current = null
      abortControllerRef.current = null
    }
  }

  const stopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
  }

  const confirmTool = async (callId: string, confirmed: boolean) => {
    const sid = sessionIdRef.current
    if (!sid) {
      console.warn('[confirmTool] 没有活跃 session')
      return
    }
    if (confirmingToolCallsRef.current.has(callId)) {
      return
    }
    confirmingToolCallsRef.current.add(callId)
    const apiBaseUrl = options.apiBaseUrl || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const response = await fetch(`${apiBaseUrl}/api/ai/chat/confirm-tool`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ session_id: sid, call_id: callId, confirmed }),
    })
    if (response.status === 409) {
      console.warn('[confirmTool] 工具确认状态已变化，忽略重复确认', { callId })
      return
    }
    if (!response.ok) {
      const detail = await response.text()
      throw new Error(detail || `工具确认失败: ${response.status}`)
    }
  }

  return {
    isStreaming,
    currentStreamingMessage,
    streamEvents,
    sessionId,
    sendStreamingMessage,
    stopStreaming,
    confirmTool,
  }
}
