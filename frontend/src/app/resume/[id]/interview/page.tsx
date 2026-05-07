'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
import {
  ArrowLeftIcon,
  MicrophoneIcon,
  PhoneXMarkIcon,
  SpeakerWaveIcon,
  SpeakerXMarkIcon,
  Cog6ToothIcon,
} from '@heroicons/react/24/outline'
import { useAuth } from '@/lib/auth'
import { digitalHumanApi, resumeApi } from '@/lib/api'
import type { DigitalHumanConversation, Resume } from '@/lib/api'
import { useInterviewSession } from '@/hooks/useInterviewSession'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const SEND_SAMPLE_RATE = 16000
const SEND_CHUNK_FRAMES = 1600

declare global {
  interface Window {
    __chatResumeVoiceCleanup?: () => void
  }
}

type VoiceStatus = 'idle' | 'connecting' | 'connected' | 'error'
type ConversationMessage = {
  id: string
  role: 'candidate' | 'interviewer'
  content: string
  isFinal?: boolean
}

interface VoicePanelProps {
  sessionId: string | undefined
  autoStart?: boolean
  onStatusChange?: (status: VoiceStatus) => void
}

function VoicePanel({ sessionId, autoStart = false, onStatusChange }: VoicePanelProps) {
  const [status, setStatus] = useState<VoiceStatus>('idle')
  const [transcript, setTranscript] = useState('')
  const [muted, setMuted] = useState(false)
  const [inputLevel, setInputLevel] = useState(0)
  const [audioDevices, setAudioDevices] = useState<MediaDeviceInfo[]>([])
  const [selectedDeviceId, setSelectedDeviceId] = useState('')
  const [activeDeviceLabel, setActiveDeviceLabel] = useState('')
  const [messages, setMessages] = useState<ConversationMessage[]>([])
  const [liveMessage, setLiveMessage] = useState<ConversationMessage | null>(null)
  const [showDeviceMenu, setShowDeviceMenu] = useState(false)

  const wsRef = useRef<WebSocket | null>(null)
  const audioCtxRef = useRef<AudioContext | null>(null)
  const streamRef = useRef<MediaStream | null>(null)
  const processorRef = useRef<ScriptProcessorNode | null>(null)
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null)
  const gainRef = useRef<GainNode | null>(null)
  const playbackQueueRef = useRef<Float32Array[]>([])
  const captureQueueRef = useRef<number[]>([])
  const sendQueueRef = useRef<ArrayBuffer[]>([])
  const sendTimerRef = useRef<number | null>(null)
  const candidateFinalizeTimerRef = useRef<number | null>(null)
  const isPlayingRef = useRef(false)
  const userStoppedRef = useRef(false)
  const liveTextRef = useRef<Record<ConversationMessage['role'], string>>({
    candidate: '',
    interviewer: '',
  })
  const messagesEndRef = useRef<HTMLDivElement>(null)

  const updateStatus = useCallback(
    (s: VoiceStatus) => {
      setStatus(s)
      onStatusChange?.(s)
    },
    [onStatusChange],
  )

  const normalizeTranscriptText = useCallback((content: string) => (
    content.replace(/\s+/g, '').trim()
  ), [])

  const isNoiseTranscript = useCallback((text: string) => (
    !text || text === '?' || text === '？' || /^[，,。.!！、；;：:\s]+$/.test(text)
  ), [])

  const appendMessage = useCallback((role: ConversationMessage['role'], content: string) => {
    const text = content.trim()
    if (isNoiseTranscript(text)) return
    setMessages((current) => {
      const lastMessage = current[current.length - 1]
      if (
        lastMessage?.role === role &&
        normalizeTranscriptText(lastMessage.content) === normalizeTranscriptText(text)
      ) {
        return current
      }
      return [
        ...current,
        {
          id: `${role}-${Date.now()}-${current.length}`,
          role,
          content: text,
          isFinal: true,
        },
      ]
    })
  }, [isNoiseTranscript, normalizeTranscriptText])

  const clearCandidateFinalizeTimer = useCallback(() => {
    if (candidateFinalizeTimerRef.current) {
      window.clearTimeout(candidateFinalizeTimerRef.current)
      candidateFinalizeTimerRef.current = null
    }
  }, [])

  const handleStreamingText = useCallback((
    role: ConversationMessage['role'],
    content: string,
    isFinal = false,
  ) => {
    const text = content.trim()
    if (isNoiseTranscript(text)) return

    const previousText = liveTextRef.current[role]
    const normalizedPrevious = normalizeTranscriptText(previousText)
    const normalizedNext = normalizeTranscriptText(text)
    const nextText = previousText
      ? (
          normalizedNext.startsWith(normalizedPrevious)
            ? text
            : `${previousText}${text}`
        )
      : text

    liveTextRef.current[role] = nextText
    setLiveMessage({ id: `${role}-live`, role, content: nextText })

    if (isFinal) {
      appendMessage(role, liveTextRef.current[role])
      liveTextRef.current[role] = ''
      setLiveMessage(null)
    }
  }, [appendMessage, isNoiseTranscript, normalizeTranscriptText])

  const flushLiveText = useCallback((role: ConversationMessage['role']) => {
    if (role === 'candidate') {
      clearCandidateFinalizeTimer()
    }
    appendMessage(role, liveTextRef.current[role])
    liveTextRef.current[role] = ''
    setLiveMessage((current) => current?.role === role ? null : current)
  }, [appendMessage, clearCandidateFinalizeTimer])

  const handleCandidateText = useCallback((content: string, isFinal = false) => {
    const text = content.trim()
    if (isNoiseTranscript(text)) return

    const previousText = liveTextRef.current.candidate
    const normalizedPrevious = normalizeTranscriptText(previousText)
    const normalizedNext = normalizeTranscriptText(text)
    const nextText = (
      !previousText ||
      normalizedNext === normalizedPrevious ||
      normalizedNext.includes(normalizedPrevious) ||
      normalizedPrevious.includes(normalizedNext)
    )
      ? text
      : `${previousText}${text}`

    liveTextRef.current.candidate = nextText
    setLiveMessage({ id: 'candidate-live', role: 'candidate', content: nextText })

    clearCandidateFinalizeTimer()
    if (isFinal) {
      flushLiveText('candidate')
      return
    }
    candidateFinalizeTimerRef.current = window.setTimeout(() => {
      flushLiveText('candidate')
    }, 1200)
  }, [
    clearCandidateFinalizeTimer,
    flushLiveText,
    isNoiseTranscript,
    normalizeTranscriptText,
  ])

  const stopAll = useCallback((manual = false) => {
    if (manual) {
      userStoppedRef.current = true
    }
    if (processorRef.current) {
      processorRef.current.disconnect()
      processorRef.current = null
    }
    if (sourceRef.current) {
      sourceRef.current.disconnect()
      sourceRef.current = null
    }
    if (gainRef.current) {
      gainRef.current.disconnect()
      gainRef.current = null
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop())
      streamRef.current = null
    }
    if (audioCtxRef.current && audioCtxRef.current.state !== 'closed') {
      audioCtxRef.current.close().catch(() => {})
      audioCtxRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    if (sendTimerRef.current) {
      window.clearInterval(sendTimerRef.current)
      sendTimerRef.current = null
    }
    clearCandidateFinalizeTimer()
    playbackQueueRef.current = []
    captureQueueRef.current = []
    sendQueueRef.current = []
    isPlayingRef.current = false
    setInputLevel(0)
    updateStatus('idle')
  }, [clearCandidateFinalizeTimer, updateStatus])

  useEffect(() => {
    return () => { stopAll() }
  }, [stopAll])

  const playPcmChunk = useCallback((pcmBytes: ArrayBuffer) => {
    const ctx = audioCtxRef.current
    if (!ctx || ctx.state === 'closed') return

    const int16 = new Int16Array(pcmBytes)
    const floats = new Float32Array(int16.length)
    for (let i = 0; i < int16.length; i++) {
      floats[i] = int16[i] / 32768
    }
    playbackQueueRef.current.push(floats)

    if (!isPlayingRef.current) {
      isPlayingRef.current = true
      const drain = () => {
        if (!ctx || ctx.state === 'closed') return
        const next = playbackQueueRef.current.shift()
        if (!next) {
          isPlayingRef.current = false
          return
        }
        const buf = ctx.createBuffer(1, next.length, 24000)
        buf.copyToChannel(next, 0)
        const src = ctx.createBufferSource()
        src.buffer = buf
        src.connect(ctx.destination)
        src.onended = drain
        src.start()
      }
      drain()
    }
  }, [])

  const enqueueInputAudio = useCallback((inputData: Float32Array, inputSampleRate: number) => {
    if (muted || !wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return

    let squareSum = 0
    let peak = 0
    for (let i = 0; i < inputData.length; i += 1) {
      const sample = inputData[i]
      squareSum += sample * sample
      peak = Math.max(peak, Math.abs(sample))
    }
    const rms = inputData.length ? Math.sqrt(squareSum / inputData.length) : 0
    setInputLevel(Math.max(rms, peak * 0.35))

    const ratio = inputSampleRate / SEND_SAMPLE_RATE
    const outputLength = Math.floor(inputData.length / ratio)
    for (let outputIndex = 0; outputIndex < outputLength; outputIndex += 1) {
      const inputIndex = outputIndex * ratio
      const beforeIndex = Math.floor(inputIndex)
      const afterIndex = Math.min(beforeIndex + 1, inputData.length - 1)
      const weight = inputIndex - beforeIndex
      const sample = inputData[beforeIndex] * (1 - weight) + inputData[afterIndex] * weight
      captureQueueRef.current.push(Math.max(-1, Math.min(1, sample)))
    }

    while (captureQueueRef.current.length >= SEND_CHUNK_FRAMES) {
      const chunk = captureQueueRef.current.splice(0, SEND_CHUNK_FRAMES)
      const pcm = new Int16Array(SEND_CHUNK_FRAMES)
      for (let i = 0; i < SEND_CHUNK_FRAMES; i += 1) {
        const sample = chunk[i]
        pcm[i] = sample < 0 ? sample * 0x8000 : sample * 0x7fff
      }
      sendQueueRef.current.push(pcm.buffer)
      if (sendQueueRef.current.length > 20) {
        sendQueueRef.current.splice(0, sendQueueRef.current.length - 20)
      }
    }
  }, [muted])

  const startVoice = useCallback(async () => {
    if (!sessionId || wsRef.current) return
    window.__chatResumeVoiceCleanup?.()
    window.__chatResumeVoiceCleanup = () => stopAll(true)
    userStoppedRef.current = false
    updateStatus('connecting')
    setTranscript('')
    setMessages([])
    setLiveMessage(null)
    liveTextRef.current = { candidate: '', interviewer: '' }

    try {
      const ctx = new AudioContext()
      await ctx.resume()
      audioCtxRef.current = ctx

      const stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          autoGainControl: true,
          channelCount: 1,
          echoCancellation: false,
          deviceId: selectedDeviceId ? { exact: selectedDeviceId } : undefined,
          noiseSuppression: false,
        },
      })
      streamRef.current = stream
      const [track] = stream.getAudioTracks()
      setActiveDeviceLabel(track?.label || '默认麦克风')
      navigator.mediaDevices.enumerateDevices()
        .then((devices) => {
          setAudioDevices(devices.filter((device) => device.kind === 'audioinput'))
        })
        .catch(() => {})

      const wsUrl = `${API_BASE_URL.replace(/^http/, 'ws')}/api/digital-human/voice-session/${sessionId}`
      const ws = new WebSocket(wsUrl)
      ws.binaryType = 'arraybuffer'
      wsRef.current = ws

      ws.onmessage = (ev) => {
        if (ev.data instanceof ArrayBuffer) {
          playPcmChunk(ev.data)
          return
        }
        try {
          const msg = JSON.parse(ev.data)
          if (msg.type === 'ready') {
            updateStatus('connected')
            setTranscript('语音已连接，请开始说话')
          } else if (msg.type === 'event') {
            if (msg.event === 451) {
              const results: Array<{ text: string }> = msg.data?.results || []
              const text = msg.text || results.map((r) => r.text).join('')
              if (text) {
                setTranscript(`你: ${text}`)
                handleCandidateText(text, msg.is_final)
              }
            } else if (msg.event === 459) {
              const text = msg.text || msg.data?.text || ''
              if (text) {
                handleCandidateText(text, true)
              } else {
                flushLiveText('candidate')
              }
            } else if (msg.event === 550) {
              const text = msg.text || msg.data?.content || msg.data?.text || ''
              if (text) {
                setTranscript(`面试官: ${text}`)
                handleStreamingText('interviewer', text, msg.is_final)
              }
            } else if (msg.event === 559) {
              const text = msg.text || msg.data?.content || msg.data?.text || ''
              if (text) {
                handleStreamingText('interviewer', text, true)
              } else {
                flushLiveText('interviewer')
              }
            } else if (msg.text) {
              handleStreamingText('interviewer', msg.text, msg.is_final)
            }
          } else if (msg.type === 'error') {
            userStoppedRef.current = true
            setTranscript(`错误: ${msg.message}`)
            updateStatus('error')
          }
        } catch { /* ignore non-JSON */ }
      }

      ws.onerror = () => {
        userStoppedRef.current = true
        updateStatus('error')
        setTranscript('WebSocket 连接失败')
      }

      ws.onclose = () => {
        if (wsRef.current) {
          wsRef.current = null
          if (!userStoppedRef.current) {
            updateStatus('idle')
          }
        }
      }

      await new Promise<void>((resolve, reject) => {
        const timer = setTimeout(() => reject(new Error('连接超时')), 10000)
        const origOnOpen = ws.onopen
        ws.onopen = () => {
          clearTimeout(timer)
          origOnOpen?.call(ws, {} as Event)
          resolve()
        }
      })

      sendTimerRef.current = window.setInterval(() => {
        if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return
        const nextChunk = sendQueueRef.current.shift()
        if (nextChunk) {
          wsRef.current.send(nextChunk)
        }
      }, 100)

      const source = ctx.createMediaStreamSource(stream)
      const processor = ctx.createScriptProcessor(4096, 1, 1)
      const gain = ctx.createGain()
      gain.gain.value = 0
      sourceRef.current = source
      processorRef.current = processor
      gainRef.current = gain
      processor.onaudioprocess = (e) => {
        const inputData = e.inputBuffer.getChannelData(0)
        enqueueInputAudio(inputData, ctx.sampleRate)
      }
      source.connect(processor)
      processor.connect(gain)
      gain.connect(ctx.destination)
    } catch (err) {
      userStoppedRef.current = true
      updateStatus('error')
      setTranscript(err instanceof Error ? err.message : '启动语音失败')
    }
  }, [
    enqueueInputAudio,
    flushLiveText,
    handleCandidateText,
    handleStreamingText,
    selectedDeviceId,
    sessionId,
    playPcmChunk,
    stopAll,
    updateStatus,
  ])

  const toggleMute = useCallback(() => {
    setMuted((m) => !m)
  }, [])

  useEffect(() => {
    if (!autoStart || !sessionId || status !== 'idle' || userStoppedRef.current) return
    startVoice().catch(() => {})
  }, [autoStart, sessionId, startVoice, status])

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, liveMessage])

  const isSpeaking = liveMessage?.role === 'interviewer'
  const micBars = Array.from({ length: 12 }, (_, i) => {
    const threshold = (i + 1) / 12
    return inputLevel * 5 > threshold
  })

  return (
    <>
      <style>{`
        @keyframes ripple {
          0% { transform: scale(1); opacity: 0.45; }
          100% { transform: scale(2.4); opacity: 0; }
        }
        @keyframes soundwave {
          0%, 100% { transform: scaleY(0.25); }
          50% { transform: scaleY(1); }
        }
        @keyframes blink-cursor {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
        @keyframes orbit {
          from { transform: rotate(0deg) translateX(68px) rotate(0deg); }
          to   { transform: rotate(360deg) translateX(68px) rotate(-360deg); }
        }
        @keyframes fade-in-up {
          from { opacity: 0; transform: translateY(10px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        .ripple-ring {
          animation: ripple 2.4s ease-out infinite;
        }
        .wave-bar {
          animation: soundwave 0.75s ease-in-out infinite;
          transform-origin: bottom;
        }
        .blink-cursor {
          animation: blink-cursor 1s ease-in-out infinite;
        }
        .msg-enter {
          animation: fade-in-up 0.25s ease-out forwards;
        }
      `}</style>

      <div className="flex flex-col h-full">


        {/* ── Conversation ──────────────────────────────── */}
        <div className="flex-1 overflow-y-auto"
          style={{ background: 'rgba(15,23,42,0.5)' }}
        >
          <div className="mx-auto w-full max-w-4xl px-4 py-4 space-y-4 h-full">
          {messages.length === 0 && !liveMessage ? (
            <div className="flex flex-col items-center justify-center h-full gap-2 pointer-events-none select-none">
              <div className="w-10 h-10 rounded-full flex items-center justify-center" style={{ background: 'rgba(99,102,241,0.1)' }}>
                <MicrophoneIcon className="w-5 h-5 text-indigo-400" />
              </div>
              <p className="text-sm text-slate-500">语音连接后，对话将在这里显示</p>
            </div>
          ) : (
            <>
              {[...messages, ...(liveMessage ? [liveMessage] : [])].map((msg, idx) => {
                const isInterviewer = msg.role === 'interviewer'
                const isLive = msg === liveMessage
                return (
                  <div
                    key={msg.id}
                    className={`msg-enter flex gap-2.5 ${isInterviewer ? 'items-end' : 'items-end flex-row-reverse'}`}
                    style={{ animationDelay: `${Math.min(idx * 0.03, 0.15)}s` }}
                  >
                    {/* 头像 */}
                    {isInterviewer ? (
                      <div className="flex-shrink-0 w-[52px] h-[52px] rounded-full overflow-hidden" style={{ background: 'linear-gradient(135deg,#6366f1,#0d9488)' }}>
                        <svg width="52" height="52" viewBox="0 0 32 32" fill="none">
                          {/* 背景 */}
                          <rect width="32" height="32" fill="url(#avBg)" rx="16"/>
                          <defs>
                            <linearGradient id="avBg" x1="0" y1="0" x2="32" y2="32">
                              <stop offset="0%" stopColor="#6366f1"/>
                              <stop offset="100%" stopColor="#0d9488"/>
                            </linearGradient>
                            <linearGradient id="avSkin" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="#fde4ca"/>
                              <stop offset="100%" stopColor="#f5c09a"/>
                            </linearGradient>
                            <linearGradient id="avHair" x1="0" y1="0" x2="0" y2="1">
                              <stop offset="0%" stopColor="#4a2c0a"/>
                              <stop offset="100%" stopColor="#2a1506"/>
                            </linearGradient>
                          </defs>
                          {/* 头发后层 */}
                          <path d="M8 20 C7 25 7 32 8 32 L10 32 C9 28 9 22 10 18 Z" fill="url(#avHair)"/>
                          <path d="M24 20 C25 25 25 32 24 32 L22 32 C23 28 23 22 22 18 Z" fill="url(#avHair)"/>
                          {/* 衣服 */}
                          <path d="M4 32 C5 26 10 23 13 22 L16 24 L19 22 C22 23 27 26 28 32 Z" fill="#3b5998"/>
                          <path d="M13 22 L16 32 L19 22 L16 20 Z" fill="#c8d8f0"/>
                          {/* 脖子 */}
                          <rect x="14" y="18" width="4" height="5" rx="2" fill="url(#avSkin)"/>
                          {/* 脸 */}
                          <ellipse cx="16" cy="13" rx="6.5" ry="7" fill="url(#avSkin)"/>
                          {/* 头发顶 */}
                          <path d="M9.5 12 C9.5 5.5 22.5 5.5 22.5 12 C22.5 8 20 5 16 4.5 C12 5 9.5 8 9.5 12 Z" fill="url(#avHair)"/>
                          {/* 眉毛 */}
                          <path d="M12 10.5 C13 9.8 14 9.7 15 10" stroke="#3a1f08" strokeWidth="0.7" fill="none" strokeLinecap="round"/>
                          <path d="M17 10 C18 9.7 19 9.8 20 10.5" stroke="#3a1f08" strokeWidth="0.7" fill="none" strokeLinecap="round"/>
                          {/* 眼白 */}
                          <ellipse cx="13.5" cy="12.5" rx="2" ry="1.6" fill="white"/>
                          <ellipse cx="18.5" cy="12.5" rx="2" ry="1.6" fill="white"/>
                          {/* 虹膜 */}
                          <circle cx="13.5" cy="12.5" r="1.2" fill="#5c3520"/>
                          <circle cx="18.5" cy="12.5" r="1.2" fill="#5c3520"/>
                          {/* 高光 */}
                          <circle cx="14" cy="12" r="0.4" fill="white" opacity="0.9"/>
                          <circle cx="19" cy="12" r="0.4" fill="white" opacity="0.9"/>
                          {/* 睫毛 */}
                          <path d="M11.5 11.5 Q13.5 10.5 15.5 11.5" stroke="#1a0a06" strokeWidth="0.6" fill="none" strokeLinecap="round"/>
                          <path d="M16.5 11.5 Q18.5 10.5 20.5 11.5" stroke="#1a0a06" strokeWidth="0.6" fill="none" strokeLinecap="round"/>
                          {/* 鼻子 */}
                          <circle cx="15.2" cy="15.2" r="0.5" fill="#d4956b" opacity="0.6"/>
                          <circle cx="16.8" cy="15.2" r="0.5" fill="#d4956b" opacity="0.6"/>
                          {/* 嘴 */}
                          <path d="M13.5 17 Q16 18.5 18.5 17" stroke="#d06868" strokeWidth="0.8" fill="none" strokeLinecap="round"/>
                          {/* 腮红 */}
                          <circle cx="11" cy="14.5" r="2" fill="#ffb0a0" opacity="0.2"/>
                          <circle cx="21" cy="14.5" r="2" fill="#ffb0a0" opacity="0.2"/>
                        </svg>
                      </div>
                    ) : (
                      <div className="flex-shrink-0 w-[52px] h-[52px] rounded-full flex items-center justify-center text-sm font-semibold text-white" style={{ background: 'rgba(13,148,136,0.7)' }}>
                        我
                      </div>
                    )}

                    {/* 气泡 */}
                    <div className="flex flex-col gap-1 max-w-[72%]">
                      <span className={`text-xs text-slate-500 ${isInterviewer ? 'pl-1' : 'pr-1 text-right'}`}>
                        {isInterviewer ? 'AI 面试官' : '我'}
                      </span>
                      <div
                        className={`px-4 py-3 text-sm leading-relaxed ${
                          isInterviewer
                            ? 'rounded-xl rounded-tl-none text-slate-100'
                            : 'rounded-xl rounded-tr-none text-white'
                        }`}
                        style={{
                          background: isInterviewer
                            ? 'rgba(51,65,85,0.85)'
                            : 'rgba(13,148,136,0.85)',
                          backdropFilter: 'blur(8px)',
                        }}
                      >
                        <span className="whitespace-pre-wrap">{msg.content}</span>
                        {isLive && (
                          <span className="blink-cursor ml-0.5 text-teal-300">|</span>
                        )}
                      </div>
                    </div>
                  </div>
                )
              })}
              <div ref={messagesEndRef} />
            </>
          )}
          </div>
        </div>

        {/* ── Control Bar ───────────────────────────────── */}
        <div
          className="border-t border-slate-800"
          style={{ background: 'rgba(15,23,42,0.9)', backdropFilter: 'blur(12px)' }}
        >
        <div className="mx-auto w-full max-w-4xl flex items-center gap-4 px-4 py-4">
          {/* Mic level + device selector */}
          <div className="flex items-center gap-2 flex-1 min-w-0">
            {/* Device selector (gear icon) */}
            {audioDevices.length > 0 && status !== 'connected' && (
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setShowDeviceMenu((v) => !v)}
                  className="p-1.5 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-slate-800 transition-colors"
                  title="选择麦克风"
                >
                  <Cog6ToothIcon className="w-4 h-4" />
                </button>
                {showDeviceMenu && (
                  <div className="absolute bottom-full left-0 mb-2 w-64 rounded-xl border border-slate-700 shadow-2xl overflow-hidden z-50"
                    style={{ background: 'rgba(15,23,42,0.97)' }}
                  >
                    <p className="px-3 pt-3 pb-1 text-xs font-medium text-slate-400 uppercase tracking-wider">选择麦克风</p>
                    {[{ deviceId: '', label: '默认麦克风' }, ...audioDevices].map((d, i) => (
                      <button
                        key={d.deviceId || i}
                        type="button"
                        onClick={() => { setSelectedDeviceId(d.deviceId); setShowDeviceMenu(false) }}
                        className={`w-full text-left px-3 py-2 text-sm transition-colors ${
                          selectedDeviceId === d.deviceId
                            ? 'text-teal-300 bg-teal-900/30'
                            : 'text-slate-300 hover:bg-slate-800'
                        }`}
                      >
                        {d.label || `麦克风 ${i}`}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Mic level bars */}
            <div className="flex items-end gap-[2px]" style={{ height: 20 }}>
              {micBars.map((active, i) => (
                <div
                  key={i}
                  className="w-[3px] rounded-full transition-all duration-75"
                  style={{
                    height: active ? `${6 + (i / 11) * 14}px` : '4px',
                    background: active ? 'rgb(45,212,191)' : 'rgba(71,85,105,0.6)',
                  }}
                />
              ))}
            </div>
            {status === 'connected' && (
              <span className="text-[10px] text-slate-600 truncate hidden sm:block ml-1">{activeDeviceLabel}</span>
            )}
          </div>

          {/* Center controls */}
          <div className="flex items-center gap-3">
            {status === 'idle' && (
              <button
                type="button"
                onClick={startVoice}
                disabled={!sessionId}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed hover:scale-105 active:scale-95"
                style={{ background: 'linear-gradient(135deg, #6366f1, #0d9488)', boxShadow: '0 4px 20px rgba(99,102,241,0.4)' }}
              >
                <MicrophoneIcon className="w-4 h-4" />
                {sessionId ? '开始面试' : '准备中…'}
              </button>
            )}

            {status === 'connecting' && (
              <div className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm text-slate-400"
                style={{ background: 'rgba(30,41,59,0.8)' }}
              >
                <span className="w-3 h-3 rounded-full border-2 border-indigo-400 border-t-transparent animate-spin" />
                连接中…
              </div>
            )}

            {status === 'connected' && (
              <>
                <button
                  type="button"
                  onClick={toggleMute}
                  className={`p-2.5 rounded-xl transition-all hover:scale-105 active:scale-95 ${
                    muted
                      ? 'text-amber-300 bg-amber-900/30 hover:bg-amber-900/50'
                      : 'text-slate-300 bg-slate-700/60 hover:bg-slate-700'
                  }`}
                  title={muted ? '取消静音' : '静音'}
                >
                  {muted
                    ? <SpeakerXMarkIcon className="w-5 h-5" />
                    : <SpeakerWaveIcon className="w-5 h-5" />
                  }
                </button>
              </>
            )}

            {status === 'error' && (
              <button
                type="button"
                onClick={() => { stopAll(); startVoice() }}
                className="flex items-center gap-2 px-5 py-2.5 rounded-xl text-sm font-semibold text-white bg-slate-700 hover:bg-slate-600 transition-all"
              >
                重试连接
              </button>
            )}
          </div>

          {/* End call */}
          <div className="flex-1 flex justify-end">
            {status === 'connected' && (
              <button
                type="button"
                onClick={() => stopAll(true)}
                className="flex items-center gap-2 px-4 py-2.5 rounded-xl text-sm font-semibold text-white transition-all hover:scale-105 active:scale-95"
                style={{ background: 'rgba(239,68,68,0.85)', boxShadow: '0 4px 16px rgba(239,68,68,0.35)' }}
              >
                <PhoneXMarkIcon className="w-4 h-4" />
                挂断
              </button>
            )}
          </div>
        </div>
        </div>
      </div>
    </>
  )
}

// ── InterviewPage ──────────────────────────────────────────────────────────

export default function InterviewPage() {
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()
  const resumeId = Number(params?.id as string)
  const requestedSessionId = Number(searchParams?.get('session') || 0)

  const { isAuthenticated, isLoading: authLoading } = useAuth()
  const [mounted, setMounted] = useState(false)
  const [resume, setResume] = useState<Resume | null>(null)
  const [resumeLoading, setResumeLoading] = useState(true)
  const [digitalHuman, setDigitalHuman] = useState<DigitalHumanConversation | null>(null)

  const {
    session,
    isSending,
    error: sessionError,
    endInterview,
  } = useInterviewSession({
    resume,
    enabled: !!resume && isAuthenticated,
    requestedSessionId: requestedSessionId || undefined,
  })

  useEffect(() => { setMounted(true) }, [])

  useEffect(() => {
    if (!resumeId) return
    setResumeLoading(true)
    resumeApi
      .getResume(resumeId)
      .then(setResume)
      .catch(() => setResume(null))
      .finally(() => setResumeLoading(false))
  }, [resumeId])

  useEffect(() => {
    if (!session?.id || session.status === 'completed') return
    if (digitalHuman?.session_id) return
    digitalHumanApi
      .createConversation(session.id)
      .then(setDigitalHuman)
      .catch(() => {})
  }, [digitalHuman?.session_id, session?.id, session?.status])

  useEffect(() => {
    return () => {
      if (digitalHuman?.conversation_id) {
        digitalHumanApi.endConversation(digitalHuman.conversation_id).catch(() => {})
      }
    }
  }, [digitalHuman?.conversation_id])

  const handleEndInterview = useCallback(async () => {
    await endInterview()
    router.push('/interviews')
  }, [endInterview, router])

  if (!mounted || authLoading || resumeLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950">
        <div className="h-8 w-8 animate-spin rounded-full border-2 border-slate-700 border-t-indigo-500" />
      </div>
    )
  }

  if (!isAuthenticated) {
    router.push('/login')
    return null
  }

  if (!resume) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-slate-950">
        <p className="text-slate-400">简历不存在</p>
        <Link href="/dashboard" className="text-sm text-teal-400 hover:underline">
          返回首页
        </Link>
      </div>
    )
  }

  const isCompleted = session?.status === 'completed'

  return (
    <div className="flex h-screen flex-col bg-slate-950 overflow-hidden">
      {/* Header */}
      <header
        className="flex-shrink-0 flex h-13 items-center justify-between px-5 border-b border-slate-800"
        style={{ background: 'rgba(15,23,42,0.9)', backdropFilter: 'blur(12px)', height: 52 }}
      >
        <div className="flex items-center gap-3">
          <Link
            href="/interviews"
            className="p-1.5 rounded-lg text-slate-500 hover:text-slate-300 hover:bg-slate-800 transition-colors"
          >
            <ArrowLeftIcon className="h-4 w-4" />
          </Link>
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold text-slate-200">Interview Room</span>
            {resume && (
              <>
                <span className="text-slate-700">·</span>
                <span className="text-xs text-slate-500 truncate max-w-[160px]">{resume.title || resume.original_filename}</span>
              </>
            )}
          </div>
        </div>

        <div className="flex items-center gap-3">
          {session && (
            <span className={`flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full ${
              isCompleted
                ? 'bg-slate-800 text-slate-400'
                : 'bg-emerald-900/40 text-emerald-400'
            }`}>
              <span className={`w-1.5 h-1.5 rounded-full ${isCompleted ? 'bg-slate-500' : 'bg-emerald-400 animate-pulse'}`} />
              {isCompleted ? '已结束' : '进行中'}
            </span>
          )}
          {!isCompleted && session && (
            <button
              type="button"
              onClick={handleEndInterview}
              disabled={isSending}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-rose-300 bg-rose-900/30 hover:bg-rose-900/50 border border-rose-800/50 transition-all disabled:opacity-50"
            >
              结束面试
            </button>
          )}
        </div>
      </header>

      {/* Error banner */}
      {sessionError && (
        <div className="flex-shrink-0 px-5 py-2.5 text-xs text-rose-300 bg-rose-900/20 border-b border-rose-900/30">
          {sessionError}
        </div>
      )}

      {/* Voice panel fills remaining height */}
      <div className="flex-1 flex flex-col min-h-0">
        <VoicePanel sessionId={digitalHuman?.session_id} autoStart />
      </div>
    </div>
  )
}
