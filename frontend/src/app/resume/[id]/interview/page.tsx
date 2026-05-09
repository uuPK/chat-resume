'use client'

import { useCallback, useEffect, useRef, useState } from 'react'
import { useParams, useRouter, useSearchParams } from 'next/navigation'
import Link from 'next/link'
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

interface VoicePanelProps {
  sessionId: string | undefined
  interviewSession?: InterviewSession | null
  onPersistMessage?: (role: ConversationMessage['role'], content: string) => void
  autoStart?: boolean
  onStatusChange?: (status: VoiceStatus) => void
}

function VoicePanel({
  sessionId,
  interviewSession,
  onPersistMessage,
  autoStart = false,
  onStatusChange,
}: VoicePanelProps) {
  const [status, setStatus] = useState<VoiceStatus>('idle')
  const [inputLevel, setInputLevel] = useState(0)
  const [audioDevices, setAudioDevices] = useState<MediaDeviceInfo[]>([])
  const [selectedDeviceId, setSelectedDeviceId] = useState('')
  const [activeDeviceLabel, setActiveDeviceLabel] = useState('')
  const [messages, setMessages] = useState<ConversationMessage[]>([])
  const [liveMessage, setLiveMessage] = useState<ConversationMessage | null>(null)
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
    setLiveMessage({ id: `${role}-live`, role, content: nextText })
    setTurnStatus(role === 'candidate' ? 'user' : 'interviewer')

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
    setLiveMessage(null)
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
  }, [messages, liveMessage])

  const micBars = Array.from({ length: 12 }, (_, i) => {
    const threshold = (i + 1) / 12
    return inputLevel * 5 > threshold
  })
  const hasInterviewHistory = (interviewSession?.turns?.length || 0) > 0

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
            <div className="flex h-full items-center justify-center pointer-events-none select-none">
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
                连接中…
              </div>
            </div>
          ) : messages.length === 0 && !liveMessage ? (
            <div className="h-full" />
          ) : (
            <>
              {[...messages, ...(liveMessage ? [liveMessage] : [])].map((msg, idx) => {
                const isInterviewer = msg.role === 'interviewer'
                const isLive = msg === liveMessage
                return (
                  <div
                    key={msg.id}
                    className={`msg-enter flex gap-3 ${isInterviewer ? 'items-start' : 'items-start flex-row-reverse'}`}
                    style={{ animationDelay: `${Math.min(idx * 0.03, 0.15)}s` }}
                  >
                    {/* Avatar */}
                    {isInterviewer ? (
                      <div
                        className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center"
                        style={{ backgroundColor: '#282b31' }}
                      >
                        <MicrophoneIcon className="w-5 h-5 text-white" />
                      </div>
                    ) : (
                      <div
                        className="flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold text-white"
                        style={{ backgroundColor: '#0052ff' }}
                      >
                        我
                      </div>
                    )}

                    {/* Bubble */}
                    <div className="flex flex-col gap-1 max-w-[72%]">
                      <span
                        className={`text-xs font-semibold ${isInterviewer ? 'pl-1' : 'pr-1 text-right'}`}
                        style={{ color: '#5b616e' }}
                      >
                        {isInterviewer ? 'AI 面试官' : '我'}
                      </span>
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
            {status === 'connected' && (
              <span className="text-xs truncate hidden sm:block ml-1" style={{ color: '#5b616e' }}>{activeDeviceLabel}</span>
            )}

            {audioDevices.length > 0 && status !== 'connected' && (
              <div className="relative">
                <button
                  type="button"
                  onClick={() => setShowDeviceMenu((v) => !v)}
                  className="p-2 rounded-xl transition-colors"
                  style={{ color: '#5b616e' }}
                  onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#eef0f3' }}
                  onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
                  title="选择麦克风"
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
                    <p className="px-4 pt-3 pb-1 text-xs font-semibold uppercase tracking-wider" style={{ color: '#5b616e' }}>选择麦克风</p>
                    {[{ deviceId: '', label: '默认麦克风' }, ...audioDevices].map((d, i) => (
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
                        {d.label || `麦克风 ${i}`}
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
                  {sessionId ? (hasInterviewHistory ? '继续面试' : '开始面试') : '准备中…'}
                </button>
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
                  重试连接
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
    error: sessionError,
  } = useInterviewSession({
    resume,
    enabled: !!resume && isAuthenticated,
    requestedSessionId: requestedSessionId || undefined,
  })
  const shouldAutoStartVoice = (session?.turns?.length || 0) === 0

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

  useEffect(() => {
    return () => {
      if (digitalHuman?.conversation_id) {
        digitalHumanApi.endConversation(digitalHuman.conversation_id).catch(() => {})
      }
    }
  }, [digitalHuman?.conversation_id])

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
        <p style={{ color: '#5b616e' }}>简历不存在</p>
        <Link href="/dashboard" className="text-sm font-semibold" style={{ color: '#0052ff' }}>
          返回首页
        </Link>
      </div>
    )
  }

  return (
    <div className="flex h-screen flex-col overflow-hidden bg-white">
      {/* Header */}
      <header
        className="flex-shrink-0 flex items-center justify-between px-5 border-b bg-white"
        style={{ borderColor: 'rgba(91,97,110,0.2)', height: 56 }}
      >
        <div className="flex items-center gap-3">
          <Link
            href="/interviews"
            className="p-2 rounded-xl transition-colors"
            style={{ color: '#5b616e' }}
            onMouseEnter={(e) => { e.currentTarget.style.backgroundColor = '#eef0f3' }}
            onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = 'transparent' }}
          >
            <ArrowLeftIcon className="h-4 w-4" />
          </Link>
          <div className="flex items-center gap-2 min-w-0">
            <span
              className="text-sm font-semibold leading-tight"
              style={{ color: '#0a0b0d', letterSpacing: '0.01em' }}
            >
              Interview Room
            </span>
            {resume && (
              <>
                <span className="text-xs leading-tight" style={{ color: '#d1d5db' }}>·</span>
                <span
                  className="text-xs truncate max-w-[180px] leading-tight"
                  style={{ color: '#5b616e' }}
                >
                  {resume.title || resume.original_filename}
                </span>
              </>
            )}
          </div>
        </div>

        <div />
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
        <VoicePanel
          sessionId={digitalHuman?.session_id}
          interviewSession={session}
          onPersistMessage={handlePersistMessage}
          autoStart={shouldAutoStartVoice}
        />
      </div>
    </div>
  )
}
