import re

with open('frontend/src/app/[locale]/resume/[id]/interview/page.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# Remove Volcengine specific constants
content = re.sub(r'const API_BASE_URL = [^\n]+\nconst SEND_SAMPLE_RATE = [^\n]+\nconst SEND_CHUNK_FRAMES = [^\n]+\n\ndeclare global \{\n\s+interface Window \{\n\s+__chatResumeVoiceCleanup\?: \(\) => void\n\s+\}\n\}\n', '', content)

# Remove VoicePanel completely
voice_panel_pattern = re.compile(r'type VoiceStatus =.*?function VoicePanel.*?return \(\n.*?<\/>\n  \)\n\}\n', re.DOTALL)
content = re.sub(voice_panel_pattern, '', content)

# Replace VoicePanel with ChatPanel
chat_panel_code = '''type ConversationMessage = {
  id: string
  role: 'candidate' | 'interviewer'
  content: string
}

function ChatPanel({
  sessionId,
  interviewSession,
  onSendMessage,
}: {
  sessionId: string | undefined
  interviewSession?: InterviewSession | null
  onSendMessage: (text: string) => Promise<void>
}) {
  const t = useTranslations('interview.session')
  const [messages, setMessages] = useState<ConversationMessage[]>([])
  const [inputValue, setInputValue] = useState('')
  const [isSending, setIsSending] = useState(false)
  const messagesEndRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!interviewSession?.turns?.length) return
    const restoredMessages = interviewSession.turns.flatMap((turn) => {
      const turnMessages: ConversationMessage[] = []
      if (turn.question) {
        turnMessages.push({ id: `turn-${turn.id}-q`, role: 'interviewer', content: turn.question })
      }
      if (turn.answer) {
        turnMessages.push({ id: `turn-${turn.id}-a`, role: 'candidate', content: turn.answer })
      }
      return turnMessages
    })
    setMessages(restoredMessages)
  }, [interviewSession?.turns])

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  const handleSend = async () => {
    if (!inputValue.trim() || isSending) return
    const text = inputValue.trim()
    setInputValue('')
    
    const userMsgId = `candidate-${Date.now()}`
    setMessages(prev => [...prev, { id: userMsgId, role: 'candidate', content: text }])
    
    setIsSending(true)
    try {
      await onSendMessage(text)
    } catch (error) {
      console.error(error)
      setMessages(prev => prev.filter(m => m.id !== userMsgId))
    } finally {
      setIsSending(false)
    }
  }

  return (
    <div className="flex flex-col h-full bg-white">
      <div className="flex-1 overflow-y-auto px-5 py-6">
        <div className="mx-auto max-w-4xl space-y-6">
          {messages.length === 0 ? (
            <div className="flex h-full items-center justify-center pt-20">
              <div className="px-6 py-4 rounded-2xl bg-[#eff6ff] text-[#1d4ed8] text-sm font-medium">
                {t('preparing') || '准备就绪，面试即将开始...'}
              </div>
            </div>
          ) : (
            messages.map((msg) => (
              <div key={msg.id} className={`flex ${msg.role === 'interviewer' ? 'justify-start' : 'justify-end'}`}>
                <div 
                  className={`px-4 py-3 text-sm leading-relaxed rounded-2xl max-w-[72%] ${
                    msg.role === 'interviewer' 
                      ? 'bg-[#eef0f3] text-[#0a0b0d] rounded-tl-sm' 
                      : 'bg-[#0052ff] text-white rounded-tr-sm'
                  }`}
                >
                  {msg.content}
                </div>
              </div>
            ))
          )}
          {isSending && (
            <div className="flex justify-end">
               <div className="px-4 py-3 text-sm rounded-2xl bg-[#0052ff] text-white opacity-60 rounded-tr-sm">
                 ...
               </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>
      
      <div className="border-t p-4 bg-white" style={{ borderColor: 'rgba(91,97,110,0.2)' }}>
        <div className="mx-auto max-w-4xl relative">
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault()
                handleSend()
              }
            }}
            placeholder="输入您的回答... (Enter 发送)"
            className="w-full bg-[#f9fafb] border border-gray-200 rounded-2xl pl-5 pr-16 py-3.5 text-sm focus:outline-none focus:border-[#0052ff] focus:ring-1 focus:ring-[#0052ff] resize-none"
            rows={2}
          />
          <button
            onClick={handleSend}
            disabled={!inputValue.trim() || isSending}
            className="absolute right-3 bottom-3 p-2 bg-[#0052ff] text-white rounded-xl hover:bg-[#578bfa] disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
          >
            发送
          </button>
        </div>
      </div>
    </div>
  )
}
'''
content = content.replace("type ReportData = NonNullable<InterviewSession['report_data']>", chat_panel_code + "\ntype ReportData = NonNullable<InterviewSession['report_data']>")

# Modify InterviewPage imports
content = content.replace('const [digitalHuman, setDigitalHuman] = useState<DigitalHumanConversation | null>(null)', '')
content = content.replace("import type { DigitalHumanConversation, InterviewSession, Resume } from '@/lib/api'", "import type { InterviewSession, Resume } from '@/lib/api'")
content = content.replace("import { digitalHumanApi, resumeApi } from '@/lib/api'", "import { resumeApi } from '@/lib/api'")

# Remove unused imports
content = content.replace('MicrophoneIcon,\n  PhoneXMarkIcon,\n  Cog6ToothIcon,', '')

# Remove digitalHuman useEffects
digital_human_use_effect_pattern = re.compile(r'\s*useEffect\(\(\) => \{\n\s+if \(!session\?\.id \|\| session\.status === \'completed\'\) return\n\s+if \(digitalHuman\?\.session_id\) return\n\s+digitalHumanApi\n\s+\.createConversation\(session\.id\)\n\s+\.then\(setDigitalHuman\)\n\s+\.catch\(\(\) => \{\}\)\n\s+\}, \[digitalHuman\?\.session_id, session\?\.id, session\?\.status\]\)\n\n\s+useEffect\(\(\) => \{\n\s+return \(\) => \{\n\s+if \(digitalHuman\?\.conversation_id\) \{\n\s+digitalHumanApi\.endConversation\(digitalHuman\.conversation_id\)\.catch\(\(\) => \{\}\)\n\s+\}\n\s+\}\n\s+\}, \[digitalHuman\?\.conversation_id\]\)', re.DOTALL)
content = re.sub(digital_human_use_effect_pattern, '', content)

# Remove window cleanup and endConversation in handleEndInterview
end_interview_pattern = re.compile(r'const handleEndInterview = useCallback\(async \(\) => \{\n.*?await endInterview\(\)\n\s+\}, \[digitalHuman\?\.conversation_id, endInterview\]\)', re.DOTALL)
content = re.sub(end_interview_pattern, 'const handleEndInterview = useCallback(async () => {\n    await endInterview()\n  }, [endInterview])', content)

# Remove start voice button block inside the header
header_btn_pattern = re.compile(r'\{canEndInterview && \(\n\s+<button\n\s+type="button"\n\s+onClick=\{handleEndInterview\}.*?</button>\n\s+\)\}', re.DOTALL)
content = re.sub(header_btn_pattern, r'{canEndInterview && (\n            <button\n              type="button"\n              onClick={handleEndInterview}\n              disabled={isSending}\n              className="flex items-center gap-2 px-4 py-2 text-sm font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 focus:outline-none focus:ring-2 focus:ring-black"\n              style={{\n                backgroundColor: \'#eef0f3\',\n                borderRadius: \'56px\',\n                border: \'1px solid #eef0f3\',\n                color: \'#0a0b0d\',\n                letterSpacing: \'0.01em\',\n              }}\n              onMouseEnter={(e) => { if (!e.currentTarget.disabled) { e.currentTarget.style.backgroundColor = \'#282b31\'; e.currentTarget.style.borderColor = \'#282b31\'; e.currentTarget.style.color = \'#ffffff\' } }}\n              onMouseLeave={(e) => { e.currentTarget.style.backgroundColor = \'#eef0f3\'; e.currentTarget.style.borderColor = \'#eef0f3\'; e.currentTarget.style.color = \'#0a0b0d\' }}\n            >\n              {isSending ? t(\'endingInterview\') : t(\'endInterview\')}\n            </button>\n          )}', content)

# Replace VoicePanel instantiation
voice_panel_inst_pattern = re.compile(r'<VoicePanel\n\s+sessionId=\{digitalHuman\?\.session_id\}\n\s+interviewSession=\{session\}\n\s+onPersistMessage=\{handlePersistMessage\}\n\s+autoStart=\{shouldAutoStartVoice\}\n\s+/>', re.DOTALL)
content = re.sub(voice_panel_inst_pattern, '<ChatPanel sessionId={session?.id?.toString()} interviewSession={session} onSendMessage={async (text) => { handlePersistMessage(\'candidate\', text) /* TODO: Hook up to text interview API */ }} />', content)

with open('frontend/src/app/[locale]/resume/[id]/interview/page.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
