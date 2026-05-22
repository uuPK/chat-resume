'use client'
// 用于提供 app/[locale]/resume/[id]/interview/page.tsx 模块。

import { useCallback, useEffect, useRef, useState } from 'react'
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

// ── 报告色彩系统（专业 slate/blue 主题） ──────────────────────────────────

const RC = {
  bg: '#f8fafc',
  card: '#ffffff',
  border: '#e2e8f0',
  borderSoft: '#f1f5f9',
  ink: '#0f172a',
  text: '#1e293b',
  muted: '#64748b',
  subtle: '#94a3b8',
  blue: '#2563eb',
  blueDark: '#1d4ed8',
  blueBg: '#eff6ff',
  blueBorder: '#bfdbfe',
  green: '#059669',
  greenBg: '#ecfdf5',
  greenBorder: '#a7f3d0',
  amber: '#d97706',
  amberBg: '#fffbeb',
  amberBorder: '#fde68a',
  red: '#dc2626',
  redBg: '#fef2f2',
  redBorder: '#fecaca',
} as const

// 用于从结论等级推导对应色彩。
function verdictColors(level?: string) {
  if (level === 'strong') return { color: RC.green, bg: RC.greenBg, border: RC.greenBorder }
  if (level === 'risky') return { color: RC.red, bg: RC.redBg, border: RC.redBorder }
  return { color: RC.amber, bg: RC.amberBg, border: RC.amberBorder }
}

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

// 用于渲染评分环状图表。
function ScoreRing({ score }: { score: number }) {
  const radius = 44
  const circumference = 2 * Math.PI * radius
  const dashOffset = circumference * (1 - score / 100)
  const ringColor = score >= 75 ? RC.green : score >= 55 ? RC.amber : RC.red
  return (
    <div style={{ height: 120, position: 'relative', width: 120 }}>
      <svg height="120" style={{ transform: 'rotate(-90deg)' }} width="120">
        <circle cx="60" cy="60" fill="none" r={radius} stroke="rgba(255,255,255,0.15)" strokeWidth="8" />
        <circle
          cx="60" cy="60" fill="none" r={radius}
          stroke={ringColor} strokeDasharray={circumference}
          strokeDashoffset={dashOffset} strokeLinecap="round" strokeWidth="8"
          style={{ transition: 'stroke-dashoffset 0.9s ease' }}
        />
      </svg>
      <div style={{ alignItems: 'center', bottom: 0, display: 'flex', flexDirection: 'column', justifyContent: 'center', left: 0, position: 'absolute', right: 0, top: 0 }}>
        <span style={{ color: '#fff', fontSize: 30, fontWeight: 900, lineHeight: 1 }}>{score}</span>
        <span style={{ color: 'rgba(255,255,255,0.55)', fontSize: 11, fontWeight: 600, marginTop: 2 }}>/ 100</span>
      </div>
    </div>
  )
}

// 用于渲染能力标签胶囊。
function CapChip({ children, tone }: { children: string; tone: 'green' | 'red' | 'blue' | 'neutral' }) {
  const styles = {
    green: { bg: RC.greenBg, border: RC.greenBorder, color: '#065f46' },
    red: { bg: RC.redBg, border: RC.redBorder, color: '#991b1b' },
    blue: { bg: RC.blueBg, border: RC.blueBorder, color: '#1e40af' },
    neutral: { bg: RC.borderSoft, border: RC.border, color: RC.muted },
  }[tone]
  return (
    <span style={{
      background: styles.bg,
      border: `1px solid ${styles.border}`,
      borderRadius: 99,
      color: styles.color,
      display: 'inline-block',
      fontSize: 12,
      fontWeight: 600,
      padding: '4px 10px',
    }}>
      {children}
    </span>
  )
}

// 用于渲染带色点的项目列表。
function BulletList({ items, tone = 'neutral' }: { items: string[]; tone?: 'green' | 'red' | 'blue' | 'neutral' }) {
  const dotColor = { green: RC.green, red: RC.red, blue: RC.blue, neutral: RC.subtle }[tone]
  return (
    <ul style={{ display: 'grid', gap: 10, listStyle: 'none', margin: 0, padding: 0 }}>
      {items.map((item, i) => (
        <li key={i} style={{ alignItems: 'flex-start', display: 'flex', gap: 10 }}>
          <span style={{ background: dotColor, borderRadius: 999, flexShrink: 0, height: 6, marginTop: 9, width: 6 }} />
          <span style={{ color: RC.text, fontSize: 14, lineHeight: 1.75 }}>{item}</span>
        </li>
      ))}
    </ul>
  )
}

// 用于渲染卡片区块标题行。
function SectionHeading({ title, badge }: { title: string; badge?: string }) {
  return (
    <div style={{ alignItems: 'center', display: 'flex', gap: 10, marginBottom: 20 }}>
      <h2 style={{ color: RC.ink, fontSize: 17, fontWeight: 800, margin: 0 }}>{title}</h2>
      {badge && (
        <span style={{ background: RC.borderSoft, border: `1px solid ${RC.border}`, borderRadius: 99, color: RC.muted, fontSize: 12, fontWeight: 600, padding: '2px 8px' }}>
          {badge}
        </span>
      )}
    </div>
  )
}

// 用于渲染可展开的能力维度行。
function DimensionRow({ dimension }: { dimension: NonNullable<ReportData['dimensions']>[number] }) {
  const [expanded, setExpanded] = useState(false)
  const pct = typeof dimension.score === 'number' ? dimension.score * 20 : 0
  const barColor = pct >= 70 ? RC.green : pct >= 50 ? RC.amber : RC.red

  return (
    <div style={{ border: `1px solid ${RC.border}`, borderRadius: 14, overflow: 'hidden' }}>
      <button
        type="button"
        onClick={() => setExpanded(v => !v)}
        style={{ alignItems: 'center', background: 'transparent', border: 'none', cursor: 'pointer', display: 'flex', gap: 14, padding: '14px 16px', textAlign: 'left', width: '100%' }}
      >
        <div style={{ flex: 1 }}>
          <div style={{ alignItems: 'center', display: 'flex', gap: 8, marginBottom: 8 }}>
            <span style={{ color: RC.ink, fontSize: 14, fontWeight: 700 }}>{dimension.title}</span>
            {typeof dimension.score === 'number' && (
              <span style={{ color: RC.muted, fontSize: 12, fontWeight: 600 }}>{dimension.score}/5</span>
            )}
          </div>
          <div style={{ background: RC.borderSoft, borderRadius: 999, height: 6, overflow: 'hidden' }}>
            <div style={{ background: barColor, borderRadius: 999, height: '100%', transition: 'width 0.7s ease', width: `${pct}%` }} />
          </div>
        </div>
        <span style={{ color: RC.subtle, flexShrink: 0, fontSize: 16, transform: expanded ? 'rotate(90deg)' : 'none', transition: 'transform 0.2s' }}>›</span>
      </button>
      {expanded && (
        <div style={{ borderTop: `1px solid ${RC.borderSoft}`, padding: '14px 16px 16px' }}>
          <p style={{ color: RC.text, fontSize: 14, lineHeight: 1.7, margin: '0 0 10px' }}>{dimension.assessment}</p>
          {dimension.evidence && (
            <p style={{ color: RC.muted, fontSize: 13, lineHeight: 1.6, margin: '0 0 10px' }}>
              <strong style={{ color: RC.ink }}>依据：</strong>{dimension.evidence}
            </p>
          )}
          {dimension.advice && (
            <p style={{ background: RC.blueBg, border: `1px solid ${RC.blueBorder}`, borderRadius: 10, color: '#1e40af', fontSize: 13, lineHeight: 1.6, margin: 0, padding: '10px 12px' }}>
              建议：{dimension.advice}
            </p>
          )}
        </div>
      )}
    </div>
  )
}

// 用于渲染可展开的单题解析卡片。
function QuestionCard({ turn, index }: { turn: InterviewSession['turns'][number]; index: number }) {
  const [expanded, setExpanded] = useState(false)
  const evaluation = getTurnEvaluation(turn)
  const strengths: string[] = evaluation?.evidence || []
  const gaps: string[] = evaluation?.gaps || []

  return (
    <article style={{ border: `1px solid ${RC.border}`, borderRadius: 16, overflow: 'hidden' }}>
      <button
        type="button"
        onClick={() => setExpanded(v => !v)}
        style={{ alignItems: 'flex-start', background: RC.borderSoft, border: 'none', cursor: 'pointer', display: 'flex', gap: 12, padding: '14px 16px', textAlign: 'left', width: '100%' }}
      >
        <span style={{ background: RC.blue, borderRadius: 8, color: '#fff', flexShrink: 0, fontSize: 11, fontWeight: 700, marginTop: 2, padding: '3px 8px' }}>
          Q{index + 1}
        </span>
        <p style={{ color: RC.ink, flex: 1, fontSize: 14, fontWeight: 700, lineHeight: 1.6, margin: 0 }}>{turn.question}</p>
        <span style={{ color: RC.subtle, flexShrink: 0, fontSize: 16, marginTop: 2, transform: expanded ? 'rotate(90deg)' : 'none', transition: 'transform 0.2s' }}>›</span>
      </button>

      {expanded && (
        <div style={{ padding: 16 }}>
          <div style={{ marginBottom: 14 }}>
            <p style={{ color: RC.subtle, fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', margin: '0 0 6px', textTransform: 'uppercase' }}>你的回答</p>
            <p style={{ background: RC.borderSoft, borderLeft: `3px solid ${RC.border}`, borderRadius: 10, color: RC.text, fontSize: 14, lineHeight: 1.75, margin: 0, padding: '12px 14px' }}>
              {turn.answer || '（候选人跳过此问题）'}
            </p>
          </div>

          {(strengths.length > 0 || gaps.length > 0) && (
            <div className="grid gap-3 md:grid-cols-2" style={{ marginBottom: 14 }}>
              {strengths.length > 0 && (
                <div style={{ background: RC.greenBg, border: `1px solid ${RC.greenBorder}`, borderRadius: 12, padding: 14 }}>
                  <p style={{ color: RC.green, fontSize: 12, fontWeight: 700, margin: '0 0 10px' }}>亮点</p>
                  <BulletList items={strengths} tone="green" />
                </div>
              )}
              {gaps.length > 0 && (
                <div style={{ background: RC.redBg, border: `1px solid ${RC.redBorder}`, borderRadius: 12, padding: 14 }}>
                  <p style={{ color: RC.red, fontSize: 12, fontWeight: 700, margin: '0 0 10px' }}>待改进</p>
                  <BulletList items={gaps} tone="red" />
                </div>
              )}
            </div>
          )}

          {(evaluation?.summary || evaluation?.advice) && (
            <div style={{ background: RC.blueBg, border: `1px solid ${RC.blueBorder}`, borderRadius: 12, padding: 14 }}>
              <p style={{ color: '#1e40af', fontSize: 12, fontWeight: 700, margin: '0 0 8px' }}>面试官点评</p>
              {evaluation.summary && <p style={{ color: RC.text, fontSize: 14, lineHeight: 1.7, margin: 0 }}>{evaluation.summary}</p>}
              {evaluation.advice && evaluation.summary && (
                <p style={{ color: RC.muted, fontSize: 13, lineHeight: 1.6, margin: '8px 0 0' }}>{evaluation.advice}</p>
              )}
              {evaluation.advice && !evaluation.summary && (
                <p style={{ color: RC.text, fontSize: 14, lineHeight: 1.7, margin: 0 }}>{evaluation.advice}</p>
              )}
            </div>
          )}
        </div>
      )}
    </article>
  )
}

// 用于渲染示范回答对比卡片。
function AnswerRewriteCard({ rewrite, index }: { rewrite: NonNullable<ReportData['answer_rewrites']>[number]; index: number }) {
  return (
    <div style={{ border: `1px solid ${RC.border}`, borderRadius: 16, overflow: 'hidden' }}>
      <div style={{ background: RC.borderSoft, borderBottom: `1px solid ${RC.border}`, padding: '12px 16px' }}>
        <span style={{ color: RC.muted, fontSize: 12, fontWeight: 700 }}>示范回答 {index + 1}</span>
        {rewrite.original_problem && (
          <p style={{ color: RC.ink, fontSize: 14, fontWeight: 700, lineHeight: 1.55, margin: '6px 0 0' }}>{rewrite.original_problem}</p>
        )}
      </div>
      <div style={{ borderBottom: `1px solid ${RC.borderSoft}`, padding: 16 }}>
        <p style={{ color: RC.green, fontSize: 12, fontWeight: 700, margin: '0 0 8px' }}>推荐回答</p>
        <p style={{ color: RC.text, fontSize: 14, lineHeight: 1.8, margin: 0 }}>{rewrite.recommended_answer}</p>
      </div>
      {rewrite.why_better && (
        <div style={{ padding: 16 }}>
          <p style={{ color: RC.amber, fontSize: 12, fontWeight: 700, margin: '0 0 6px' }}>为什么更好</p>
          <p style={{ color: RC.muted, fontSize: 13, lineHeight: 1.7, margin: 0 }}>{rewrite.why_better}</p>
        </div>
      )}
    </div>
  )
}

// 用于渲染完整的面试复盘报告。
function ReportPreview({
  report,
  turns,
}: {
  report: InterviewSession['report_data']
  turns: InterviewSession['turns']
}) {
  if (!report) return null

  const data = report as ReportData
  const verdict = data.candidate_verdict
  const match = data.job_match
  const vc = verdictColors(verdict?.level)
  const score = computeOverallScore(data.dimensions, verdict?.level)
  const targetLabel = [match?.target_company, match?.target_title].filter(Boolean).join(' · ') || '综合面试'
  const verdictBadge = verdict?.label || (verdict?.level === 'strong' ? '推进意向强' : verdict?.level === 'risky' ? '风险较高' : '边缘候选')
  const dimensions = data.dimensions || []
  const rewrites = data.answer_rewrites || []
  const hasCovered = (match?.covered_capabilities || []).length > 0
  const hasMissing = (match?.missing_capabilities || []).length > 0
  const hasConcerns = (match?.interviewer_concerns || []).length > 0
  const hasFollowups = (match?.likely_followups || []).length > 0
  const hasTraining = (data.next_training_plan || []).length > 0
  const hasResumeFeedback = (data.resume_feedback || []).length > 0

  return (
    <div style={{ display: 'grid', gap: 20 }}>

      {/* ── Hero ──────────────────────────────────────────────────────── */}
      <section style={{
        background: 'linear-gradient(135deg, #0f172a 0%, #1e293b 100%)',
        borderRadius: 24,
        boxShadow: '0 20px 60px rgba(15,23,42,0.18)',
        overflow: 'hidden',
        padding: '32px 32px 28px',
      }}>
        {/* badges */}
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 24 }}>
          <span style={{ background: 'rgba(255,255,255,0.12)', borderRadius: 99, color: 'rgba(255,255,255,0.9)', fontSize: 12, fontWeight: 700, padding: '5px 12px' }}>
            面试复盘报告
          </span>
          <span style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.15)', borderRadius: 99, color: 'rgba(255,255,255,0.6)', fontSize: 12, fontWeight: 600, padding: '5px 12px' }}>
            {targetLabel}
          </span>
          {verdict?.level && (
            <span style={{ background: vc.bg, border: `1px solid ${vc.border}`, borderRadius: 99, color: vc.color, fontSize: 12, fontWeight: 700, padding: '5px 12px' }}>
              {verdictBadge}
            </span>
          )}
        </div>

        {/* title + score ring */}
        <div className="grid gap-6 md:grid-cols-[1fr_auto]" style={{ alignItems: 'center', marginBottom: 24 }}>
          <div>
            <h1 style={{ color: '#fff', fontSize: 34, fontWeight: 900, letterSpacing: '-0.03em', lineHeight: 1.12, margin: '0 0 12px' }}>
              面试复盘报告
            </h1>
            <p style={{ color: 'rgba(255,255,255,0.7)', fontSize: 15, lineHeight: 1.8, margin: 0, maxWidth: 620 }}>
              {data.summary || verdict?.reason || '报告已生成，请查看下方各维度详细分析。'}
            </p>
          </div>
          <ScoreRing score={score} />
        </div>

        {/* key stats */}
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: '岗位名称', value: match?.target_title || '目标岗位' },
            { label: '目标公司', value: match?.target_company || '综合面试' },
            { label: '题目数量', value: `${turns.length} 题` },
          ].map(({ label, value }) => (
            <div key={label} style={{ background: 'rgba(255,255,255,0.06)', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 14, padding: '13px 16px' }}>
              <p style={{ color: 'rgba(255,255,255,0.45)', fontSize: 11, fontWeight: 700, letterSpacing: '0.08em', margin: '0 0 5px', textTransform: 'uppercase' }}>{label}</p>
              <p style={{ color: '#fff', fontSize: 15, fontWeight: 800, lineHeight: 1.2, margin: 0, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{value}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── 面试官核心评价 ───────────────────────────────────────────── */}
      <section style={{ background: RC.card, border: `1px solid ${RC.border}`, borderRadius: 20, boxShadow: '0 1px 4px rgba(15,23,42,0.05)', padding: '26px 26px 28px' }}>
        <SectionHeading title="面试官核心评价" />
        {verdict?.reason && (
          <p style={{ color: RC.text, fontSize: 15, lineHeight: 1.85, margin: '0 0 20px' }}>{verdict.reason}</p>
        )}
        <div className="grid gap-4 md:grid-cols-2">
          {(data.strengths || []).length > 0 && (
            <div style={{ background: RC.greenBg, border: `1px solid ${RC.greenBorder}`, borderRadius: 14, padding: 18 }}>
              <p style={{ color: RC.green, fontSize: 13, fontWeight: 700, margin: '0 0 12px' }}>突出优势</p>
              <BulletList items={data.strengths || []} tone="green" />
            </div>
          )}
          {([...(data.interviewer_risks || []), ...(data.weaknesses || [])]).length > 0 && (
            <div style={{ background: RC.redBg, border: `1px solid ${RC.redBorder}`, borderRadius: 14, padding: 18 }}>
              <p style={{ color: RC.red, fontSize: 13, fontWeight: 700, margin: '0 0 12px' }}>面试官顾虑</p>
              <BulletList items={[...(data.interviewer_risks || []), ...(data.weaknesses || [])]} tone="red" />
            </div>
          )}
        </div>
      </section>

      {/* ── 岗位匹配分析 ─────────────────────────────────────────────── */}
      {(hasCovered || hasMissing || hasConcerns || hasFollowups) && (
        <section style={{ background: RC.card, border: `1px solid ${RC.border}`, borderRadius: 20, boxShadow: '0 1px 4px rgba(15,23,42,0.05)', padding: '26px 26px 28px' }}>
          <SectionHeading title="岗位匹配分析" />
          {(hasCovered || hasMissing) && (
            <div className="grid gap-4 md:grid-cols-2" style={{ marginBottom: hasConcerns || hasFollowups ? 16 : 0 }}>
              {hasCovered && (
                <div>
                  <p style={{ color: RC.green, fontSize: 13, fontWeight: 700, margin: '0 0 10px' }}>已覆盖能力</p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {(match?.covered_capabilities || []).map((cap, i) => <CapChip key={i} tone="green">{cap}</CapChip>)}
                  </div>
                </div>
              )}
              {hasMissing && (
                <div>
                  <p style={{ color: RC.red, fontSize: 13, fontWeight: 700, margin: '0 0 10px' }}>能力缺口</p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {(match?.missing_capabilities || []).map((cap, i) => <CapChip key={i} tone="red">{cap}</CapChip>)}
                  </div>
                </div>
              )}
            </div>
          )}
          {hasConcerns && (
            <div style={{ background: RC.amberBg, border: `1px solid ${RC.amberBorder}`, borderRadius: 14, marginBottom: hasFollowups ? 12 : 0, padding: 16 }}>
              <p style={{ color: RC.amber, fontSize: 13, fontWeight: 700, margin: '0 0 10px' }}>面试官可能追问</p>
              <BulletList items={match?.interviewer_concerns || []} />
            </div>
          )}
          {hasFollowups && (
            <div style={{ background: RC.blueBg, border: `1px solid ${RC.blueBorder}`, borderRadius: 14, padding: 16 }}>
              <p style={{ color: RC.blue, fontSize: 13, fontWeight: 700, margin: '0 0 10px' }}>预计追问方向</p>
              <BulletList items={match?.likely_followups || []} tone="blue" />
            </div>
          )}
        </section>
      )}

      {/* ── 综合能力维度 ─────────────────────────────────────────────── */}
      {dimensions.length > 0 && (
        <section style={{ background: RC.card, border: `1px solid ${RC.border}`, borderRadius: 20, boxShadow: '0 1px 4px rgba(15,23,42,0.05)', padding: '26px 26px 28px' }}>
          <SectionHeading title="综合能力维度" badge={`${dimensions.length} 项`} />
          <div style={{ display: 'grid', gap: 10 }}>
            {dimensions.map((dim, i) => <DimensionRow key={i} dimension={dim} />)}
          </div>
        </section>
      )}

      {/* ── 成长建议 ─────────────────────────────────────────────────── */}
      {(hasTraining || hasResumeFeedback) && (
        <section style={{ background: RC.card, border: `1px solid ${RC.border}`, borderRadius: 20, boxShadow: '0 1px 4px rgba(15,23,42,0.05)', padding: '26px 26px 28px' }}>
          <SectionHeading title="成长建议" />
          <div className="grid gap-4 md:grid-cols-2">
            {hasTraining && (
              <div>
                <p style={{ color: RC.blue, fontSize: 13, fontWeight: 700, margin: '0 0 12px' }}>训练计划</p>
                <BulletList items={data.next_training_plan || []} tone="blue" />
              </div>
            )}
            {hasResumeFeedback && (
              <div>
                <p style={{ color: RC.amber, fontSize: 13, fontWeight: 700, margin: '0 0 12px' }}>简历优化建议</p>
                <BulletList items={data.resume_feedback || []} />
              </div>
            )}
          </div>
        </section>
      )}

      {/* ── 示范回答 ─────────────────────────────────────────────────── */}
      {rewrites.length > 0 && (
        <section style={{ background: RC.card, border: `1px solid ${RC.border}`, borderRadius: 20, boxShadow: '0 1px 4px rgba(15,23,42,0.05)', padding: '26px 26px 28px' }}>
          <SectionHeading title="示范回答" badge={`${rewrites.length} 题`} />
          <div style={{ display: 'grid', gap: 14 }}>
            {rewrites.map((rewrite, i) => <AnswerRewriteCard key={i} rewrite={rewrite} index={i} />)}
          </div>
        </section>
      )}

      {/* ── 逐题解析 ─────────────────────────────────────────────────── */}
      {turns.length > 0 && (
        <section style={{ background: RC.card, border: `1px solid ${RC.border}`, borderRadius: 20, boxShadow: '0 1px 4px rgba(15,23,42,0.05)', padding: '26px 26px 28px' }}>
          <SectionHeading title="逐题解析" badge={`共 ${turns.length} 题`} />
          <div style={{ display: 'grid', gap: 12 }}>
            {turns.map((turn, i) => <QuestionCard key={turn.id} turn={turn} index={i} />)}
          </div>
        </section>
      )}
    </div>
  )
}

// 用于在完成态展示已经生成的报告。
function CompletedInterviewReview({ session }: { session: InterviewSession }) {
  const report = session.report_data
  return (
    <div className="flex-1 overflow-y-auto" style={{ background: RC.bg }}>
      <div className="mx-auto w-full max-w-5xl px-5 py-8">
        {report ? (
          <ReportPreview report={report} turns={session.turns || []} />
        ) : (
          <div style={{ background: RC.card, border: `1px solid ${RC.border}`, borderRadius: 16, color: RC.muted, fontSize: 14, padding: 24, textAlign: 'center' }}>
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
