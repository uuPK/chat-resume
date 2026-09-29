'use client'
// 用于在打印页渲染 URL 或浏览器注入的简历数据。

import { useEffect, useState } from 'react'
import ResumePreview from '@/components/preview/ResumePreview'
import { buildModuleConfig, deserializeLayoutConfig } from '@/lib/resumeLayoutConfig'
import type { ResumeContent } from '@/types/resume'
import type { ResumeTemplateStyle } from '@/types/resumeLayout'

export interface PrintPayload {
  content?: ResumeContent
  template?: string
  layoutConfig?: Record<string, unknown> | null
}

declare global {
  interface Window {
    __RESUME_PRINT_PAYLOAD__?: PrintPayload
  }
}

// 用于标准化打印模板名称。
function normalizeTemplateStyle(template?: string): ResumeTemplateStyle {
  return template === 'modern' || template === 'formal' || template === 'emerald' ? template : 'classic'
}

// 用于等待浏览器导出数据，并复用网页预览组件。
export default function PrintResumeClient({ initialPayload, invalidMessage }: {
  initialPayload: PrintPayload | null
  invalidMessage: string
}) {
  const [payload, setPayload] = useState(initialPayload)

  useEffect(() => {
    if (!payload && window.__RESUME_PRINT_PAYLOAD__) {
      setPayload(window.__RESUME_PRINT_PAYLOAD__)
    }
  }, [payload])

  if (!payload?.content) {
    return <main className="flex items-center justify-center bg-white text-gray-500">{invalidMessage}</main>
  }

  const layoutConfig = deserializeLayoutConfig(payload.layoutConfig)
  return (
    <main className="bg-white">
      <ResumePreview
        content={payload.content}
        moduleOrder={buildModuleConfig(layoutConfig.moduleOrder, layoutConfig.visibleModules)}
        spacingScale={layoutConfig.spacingScale}
        templateStyle={normalizeTemplateStyle(payload.template)}
      />
    </main>
  )
}
