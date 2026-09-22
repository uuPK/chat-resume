'use client'
// 用于提供支持选区加粗的简历文本输入框。

import { useRef, type TextareaHTMLAttributes } from 'react'
import { useTranslations } from 'next-intl'

import { toggleBoldSelection } from '@/lib/resumeInlineFormat'

interface BoldTextareaProps extends Omit<
  TextareaHTMLAttributes<HTMLTextAreaElement>,
  'onChange' | 'value'
> {
  value: string
  onValueChange: (value: string) => void
  containerClassName?: string
  onHeightChange?: (element: HTMLTextAreaElement) => void
}

/** 渲染带加粗按钮的文本框，选中文字后可添加或移除加粗标记。 */
export default function BoldTextarea({
  value,
  onValueChange,
  containerClassName = '',
  onHeightChange,
  className = '',
  onKeyDown,
  ...textareaProps
}: BoldTextareaProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null)
  const t = useTranslations('resume.forms.formatting')

  /** 更新文本值并让自适应高度输入框重新测量。 */
  const updateValue = (nextValue: string, element: HTMLTextAreaElement) => {
    onValueChange(nextValue)
    onHeightChange?.(element)
  }

  /** 切换当前选区的加粗标记，并保留选中范围。 */
  const toggleBold = () => {
    const textarea = textareaRef.current
    if (!textarea) return

    const result = toggleBoldSelection(
      value,
      textarea.selectionStart,
      textarea.selectionEnd,
    )
    updateValue(result.value, textarea)
    window.requestAnimationFrame(() => {
      textarea.focus()
      textarea.setSelectionRange(result.selectionStart, result.selectionEnd)
      onHeightChange?.(textarea)
    })
  }

  return (
    <div className={containerClassName}>
      <div className="mb-1 flex items-center justify-end gap-2 text-xs text-gray-500">
        <span>{t('hint')}</span>
        <button
          type="button"
          aria-label={t('bold')}
          title={`${t('bold')} (Ctrl+B)`}
          className="inline-flex h-7 min-w-7 items-center justify-center rounded border border-gray-300 bg-white px-2 font-bold text-gray-700 transition-colors hover:border-primary-500 hover:text-primary-600"
          onMouseDown={(event) => event.preventDefault()}
          onClick={toggleBold}
        >
          B
        </button>
      </div>
      <textarea
        {...textareaProps}
        ref={textareaRef}
        value={value}
        className={className}
        onChange={(event) => updateValue(event.target.value, event.currentTarget)}
        onKeyDown={(event) => {
          if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'b') {
            event.preventDefault()
            toggleBold()
            return
          }
          onKeyDown?.(event)
        }}
      />
    </div>
  )
}
