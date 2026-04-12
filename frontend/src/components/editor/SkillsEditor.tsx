'use client'

import { useEffect, useRef, useState } from 'react'
import {
  CodeBracketIcon,
  PlusIcon,
  TrashIcon
} from '@heroicons/react/24/outline'

interface SkillGroup {
  id?: string
  category: string
  items: string[]
}

interface SkillsEditorProps {
  data: SkillGroup[]
  onChange: (data: SkillGroup[]) => void
}

const DEFAULT_CATEGORIES = [
  '编程语言',
  '前端技术',
  '后端技术',
  '数据库',
  '开发工具',
  '云平台',
  'AI 技术栈',
  '其他技能'
]

function createEmptyGroup(category = '编程语言'): SkillGroup {
  return {
    id: `skill_group_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    category,
    items: []
  }
}

export default function SkillsEditor({ data, onChange }: SkillsEditorProps) {
  const [skillGroups, setSkillGroups] = useState<SkillGroup[]>([])
  const focusChipRef = useRef<{ groupId: string; index: number } | null>(null)
  const chipRefs = useRef<Map<string, HTMLInputElement | null>>(new Map())

  useEffect(() => {
    const safeData = Array.isArray(data) ? data : []
    const normalized = safeData.map((group, index) => ({
      id: group.id || `skill_group_${Date.now()}_${index}`,
      category: group.category || '其他技能',
      items: Array.isArray(group.items) ? group.items : []
    }))
    setSkillGroups(normalized)
  }, [data])

  useEffect(() => {
    if (focusChipRef.current) {
      const key = `${focusChipRef.current.groupId}-${focusChipRef.current.index}`
      chipRefs.current.get(key)?.focus()
      focusChipRef.current = null
    }
  })

  const commit = (next: SkillGroup[]) => {
    setSkillGroups(next)
    onChange(
      next.map(group => ({
        ...group,
        category: group.category.trim(),
        items: group.items
      }))
    )
  }

  const addGroup = () => {
    const existing = new Set(skillGroups.map(g => g.category))
    const nextCategory = DEFAULT_CATEGORIES.find(c => !existing.has(c)) || '新分类'
    commit([...skillGroups, createEmptyGroup(nextCategory)])
  }

  const removeGroup = (groupId: string) => {
    commit(skillGroups.filter(g => g.id !== groupId))
  }

  const updateCategory = (groupId: string, category: string) => {
    commit(skillGroups.map(g => g.id === groupId ? { ...g, category } : g))
  }

  const addItem = (groupId: string) => {
    const next = skillGroups.map(g => (
      g.id === groupId ? { ...g, items: [...g.items, ''] } : g
    ))
    const target = next.find(g => g.id === groupId)
    if (target) focusChipRef.current = { groupId, index: target.items.length - 1 }
    commit(next)
  }

  const updateItem = (groupId: string, itemIndex: number, value: string) => {
    commit(skillGroups.map(g => {
      if (g.id !== groupId) return g
      const items = [...g.items]
      items[itemIndex] = value
      return { ...g, items }
    }))
  }

  const removeItem = (groupId: string, itemIndex: number) => {
    commit(skillGroups.map(g => (
      g.id === groupId
        ? { ...g, items: g.items.filter((_, i) => i !== itemIndex) }
        : g
    )))
  }

  if (skillGroups.length === 0) {
    return (
      <div className="space-y-6">
        <div className="text-center py-8 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
          <CodeBracketIcon className="w-12 h-12 text-gray-400 mx-auto mb-2" />
          <p className="text-gray-500 mb-4">还没有添加技能</p>
          <button
            onClick={addGroup}
            className="btn-primary flex items-center space-x-2 mx-auto"
          >
            <PlusIcon className="w-4 h-4" />
            <span>添加第一个技能分类</span>
          </button>
        </div>
      </div>
    )
  }

  return (
    <div className="space-y-3">
      {skillGroups.map((group) => (
        <div
          key={group.id}
          className="group/cat rounded-lg border border-gray-200 bg-white p-3 hover:border-gray-300 transition-colors"
        >
          <div className="flex items-center gap-2 flex-wrap">
            <input
              type="text"
              value={group.category}
              onChange={(e) => updateCategory(group.id!, e.target.value)}
              placeholder="分类名"
              className="text-sm font-semibold text-gray-900 bg-transparent border-0 focus:ring-0 focus:outline-none px-1 py-0.5 rounded hover:bg-gray-50 focus:bg-gray-50 w-auto min-w-[80px]"
              style={{ width: `${Math.max(group.category.length, 4) + 2}ch` }}
            />

            {group.items.map((item, idx) => {
              const key = `${group.id}-${idx}`
              return (
                <span
                  key={key}
                  className="group/chip relative inline-flex items-center justify-center rounded-full border border-gray-200 hover:border-gray-300 transition-colors px-2.5 py-1"
                >
                  <input
                    ref={(el) => { chipRefs.current.set(key, el) }}
                    type="text"
                    value={item}
                    onChange={(e) => updateItem(group.id!, idx, e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter') {
                        e.preventDefault()
                        addItem(group.id!)
                      } else if (e.key === 'Backspace' && item === '') {
                        e.preventDefault()
                        removeItem(group.id!, idx)
                      }
                    }}
                    placeholder="技能"
                    className="bg-transparent border-0 focus:ring-0 focus:outline-none text-xs text-gray-800 p-0 text-center"
                    style={{ width: `${Math.max(item.length, 2) + 1}ch` }}
                  />
                  <button
                    onClick={() => removeItem(group.id!, idx)}
                    className="absolute -top-1.5 -right-1.5 bg-white border border-gray-200 rounded-full p-0.5 text-gray-400 hover:text-red-600 opacity-0 group-hover/chip:opacity-100 transition-opacity shadow-sm"
                    title="删除"
                  >
                    <TrashIcon className="w-3 h-3" />
                  </button>
                </span>
              )
            })}

            <button
              onClick={() => addItem(group.id!)}
              className="inline-flex items-center gap-1 rounded-full border border-dashed border-gray-300 hover:border-primary-400 hover:text-primary-600 px-3 py-1 text-xs text-gray-500 transition-colors"
            >
              <PlusIcon className="w-3 h-3" />
              <span>添加</span>
            </button>

            <button
              onClick={() => removeGroup(group.id!)}
              className="ml-auto text-gray-300 hover:text-red-600 opacity-0 group-hover/cat:opacity-100 transition-opacity p-1"
              title="删除分类"
            >
              <TrashIcon className="w-4 h-4" />
            </button>
          </div>
        </div>
      ))}

      <button
        onClick={addGroup}
        className="w-full py-3 rounded-lg border-2 border-dashed border-gray-300 text-gray-500 hover:text-primary-600 hover:border-primary-400 transition-colors flex items-center justify-center space-x-2 text-sm"
      >
        <PlusIcon className="w-4 h-4" />
        <span>添加技能分类</span>
      </button>
    </div>
  )
}
