'use client'
// 用于提供 components/editor/SkillsEditor.tsx 模块。

import { useEffect, useLayoutEffect, useRef, useState } from 'react'
import {
  CodeBracketIcon,
  PlusIcon,
  TrashIcon
} from '@heroicons/react/24/outline'
import type { Skill as SkillGroup } from '@/types/resume'
import { useTranslations } from 'next-intl'

interface SkillsEditorProps {
  data: SkillGroup[]
  onChange: (data: SkillGroup[]) => void
}

// 用于创建标题可留空的技能分组。
function createEmptyGroup(): SkillGroup {
  return {
    id: `skill_group_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
    category: '',
    items: []
  }
}

// 用于渲染 SkillsEditor 组件。
export default function SkillsEditor({ data, onChange }: SkillsEditorProps) {
  const [skillGroups, setSkillGroups] = useState<SkillGroup[]>([])
  const focusItemRef = useRef<{ groupId: string; index: number } | null>(null)
  const itemRefs = useRef<Map<string, HTMLTextAreaElement>>(new Map())
  const t = useTranslations('resume.forms.skills')

  useEffect(() => {
    const safeData = Array.isArray(data) ? data : []
    const normalized = safeData.map((group, index) => ({
      id: group.id || `skill_group_${Date.now()}_${index}`,
      category: group.category ?? '',
      items: Array.isArray(group.items) ? group.items : []
    }))
    setSkillGroups(normalized)
  }, [data])

  useEffect(() => {
    if (focusItemRef.current) {
      const key = `${focusItemRef.current.groupId}-${focusItemRef.current.index}`
      itemRefs.current.get(key)?.focus()
      focusItemRef.current = null
    }
  })

  // 用于根据技能文字实际行数调整输入框高度。
  useLayoutEffect(() => {
    itemRefs.current.forEach((element) => {
      element.style.height = 'auto'
      element.style.height = `${element.scrollHeight + 2}px`
    })
  }, [skillGroups])

  // 用于处理commit。
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

  // 用于新增分组。
  const addGroup = () => {
    commit([...skillGroups, createEmptyGroup()])
  }

  // 用于删除分组。
  const removeGroup = (groupId: string) => {
    commit(skillGroups.filter(g => g.id !== groupId))
  }

  // 用于更新category。
  const updateCategory = (groupId: string, category: string) => {
    commit(skillGroups.map(g => g.id === groupId ? { ...g, category } : g))
  }

  // 用于新增item。
  const addItem = (groupId: string) => {
    const next = skillGroups.map(g => (
      g.id === groupId ? { ...g, items: [...g.items, ''] } : g
    ))
    const target = next.find(g => g.id === groupId)
    if (target) focusItemRef.current = { groupId, index: target.items.length - 1 }
    commit(next)
  }

  // 用于更新item。
  const updateItem = (groupId: string, itemIndex: number, value: string) => {
    commit(skillGroups.map(g => {
      if (g.id !== groupId) return g
      const items = [...g.items]
      items[itemIndex] = value
      return { ...g, items }
    }))
  }

  // 用于删除item。
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
        <div className="text-center py-6 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
          <CodeBracketIcon className="w-10 h-10 text-gray-400 mx-auto mb-2" />
          <p className="text-sm text-gray-500 mb-3">{t('empty')}</p>
          <button
            onClick={addGroup}
            className="btn-primary flex items-center space-x-1.5 mx-auto px-4 py-2 text-sm"
          >
            <PlusIcon className="w-3.5 h-3.5" />
            <span>{t('addFirst')}</span>
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
          <div className="flex items-center gap-2">
            <input
              type="text"
              value={group.category}
              onChange={(e) => updateCategory(group.id!, e.target.value)}
              placeholder={t('categoryPlaceholder')}
              className="min-w-0 flex-1 rounded border-0 bg-transparent px-1 py-0.5 text-sm font-semibold text-gray-900 hover:bg-gray-50 focus:bg-gray-50 focus:outline-none focus:ring-0"
            />
            <button
              type="button"
              onClick={() => removeGroup(group.id!)}
              className="p-1 text-gray-400 transition-colors hover:text-red-600"
              title={t('deleteCategory')}
            >
              <TrashIcon className="h-4 w-4" />
            </button>
          </div>

          <div className="mt-2 space-y-2">
            {group.items.map((item, idx) => {
              const key = `${group.id}-${idx}`
              return (
                <div key={key} className="flex items-start gap-2">
                  <textarea
                    ref={(element) => {
                      if (element) itemRefs.current.set(key, element)
                      else itemRefs.current.delete(key)
                    }}
                    value={item}
                    onChange={(e) => updateItem(group.id!, idx, e.target.value)}
                    placeholder={t('skillPlaceholder')}
                    rows={2}
                    className="min-h-[56px] min-w-0 flex-1 resize-none overflow-hidden rounded-lg border border-gray-300 px-3 py-2 text-sm leading-relaxed text-gray-800 focus:border-primary-500 focus:outline-none focus:ring-2 focus:ring-primary-500"
                  />
                  <button
                    type="button"
                    onClick={() => removeItem(group.id!, idx)}
                    className="mt-2 p-1 text-gray-400 transition-colors hover:text-red-600"
                    title={t('delete')}
                  >
                    <TrashIcon className="h-4 w-4" />
                  </button>
                </div>
              )
            })}
            <button
              type="button"
              onClick={() => addItem(group.id!)}
              className="inline-flex items-center gap-1 rounded-lg border border-dashed border-gray-300 px-3 py-1 text-xs text-gray-500 transition-colors hover:border-primary-400 hover:text-primary-600"
            >
              <PlusIcon className="w-3 h-3" />
              <span>{t('addItem')}</span>
            </button>

          </div>
        </div>
      ))}

      <button
        onClick={addGroup}
        className="w-full py-3 rounded-lg border-2 border-dashed border-gray-300 text-gray-500 hover:text-primary-600 hover:border-primary-400 transition-colors flex items-center justify-center space-x-2 text-sm"
      >
        <PlusIcon className="w-4 h-4" />
        <span>{t('addGroup')}</span>
      </button>
    </div>
  )
}
