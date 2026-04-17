'use client'

import { motion } from 'framer-motion'
import type { ChangeEvent, ClipboardEvent } from 'react'
import { PhotoIcon } from '@heroicons/react/24/outline'
import { useEffect, useRef, useState } from 'react'
import toast from 'react-hot-toast'

import { resumeApi } from '@/lib/api'

interface JobApplicationData {
  target_company?: string
  target_title?: string
  jd_text?: string
  strategy?: string
}

interface JobApplicationEditorProps {
  data: JobApplicationData
  onChange: (data: JobApplicationData) => void
}

const ALLOWED_JD_IMAGE_TYPES = ['image/png', 'image/jpeg', 'image/jpg', 'image/webp']

/**
 * 用于编辑目标岗位信息，并支持从 JD 图片中自动识别文字。
 */
export default function JobApplicationEditor({ data, onChange }: JobApplicationEditorProps) {
  const fileInputRef = useRef<HTMLInputElement | null>(null)
  const [formData, setFormData] = useState<JobApplicationData>({
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
  const handleInputChange = (field: keyof JobApplicationData, value: string) => {
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
      toast.error('图片里没有识别到可用文字')
      return
    }

    const nextValue = formData.jd_text?.trim()
      ? `${formData.jd_text?.trim()}\n\n${cleanText}`
      : cleanText

    handleInputChange('jd_text', nextValue)
    toast.success('JD 图片识别成功，已插入文本')
  }

  /**
   * 用于校验并触发一张 JD 图片的 OCR 识别。
   */
  const handleJdImageOcr = async (file: File) => {
    if (!ALLOWED_JD_IMAGE_TYPES.includes(file.type)) {
      toast.error('仅支持 PNG、JPG、JPEG、WEBP 图片')
      return
    }

    setIsOcrProcessing(true)
    const toastId = toast.loading('正在识别 JD 图片...')

    try {
      const result = await resumeApi.ocrJobDescriptionImage(file)
      toast.dismiss(toastId)
      applyRecognizedText(result.text)
    } catch (error) {
      toast.dismiss(toastId)
      const message = error instanceof Error ? error.message : 'JD 图片识别失败，请重试'
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
            目标公司
          </label>
          <input
            type="text"
            value={formData.target_company || ''}
            onChange={(e) => handleInputChange('target_company', e.target.value)}
            placeholder="请输入目标公司名称"
            className="w-full p-3 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            目标岗位
          </label>
          <input
            type="text"
            value={formData.target_title || ''}
            onChange={(e) => handleInputChange('target_title', e.target.value)}
            placeholder="请输入目标岗位名称"
            className="w-full p-3 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

        <div>
          <div className="mb-2 flex items-center justify-between gap-3">
            <label className="block text-sm font-medium text-gray-700">
              职位描述 (JD)
            </label>
            <button
              type="button"
              onClick={() => fileInputRef.current?.click()}
              disabled={isOcrProcessing}
              className="inline-flex items-center gap-1 rounded-md border border-blue-200 px-3 py-1.5 text-xs font-medium text-blue-600 transition hover:bg-blue-50 disabled:cursor-not-allowed disabled:opacity-60"
            >
              <PhotoIcon className="h-4 w-4" />
              识别图片
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
            placeholder="请粘贴 JD 相关文字/图片"
            rows={12}
            className="w-full p-3 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
          />
          {isOcrProcessing && (
            <p className="mt-2 text-xs text-blue-600">
              正在识别图片文字，识别完成后会自动填入 JD 文本框。
            </p>
          )}
        </div>
      </div>

    </motion.div>
  )
}
