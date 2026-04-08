'use client'

import { motion } from 'framer-motion'
import { useState } from 'react'

interface JobApplicationData {
  target_company?: string
  target_title?: string
  jd_text?: string
  strategy?: string
}

interface JobApplicationEditorProps {
  data: JobApplicationData
  onChange: (data: JobApplicationData) => void
  resumeTitle?: string
  onTitleChange?: (title: string) => void
}

export default function JobApplicationEditor({ data, onChange, resumeTitle, onTitleChange }: JobApplicationEditorProps) {
  const [formData, setFormData] = useState<JobApplicationData>({
    target_company: data.target_company || '',
    target_title: data.target_title || '',
    jd_text: data.jd_text || '',
    strategy: data.strategy || ''
  })

  const handleInputChange = (field: keyof JobApplicationData, value: string) => {
    const newData = { ...formData, [field]: value }
    setFormData(newData)
    onChange(newData)
  }

  const handleTitleChange = (value: string) => {
    if (onTitleChange) {
      onTitleChange(value)
    }
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
            简历名称
          </label>
          <input
            type="text"
            value={resumeTitle || ''}
            onChange={(e) => handleTitleChange(e.target.value)}
            placeholder="请输入简历名称"
            className="w-full p-3 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          />
        </div>

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
          <label className="block text-sm font-medium text-gray-700 mb-2">
            职位描述 (JD)
          </label>
          <textarea
            value={formData.jd_text || ''}
            onChange={(e) => handleInputChange('jd_text', e.target.value)}
            placeholder="请粘贴完整的职位描述，包括岗位职责、任职要求等信息"
            rows={12}
            className="w-full p-3 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent resize-none"
          />
        </div>
      </div>

    </motion.div>
  )
}
