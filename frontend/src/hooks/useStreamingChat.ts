import { useState, useRef } from 'react'

interface ToolCall {
  name: string
  result: string
}

export type StreamEvent =
  | { type: 'tool'; name: string }
  | { type: 'text'; content: string }
  | { type: 'tool_pending'; callId: string; toolName: string; diffSummary: string }
  | { type: 'tool_confirmed'; callId: string; toolName: string }
  | { type: 'tool_rejected'; callId: string; toolName: string }

export interface ChatProposal {
  proposalId: number
  proposalStatus: 'pending' | 'applied' | 'rejected' | string
  proposalPatch?: {
    changes: Array<{
      section: string
      op?: 'add' | 'update' | 'remove' | string
      item_id?: string
      item_label?: string
      field?: string
      before: string
      after: string
    }>
  }
}

export interface ChatMessage {
  id: string
  type: 'user' | 'ai'
  content: string
  timestamp: Date
  toolCalls?: ToolCall[]
  proposal?: ChatProposal
}

interface StreamingChatOptions {
  onMessage?: (message: ChatMessage) => void
  onError?: (error: string) => void
  apiBaseUrl?: string
  onQrImages?: (images: string[]) => void
  onResumeUpdate?: (resumeContent: Record<string, unknown>) => void
}

export function useStreamingChat(resumeId: number, options: StreamingChatOptions = {}) {
  const [isStreaming, setIsStreaming] = useState(false)
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState('')
  const [currentToolCalls, setCurrentToolCalls] = useState<ToolCall[]>([])
  const [currentProposal, setCurrentProposal] = useState<ChatProposal | null>(null)
  const [streamEvents, setStreamEvents] = useState<StreamEvent[]>([])
  const [sessionId, setSessionId] = useState<string | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)
  // 使用 ref 作为立即生效的锁，因为 useState 更新是异步的
  const isStreamingLockRef = useRef(false)
  // 用 ref 跟踪当前 sessionId，以便在异步回调中读取最新值
  const sessionIdRef = useRef<string | null>(null)

  const {
    onMessage,
    onError,
    apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    onQrImages,
    onResumeUpdate
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
    setCurrentToolCalls([])
    setCurrentProposal(null)

    // 创建中止控制器
    abortControllerRef.current = new AbortController()

    try {
      // 获取认证token
      const token = localStorage.getItem('access_token')
      if (!token) {
        throw new Error('未找到认证token，请重新登录')
      }

      // 转换聊天记录格式为后端需要的 OpenAI 格式
      const historyToSend = chatHistory.map((msg) => ({
        role: msg.type === 'ai' ? 'assistant' : 'user',
        content: msg.content
      }))

      const response = await fetch(`${apiBaseUrl}/api/ai/chat/stream`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`,
        },
        body: JSON.stringify({
          message,
          resume_id: resumeId,
          chat_history: historyToSend
        }),
        signal: abortControllerRef.current.signal
      })

      if (!response.ok) {
        if (response.status === 401) {
          // 处理认证失败
          localStorage.removeItem('access_token')
          localStorage.removeItem('user')
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
      let toolCalls: ToolCall[] = []
      let proposal: ChatProposal | null = null
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
                  // 流式传输完成，创建完整的AI消息
                  // 不携带 toolCalls：工具确认已在流式过程中内联展示，无需重复显示
                  const aiMessage: ChatMessage = {
                    id: Date.now().toString(),
                    type: 'ai',
                    content: streamingContent,
                    timestamp: new Date(),
                  }
                  onMessage?.(aiMessage)
                  setCurrentStreamingMessage('')
                  setCurrentToolCalls([])
                  setCurrentProposal(null)
                  setStreamEvents([])
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

                // tool_pending: agent 暂停，等待用户确认
                if (data.tool_pending && data.call_id) {
                  eventsBuffer = [...eventsBuffer, {
                    type: 'tool_pending',
                    callId: data.call_id,
                    toolName: data.tool_name || '',
                    diffSummary: data.diff_summary || '',
                  }]
                  setStreamEvents([...eventsBuffer])
                }

                // tool_confirmed / tool_rejected: 更新对应的 pending 事件状态
                if ((data.tool_confirmed || data.tool_rejected) && data.call_id) {
                  const newType = data.tool_confirmed ? 'tool_confirmed' : 'tool_rejected'
                  eventsBuffer = eventsBuffer.map(e =>
                    e.type === 'tool_pending' && (e as { type: 'tool_pending'; callId: string }).callId === data.call_id
                      ? { type: newType, callId: data.call_id, toolName: data.tool_name || '' }
                      : e
                  )
                  setStreamEvents([...eventsBuffer])
                }

                if (data.tool_calls && Array.isArray(data.tool_calls)) {
                  toolCalls = data.tool_calls
                  setCurrentToolCalls(toolCalls)
                }

                if (data.proposal_id) {
                  proposal = {
                    proposalId: data.proposal_id,
                    proposalStatus: data.proposal_status || 'pending',
                    proposalPatch: data.proposal_patch,
                  }
                  setCurrentProposal(proposal)
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
              } catch (error) {
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
      // 释放锁
      isStreamingLockRef.current = false
      setIsStreaming(false)
      setCurrentStreamingMessage('')
      setCurrentToolCalls([])
      setCurrentProposal(null)
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
    const apiBaseUrl = options.apiBaseUrl || process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
    const token = localStorage.getItem('access_token')
    await fetch(`${apiBaseUrl}/api/ai/chat/confirm-tool`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`,
      },
      body: JSON.stringify({ session_id: sid, call_id: callId, confirmed }),
    })
  }

  return {
    isStreaming,
    currentStreamingMessage,
    currentToolCalls,
    currentProposal,
    streamEvents,
    sessionId,
    sendStreamingMessage,
    stopStreaming,
    confirmTool,
  }
}
