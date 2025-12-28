'use client'

import { useState, useEffect } from 'react'
import { 
  CodeBracketIcon,
  PlusIcon,
  TrashIcon,
  ChevronDownIcon,
  ChevronRightIcon
} from '@heroicons/react/24/outline'

interface Skill {
  id?: number
  name: string
  level: string
  category: string
}

interface SkillCategory {
  name: string
  skills: Skill[]
}

interface SkillsEditorProps {
  data: Skill[]
  onChange: (data: Skill[]) => void
}

export default function SkillsEditor({ data, onChange }: SkillsEditorProps) {
  const [skillsList, setSkillsList] = useState<Skill[]>(Array.isArray(data) ? data : [])
  const [expandedCategories, setExpandedCategories] = useState<Set<string>>(new Set(['技术栈', '编程语言', '工具']))

  const skillCategories = [
    '编程语言',
    '前端技术',
    '后端技术', 
    '数据库',
    '开发工具',
    '云平台',
    '项目管理',
    '其他技能'
  ]

  const skillLevels = [
    '入门',
    '熟悉',
    '熟练',
    '精通',
    '专家'
  ]

  useEffect(() => {
    const safeData = Array.isArray(data) ? data : []
    const normalizedSkills = safeData.map((skill, index) => ({
      ...skill,
      id: typeof skill.id === 'number' ? skill.id : Date.now() + index
    }))
    setSkillsList(normalizedSkills)
  }, [data])

  const addSkill = (category?: string) => {
    const newSkill: Skill = {
      id: Date.now(),
      name: '',
      level: '熟悉',
      category: category || '编程语言'
    }
    const newList = [...skillsList, newSkill]
    setSkillsList(newList)
    onChange(newList)
  }

  const removeSkill = (id: number) => {
    const newList = skillsList.filter(skill => skill.id !== id)
    setSkillsList(newList)
    onChange(newList)
  }

  const updateSkill = (id: number, field: keyof Skill, value: string) => {
    const newList = skillsList.map(skill => 
      skill.id === id ? { ...skill, [field]: value } : skill
    )
    setSkillsList(newList)
    onChange(newList)
  }

  const toggleCategory = (category: string) => {
    const newExpanded = new Set(expandedCategories)
    if (newExpanded.has(category)) {
      newExpanded.delete(category)
    } else {
      newExpanded.add(category)
    }
    setExpandedCategories(newExpanded)
  }

  const getSkillsByCategory = (category: string) => {
    return skillsList.filter(skill => skill.category === category)
  }

  const getAllCategories = () => {
    const usedCategories = Array.from(new Set(skillsList.map(skill => skill.category)))
    const allCategories = Array.from(new Set([...skillCategories, ...usedCategories]))
    return allCategories
  }

  const getLevelColor = (level: string) => {
    switch (level) {
      case '入门': return 'bg-gray-100 text-gray-800'
      case '熟悉': return 'bg-blue-100 text-blue-800'
      case '熟练': return 'bg-green-100 text-green-800'
      case '精通': return 'bg-yellow-100 text-yellow-800'
      case '专家': return 'bg-red-100 text-red-800'
      default: return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center">
          <CodeBracketIcon className="w-5 h-5 mr-2" />
          技能与能力
        </h3>
        <button
          onClick={() => addSkill()}
          className="btn-secondary flex items-center space-x-1 text-sm"
        >
          <PlusIcon className="w-4 h-4" />
          <span>添加技能</span>
        </button>
      </div>

      {skillsList.length === 0 ? (
        <div className="text-center py-8 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
          <CodeBracketIcon className="w-12 h-12 text-gray-400 mx-auto mb-2" />
          <p className="text-gray-500 mb-4">还没有添加技能</p>
          <button
            onClick={() => addSkill()}
            className="btn-primary flex items-center space-x-2 mx-auto"
          >
            <PlusIcon className="w-4 h-4" />
            <span>添加第一个技能</span>
          </button>
        </div>
      ) : (
        <div className="space-y-4">
          {getAllCategories().map((category) => {
            const categorySkills = getSkillsByCategory(category)
            if (categorySkills.length === 0) return null
            
            const isExpanded = expandedCategories.has(category)
            
            return (
              <div key={category} className="border border-gray-200 rounded-lg">
                <button
                  onClick={() => toggleCategory(category)}
                  className="w-full flex items-center justify-between p-4 bg-gray-50 hover:bg-gray-100 rounded-t-lg"
                >
                  <div className="flex items-center space-x-2">
                    {isExpanded ? (
                      <ChevronDownIcon className="w-4 h-4 text-gray-500" />
                    ) : (
                      <ChevronRightIcon className="w-4 h-4 text-gray-500" />
                    )}
                    <span className="font-medium text-gray-900">{category}</span>
                    <span className="text-sm text-gray-500">({categorySkills.length})</span>
                  </div>
                  <button
                    onClick={(e) => {
                      e.stopPropagation()
                      addSkill(category)
                    }}
                    className="text-primary-600 hover:text-primary-800 p-1"
                    title={`添加${category}技能`}
                  >
                    <PlusIcon className="w-4 h-4" />
                  </button>
                </button>

                {isExpanded && (
                  <div className="p-4 space-y-3">
                    {categorySkills.map((skill, index) => (
                      <div key={skill.id || index} className="flex items-center space-x-3">
                        <div className="flex-1 grid grid-cols-1 md:grid-cols-3 gap-3">
                          {/* 技能名称 */}
                          <input
                            type="text"
                            value={skill.name}
                            onChange={(e) => updateSkill(skill.id!, 'name', e.target.value)}
                            placeholder="技能名称 (如: React)"
                            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                          />

                          {/* 熟练程度 */}
                          <select
                            value={skill.level}
                            onChange={(e) => updateSkill(skill.id!, 'level', e.target.value)}
                            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                          >
                            {skillLevels.map(level => (
                              <option key={level} value={level}>{level}</option>
                            ))}
                          </select>

                          {/* 分类 */}
                          <select
                            value={skill.category}
                            onChange={(e) => updateSkill(skill.id!, 'category', e.target.value)}
                            className="px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                          >
                            {skillCategories.map(cat => (
                              <option key={cat} value={cat}>{cat}</option>
                            ))}
                          </select>
                        </div>

                        {/* 熟练程度标签 */}
                        <span className={`px-2 py-1 text-xs font-medium rounded-full ${getLevelColor(skill.level)}`}>
                          {skill.level}
                        </span>

                        {/* 删除按钮 */}
                        <button
                          onClick={() => removeSkill(skill.id!)}
                          className="text-red-600 hover:text-red-800 p-1"
                          title="删除此技能"
                        >
                          <TrashIcon className="w-4 h-4" />
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}

      {/* 技能统计 */}
      {skillsList.length > 0 && (
        <div className="bg-blue-50 border border-blue-200 rounded-lg p-4">
          <h4 className="font-medium text-blue-900 mb-2">技能统计</h4>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-2 text-sm">
            {skillLevels.map(level => {
              const count = skillsList.filter(skill => skill.level === level).length
              return count > 0 ? (
                <div key={level} className="text-center">
                  <span className={`inline-block px-2 py-1 rounded-full text-xs ${getLevelColor(level)}`}>
                    {level}: {count}
                  </span>
                </div>
              ) : null
            })}
          </div>
          <p className="text-xs text-blue-700 mt-2">
            💡 建议：保持技能的多样性，突出核心技术栈的熟练程度
          </p>
        </div>
      )}
    </div>
  )
}
