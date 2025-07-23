'use client'

import { useState, useRef, useCallback } from 'react'

interface ChatMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp?: Date
}

interface Suggestion {
  suggestion_type: string
  section: string
  original_content?: string
  suggested_content: string
  reasoning: string
  apply_action?: string
}

interface UseResumeOptimizerAgentOptions {
  resumeId: number
  targetJob?: string
  onError?: (error: string) => void
  onSuggestion?: (suggestions: Suggestion[]) => void
}

export function useResumeOptimizerAgent({
  resumeId,
  targetJob,
  onError,
  onSuggestion
}: UseResumeOptimizerAgentOptions) {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [isStreaming, setIsStreaming] = useState(false)
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState('')
  const [currentTargetJob, setCurrentTargetJob] = useState(targetJob)
  
  const eventSourceRef = useRef<EventSource | null>(null)
  const abortControllerRef = useRef<AbortController | null>(null)

  const sendMessage = useCallback(async (message: string) => {
    if (isStreaming || !message.trim()) return

    // 添加用户消息到历史
    const userMessage: ChatMessage = {
      role: 'user',
      content: message,
      timestamp: new Date()
    }
    
    setMessages(prev => [...prev, userMessage])
    setIsStreaming(true)
    setCurrentStreamingMessage('')

    try {
      const token = localStorage.getItem('access_token')
      if (!token) {
        throw new Error('未找到认证令牌')
      }

      // 构建请求体
      const requestBody = {
        resume_id: resumeId,
        target_job: currentTargetJob,
        history: messages.map(msg => ({
          role: msg.role,
          content: msg.content
        }))
      }

      // 发送POST请求到流式接口
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/ai/resume-optimizer-chat`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(requestBody)
      })

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`)
      }

      const reader = response.body?.getReader()
      if (!reader) {
        throw new Error('无法读取响应流')
      }

      const decoder = new TextDecoder()
      let aiMessageContent = ''

      while (true) {
        const { done, value } = await reader.read()
        
        if (done) break

        const chunk = decoder.decode(value, { stream: true })
        const lines = chunk.split('\n')

        for (const line of lines) {
          if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6))
              
              if (data.error) {
                onError?.(data.error)
                setIsStreaming(false)
                return
              }
              
              if (data.content) {
                aiMessageContent += data.content
                setCurrentStreamingMessage(aiMessageContent)
              }
              
              if (data.suggestions) {
                // 处理建议数据
                onSuggestion?.(data.suggestions)
              }
              
              if (data.done) {
                // 流式传输完成
                if (aiMessageContent) {
                  const aiMessage: ChatMessage = {
                    role: 'assistant',
                    content: aiMessageContent,
                    timestamp: new Date()
                  }
                  setMessages(prev => [...prev, aiMessage])
                }
                setCurrentStreamingMessage('')
                setIsStreaming(false)
                return
              }
              
            } catch (e) {
              console.warn('解析SSE数据失败:', e)
            }
          }
        }
      }

    } catch (error: any) {
      console.error('发送消息失败:', error)
      onError?.(error.message || '发送消息失败')
      setIsStreaming(false)
      setCurrentStreamingMessage('')
    }
  }, [resumeId, currentTargetJob, messages, isStreaming, onError, onSuggestion])

  const applySuggestion = useCallback(async (suggestion: Suggestion): Promise<void> => {
    try {
      const token = localStorage.getItem('access_token')
      if (!token) {
        throw new Error('未找到认证令牌')
      }

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/v1/ai/resume-optimizer/apply-suggestion`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          resume_id: resumeId,
          section: suggestion.section,
          suggestion: suggestion
        })
      })

      if (!response.ok) {
        const errorData = await response.json()
        throw new Error(errorData.detail || '应用建议失败')
      }

      const result = await response.json()
      
      // 自动添加确认消息到对话历史
      const confirmMessage: ChatMessage = {
        role: 'user',
        content: `我已采纳了关于"${suggestion.section}"的建议：${suggestion.suggested_content}`,
        timestamp: new Date()
      }
      
      setMessages(prev => [...prev, confirmMessage])
      
      return result

    } catch (error: any) {
      console.error('应用建议失败:', error)
      throw error
    }
  }, [resumeId])

  const setTargetJob = useCallback((job: string) => {
    setCurrentTargetJob(job)
  }, [])

  const clearHistory = useCallback(() => {
    setMessages([])
    setCurrentStreamingMessage('')
    setIsStreaming(false)
  }, [])

  const stopStreaming = useCallback(() => {
    if (eventSourceRef.current) {
      eventSourceRef.current.close()
      eventSourceRef.current = null
    }
    
    if (abortControllerRef.current) {
      abortControllerRef.current.abort()
      abortControllerRef.current = null
    }
    
    setIsStreaming(false)
    setCurrentStreamingMessage('')
  }, [])

  return {
    messages,
    isStreaming,
    currentStreamingMessage,
    targetJob: currentTargetJob,
    sendMessage,
    applySuggestion,
    setTargetJob,
    clearHistory,
    stopStreaming
  }
}