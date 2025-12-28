import { useState, useRef } from 'react'

interface ToolCall {
  name: string
  result: string
}

export interface ChatMessage {
  id: string
  type: 'user' | 'ai'
  content: string
  timestamp: Date
  toolCalls?: ToolCall[]
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
  const abortControllerRef = useRef<AbortController | null>(null)
  // 使用 ref 作为立即生效的锁，因为 useState 更新是异步的
  const isStreamingLockRef = useRef(false)

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
                  // 流式传输完成，创建完整的AI消息
                  const aiMessage: ChatMessage = {
                    id: Date.now().toString(),
                    type: 'ai',
                    content: streamingContent,
                    timestamp: new Date(),
                    toolCalls: toolCalls.length > 0 ? toolCalls : undefined
                  }
                  onMessage?.(aiMessage)
                  setCurrentStreamingMessage('')
                  setCurrentToolCalls([])
                  return
                }

                if (data.qr_images && Array.isArray(data.qr_images) && data.qr_images.length > 0) {
                  onQrImages?.(data.qr_images)
                }

                if (data.tool_calls && Array.isArray(data.tool_calls)) {
                  toolCalls = data.tool_calls
                  setCurrentToolCalls(toolCalls)
                }

                // 处理简历更新
                if (data.resume_content) {
                  onResumeUpdate?.(data.resume_content)
                }

                if (data.content) {
                  streamingContent += data.content
                  setCurrentStreamingMessage(streamingContent)
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
      abortControllerRef.current = null
    }
  }

  const stopStreaming = () => {
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
    }
  }

  return {
    isStreaming,
    currentStreamingMessage,
    currentToolCalls,
    sendStreamingMessage,
    stopStreaming
  }
}
