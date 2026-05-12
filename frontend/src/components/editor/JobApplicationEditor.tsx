'use client'

import { motion } from 'framer-motion'
import type { ChangeEvent, ClipboardEvent } from 'react'
import { PhotoIcon } from '@heroicons/react/24/outline'
import { useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'
import type { JobApplication } from '@/types/resume'
import { useTranslations } from 'next-intl'

interface JobApplicationEditorProps {
  data: JobApplication
  onChange: (data: JobApplication) => void
  onRecognizeJdImage: (file: File) => Promise<string>
}

const ALLOWED_JD_IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp']

/**
 * 用于编辑目标岗位信息，并支持从 JD 图片中自动识别文字。
 */
export default function JobApplicationEditor({
  data,
  onChange,
  onRecognizeJdImage,
}: JobApplicationEditorProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const t = useTranslations('resume.forms.job')
  const [formData, setFormData] = useState<JobApplication>({
    target_company: data.target_company || '',
    target_title: data.target_title || '',
    jd_text: data.jd_text || '',
    strategy: data.strategy || ''
  })
  const [isOcrProcessing, setIsOcrProcessing] = useState(false)

  /**
   * 用于在外部数据变化时同步本地表单状态。
   */
  useEffect(() => {
    setFormData({
      target_company: data.target_company || '',
      target_title: data.target_title || '',
      jd_text: data.jd_text || '',
      strategy: data.strategy || ''
    })
  }, [data])

  /**
   * 用于统一更新字段并把变更同步给父组件。
   */
  const handleInputChange = (field: keyof JobApplication, value: string) => {
    const newData = { ...formData, [field]: value }
    setFormData(newData)
    onChange(newData)
  }

  /**
   * 用于把 OCR 识别出的文本合并进当前 JD 内容。
   */
  const applyRecognizedText = (recognizedText: string) => {
    const cleanText = recognizedText.trim()
    if (!cleanText) {
      toast.error(t('emptyImage'))
      return
    }

    const nextValue = formData.jd_text?.trim()
      ? `${formData.jd_text?.trim()}\n\n${cleanText}`
      : cleanText

    handleInputChange('jd_text', nextValue)
    toast.success(t('ocrSuccess'))
  }

  /**
   * 用于校验并触发一张 JD 图片的 OCR 识别。
   */
  const handleJdImageOcr = async (file: File) => {
    if (!ALLOWED_JD_IMAGE_TYPES.includes(file.type)) {
      toast.error(t('invalidImage'))
      return
    }

    setIsOcrProcessing(true)
    const toastId = toast.loading(t('ocrLoading'))

    try {
      const recognizedText = await onRecognizeJdImage(file)
      toast.dismiss(toastId)
      applyRecognizedText(recognizedText)
    } catch (error) {
      toast.dismiss(toastId)
      const message = error instanceof Error ? error.message : t('ocrFailed')
      toast.error(message)
    } finally {
      setIsOcrProcessing(false)
    }
  }

  /**
   * 用于响应手动上传的 JD 图片文件。
   */
  const handleFileInputChange = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (!file) return

    await handleJdImageOcr(file)
    event.target.value = ''
  }

  /**
   * 用于拦截粘贴到 JD 输入框中的图片并触发 OCR。
   */
  const handleJdPaste = async (event: ClipboardEvent<HTMLTextAreaElement>) => {
    const items = Array.from(event.clipboardData.items || [])
    const imageItem = items.find((item) => item.type.startsWith('image/'))
    if (!imageItem) return

    const file = imageItem.getAsFile()
    if (!file) return

    event.preventDefault()
    await handleJdImageOcr(file)
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="space-y-6"
    >
      <div className="space-y-4">
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('targetCompany')}
          </label>
          <input
            type="text"
            value={formData.target_company || ''}
            onChange={(e) => handleInputChange('target_company', e.target.value)}
            placeholder={t('companyPlaceholder')}
            className="w-full p-3 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            {t('targetTitle')}
          </label>
          <input
            type="text"
            value={formData.target_title || ''}
            onChange={(e) => handleInputChange('target_title', e.target.value)}
            placeholder={t('titlePlaceholder')}
            className="w-full p-3 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between gap-3">
            <label className="block text-sm font-medium text-gray-700">
              {t('jd')}
            </label>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isOcrProcessing}
              className="inline-flex items-center gap-1 rounded-md border border-blue-200 px-3 py-1.5 text-xs font-medium text-blue-600 transition hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <PhotoIcon className="h-4 w-4" />
              {t('ocrButton')}
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            accept="image/png,image/jpeg,image/jpg,image/webp"
            onChange={handleFileInputChange}
            className="hidden"
          />
          <textarea
            value={formData.jd_text || ''}
            onChange={(e) => handleInputChange('jd_text', e.target.value)}
            onPaste={handleJdPaste}
            placeholder={t('jdPlaceholder')}
            rows={26}
            className="w-full p-3 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
          />
          {isOcrProcessing && (
            <p className="mt-2 text-xs text-blue-600">
              {t('ocrInline')}
            </p>
          )}
        </div>
      </div>

    </motion.div>
  )
}
