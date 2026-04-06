'use client'

import { useEffect, useState } from 'react'
import {
  BriefcaseIcon,
  PlusIcon,
  TrashIcon
} from '@heroicons/react/24/outline'

interface Highlight {
  id?: string
  text: string
}

interface WorkExperience {
  id?: string
  company: string
  position: string
  duration: string
  description?: string
  summary?: string
  location?: string
  employment_type?: string
  highlights?: Highlight[]
}

interface WorkExperienceEditorProps {
  data: WorkExperience[]
  onChange: (data: WorkExperience[]) => void
}

function normalizeHighlights(work: WorkExperience): Highlight[] {
  if (work.highlights && work.highlights.length > 0) {
    return work.highlights
  }
  if (work.description) {
    const lines = work.description
      .split('\n')
      .map(line => line.trim().replace(/^•\s*/, ''))
      .filter(Boolean)
    if (lines.length > 1) {
      return lines.map((text, index) => ({
        id: `${work.id || 'work'}_hl_${index}`,
        text
      }))
    }
  }
  return [{ id: `${work.id || 'work'}_hl_0`, text: '' }]
}

export default function WorkExperienceEditor({ data, onChange }: WorkExperienceEditorProps) {
  const [workList, setWorkList] = useState<WorkExperience[]>(Array.isArray(data) ? data : [])

  useEffect(() => {
    const next = Array.isArray(data)
      ? data.map((work, index) => ({
          ...work,
          id: work.id || `work_${Date.now()}_${index}`,
          summary: work.summary || (work.description?.includes('\n') ? '' : work.description) || '',
          description: work.description || work.summary || '',
          highlights: normalizeHighlights(work)
        }))
      : []
    setWorkList(next)
  }, [data])

  const commit = (next: WorkExperience[]) => {
    setWorkList(next)
    onChange(next.map(work => ({
      ...work,
      description: [
        work.summary || '',
        ...(work.highlights || []).map(item => `• ${item.text}`),
      ].filter(Boolean).join('\n')
    })))
  }

  const addWork = () => {
    commit([
      ...workList,
      {
        id: `work_${Date.now()}`,
        company: '',
        position: '',
        duration: '',
        description: '',
        summary: '',
        location: '',
        employment_type: '全职',
        highlights: [{ id: `hl_${Date.now()}`, text: '' }]
      }
    ])
  }

  const removeWork = (id: string) => {
    commit(workList.filter(work => work.id !== id))
  }

  const updateWork = (id: string, field: keyof WorkExperience, value: unknown) => {
    commit(workList.map(work => (
      work.id === id ? { ...work, [field]: value } : work
    )))
  }

  const addHighlight = (workId: string) => {
    const work = workList.find(item => item.id === workId)
    if (!work) return
    updateWork(workId, 'highlights', [...(work.highlights || []), { id: `hl_${Date.now()}`, text: '' }])
  }

  const updateHighlight = (workId: string, index: number, value: string) => {
    const work = workList.find(item => item.id === workId)
    if (!work) return
    const next = [...(work.highlights || [])]
    next[index] = { ...next[index], text: value }
    updateWork(workId, 'highlights', next)
  }

  const removeHighlight = (workId: string, index: number) => {
    const work = workList.find(item => item.id === workId)
    if (!work) return
    const current = work.highlights || []
    if (current.length <= 1) return
    updateWork(workId, 'highlights', current.filter((_, itemIndex) => itemIndex !== index))
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center">
          <BriefcaseIcon className="w-5 h-5 mr-2" />
          工作经验
        </h3>
        <button
          onClick={addWork}
          className="btn-secondary flex items-center space-x-1 text-sm"
        >
          <PlusIcon className="w-4 h-4" />
          <span>添加工作经验</span>
        </button>
      </div>

      {workList.length === 0 ? (
        <div className="text-center py-8 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
          <BriefcaseIcon className="w-12 h-12 text-gray-400 mx-auto mb-2" />
          <p className="text-gray-500 mb-4">还没有添加工作经验</p>
          <button
            onClick={addWork}
            className="btn-primary flex items-center space-x-2 mx-auto"
          >
            <PlusIcon className="w-4 h-4" />
            <span>添加第一个工作经验</span>
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {workList.map((work, index) => (
            <div key={work.id || index} className="bg-gray-50 rounded-lg p-4 border">
              <div className="flex items-center justify-between mb-4">
                <h4 className="font-medium text-gray-900">工作经验 {index + 1}</h4>
                {workList.length > 1 && (
                  <button
                    onClick={() => removeWork(work.id!)}
                    className="text-red-600 hover:text-red-800 p-1"
                    title="删除此工作经验"
                  >
                    <TrashIcon className="w-4 h-4" />
                  </button>
                )}
              </div>

              <div className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      公司名称 <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={work.company}
                      onChange={(e) => updateWork(work.id!, 'company', e.target.value)}
                      placeholder="腾讯科技"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      职位 <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={work.position}
                      onChange={(e) => updateWork(work.id!, 'position', e.target.value)}
                      placeholder="软件工程师"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      工作时间 <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={work.duration}
                      onChange={(e) => updateWork(work.id!, 'duration', e.target.value)}
                      placeholder="2022.07 - 2024.06"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      工作地点
                    </label>
                    <input
                      type="text"
                      value={work.location || ''}
                      onChange={(e) => updateWork(work.id!, 'location', e.target.value)}
                      placeholder="北京"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      雇佣类型
                    </label>
                    <select
                      value={work.employment_type || '全职'}
                      onChange={(e) => updateWork(work.id!, 'employment_type', e.target.value)}
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    >
                      <option value="全职">全职</option>
                      <option value="兼职">兼职</option>
                      <option value="实习">实习</option>
                      <option value="自由职业">自由职业</option>
                      <option value="合同工">合同工</option>
                    </select>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    工作概述 <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    value={work.summary || ''}
                    onChange={(e) => updateWork(work.id!, 'summary', e.target.value)}
                    placeholder="概述职责范围、业务场景和核心定位..."
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-gray-700">
                      关键成果与亮点 <span className="text-red-500">*</span>
                    </label>
                    <button
                      onClick={() => addHighlight(work.id!)}
                      className="text-primary-600 hover:text-primary-800 text-sm flex items-center space-x-1"
                    >
                      <PlusIcon className="w-3 h-3" />
                      <span>添加亮点</span>
                    </button>
                  </div>
                  <div className="mb-2">
                    <p className="text-xs text-gray-500">
                      💡 建议写成动作 + 结果 + 数据指标
                    </p>
                  </div>
                  <div className="space-y-2">
                    {(work.highlights || []).map((highlight, highlightIndex) => (
                      <div key={highlight.id || highlightIndex} className="flex items-start space-x-2">
                        <span className="text-gray-400 mt-2">•</span>
                        <textarea
                          value={highlight.text}
                          onChange={(e) => updateHighlight(work.id!, highlightIndex, e.target.value)}
                          placeholder="负责后端系统重构，接口平均响应时间下降 35%"
                          rows={2}
                          className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
                        />
                        {(work.highlights || []).length > 1 && (
                          <button
                            onClick={() => removeHighlight(work.id!, highlightIndex)}
                            className="text-red-600 hover:text-red-800 p-1 mt-1"
                          >
                            <TrashIcon className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
