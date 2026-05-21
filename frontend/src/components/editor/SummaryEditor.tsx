'use client'
// 用于提供 components/editor/SummaryEditor.tsx 模块。

import { useEffect, useState } from 'react'
import { useTranslations } from 'next-intl'

type SummaryData = { text?: string }

interface SummaryEditorProps {
  data: SummaryData
  onChange: (data: SummaryData) => void
}

// 用于编辑简历个人简介文本。
export default function SummaryEditor({ data, onChange }: SummaryEditorProps) {
  const [formData, setFormData] = useState<SummaryData>(data || {})
  const t = useTranslations('resume.forms.summary')

  useEffect(() => {
    setFormData(data || {})
  }, [data])

  // 用于同步个人简介文本。
  const handleTextChange = (text: string) => {
    const next = { ...formData, text }
    setFormData(next)
    onChange(next)
  }

  return (
    <div className="space-y-4">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-1">
          {t('text')}
        </label>
        <textarea
          value={formData.text || ''}
          onChange={(event) => handleTextChange(event.target.value)}
          placeholder={t('placeholder')}
          rows={8}
          className="w-full resize-y rounded-lg border border-gray-300 px-3 py-2 text-sm leading-6 focus:border-transparent focus:ring-2 focus:ring-primary-500"
        />
        <p className="mt-2 text-xs text-gray-500">{t('hint')}</p>
      </div>
    </div>
  )
}
