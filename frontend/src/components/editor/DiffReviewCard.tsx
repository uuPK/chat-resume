/**
 * 简历改动 diff 展示组件
 *
 * 用于把 Agent 返回的改动摘要拆成结构化卡片，减少编辑页里的展示逻辑。
 */

import React from 'react'

import type { DiffItem } from '@/hooks/useStreamingChat'
import {
  DIFF_AFTER_LABEL,
  DIFF_BEFORE_LABEL,
  DIFF_CREATED_MARKER,
  DIFF_DELETED_MARKER,
  DIFF_REASON_LABEL,
  DIFF_SUMMARY_SECTION_SUFFIXES,
} from '@/lib/resumeDiffProtocol'

type DiffLine = { type: 'remove' | 'add' | 'reason' | 'meta'; text: string }
type DiffGroup = { remove?: string; add?: string; reason?: string }

/**
 * 将 diffSummary 文本解析为可渲染的 diff 行。
 */
// 用于解析差异摘要。
function parseDiffSummary(raw: string): DiffLine[] {
  const lines = raw.split('\n')
  const result: DiffLine[] = []
  for (const line of lines) {
    if (!line.trim()) continue
    if (DIFF_SUMMARY_SECTION_SUFFIXES.some((suffix) => line.endsWith(suffix))) continue
    if (line.startsWith(DIFF_BEFORE_LABEL) || line.startsWith(`  ${DIFF_BEFORE_LABEL}`)) {
      const text = line.replace(new RegExp(`^\\s*${DIFF_BEFORE_LABEL}`), '').trim()
      if (text === DIFF_CREATED_MARKER) continue
      result.push({ type: 'remove', text: `- ${text}` })
    } else if (line.startsWith(DIFF_AFTER_LABEL) || line.startsWith(`  ${DIFF_AFTER_LABEL}`)) {
      const text = line.replace(new RegExp(`^\\s*${DIFF_AFTER_LABEL}`), '').trim()
      if (text === DIFF_DELETED_MARKER) continue
      result.push({ type: 'add', text: `+ ${text}` })
    } else if (line.startsWith(DIFF_REASON_LABEL) || line.startsWith(`  ${DIFF_REASON_LABEL}`)) {
      const text = line.replace(new RegExp(`^\\s*${DIFF_REASON_LABEL}`), '').trim()
      if (text) result.push({ type: 'reason', text })
    }
  }
  return result
}

/**
 * 将平铺的 diff 行按一组改动重新整理，便于卡片化展示。
 */
// 用于分组差异行。
function groupDiffLines(lines: DiffLine[]): DiffGroup[] {
  const groups: DiffGroup[] = []
  let current: DiffGroup | null = null
  for (const line of lines) {
    if (line.type === 'remove') {
      if (current) groups.push(current)
      current = { remove: line.text }
    } else if (line.type === 'add') {
      if (!current) current = {}
      current.add = line.text
    } else if (line.type === 'reason') {
      if (!current) current = {}
      current.reason = line.text
    }
  }
  if (current) groups.push(current)
  return groups.map(compactDiffGroup)
}

// 用于分组差异条目。
function groupDiffItems(items: DiffItem[]): DiffGroup[] {
  return items
    .map((item) => {
      const compact = buildCompactObjectDiff(item.before, item.after)
      const group: DiffGroup = compact || {}
      if (!compact && item.before) group.remove = `- ${item.before}`
      if (!compact && item.after) group.add = `+ ${item.after}`
      if (item.reason) group.reason = item.reason
      return group
    })
    .filter((group) => group.remove || group.add || group.reason)
}

const NUMBER_SPLIT_RE = /(\d[\d,，]*(?:\.\d+)?(?:%|％|万|亿|千|百|倍|x|X|次|人|个|项|天|月|年|ms|GB|MB|TB|KB)?)/
// 用于判断对象是否拥有指定字段。
function hasOwnField(record: Record<string, unknown>, key: string) {
  return Object.prototype.hasOwnProperty.call(record, key)
}

// 用于解析 JSON 对象差异。
function parseJsonObject(text?: string) {
  if (!text) return null
  const trimmed = text.trim()
  if (!trimmed.startsWith('{') || !trimmed.endsWith('}')) return null
  try {
    const value = JSON.parse(trimmed)
    return value && typeof value === 'object' && !Array.isArray(value)
      ? (value as Record<string, unknown>)
      : null
  } catch {
    return null
  }
}

// 用于生成稳定的值比较键。
function valueKey(value: unknown) {
  return typeof value === 'string' ? `s:${value}` : JSON.stringify(value)
}

// 用于格式化字段值。
function formatDiffValue(value: unknown) {
  if (!Array.isArray(value)) return typeof value === 'string' ? value : String(JSON.stringify(value))
  const items = value.map((item) => (typeof item === 'string' ? item : String(JSON.stringify(item))))
  return items.length > 0 ? items.join('、') : '[]'
}

// 用于计算数组中的新增或删除项。
function arrayDelta(source: unknown[], target: unknown[]) {
  const targetCounts = new Map<string | undefined, number>()
  const result: unknown[] = []
  for (const item of target) {
    const key = valueKey(item)
    targetCounts.set(key, (targetCounts.get(key) || 0) + 1)
  }
  for (const item of source) {
    const key = valueKey(item)
    const count = targetCounts.get(key) || 0
    if (count > 0) {
      targetCounts.set(key, count - 1)
    } else {
      result.push(item)
    }
  }
  return result
}

// 用于把 JSON 对象差异压缩成只包含变化字段的 diff。
function buildCompactObjectDiff(beforeText?: string, afterText?: string): DiffGroup | null {
  const before = parseJsonObject(beforeText)
  const after = parseJsonObject(afterText)
  if (!before || !after) return null

  const removeLines: string[] = []
  const addLines: string[] = []
  const keys = Object.keys(before).concat(Object.keys(after).filter((key) => !hasOwnField(before, key)))
  for (const key of keys) {
    const hasBefore = hasOwnField(before, key)
    const hasAfter = hasOwnField(after, key)
    if (hasBefore && hasAfter && valueKey(before[key]) === valueKey(after[key])) continue
    if (hasBefore && hasAfter && Array.isArray(before[key]) && Array.isArray(after[key])) {
      const removed = arrayDelta(before[key], after[key])
      const added = arrayDelta(after[key], before[key])
      if (removed.length > 0) removeLines.push(`${key}: ${formatDiffValue(removed)}`)
      if (added.length > 0) addLines.push(`${key}: ${formatDiffValue(added)}`)
    } else {
      if (hasBefore) removeLines.push(`${key}: ${formatDiffValue(before[key])}`)
      if (hasAfter) addLines.push(`${key}: ${formatDiffValue(after[key])}`)
    }
  }

  if (removeLines.length === 0 && addLines.length === 0) return null
  return {
    remove: removeLines.length > 0 ? `- ${removeLines.join('\n- ')}` : undefined,
    add: addLines.length > 0 ? `+ ${addLines.join('\n+ ')}` : undefined,
  }
}

// 用于压缩已有 diff 分组。
function compactDiffGroup(group: DiffGroup) {
  const compact = buildCompactObjectDiff(group.remove?.slice(2), group.add?.slice(2))
  if (!compact) return group
  return { ...compact, reason: group.reason }
}


/**
 * 将文本中的数字和量化词高亮，帮助用户快速看出量化优化结果。
 */
// 用于渲染 HighlightNumbers 组件。
function HighlightNumbers({ text, active }: { text: string; active: boolean }) {
  if (!active) return <>{text}</>
  const parts = text.split(NUMBER_SPLIT_RE)
  return (
    <>
      {parts.map((part, index) => (
        index % 2 === 1 ? (
          <span key={index} className="font-bold text-emerald-600 bg-emerald-100 rounded px-0.5">
            {part}
          </span>
        ) : (
          part
        )
      ))}
    </>
  )
}

/**
 * 渲染一组改动卡片，供 Agent tool pending/confirmed/rejected 复用。
 */
// 用于渲染 DiffGroupCards 组件。
export function DiffGroupCards({
  diffSummary,
  diffItems = [],
  isConfirmed,
}: {
  diffSummary: string
  diffItems?: DiffItem[]
  isConfirmed?: boolean
}) {
  const groups =
    diffItems.length > 0
      ? groupDiffItems(diffItems)
      : groupDiffLines(parseDiffSummary(diffSummary))
  if (groups.length === 0) return null
  const addActive = isConfirmed !== false

  return (
    <div className="divide-y divide-gray-100">
      {groups.map((group, index) => (
        <div key={index} className="px-3 py-2 space-y-0.5 font-mono text-xs">
          {group.remove && (
            <div className="px-2 py-1 rounded bg-red-50 text-red-600 whitespace-pre-wrap">
              {group.remove}
            </div>
          )}
          {group.add && (
            <div
              className={`px-2 py-1 rounded whitespace-pre-wrap ${
                isConfirmed === false ? 'bg-gray-100 text-gray-400' : 'bg-green-50 text-green-700'
              }`}
            >
              <HighlightNumbers text={group.add} active={addActive} />
            </div>
          )}
          {group.reason && (
            <div className="px-2 py-1 rounded bg-amber-50 flex items-start gap-1 font-sans not-italic">
              <span className="flex-shrink-0">💡</span>
              <span className="italic text-amber-700">{group.reason}</span>
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
