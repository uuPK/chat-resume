'use client'
// 用于提供 app/[locale]/resume/[id]/interview/page.tsx 模块。

import { useCallback, useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { useParams, useSearchParams } from 'next/navigation'
import { useRouter } from '@/i18n/navigation'
import { Link } from '@/i18n/navigation'
import {
  ArrowLeftIcon,
  MicrophoneIcon,
  PhoneXMarkIcon,
  Cog6ToothIcon,
} from '@heroicons/react/24/outline'
import { useAuth } from '@/lib/auth'
import { digitalHumanApi, resumeApi } from '@/lib/api'
import type { DigitalHumanConversation, InterviewSession, Resume } from '@/lib/api'
import { useInterviewSession } from '@/hooks/useInterviewSession'
import { useLocale, useTranslations } from 'next-intl'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const SEND_SAMPLE_RATE = 16000
const SEND_CHUNK_FRAMES = 1600

declare global {
  interface Window {
    __chatResumeVoiceCleanup?: () => void
  }
}

type VoiceStatus = 'idle' | 'connecting' | 'connected' | 'error'
type TurnStatus = 'idle' | 'interviewer' | 'user'
type ConversationMessage = {
  id: string
  role: 'candidate' | 'interviewer'
  content: string
  isFinal?: boolean
}
type LiveMessagesByRole = Partial<Record<ConversationMessage['role'], ConversationMessage>>

// 用于从当前实时消息集合中移除指定角色的临时气泡。
function withoutLiveMessage(
  current: LiveMessagesByRole,
  role: ConversationMessage['role'],
): LiveMessagesByRole {
  const { [role]: _removed, ...remaining } = current
  return remaining
}


interface VoicePanelProps {
  sessionId: string | undefined
  interviewSession?: InterviewSession | null
  onPersistMessage?: (role: ConversationMessage['role'], content: string) => void
  autoStart?: boolean
  onStatusChange?: (status: VoiceStatus) => void
  canEndInterview?: boolean
  isEndingInterview?: boolean
  onEndInterview?: () => void
}


// 用于渲染 VoicePanel 组件。
function VoicePanel({
  sessionId,
  interviewSession,
  onPersistMessage,
  autoStart = false,
  onStatusChange,
  canEndInterview = false,
  isEndingInterview = false,
  onEndInterview,
}: VoicePanelProps) {
  const t = useTranslations('interview.session')
  const [status, setStatus] = useState<VoiceStatus>('idle')
  const [inputLevel, setInputLevel] = useState(0)
  const [audioDevices, setAudioDevices] = useState<MediaDeviceInfo[]>([])
  const [selectedDeviceId, setSelectedDeviceId] = useState('')
  const [messages, setMessages] = useState<ConversationMessage[]>([])
  const [liveMessages, setLiveMessages] = useState<LiveMessagesByRole>({})
  const [showDeviceMenu, setShowDeviceMenu] = useState(false)
  const [turnStatus, setTurnStatus] = useState<TurnStatus>('idle')

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
    setTurnStatus(role === 'interviewer' ? 'user' : 'interviewer')
    onPersistMessage?.(role, text)
  }, [isNoiseTranscript, normalizeTranscriptText, onPersistMessage])

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
    setLiveMessages((current) => ({
      ...current,
      [role]: { id: `${role}-live`, role, content: nextText },
    }))
    setTurnStatus(role === 'candidate' ? 'user' : 'interviewer')

    if (isFinal) {
      appendMessage(role, liveTextRef.current[role])
      liveTextRef.current[role] = ''
      setLiveMessages((current) => withoutLiveMessage(current, role))
    }
  }, [appendMessage, isNoiseTranscript, normalizeTranscriptText])

  const flushLiveText = useCallback((role: ConversationMessage['role']) => {
    if (role === 'candidate') {
      clearCandidateFinalizeTimer()
    }
    appendMessage(role, liveTextRef.current[role])
    liveTextRef.current[role] = ''
    setLiveMessages((current) => withoutLiveMessage(current, role))
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
    setLiveMessages((current) => ({
      ...current,
      candidate: { id: 'candidate-live', role: 'candidate', content: nextText },
    }))
    setTurnStatus('user')

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

  useEffect(() => {
    if (!interviewSession?.turns?.length) return

    const restoredMessages = interviewSession.turns.flatMap((turn) => {
      const turnMessages: ConversationMessage[] = []
      if (turn.question) {
        turnMessages.push({
          id: `turn-${turn.id}-question`,
          role: 'interviewer',
          content: turn.question,
          isFinal: true,
        })
      }
      if (turn.answer) {
        turnMessages.push({
          id: `turn-${turn.id}-answer`,
          role: 'candidate',
          content: turn.answer,
          isFinal: true,
        })
      }
      return turnMessages
    })

    setMessages(restoredMessages)
    setLiveMessages({})
  }, [interviewSession?.turns])

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
      // 用于排空当前数据。
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
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) return

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
  }, [])

  const startVoice = useCallback(async () => {
    if (!sessionId || wsRef.current) return
    window.__chatResumeVoiceCleanup?.()
    window.__chatResumeVoiceCleanup = () => stopAll(true)
    userStoppedRef.current = false
    updateStatus('connecting')
    setMessages((current) => (current.length ? current : []))
    setLiveMessages({})
    setTurnStatus('idle')
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
            setTurnStatus('user')
          } else if (msg.type === 'greeting') {
            const text = msg.text || msg.content || ''
            if (text) {
              appendMessage('interviewer', text)
            }
          } else if (msg.type === 'event') {
            if (msg.event === 451) {
              const results: Array<{ text: string }> = msg.data?.results || []
              const text = msg.text || results.map((r) => r.text).join('')
              if (text) {
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
            updateStatus('error')
          }
        } catch { /* ignore non-JSON */ }
      }

      ws.onerror = () => {
        userStoppedRef.current = true
        updateStatus('error')
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
        const timer = setTimeout(() => reject(new Error(t('timeout'))), 10000)
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
    } catch {
      userStoppedRef.current = true
      updateStatus('error')
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
    appendMessage,
  ])

  useEffect(() => {
    if (!autoStart || !sessionId || status !== 'idle' || userStoppedRef.current) return
    startVoice().catch(() => {})
  }, [autoStart, sessionId, startVoice, status])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, liveMessages])

  const micBars = Array.from({ length: 12 }, (_, i) => {
    const threshold = (i + 1) / 12
    return inputLevel * 5 > threshold
  })
  const visibleLiveMessages = [liveMessages.interviewer, liveMessages.candidate]
    .filter((message): message is ConversationMessage => Boolean(message))
  const hasVisibleInterviewMessages = messages.length > 0 || visibleLiveMessages.length > 0
  const hasPersistedInterviewHistory = (interviewSession?.turns?.length || 0) > 0
  const hasStartedInterviewSession = Boolean(interviewSession?.started_at)
    || interviewSession?.status === 'in_progress'
    || interviewSession?.status === 'waiting_user_answer'
  const shouldContinueInterview = hasVisibleInterviewMessages
    || hasPersistedInterviewHistory
    || hasStartedInterviewSession

  return (
    <>
      <style>{`
        @keyframes soundwave {
          0%, 100% { transform: scaleY(0.25); }
          50% { transform: scaleY(1); }
        }
        @keyframes blink-cursor {
          0%, 100% { opacity: 1; }
          50% { opacity: 0; }
        }
        @keyframes fade-in-up {
          from { opacity: 0; transform: translateY(10px); }
          to   { opacity: 1; transform: translateY(0); }
        }
        @keyframes pulse-dot {
          0%, 100% { opacity: 1; }
          50% { opacity: 0.4; }
        }
        @keyframes prompt-dot {
          0%, 80%, 100% { transform: scale(0.75); opacity: 0.45; }
          40% { transform: scale(1); opacity: 1; }
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
        .pulse-dot {
          animation: pulse-dot 1.5s ease-in-out infinite;
        }
        .prompt-dot {
          animation: prompt-dot 1.1s ease-in-out infinite;
        }
      `}</style>

      <div className="flex flex-col h-full">

        {/* ── Conversation ──────────────────────────────── */}
        <div
          className="flex-1 overflow-y-auto bg-white"
        >
          <div className="mx-auto w-full max-w-4xl px-5 pt-6 pb-[25px] space-y-5 min-h-full">
          {status === 'connecting' ? (
            <div className="fixed inset-0 z-40 flex items-center justify-center pointer-events-none select-none">
              <div
                className="flex items-center gap-2 px-5 py-3 text-sm font-medium"
                style={{
                  backgroundColor: '#eef0f3',
                  color: '#5b616e',
                  borderRadius: '56px',
                }}
              >
                <span
                  className="w-3 h-3 rounded-full border-2 border-t-transparent animate-spin"
                  style={{ borderColor: '#0052ff', borderTopColor: 'transparent' }}
                />
                {t('connecting')}
              </div>
            </div>
          ) : messages.length === 0 && visibleLiveMessages.length === 0 ? (
            <div className="h-full" />
          ) : (
            <>
              {[...messages, ...visibleLiveMessages].map((msg, idx) => {
                const isInterviewer = msg.role === 'interviewer'
                const isLive = visibleLiveMessages.includes(msg)
                return (
                  <div
                    key={msg.id}
                    className={`msg-enter flex ${isInterviewer ? 'justify-start' : 'justify-end'}`}
                    style={{ animationDelay: `${Math.min(idx * 0.03, 0.15)}s` }}
                  >
                    {/* Bubble */}
                    <div className="flex flex-col gap-1 max-w-[72%]">
                      <div
                        className={`px-4 py-3 text-sm leading-relaxed rounded-2xl ${
                          isInterviewer
                            ? 'rounded-tl-md'
                            : 'rounded-tr-md text-white'
                        }`}
                        style={{
                          backgroundColor: isInterviewer
                            ? '#eef0f3'
                            : '#0052ff',
                          color: isInterviewer ? '#0a0b0d' : '#ffffff',
                        }}
                      >
                        <span className="whitespace-pre-wrap">{msg.content}</span>
                        {isLive && (
                          <span className="blink-cursor ml-0.5" style={{ color: '#578bfa' }}>|</span>
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
          className="relative border-t bg-white"
          style={{ borderColor: 'rgba(91,97,110,0.2)' }}
        >
          {status === 'connected' && turnStatus === 'user' && (
            <div
              className="absolute left-1/2 bottom-full mb-3 -translate-x-1/2"
            >
              <span className="flex items-center gap-2">
                {[0, 1, 2].map((index) => (
                  <span
                    key={index}
                    className="prompt-dot h-2 w-2 rounded-full"
                    style={{
                      backgroundColor: '#0052ff',
                      animationDelay: `${index * 0.14}s`,
                    }}
                  />
                ))}
              </span>
            </div>
          )}

          {/* Mic level + device selector */}
          <div className="absolute right-5 top-1/2 flex -translate-y-1/2 items-center justify-end gap-2 min-w-0">
            {/* Mic level bars */}
            <div className="flex h-10 items-center gap-[2px]">
              {micBars.map((active, i) => (
                <div
                  key={i}
                  className="w-[3px] rounded-full transition-all duration-75"
                  style={{
                    height: active ? `${6 + (i / 11) * 14}px` : '4px',
                    backgroundColor: active ? '#0052ff' : 'rgba(91,97,110,0.3)',
                  }}
                />
              ))}
            </div>
            {audioDevices.length > 0 && (
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setShowDeviceMenu((v) => !v)}
                  className="p-2 rounded-xl transition-colors"
                  style={{ color: '#5b616e' }}
                  onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#eef0f3' }}
                  onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
                  title={t('microphone')}
                >
                  <Cog6ToothIcon className="w-4 h-4" />
                </button>
                {showDeviceMenu && (
                  <div
                    className="absolute bottom-full right-0 mb-2 w-64 rounded-2xl overflow-hidden z-50"
                    style={{
                      backgroundColor: '#ffffff',
                      border: '1px solid rgba(91,97,110,0.2)',
                      boxShadow: '0 8px 24px rgba(0,0,0,0.08)',
                    }}
                  >
                    <p className="px-4 pt-3 pb-1 text-xs font-semibold uppercase tracking-wider" style={{ color: '#5b616e' }}>{t('microphone')}</p>
                    {[{ deviceId: '', label: t('defaultMicrophone') }, ...audioDevices].map((d, i) => (
                      <button
                        key={d.deviceId || i}
                        type="button"
                        onClick={() => { setSelectedDeviceId(d.deviceId); setShowDeviceMenu(false) }}
                        className="w-full text-left px-4 py-2.5 text-sm font-medium transition-colors"
                        style={{
                          color: selectedDeviceId === d.deviceId ? '#0052ff' : '#0a0b0d',
                          backgroundColor: selectedDeviceId === d.deviceId ? 'rgba(0,82,255,0.08)' : 'transparent',
                        }}
                        onMouseEnter={(e) => { if (selectedDeviceId !== d.deviceId) e.currentTarget.style.backgroundColor = '#eef0f3' }}
                        onMouseLeave={(e) => { if (selectedDeviceId !== d.deviceId) e.currentTarget.style.backgroundColor = 'transparent' }}
                      >
                        {d.label || `${t('microphone')} ${i}`}
                      </button>
                    ))}
                  </div>
                )}
              </div>
            )}
          </div>

          <div className="relative mx-auto flex min-h-[72px] w-full max-w-4xl items-center justify-center px-5 py-4">
            {/* Primary controls */}
            <div className="flex items-center gap-3">
              {status === 'idle' && (
                <>
                  <button
                    type="button"
                    onClick={startVoice}
                    disabled={!sessionId}
                    className="flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white transition-all disabled:opacity-40 disabled:cursor-not-allowed focus:outline-none focus:ring-2 focus:ring-black"
                    style={{
                      backgroundColor: '#0052ff',
                      borderRadius: '56px',
                      border: '1px solid #0052ff',
                      letterSpacing: '0.01em',
                    }}
                    onMouseEnter={(e) => { if (!e.currentTarget.disabled) { e.currentTarget.style.backgroundColor = '#578bfa'; e.currentTarget.style.borderColor = '#578bfa' } }}
                    onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = '#0052ff'; e.currentTarget.style.borderColor = '#0052ff' }}
                  >
                    <MicrophoneIcon className="w-3.5 h-3.5" />
                    {sessionId ? (shouldContinueInterview ? t('continue') : t('start')) : t('preparing')}
                  </button>
                  {shouldContinueInterview && canEndInterview && onEndInterview && (
                    <button
                      type="button"
                      onClick={onEndInterview}
                      disabled={isEndingInterview}
                      className="flex items-center gap-2 px-5 py-2.5 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-black"
                      style={{
                        backgroundColor: '#eef0f3',
                        borderRadius: '56px',
                        border: '1px solid #eef0f3',
                        color: '#0a0b0d',
                        letterSpacing: '0.01em',
                      }}
                      onMouseEnter={(e) => { if (!e.currentTarget.disabled) { e.currentTarget.style.backgroundColor = '#282b31'; e.currentTarget.style.borderColor = '#282b31'; e.currentTarget.style.color = '#ffffff' } }}
                      onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = '#eef0f3'; e.currentTarget.style.borderColor = '#eef0f3'; e.currentTarget.style.color = '#0a0b0d' }}
                    >
                      <PhoneXMarkIcon className="w-3.5 h-3.5" />
                      {isEndingInterview ? t('endingInterview') : t('endInterview')}
                    </button>
                  )}
                </>
              )}

              {status === 'error' && (
                <button
                  type="button"
                  onClick={() => { stopAll(); startVoice() }}
                  className="flex items-center gap-2 px-6 py-3 text-base font-semibold transition-colors focus:outline-none focus:ring-2 focus:ring-black"
                  style={{
                    backgroundColor: '#eef0f3',
                    borderRadius: '56px',
                    border: '1px solid #eef0f3',
                    color: '#0a0b0d',
                    letterSpacing: '0.01em',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#578bfa'; e.currentTarget.style.borderColor = '#578bfa'; e.currentTarget.style.color = '#ffffff' }}
                  onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = '#eef0f3'; e.currentTarget.style.borderColor = '#eef0f3'; e.currentTarget.style.color = '#0a0b0d' }}
                >
                  {t('retry')}
                </button>
              )}

              {status === 'connected' && (
                <button
                  type="button"
                  onClick={() => stopAll(true)}
                  className="flex items-center gap-2 px-5 py-2.5 text-sm font-semibold text-white transition-colors focus:outline-none focus:ring-2 focus:ring-black"
                  style={{
                    backgroundColor: '#282b31',
                    borderRadius: '56px',
                    border: '1px solid #282b31',
                    letterSpacing: '0.01em',
                  }}
                  onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#578bfa'; e.currentTarget.style.borderColor = '#578bfa' }}
                  onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = '#282b31'; e.currentTarget.style.borderColor = '#282b31' }}
                >
                  <PhoneXMarkIcon className="w-3.5 h-3.5" />
                  {t('hangup')}
                </button>
              )}
            </div>
          </div>
        </div>
      </div>
    </>
  )
}

type ReportData = NonNullable<InterviewSession['report_data']>

// 报告色彩系统（暖白设计语言）
const RD = {
  bg: '#F7F5F0',
  surface: '#FFFFFF',
  surface2: '#F0EDE7',
  border: '#E2DDD6',
  text: '#1A1814',
  textMuted: '#7A756D',
  textFaint: '#B0A99F',
  blue: '#2B5CE6',
  blueLight: '#EEF2FD',
  green: '#1D7A4E',
  greenLight: '#E8F5EE',
  amber: '#B85C00',
  amberLight: '#FDF3E7',
  red: '#C0392B',
  redLight: '#FDECEA',
  dark: '#1A1814',
} as const

// 用于从维度平均分或结论等级推导综合评分。
function computeOverallScore(dimensions: ReportData['dimensions'] = [], level?: string): number {
  const scored = (dimensions ?? []).filter(d => typeof d.score === 'number')
  if (scored.length > 0) {
    const avg = scored.reduce((s, d) => s + (d.score || 0), 0) / scored.length
    return Math.round(avg * 20)
  }
  return level === 'strong' ? 85 : level === 'risky' ? 55 : 70
}

// 用于把面试轮次评价统一成可渲染对象。
function getTurnEvaluation(turn: InterviewSession['turns'][number]) {
  if (!turn.evaluation) return null
  if (typeof turn.evaluation === 'string') return { summary: turn.evaluation }
  return turn.evaluation
}

// 用于把分数百分比分类为 good/mid/low。
function scoreTier(pct: number): 'good' | 'mid' | 'low' {
  if (pct >= 70) return 'good'
  if (pct >= 50) return 'mid'
  return 'low'
}

// 用于从分数等级取对应颜色。
function tierColor(tier: 'good' | 'mid' | 'low'): string {
  if (tier === 'good') return RD.green
  if (tier === 'mid') return RD.amber
  return RD.red
}

// 用于渲染带延伸线的区块标签。
function RdSectionLabel({ label }: { label: string }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 16 }}>
      <span style={{
        fontFamily: "'DM Mono', 'SFMono-Regular', monospace",
        fontSize: 10,
        letterSpacing: '0.12em',
        textTransform: 'uppercase' as const,
        color: RD.textMuted,
        whiteSpace: 'nowrap' as const,
        flexShrink: 0,
      }}>
        {label}
      </span>
      <div style={{ flex: 1, height: 1, background: RD.border }} />
    </div>
  )
}

// 用于渲染带色边的维度评分卡片。
function RdDimCard({ dimension }: { dimension: NonNullable<ReportData['dimensions']>[number] }) {
  const pct = typeof dimension.score === 'number' ? dimension.score * 20 : 0
  const tier = scoreTier(pct)
  const color = tierColor(tier)
  return (
    <div style={{
      background: RD.surface,
      border: `1px solid ${RD.border}`,
      borderLeft: `3px solid ${color}`,
      borderRadius: 12,
      padding: '18px 20px',
      overflow: 'hidden',
    }}>
      <div style={{ fontSize: 12, color: RD.textMuted, marginBottom: 8 }}>{dimension.title}</div>
      <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 8 }}>
        <span style={{
          fontFamily: "'DM Serif Display', Georgia, serif",
          fontSize: 28,
          letterSpacing: '-0.03em',
          lineHeight: 1,
          color,
        }}>
          {Math.round(pct)}
        </span>
        <div style={{ flex: 1, height: 3, background: RD.surface2, borderRadius: 2, overflow: 'hidden' }}>
          <div style={{ height: '100%', background: color, borderRadius: 2, width: `${pct}%`, transition: 'width 1s cubic-bezier(.16,1,.3,1)' }} />
        </div>
      </div>
      {dimension.assessment && (
        <div style={{
          fontFamily: "'DM Mono', 'SFMono-Regular', monospace",
          fontSize: 10,
          marginTop: 6,
          color: RD.textFaint,
          lineHeight: 1.5,
        }}>
          {dimension.assessment}
        </div>
      )}
    </div>
  )
}

// 用于渲染可展开的单题解析卡片。
function RdQACard({ turn, index }: { turn: InterviewSession['turns'][number]; index: number }) {
  const [open, setOpen] = useState(false)
  const evaluation = getTurnEvaluation(turn)
  const summary = evaluation?.summary || ''
  const strengths: string[] = Array.isArray(evaluation?.evidence) ? (evaluation.evidence as string[]) : []
  const gaps: string[] = Array.isArray(evaluation?.gaps) ? (evaluation.gaps as string[]) : []

  return (
    <div style={{
      background: RD.surface,
      border: `1px solid ${RD.border}`,
      borderRadius: 12,
      overflow: 'hidden',
    }}>
      <div
        role="button"
        tabIndex={0}
        style={{ display: 'flex', alignItems: 'flex-start', gap: 14, padding: '18px 20px', cursor: 'pointer' }}
        onClick={() => setOpen(v => !v)}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') setOpen(v => !v) }}
      >
        <span style={{
          fontFamily: "'DM Mono', 'SFMono-Regular', monospace",
          fontSize: 11,
          color: RD.textFaint,
          paddingTop: 2,
          flexShrink: 0,
          minWidth: 20,
        }}>
          {String(index + 1).padStart(2, '0')}
        </span>
        <p style={{ flex: 1, fontSize: 14, fontWeight: 500, lineHeight: 1.5, margin: 0, color: RD.text }}>
          {turn.question}
        </p>
        <span style={{
          fontSize: 16,
          color: RD.textFaint,
          flexShrink: 0,
          transition: 'transform 0.2s',
          transform: open ? 'rotate(180deg)' : 'none',
          display: 'inline-block',
        }}>▾</span>
      </div>
      {open && (
        <div style={{ borderTop: `1px solid ${RD.border}`, padding: '18px 20px' }}>
          <div style={{
            fontFamily: "'DM Mono', 'SFMono-Regular', monospace",
            fontSize: 10,
            letterSpacing: '0.1em',
            textTransform: 'uppercase' as const,
            color: RD.textFaint,
            marginBottom: 8,
          }}>
            你的回答
          </div>
          <div style={{
            fontSize: 13,
            color: RD.textMuted,
            lineHeight: 1.7,
            paddingLeft: 12,
            borderLeft: `2px solid ${RD.border}`,
            marginBottom: 16,
          }}>
            {turn.answer || '（候选人跳过此问题）'}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 8 }}>
            {strengths.map((s, i) => (
              <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', fontSize: 13, lineHeight: 1.55 }}>
                <span style={{ width: 18, height: 18, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 2, fontSize: 10, background: RD.greenLight, color: RD.green }}>✓</span>
                <span style={{ color: RD.textMuted }}>{s}</span>
              </div>
            ))}
            {gaps.map((g, i) => (
              <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', fontSize: 13, lineHeight: 1.55 }}>
                <span style={{ width: 18, height: 18, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 2, fontSize: 10, background: RD.amberLight, color: RD.amber }}>!</span>
                <span style={{ color: RD.textMuted }}>{g}</span>
              </div>
            ))}
            {summary && !strengths.length && !gaps.length && (
              <div style={{ display: 'flex', gap: 10, alignItems: 'flex-start', fontSize: 13, lineHeight: 1.55 }}>
                <span style={{ width: 18, height: 18, borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', flexShrink: 0, marginTop: 2, fontSize: 10, background: RD.blueLight, color: RD.blue }}>↗</span>
                <span style={{ color: RD.textMuted }}>{summary}</span>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

// 用于渲染关键词胶囊（命中/缺失两态）。
function RdKeyword({ label, hit }: { label: string; hit: boolean }) {
  return (
    <span style={{
      fontFamily: "'DM Mono', 'SFMono-Regular', monospace",
      fontSize: 11,
      padding: '3px 10px',
      borderRadius: 99,
      border: `1px solid ${hit ? '#b2ddc5' : RD.border}`,
      background: hit ? RD.greenLight : RD.surface2,
      color: hit ? RD.green : RD.textFaint,
    }}>
      {label}
    </span>
  )
}

// 用于渲染侧边栏卡片容器。
function RdSideCard({ title, icon, children }: { title: string; icon: ReactNode; children: ReactNode }) {
  return (
    <div style={{ background: RD.surface, border: `1px solid ${RD.border}`, borderRadius: 12, padding: 20, marginBottom: 16 }}>
      <div style={{ fontSize: 12, fontWeight: 500, color: RD.textMuted, marginBottom: 14, display: 'flex', alignItems: 'center', gap: 7 }}>
        {icon}
        {title}
      </div>
      {children}
    </div>
  )
}

// 用于渲染面试官综合评价板块。
function RdInterviewerEvaluation({ evaluation }: {
  evaluation: NonNullable<ReportData['interviewer_evaluation']>
}) {
  const observations = evaluation.key_observations || []
  const recommendations = evaluation.core_recommendations || []
  return (
    <div style={{ marginBottom: 28 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 16 }}>
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke={RD.text} strokeWidth="2">
          <path d="M9 5H7a2 2 0 0 0-2 2v12a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2h-2"/>
          <rect x="9" y="3" width="6" height="4" rx="1"/>
          <line x1="9" y1="12" x2="15" y2="12"/>
          <line x1="9" y1="16" x2="13" y2="16"/>
        </svg>
        <span style={{ fontSize: 18, fontWeight: 600, color: RD.text }}>面试官评价</span>
      </div>

      {evaluation.overall && (
        <p style={{ fontSize: 14, color: RD.textMuted, lineHeight: 1.75, marginBottom: 20 }}>
          {evaluation.overall}
        </p>
      )}

      {(observations.length > 0 || recommendations.length > 0) && (
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 16 }}>
          {observations.length > 0 && (
            <div style={{
              background: '#FFFBF0',
              border: '1px solid #F0D9A0',
              borderRadius: 12,
              padding: '18px 20px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 14 }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={RD.amber} strokeWidth="2">
                  <circle cx="12" cy="12" r="10"/>
                  <line x1="12" y1="8" x2="12" y2="12"/>
                  <line x1="12" y1="16" x2="12.01" y2="16"/>
                </svg>
                <span style={{ fontSize: 13, fontWeight: 600, color: RD.amber }}>关键观察</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 10 }}>
                {observations.map((obs, i) => (
                  <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 13, lineHeight: 1.6 }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: RD.amber, flexShrink: 0, marginTop: 7 }} />
                    <span style={{ color: RD.textMuted }}>{obs}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {recommendations.length > 0 && (
            <div style={{
              background: '#F0FAF4',
              border: '1px solid #A8D8BC',
              borderRadius: 12,
              padding: '18px 20px',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 7, marginBottom: 14 }}>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke={RD.green} strokeWidth="2.5">
                  <circle cx="12" cy="12" r="10"/>
                  <polyline points="9 12 11 14 15 10"/>
                </svg>
                <span style={{ fontSize: 13, fontWeight: 600, color: RD.green }}>核心建议</span>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 10 }}>
                {recommendations.map((rec, i) => (
                  <div key={i} style={{ display: 'flex', gap: 8, alignItems: 'flex-start', fontSize: 13, lineHeight: 1.6 }}>
                    <span style={{ width: 6, height: 6, borderRadius: '50%', background: RD.green, flexShrink: 0, marginTop: 7 }} />
                    <span style={{ color: RD.textMuted }}>{rec}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// 用于渲染完整的面试复盘报告。
function ReportPreview({
  report,
  turns,
  session,
}: {
  report: InterviewSession['report_data']
  turns: InterviewSession['turns']
  session?: InterviewSession
}) {
  if (!report) return null

  const data = report as ReportData
  const verdict = data.candidate_verdict
  const match = data.job_match
  const score = computeOverallScore(data.dimensions, verdict?.level)
  const scoreBadge = score >= 75 ? '良好' : score >= 55 ? '一般' : '需提高'
  const dimensions = data.dimensions || []
  const hitKeywords = match?.covered_capabilities || []
  const missKeywords = match?.missing_capabilities || []
  const suggestions = data.next_training_plan || []
  const targetTitle = match?.target_title || session?.target_title || '综合面试'
  const targetCompany = match?.target_company || session?.target_company || ''

  const startedAt = session?.started_at
  const endedAt = session?.ended_at
  let duration = ''
  if (startedAt) {
    const s = new Date(startedAt.includes('Z') ? startedAt : `${startedAt}Z`).getTime()
    const e = endedAt ? new Date(endedAt.includes('Z') ? endedAt : `${endedAt}Z`).getTime() : Date.now()
    const mins = Math.max(1, Math.round((e - s) / 60000))
    duration = mins >= 60 ? `${Math.floor(mins / 60)}小时${mins % 60 ? `${mins % 60}分钟` : ''}` : `${mins}分钟`
  }

  const hasSidebar = hitKeywords.length > 0 || missKeywords.length > 0 || suggestions.length > 0
    || (data.strengths || []).length > 0 || (data.weaknesses || []).length > 0

  return (
    <>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display:ital@0;1&family=DM+Mono:wght@400;500&family=DM+Sans:wght@300;400;500&display=swap');`}</style>
      <div style={{ fontFamily: "'DM Sans', system-ui, sans-serif", fontSize: 14, lineHeight: 1.6, color: RD.text }}>

        {/* Hero */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr auto', gap: 40, alignItems: 'start', marginBottom: 40 }}>
          <div>
            <div style={{ fontFamily: "'DM Mono', 'SFMono-Regular', monospace", fontSize: 11, color: RD.textMuted, letterSpacing: '0.1em', textTransform: 'uppercase' as const, marginBottom: 12, display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ display: 'inline-block', width: 20, height: 1, background: RD.textMuted }} />
              面试报告
            </div>
            <h1 style={{ fontFamily: "'DM Serif Display', Georgia, serif", fontSize: 'clamp(26px, 4vw, 40px)', lineHeight: 1.15, letterSpacing: '-0.02em', margin: '0 0 10px' }}>
              {targetCompany && <>{targetCompany}<br /></>}
              <em style={{ fontStyle: 'italic', color: RD.blue }}>{targetTitle}</em>
            </h1>
            <div style={{ fontSize: 13, color: RD.textMuted, display: 'flex', gap: 16, flexWrap: 'wrap' as const, marginTop: 16 }}>
              {duration && (
                <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                  用时 {duration}
                </span>
              )}
              <span style={{ display: 'flex', alignItems: 'center', gap: 5 }}>
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"/></svg>
                {turns.length} 道题目
              </span>
            </div>
          </div>

          {/* Score card */}
          <div style={{ background: RD.dark, color: '#fff', borderRadius: 16, padding: '28px 32px', textAlign: 'center' as const, minWidth: 160, position: 'relative' as const, overflow: 'hidden' }}>
            <div style={{ position: 'absolute' as const, top: -30, right: -30, width: 100, height: 100, borderRadius: '50%', background: 'rgba(255,255,255,0.04)' }} />
            <div style={{ fontFamily: "'DM Serif Display', Georgia, serif", fontSize: 64, lineHeight: 1, letterSpacing: '-0.04em' }}>
              {score}<span style={{ fontSize: 18, opacity: 0.4, fontWeight: 300 }}>/100</span>
            </div>
            <div style={{ fontFamily: "'DM Mono', 'SFMono-Regular', monospace", fontSize: 10, letterSpacing: '0.12em', textTransform: 'uppercase' as const, opacity: 0.5, marginTop: 8 }}>
              综合得分
            </div>
            <div style={{ display: 'inline-flex', alignItems: 'center', gap: 4, marginTop: 10, background: 'rgba(255,255,255,0.12)', borderRadius: 99, padding: '3px 10px', fontSize: 11, fontWeight: 500 }}>
              ★ {scoreBadge}
            </div>
          </div>
        </div>

        {/* Two-column layout */}
        <div style={{ display: 'grid', gridTemplateColumns: hasSidebar ? '1fr 300px' : '1fr', gap: 28, alignItems: 'start' }}>
          <div>
            {/* AI Summary */}
            {(data.summary || verdict?.reason) && (
              <div style={{ marginBottom: 28 }}>
                <RdSectionLabel label="AI 综合评价" />
                <div style={{ background: RD.blueLight, border: '1px solid #c5d6f9', borderRadius: 12, padding: '20px 22px', fontSize: 14, color: '#1a2a6e', lineHeight: 1.7, fontStyle: 'italic' as const }}>
                  {data.summary || verdict?.reason}
                </div>
              </div>
            )}

            {/* Dimensions */}
            {dimensions.length > 0 && (
              <div style={{ marginBottom: 28 }}>
                <RdSectionLabel label="维度评分" />
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: 12 }}>
                  {dimensions.map((dim, i) => <RdDimCard key={i} dimension={dim} />)}
                </div>
              </div>
            )}

            {/* Q&A */}
            {turns.length > 0 && (
              <div style={{ marginBottom: 28 }}>
                <RdSectionLabel label="题目详情" />
                <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 16 }}>
                  {turns.map((turn, i) => <RdQACard key={turn.id} turn={turn} index={i} />)}
                </div>
              </div>
            )}

            {/* Interviewer Evaluation */}
            {data.interviewer_evaluation && (
              data.interviewer_evaluation.overall ||
              (data.interviewer_evaluation.key_observations || []).length > 0 ||
              (data.interviewer_evaluation.core_recommendations || []).length > 0
            ) && (
              <RdInterviewerEvaluation evaluation={data.interviewer_evaluation} />
            )}
          </div>

          {/* Sidebar */}
          {hasSidebar && (
            <div style={{ position: 'sticky' as const, top: 72 }}>
              {((data.strengths || []).length > 0 || (data.weaknesses || []).length > 0) && (
                <RdSideCard
                  title="核心评价"
                  icon={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"/></svg>}
                >
                  {(data.strengths || []).length > 0 && (
                    <div style={{ marginBottom: 12 }}>
                      <p style={{ fontSize: 11, fontWeight: 500, color: RD.green, marginBottom: 8, margin: '0 0 8px' }}>突出优势</p>
                      <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 6 }}>
                        {(data.strengths || []).slice(0, 3).map((s, i) => (
                          <div key={i} style={{ display: 'flex', gap: 8, fontSize: 12, color: RD.textMuted }}>
                            <span style={{ color: RD.green, flexShrink: 0 }}>•</span>
                            <span>{s}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                  {(data.weaknesses || []).length > 0 && (
                    <div>
                      <p style={{ fontSize: 11, fontWeight: 500, color: RD.amber, margin: '0 0 8px' }}>待改进</p>
                      <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 6 }}>
                        {(data.weaknesses || []).slice(0, 3).map((w, i) => (
                          <div key={i} style={{ display: 'flex', gap: 8, fontSize: 12, color: RD.textMuted }}>
                            <span style={{ color: RD.amber, flexShrink: 0 }}>•</span>
                            <span>{w}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </RdSideCard>
              )}

              {(hitKeywords.length > 0 || missKeywords.length > 0) && (
                <RdSideCard
                  title="关键词覆盖"
                  icon={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/><line x1="7" y1="7" x2="7.01" y2="7"/></svg>}
                >
                  <div style={{ display: 'flex', flexWrap: 'wrap' as const, gap: 6 }}>
                    {hitKeywords.map((k, i) => <RdKeyword key={`hit-${i}`} label={k} hit={true} />)}
                    {missKeywords.map((k, i) => <RdKeyword key={`miss-${i}`} label={k} hit={false} />)}
                  </div>
                </RdSideCard>
              )}

              {suggestions.length > 0 && (
                <RdSideCard
                  title="优先改进建议"
                  icon={<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>}
                >
                  <div style={{ display: 'flex', flexDirection: 'column' as const, gap: 10 }}>
                    {suggestions.slice(0, 4).map((sug, i) => (
                      <div key={i} style={{ display: 'flex', gap: 10, alignItems: 'flex-start', fontSize: 13, color: RD.textMuted, lineHeight: 1.55 }}>
                        <span style={{ fontFamily: "'DM Mono', 'SFMono-Regular', monospace", fontSize: 11, color: RD.textFaint, paddingTop: 2, flexShrink: 0 }}>
                          {String(i + 1).padStart(2, '0')}
                        </span>
                        <span>{sug}</span>
                      </div>
                    ))}
                  </div>
                </RdSideCard>
              )}
            </div>
          )}
        </div>
      </div>
    </>
  )
}

// 用于在完成态展示已经生成的报告。
function CompletedInterviewReview({ session }: { session: InterviewSession }) {
  const report = session.report_data
  return (
    <div className="flex-1 overflow-y-auto" style={{ background: RD.bg }}>
      <div className="mx-auto w-full max-w-5xl px-8 py-10">
        {report ? (
          <ReportPreview report={report} turns={session.turns || []} session={session} />
        ) : (
          <div style={{ background: RD.surface, border: `1px solid ${RD.border}`, borderRadius: 16, color: RD.textMuted, fontSize: 14, padding: 24, textAlign: 'center' }}>
            报告尚未生成，请回到面试中心生成报告。
          </div>
        )}
      </div>
    </div>
  )
}

// ── InterviewPage ──────────────────────────────────────────────────────────

// 用于渲染 InterviewPage 组件。
export default function InterviewPage() {
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()
  const t = useTranslations('interview.session')
  const locale = useLocale()
  const resumeId = Number(params?.id as string)
  const requestedSessionId = Number(searchParams?.get('session') || 0)

  const { isAuthenticated, isLoading: authLoading } = useAuth()
  const [mounted, setMounted] = useState(false)
  const [resume, setResume] = useState<Resume | null>(null)
  const [resumeLoading, setResumeLoading] = useState(true)
  const [digitalHuman, setDigitalHuman] = useState<DigitalHumanConversation | null>(null)
  const [isRedirectingAfterEnd, setIsRedirectingAfterEnd] = useState(false)

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
  const shouldAutoStartVoice = (session?.turns?.length || 0) === 0
  const isCompletedSession = session?.status === 'completed'
  const canEndInterview = Boolean(session && !isCompletedSession)

  const handleEndInterview = useCallback(async () => {
    setIsRedirectingAfterEnd(true)
    window.__chatResumeVoiceCleanup?.()
    const ended = await endInterview()
    if (ended) router.push('/interviews')
    if (!ended) setIsRedirectingAfterEnd(false)
  }, [endInterview, router])


  const handlePersistMessage = useCallback((
    role: ConversationMessage['role'],
    content: string,
  ) => {
    if (!session?.id) return
    resumeApi
      .recordInterviewMessage(session.id, { role, text: content })
      .catch(() => {})
  }, [session?.id])

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


  if (!mounted || authLoading || resumeLoading) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-white">
        <div className="h-8 w-8 animate-spin rounded-full border-2" style={{ borderColor: '#eef0f3', borderTopColor: '#0052ff' }} />
      </div>
    )
  }

  if (!isAuthenticated) {
    router.push('/login')
    return null
  }

  if (!resume) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-white">
        <p style={{ color: '#5b616e' }}>{t('resumeMissing')}</p>
        <Link href="/dashboard" className="text-sm font-semibold" style={{ color: '#0052ff' }}>
          {t('home')}
        </Link>
      </div>
    )
  }

  if (isRedirectingAfterEnd) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3 bg-white">
        <div className="h-8 w-8 animate-spin rounded-full border-2" style={{ borderColor: '#eef0f3', borderTopColor: '#0052ff' }} />
        <p style={{ color: '#5b616e', fontSize: 14, fontWeight: 650 }}>正在返回面试中心...</p>
      </div>
    )
  }

  const interviewTitle = [
    t('title'),
    resume.content.job_application?.target_company,
    resume.content.job_application?.target_title,
  ].filter(Boolean).join(' · ')

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-white">
      {/* Header */}
      <header
        className="flex-shrink-0 flex items-center justify-between gap-3 px-4 sm:px-5 border-b bg-white"
        style={{ borderColor: 'rgba(91,97,110,0.2)', height: 56 }}
      >
        <div className="flex min-w-0 flex-1 items-center gap-2 sm:gap-3">
          <Link
            href="/interviews"
            className="p-2 rounded-xl transition-colors"
            style={{ color: '#5b616e' }}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#eef0f3' }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
          >
            <ArrowLeftIcon className="h-4 w-4" />
          </Link>
          <div className="min-w-0 flex-1">
            <span
              className="text-sm font-semibold leading-tight truncate"
              style={{ color: '#0a0b0d', letterSpacing: '0.01em' }}
            >
              {interviewTitle}
            </span>
          </div>
        </div>

      </header>

      {/* Error banner */}
      {sessionError && (
        <div
          className="flex-shrink-0 px-5 py-2.5 text-xs font-medium border-b"
          style={{
            color: '#0a0b0d',
            backgroundColor: '#eef0f3',
            borderColor: 'rgba(91,97,110,0.2)',
          }}
        >
          {sessionError}
        </div>
      )}

      {/* Voice panel fills remaining height */}
      <div className="flex-1 flex flex-col min-h-0">
        {isCompletedSession && session ? (
          <CompletedInterviewReview session={session} />
        ) : (
          <VoicePanel
            sessionId={digitalHuman?.session_id}
            interviewSession={session}
            onPersistMessage={handlePersistMessage}
            autoStart={shouldAutoStartVoice}
            canEndInterview={canEndInterview}
            isEndingInterview={isSending}
            onEndInterview={handleEndInterview}
          />
        )}
      </div>
    </div>
  )
}
