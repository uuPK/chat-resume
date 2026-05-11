'use client'

import { useState, useEffect } from 'react'
import {
  AcademicCapIcon,
  PlusIcon,
  TrashIcon
} from '@heroicons/react/24/outline'
import type { Education } from '@/types/resume'

interface EducationEditorProps {
  data: Education[]
  onChange: (data: Education[]) => void
}

export default function EducationEditor({ data, onChange }: EducationEditorProps) {
  const [educationList, setEducationList] = useState<Education[]>(Array.isArray(data) ? data : [])

  useEffect(() => {
    setEducationList(Array.isArray(data) ? data : [])
  }, [data])

  const commit = (next: Education[]) => {
    setEducationList(next)
    onChange(next.map(({ description: _description, ...education }) => education))
  }

  const addEducation = () => {
    const newEducation: Education = {
      id: `edu_${Date.now()}`,
      school: '',
      major: '',
      degree: '',
      duration: '',
      highlights: [{ id: `edu_hl_${Date.now()}`, text: '' }],
      gpa: ''
    }
    commit([...educationList, newEducation])
  }

  const removeEducation = (id: string) => {
    commit(educationList.filter(edu => edu.id !== id))
  }

  const updateEducation = (id: string, field: keyof Education, value: string) => {
    const newList = educationList.map(edu =>
      edu.id === id ? { ...edu, [field]: value } : edu
    )
    commit(newList)
  }

  const addBullet = (educationId: string) => {
    const education = educationList.find(item => item.id === educationId)
    if (!education) return
    const next = [...(education.highlights || []), { id: `edu_hl_${Date.now()}`, text: '' }]
    updateEducationList(
      educationList.map(item => item.id === educationId ? { ...item, highlights: next } : item)
    )
  }

  const updateBullet = (educationId: string, index: number, value: string) => {
    const education = educationList.find(item => item.id === educationId)
    if (!education) return
    const next = [...(education.highlights || [])]
    next[index] = { ...next[index], text: value }
    updateEducationList(
      educationList.map(item => item.id === educationId ? { ...item, highlights: next } : item)
    )
  }

  const removeBullet = (educationId: string, index: number) => {
    const education = educationList.find(item => item.id === educationId)
    if (!education) return
    const current = education.highlights || []
    if (current.length <= 1) return
    updateEducationList(
      educationList.map(item =>
        item.id === educationId
          ? { ...item, highlights: current.filter((_, itemIndex) => itemIndex !== index) }
          : item
      )
    )
  }

  const updateEducationList = (next: Education[]) => {
    commit(next)
  }

  return (
    <div className="space-y-6">
      {educationList.length === 0 ? (
        <div className="text-center py-8 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
          <AcademicCapIcon className="w-12 h-12 text-gray-400 mx-auto mb-2" />
          <p className="text-gray-500 mb-4">还没有添加教育经历</p>
          <button
            onClick={addEducation}
            className="btn-primary flex items-center space-x-2 mx-auto"
          >
            <PlusIcon className="w-4 h-4" />
            <span>添加第一个教育经历</span>
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {educationList.map((education, index) => (
            <div key={education.id || index} className="bg-white rounded-lg p-4 border">
              <div className="flex items-center justify-end mb-1">
                {educationList.length > 1 && (
                  <button
                    onClick={() => removeEducation(education.id!)}
                    className="text-gray-400 hover:text-gray-600 p-1 transition-colors"
                    title="删除此教育经历"
                  >
                    <TrashIcon className="w-4 h-4" />
                  </button>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {/* 学校名称 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    学校名称
                  </label>
                  <input
                    type="text"
                    value={education.school}
                    onChange={(e) => updateEducation(education.id!, 'school', e.target.value)}
                    placeholder="北京大学"
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>

                {/* 专业 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    专业
                  </label>
                  <input
                    type="text"
                    value={education.major}
                    onChange={(e) => updateEducation(education.id!, 'major', e.target.value)}
                    placeholder="计算机科学与技术"
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>

                {/* 学历 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    学历
                  </label>
                  <select
                    value={education.degree}
                    onChange={(e) => updateEducation(education.id!, 'degree', e.target.value)}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  >
                    <option value="">请选择学历</option>
                    <option value="博士">博士</option>
                    <option value="硕士">硕士</option>
                    <option value="本科">本科</option>
                    <option value="专科">专科</option>
                    <option value="高中">高中</option>
                    <option value="中专">中专</option>
                  </select>
                </div>

                {/* 就读时间 */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    就读时间
                  </label>
                  <input
                    type="text"
                    value={education.duration}
                    onChange={(e) => updateEducation(education.id!, 'duration', e.target.value)}
                    placeholder="2018.09 - 2022.06"
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>

                {/* GPA */}
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    GPA (可选)
                  </label>
                  <input
                    type="text"
                    value={education.gpa || ''}
                    onChange={(e) => updateEducation(education.id!, 'gpa', e.target.value)}
                    placeholder="3.8/4.0"
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                  />
                </div>
              </div>

              <div className="mt-4">
                <div className="flex items-center justify-between mb-2">
                  <label className="block text-sm font-medium text-gray-700">
                    教育要点
                  </label>
                  <button
                    onClick={() => addBullet(education.id!)}
                    className="text-primary-600 hover:text-primary-800 text-sm flex items-center space-x-1"
                  >
                    <PlusIcon className="w-3 h-3" />
                    <span>添加要点</span>
                  </button>
                </div>
                <div className="space-y-2">
                  {(education.highlights || [{ id: `edu_hl_${education.id || '0'}`, text: '' }]).map((highlight, highlightIndex) => (
                    <div key={highlight.id || highlightIndex} className="flex items-center space-x-2">
                      <textarea
                        value={highlight.text}
                        onChange={(e) => updateBullet(education.id!, highlightIndex, e.target.value)}
                        placeholder="985高校、主要课程、奖项、研究方向等"
                        rows={1}
                        className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none [field-sizing:content]"
                      />
                      {(education.highlights || []).length > 1 && (
                        <button
                          onClick={() => removeBullet(education.id!, highlightIndex)}
                          className="text-gray-400 hover:text-gray-600 p-1 transition-colors"
                          title="删除此要点"
                        >
                          <TrashIcon className="w-4 h-4" />
                        </button>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ))}
          <button
            onClick={addEducation}
            className="w-full py-4 rounded-lg border-2 border-dashed border-gray-300 text-gray-500 hover:text-primary-600 hover:border-primary-400 transition-colors flex items-center justify-center space-x-2"
          >
            <PlusIcon className="w-4 h-4" />
            <span>添加教育经历</span>
          </button>
        </div>
      )}
    </div>
  )
}
