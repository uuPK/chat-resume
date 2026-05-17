import {
  CheckCircleIcon,
} from '@heroicons/react/24/outline'
import { useTranslations } from 'next-intl'

import type { StreamEvent } from '@/hooks/useStreamingChat'

type ToolActivityEvent = Extract<StreamEvent, { type: 'tool_call' | 'tool_result' }>

export function AgentToolActivity({
  event,
  live = false,
}: {
  event: ToolActivityEvent
  live?: boolean
}) {
  const t = useTranslations('resume.editor')
  const isResult = event.type === 'tool_result'
  const title = isResult || !live ? t('toolResult') : t('toolRunning')

  return (
    <div className="mb-2 rounded-xl border border-gray-200 bg-white px-3 py-2 text-xs shadow-sm">
      <div className="flex min-w-0 items-center gap-2">
        {isResult || !live ? (
          <CheckCircleIcon className="h-[0.9rem] w-[0.9rem] flex-shrink-0 text-emerald-600" />
        ) : (
          <span className="h-3 w-3 flex-shrink-0 rounded-full border border-blue-200 border-t-blue-600 animate-spin" />
        )}
        <span className="font-semibold text-[#0a0b0d]">{title}</span>
        <code className="min-w-0 truncate font-mono text-[#3f4654]">
          {event.toolName}
        </code>
      </div>
    </div>
  )
}
