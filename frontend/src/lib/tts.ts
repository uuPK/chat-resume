/**
 * TTS (Text-to-Speech) 服务
 * 提供文本转语音和语音播放功能
 */

interface TTSRequest {
  text: string
  voice_id?: string
  emotion?: string
  model?: string
  format?: string
  sample_rate?: number
}

interface TTSResponse {
  success: boolean
  data: {
    audio_url?: string
    audio_base64?: string
    duration?: number
    format: string
    sample_rate: number
  }
  message: string
}

interface VoiceConfig {
  voice_id: string
  emotion: string
  description: string
}

class TTSService {
  private apiBase: string
  private audioCache: Map<string, string> = new Map()
  private currentAudio: HTMLAudioElement | null = null

  constructor() {
    this.apiBase = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
  }

  /**
   * 获取认证头部
   */
  private getAuthHeaders(): Record<string, string> {
    const token = localStorage.getItem('access_token')
    return token ? { 'Authorization': `Bearer ${token}` } : {}
  }

  /**
   * 文本转语音
   */
  async textToSpeech(request: TTSRequest): Promise<TTSResponse> {
    try {
      const response = await fetch(`${this.apiBase}/api/tts/text-to-speech`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders()
        },
        body: JSON.stringify(request)
      })

      if (!response.ok) {
        throw new Error(`TTS API请求失败: ${response.status}`)
      }

      const result = await response.json()
      return result
    } catch (error) {
      console.error('TTS服务错误:', error)
      throw error
    }
  }

  /**
   * 面试问题语音生成
   */
  async generateInterviewQuestionSpeech(
    text: string,
    voiceConfig?: Partial<VoiceConfig>
  ): Promise<TTSResponse> {
    const request: TTSRequest = {
      text,
      voice_id: voiceConfig?.voice_id || 'female-tianmei-jingpin',
      emotion: voiceConfig?.emotion || 'neutral',
      model: 'speech-02-turbo',
      format: 'mp3',
      sample_rate: 32000
    }

    console.log('[TTS] 开始生成面试问题语音:', { textLength: text.length, voiceId: request.voice_id })

    try {
      const response = await fetch(`${this.apiBase}/api/tts/interview-question-speech`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          ...this.getAuthHeaders()
        },
        body: JSON.stringify(request)
      })

      console.log('[TTS] API响应状态:', response.status, response.statusText)

      if (!response.ok) {
        const errorText = await response.text()
        console.error('[TTS] API错误响应:', errorText)
        throw new Error(`面试问题TTS API请求失败: ${response.status}`)
      }

      const result = await response.json()
      console.log('[TTS] API响应成功:', {
        success: result.success,
        hasAudioBase64: !!result.data?.audio_base64,
        audioBase64Length: result.data?.audio_base64?.length,
        format: result.data?.format
      })
      return result
    } catch (error) {
      console.error('[TTS] 面试问题TTS服务错误:', error)
      throw error
    }
  }

  /**
   * 检查是否有用户交互（用于自动播放策略）
   */
  private hasUserInteraction: boolean = false

  /**
   * 标记用户已交互（应在用户点击时调用）
   */
  markUserInteraction(): void {
    this.hasUserInteraction = true
  }

  /**
   * 播放语音
   */
  async playAudio(audioUrl: string): Promise<void> {
    return new Promise((resolve, reject) => {
      // 停止当前播放的音频
      this.stopAudio()

      this.currentAudio = new Audio(audioUrl)

      this.currentAudio.addEventListener('ended', () => {
        resolve()
      })

      this.currentAudio.addEventListener('error', (error) => {
        console.error('[TTS] 音频播放错误:', error)
        reject(error)
      })

      // 尝试播放，处理自动播放限制
      this.currentAudio.play()
        .then(() => {
          console.log('[TTS] 音频开始播放')
          this.hasUserInteraction = true // 播放成功意味着有用户交互权限
        })
        .catch((error) => {
          if (error.name === 'NotAllowedError') {
            console.warn('[TTS] 浏览器阻止自动播放，需要用户交互后才能播放')
            // 创建一个友好的提示，让用户知道需要手动点击
            reject(new Error('请先点击页面任意位置以启用音频播放功能'))
          } else {
            reject(error)
          }
        })
    })
  }

  /**
   * 播放Base64音频
   */
  async playBase64Audio(base64Data: string, format: string = 'mp3'): Promise<void> {
    const audioUrl = `data:audio/${format};base64,${base64Data}`
    return this.playAudio(audioUrl)
  }

  /**
   * 停止音频播放
   */
  stopAudio(): void {
    if (this.currentAudio) {
      this.currentAudio.pause()
      this.currentAudio.currentTime = 0
      this.currentAudio = null
    }
  }

  /**
   * 获取面试官音色配置
   */
  async getInterviewerVoices(): Promise<Record<string, VoiceConfig>> {
    try {
      const response = await fetch(`${this.apiBase}/api/tts/interviewer-voices`, {
        method: 'GET',
        headers: this.getAuthHeaders()
      })

      if (!response.ok) {
        throw new Error(`获取面试官音色配置失败: ${response.status}`)
      }

      const result = await response.json()
      return result.data
    } catch (error) {
      console.error('获取面试官音色配置错误:', error)
      throw error
    }
  }

  /**
   * 获取可用音色列表
   */
  async getVoiceList(): Promise<any[]> {
    try {
      const response = await fetch(`${this.apiBase}/api/tts/voices`, {
        method: 'GET',
        headers: this.getAuthHeaders()
      })

      if (!response.ok) {
        throw new Error(`获取音色列表失败: ${response.status}`)
      }

      const result = await response.json()
      return result.data
    } catch (error) {
      console.error('获取音色列表错误:', error)
      throw error
    }
  }

  /**
   * 缓存音频
   */
  cacheAudio(key: string, audioUrl: string): void {
    this.audioCache.set(key, audioUrl)
  }

  /**
   * 获取缓存的音频
   */
  getCachedAudio(key: string): string | undefined {
    return this.audioCache.get(key)
  }

  /**
   * 清空音频缓存
   */
  clearAudioCache(): void {
    this.audioCache.clear()
  }

  /**
   * 检查是否正在播放
   */
  isPlaying(): boolean {
    return this.currentAudio !== null && !this.currentAudio.paused
  }
}

// 导出单例实例
export const ttsService = new TTSService()
export default ttsService