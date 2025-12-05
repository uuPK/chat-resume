import { useState, useRef, useEffect, useCallback } from 'react'
import { interviewApi } from '@/lib/api'

interface ChatMessage {
  id: string
  type: 'user' | 'ai'
  content: string
  timestamp: Date
}

interface InterviewSession {
  id: number
  resumeId: number
  status: 'active' | 'completed' | 'paused'
  startTime: Date
  questions: any[]
  answers: any[]
  currentQuestionIndex: number
}

interface InterviewHookOptions {
  onMessage?: (message: ChatMessage) => void
  onError?: (error: string) => void
  apiBaseUrl?: string
  jobPosition?: string
  jdContent?: string
  existingSessionId?: number | null
}

export function useInterview(resumeId: number, options: InterviewHookOptions = {}) {
  const [isInterviewActive, setIsInterviewActive] = useState(false)
  const [currentSession, setCurrentSession] = useState<InterviewSession | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [currentStreamingMessage, setCurrentStreamingMessage] = useState('')
  const [hasAutoLoaded, setHasAutoLoaded] = useState(false) // 防止重复自动加载
  
  
  const {
    onMessage,
    onError,
    apiBaseUrl = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000',
    jobPosition,
    jdContent,
    existingSessionId
  } = options

  // 稳定的回调函数引用  
  const stableOnMessage = useCallback((message: ChatMessage) => {
    onMessage?.(message)
  }, [onMessage])

  const stableOnError = useCallback((error: string) => {
    onError?.(error)
  }, [onError])

  // 加载现有面试会话
  const loadExistingSession = useCallback(async (sessionId: number) => {
    console.log('loadExistingSession started for session:', sessionId)
    setIsLoading(true)
    
    try {
      console.log('获取面试会话列表...')
      // 首先获取会话详情，检查状态
      const sessions = await interviewApi.getInterviewSessions(resumeId)
      console.log('面试会话列表:', sessions.map(s => ({ id: s.id, status: s.status })))
      
      const existingSession = sessions.find(s => s.id === sessionId)
      console.log('找到的会话:', existingSession ? { id: existingSession.id, status: existingSession.status } : '未找到')
      
      if (!existingSession) {
        throw new Error('面试会话不存在')
      }
      
      if (existingSession.status === 'completed') {
        stableOnError('该面试已经完成，无法继续')
        return null
      }
      
      // 计算已完成的问题数和当前问题索引
      const answeredCount = (existingSession.answers || []).length
      const totalQuestions = (existingSession.questions || []).length
      const currentQuestionIndex = answeredCount // 当前应该回答的问题索引
      
      console.log(`面试状态分析: 已回答${answeredCount}题，总共${totalQuestions}题，当前问题索引: ${currentQuestionIndex}`)
      
      // 创建本地面试会话状态
      const session: InterviewSession = {
        id: sessionId,
        resumeId,
        status: 'active',
        startTime: new Date(existingSession.created_at),
        questions: existingSession.questions || [],
        answers: existingSession.answers || [],
        currentQuestionIndex: currentQuestionIndex
      }

      console.log('设置面试会话状态...')
      setCurrentSession(session)
      setIsInterviewActive(true)
      console.log('面试状态已设置为活跃')
      
      // 检查是否还有问题需要回答
      if (currentQuestionIndex < totalQuestions) {
        // 还有预设问题未回答
        const currentQuestion = existingSession.questions[currentQuestionIndex]
        console.log('发送继续面试消息...')
        const welcomeMessage: ChatMessage = {
          id: `ai_continue_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          type: 'ai',
          content: `欢迎回到面试！您已完成 ${answeredCount}/${totalQuestions} 题。让我们继续您的面试。\n\n**当前问题：**\n${currentQuestion.question}`,
          timestamp: new Date()
        }
        stableOnMessage(welcomeMessage)
      } else if (answeredCount === totalQuestions && totalQuestions > 0) {
        // 已完成所有预设问题，可以生成新问题或结束面试
        console.log('所有预设问题已完成，发送继续消息...')
        const welcomeMessage: ChatMessage = {
          id: `ai_continue_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          type: 'ai',
          content: `欢迎回到面试！您已完成所有预设问题 ${answeredCount}/${totalQuestions}。我可以为您提出一些深入的问题，或者您可以选择结束面试。请告诉我您想继续还是结束面试？`,
          timestamp: new Date()
        }
        stableOnMessage(welcomeMessage)
      } else {
        // 异常情况
        console.log('发送默认欢迎消息...')
        const welcomeMessage: ChatMessage = {
          id: `ai_continue_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          type: 'ai',
          content: `欢迎回到面试！让我们继续您的面试。`,
          timestamp: new Date()
        }
        stableOnMessage(welcomeMessage)
      }
      console.log('欢迎消息已发送')
      
      return session
    } catch (error) {
      console.error('Load existing session error:', error)
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      
      // 提供更详细的错误信息
      if (errorMessage.includes('404')) {
        stableOnError('面试会话不存在或已被删除')
      } else if (errorMessage.includes('403')) {
        stableOnError('无权限访问该面试会话')
      } else if (errorMessage.includes('Failed to fetch')) {
        stableOnError('网络连接失败，请检查网络连接后重试')
      } else {
        stableOnError(`加载面试会话失败: ${errorMessage}`)
      }
      
      return null
    } finally {
      setIsLoading(false)
    }
  }, [resumeId, stableOnMessage, stableOnError])

  // 当existingSessionId变化时重置自动加载状态
  useEffect(() => {
    if (existingSessionId) {
      console.log('existingSessionId changed to:', existingSessionId, 'resetting hasAutoLoaded')
      setHasAutoLoaded(false)
    }
  }, [existingSessionId])

  // 自动加载现有会话
  useEffect(() => {
    if (existingSessionId && !hasAutoLoaded && !isInterviewActive && !isLoading && resumeId) {
      console.log('Auto-loading existing session:', existingSessionId)
      setHasAutoLoaded(true)
      loadExistingSession(existingSessionId)
    }
  }, [existingSessionId, hasAutoLoaded, isInterviewActive, isLoading, resumeId])

  // 开始面试会话
  const startInterview = async (jdContent?: string) => {
    console.log('startInterview called with:', {
      existingSessionId,
      isInterviewActive,
      resumeId,
      isLoading,
      currentSession: currentSession?.id,
      hasAutoLoaded
    })

    if (isInterviewActive) {
      console.log('面试已经活跃，返回现有会话:', currentSession?.id)
      return currentSession
    }

    // 如果有现有会话ID，但还没有自动加载，则不应该在这里处理
    // Hook的useEffect会自动处理现有会话的加载
    if (existingSessionId && !hasAutoLoaded) {
      console.log('现有会话将由Hook自动加载，跳过手动处理')
      return null
    }

    // 如果有现有会话ID且已经尝试过自动加载，但仍然调用了这里，说明需要重新加载
    if (existingSessionId && hasAutoLoaded) {
      console.log('重新加载现有会话:', existingSessionId)
      const session = await loadExistingSession(existingSessionId)
      console.log('现有会话重新加载结果:', session ? `成功 (ID: ${session.id})` : '失败')
      return session
    }

    setIsLoading(true)

    try {
      // 使用结构化的面试API创建新会话
      const backendSession = await interviewApi.startInterview(resumeId, {
        job_position: jobPosition || '未指定职位',
        jd_content: jdContent || ''
      })

      console.log('面试会话已创建:', backendSession)

      // 创建本地面试会话状态
      const session: InterviewSession = {
        id: backendSession.id,
        resumeId,
        status: 'active',
        startTime: new Date(),
        questions: backendSession.questions || [],
        answers: backendSession.answers || [],
        currentQuestionIndex: 0
      }

      setCurrentSession(session)
      setIsInterviewActive(true)
      
      // 获取第一个问题
      try {
        const firstQuestion = await interviewApi.getNextInterviewQuestion(resumeId, backendSession.id)
        
        const welcomeMessage: ChatMessage = {
          id: `ai_welcome_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          type: 'ai',
          content: `您好！我是您的AI面试官。今天我将基于您的简历进行模拟面试。\n\n${firstQuestion.question}`,
          timestamp: new Date()
        }
        stableOnMessage(welcomeMessage)
        
        // 更新会话状态，记录当前问题
        setCurrentSession(prev => prev ? {
          ...prev,
          currentQuestionIndex: firstQuestion.question_index
        } : null)
        
      } catch (error) {
        console.error('获取第一个问题失败:', error)
        // 使用默认欢迎消息
        const welcomeMessage: ChatMessage = {
          id: `ai_fallback_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          type: 'ai',
          content: `您好！我是您的AI面试官。今天我将基于您的简历进行模拟面试。请先做一个简单的自我介绍，包括您的姓名、职位和主要工作经验。`,
          timestamp: new Date()
        }
        stableOnMessage(welcomeMessage)
      }
      
      return session
    } catch (error) {
      console.error('Start interview error:', error)
      const errorMessage = error instanceof Error ? error.message : 'Unknown error'
      stableOnError(errorMessage)
      return null
    } finally {
      setIsLoading(false)
    }
  }

  // 发送面试答案并获取下一个问题
  const sendAnswer = async (answer: string) => {
    if (!currentSession || !isInterviewActive) return

    setIsLoading(true)
    
    try {
      // 发送用户答案消息
      const userMessage: ChatMessage = {
        id: `user_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        type: 'user',
        content: answer,
        timestamp: new Date()
      }
      stableOnMessage(userMessage)

      // 检查当前问题索引是否有效
      if (currentSession.currentQuestionIndex >= currentSession.questions.length) {
        // 所有预设问题已完成，需要生成新问题或结束面试
        const aiMessage: ChatMessage = {
          id: `ai_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
          type: 'ai',
          content: `感谢您的回答！您已经完成了所有预设的面试问题。\n\n🎉 恭喜您完成面试！您可以选择结束面试查看详细报告，或者我可以为您提出一些额外的深入问题。请告诉我您的选择。`,
          timestamp: new Date()
        }
        stableOnMessage(aiMessage)
        return
      }

      // 提交答案到后端并获取评估
      const evaluation = await interviewApi.submitInterviewAnswer(
        resumeId, 
        currentSession.id, 
        answer, 
        currentSession.currentQuestionIndex
      )
      
      console.log('答案评估结果:', evaluation)

      // 直接使用面试官的自然回应，不再单独获取下一个问题
      const aiMessage: ChatMessage = {
        id: `ai_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        type: 'ai',
        content: evaluation.feedback || '好的，让我们继续下一个问题。',
        timestamp: new Date()
      }
      stableOnMessage(aiMessage)
      
      // 更新会话状态，记录当前答案并增加问题索引
      setCurrentSession(prev => prev ? {
        ...prev,
        currentQuestionIndex: prev.currentQuestionIndex + 1,
        answers: [...prev.answers, {
          answer,
          evaluation: evaluation.evaluation,
          question_index: currentSession.currentQuestionIndex
        }]
      } : null)
      
    } catch (error) {
      console.error('Send answer error:', error)
      let errorMessage = 'Unknown error'
      
      if (error instanceof Error) {
        if (error.message.includes('Load failed') || error.message.includes('fetch')) {
          errorMessage = '网络连接失败，请检查后端服务是否运行'
        } else if (error.message.includes('Failed to fetch')) {
          errorMessage = '无法连接到服务器，请检查网络连接'
        } else {
          errorMessage = error.message
        }
      }
      
      stableOnError(errorMessage)
    } finally {
      setIsLoading(false)
      setCurrentStreamingMessage('')
    }
  }

  // 结束面试
  const endInterview = async () => {
    if (!currentSession) return

    try {
      // 调用结构化的面试API结束会话
      await interviewApi.endInterview(resumeId, currentSession.id)
      console.log('面试会话已结束并保存')
      
      setIsInterviewActive(false)
      
      const endMessage: ChatMessage = {
        id: `ai_end_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`,
        type: 'ai',
        content: `面试结束！感谢您的参与。\n\n**面试问题数**: ${currentSession.answers.length}\n**面试时长**: ${Math.floor((Date.now() - currentSession.startTime.getTime()) / 1000 / 60)} 分钟\n\n您可以回到简历编辑页面继续优化简历，或查看面试反馈报告。`,
        timestamp: new Date()
      }
      
      stableOnMessage(endMessage)
      setCurrentSession(null)
      
    } catch (error) {
      console.error('End interview error:', error)
      stableOnError('结束面试时出现错误')
    }
  }

  // 停止当前请求 (保留接口兼容性，但不再需要实际功能)
  const stopCurrentRequest = () => {
    // 新的API不使用流式请求，无需中断
    console.log('Stop request called - no action needed with structured API')
  }

  return {
    isInterviewActive,
    currentSession,
    isLoading,
    currentStreamingMessage,
    startInterview,
    sendAnswer,
    endInterview,
    stopCurrentRequest
  }
}