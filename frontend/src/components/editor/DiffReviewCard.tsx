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
  DIFF_EMPTY_MARKER,
  DIFF_REASON_LABEL,
  DIFF_SUMMARY_SECTION_SUFFIXES,
} from '@/lib/resumeDiffProtocol'

type DiffLine = { type: 'remove' | 'add' | 'reason' | 'meta'; text: string }
type DiffGroup = { remove?: string; add?: string; reason?: string }
type TextSegment = { text: string; changed: boolean }

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
      if (text === DIFF_CREATED_MARKER || isEmptyDiffMarker(text)) continue
      result.push({ type: 'remove', text: `- ${text}` })
    } else if (line.startsWith(DIFF_AFTER_LABEL) || line.startsWith(`  ${DIFF_AFTER_LABEL}`)) {
      const text = line.replace(new RegExp(`^\\s*${DIFF_AFTER_LABEL}`), '').trim()
      if (text === DIFF_DELETED_MARKER || isEmptyDiffMarker(text)) continue
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
  return groups.map(compactDiffGroup).filter((group) => group.remove || group.add || group.reason)
}

// 用于分组差异条目。
function groupDiffItems(items: DiffItem[]): DiffGroup[] {
  return items
    .map((item) => {
      const before = normalizeDiffSide(item.before, 'before')
      const after = normalizeDiffSide(item.after, 'after')
      const compact = buildCompactObjectDiff(before, after)
      const group: DiffGroup = compact || {}
      if (compact === null && before) group.remove = `- ${formatStandaloneDiffText(before)}`
      if (compact === null && after) group.add = `+ ${formatStandaloneDiffText(after)}`
      if (item.reason) group.reason = item.reason
      return group
    })
    .filter((group) => group.remove || group.add)
}

const DIFF_PREFIX_RE = /^([+-]\s)([\s\S]*)$/

const INTERNAL_DIFF_KEYS = new Set(['id', '_id', 'is_current'])
// 用于判断对象字段是否应展示给用户。
function isVisibleObjectDiffKey(key: string) {
  return !INTERNAL_DIFF_KEYS.has(key)
}
// 用于判断对象是否拥有指定字段。
function hasOwnField(record: Record<string, unknown>, key: string) {
  return Object.prototype.hasOwnProperty.call(record, key)
}

// 用于判断文本是否像 JSON 对象。
function looksLikeJsonObject(text?: string) {
  return Boolean(text?.trim().startsWith('{'))
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

// 用于识别后端摘要里的空值占位符，避免渲染成真实删减内容。
function isEmptyDiffMarker(text: string) {
  return text === DIFF_EMPTY_MARKER
}

// 用于移除新增/删除占位符，避免把元信息渲染成真实改动。
function normalizeDiffSide(text: string | undefined, side: 'before' | 'after') {
  const trimmed = text?.trim()
  if (!trimmed) return undefined
  if (isEmptyDiffMarker(trimmed)) return undefined
  if (side === 'before' && trimmed === DIFF_CREATED_MARKER) return undefined
  if (side === 'after' && trimmed === DIFF_DELETED_MARKER) return undefined
  return trimmed
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

// 用于隐藏简历内部字段名，只展示用户关心的改动内容。
function formatObjectDiffLine(key: string, value: unknown) {
  const text = formatDiffValue(value)
  return key === 'items' || key === 'category' || key === 'text' ? text : `${key}: ${text}`
}

// 用于格式化单侧 JSON diff，只展示用户可读字段。
function formatStandaloneDiffText(text: string) {
  const record = parseJsonObject(text)
  if (!record) return text
  const visibleLines = Object.keys(record)
    .filter(isVisibleObjectDiffKey)
    .map((key) => formatObjectDiffLine(key, record[key]))
    .filter(Boolean)
  return visibleLines.length > 0 ? visibleLines.join('\n') : text
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
function buildCompactObjectDiff(beforeText?: string, afterText?: string): DiffGroup | false | null {
  const before = parseJsonObject(beforeText)
  const after = parseJsonObject(afterText)
  if (!before || !after) {
    return looksLikeJsonObject(beforeText) && looksLikeJsonObject(afterText) ? false : null
  }

  const removeLines: string[] = []
  const addLines: string[] = []
  const keys = Object.keys(before).concat(Object.keys(after).filter((key) => !hasOwnField(before, key)))
  for (const key of keys) {
    if (!isVisibleObjectDiffKey(key)) continue
    const hasBefore = hasOwnField(before, key)
    const hasAfter = hasOwnField(after, key)
    if (hasBefore && hasAfter && valueKey(before[key]) === valueKey(after[key])) continue
    if (hasBefore && hasAfter && Array.isArray(before[key]) && Array.isArray(after[key])) {
      const removed = arrayDelta(before[key], after[key])
      const added = arrayDelta(after[key], before[key])
      if (removed.length > 0) removeLines.push(formatObjectDiffLine(key, removed))
      if (added.length > 0) addLines.push(formatObjectDiffLine(key, added))
    } else {
      if (hasBefore) removeLines.push(formatObjectDiffLine(key, before[key]))
      if (hasAfter) addLines.push(formatObjectDiffLine(key, after[key]))
    }
  }

  if (removeLines.length === 0 && addLines.length === 0) return false
  return {
    remove: removeLines.length > 0 ? `- ${removeLines.join('\n- ')}` : undefined,
    add: addLines.length > 0 ? `+ ${addLines.join('\n+ ')}` : undefined,
  }
}

// 用于压缩已有 diff 分组。
function compactDiffGroup(group: DiffGroup) {
  const compact = buildCompactObjectDiff(group.remove?.slice(2), group.add?.slice(2))
  if (compact === null) return group
  if (compact === false) return {}
  return { ...compact, reason: group.reason }
}


/**
 * 将一对 before/after 文本切成相同前后缀和实际变化片段。
 */
// 用于计算行内真实变化片段。
function buildInlineDiffSegments(text: string, peerText?: string): TextSegment[] {
  if (!peerText || text === peerText) return [{ text, changed: Boolean(!peerText && text) }]
  const source = Array.from(text)
  const peer = Array.from(peerText)
  let prefixLength = 0
  while (
    prefixLength < source.length &&
    prefixLength < peer.length &&
    source[prefixLength] === peer[prefixLength]
  ) {
    prefixLength += 1
  }

  let suffixLength = 0
  while (
    suffixLength < source.length - prefixLength &&
    suffixLength < peer.length - prefixLength &&
    source[source.length - 1 - suffixLength] === peer[peer.length - 1 - suffixLength]
  ) {
    suffixLength += 1
  }

  const segments: TextSegment[] = []
  const changedEnd = source.length - suffixLength
  if (prefixLength > 0) segments.push({ text: source.slice(0, prefixLength).join(''), changed: false })
  if (changedEnd > prefixLength) segments.push({ text: source.slice(prefixLength, changedEnd).join(''), changed: true })
  if (suffixLength > 0) segments.push({ text: source.slice(changedEnd).join(''), changed: false })
  return segments.length > 0 ? segments : [{ text, changed: false }]
}

// 用于拆出 diff 行前缀，避免把 +/- 也当作正文变化。
function splitDiffPrefix(line: string) {
  const match = line.match(DIFF_PREFIX_RE)
  return match ? { prefix: match[1], body: match[2] } : { prefix: '', body: line }
}

// 用于按行渲染 before/after，只给实际变化片段上色。
function renderInlineDiffLine(line: string, peerLine: string | undefined, kind: 'remove' | 'add', active: boolean) {
  const { prefix, body } = splitDiffPrefix(line)
  const peer = peerLine ? splitDiffPrefix(peerLine).body : undefined
  const segments = buildInlineDiffSegments(body, peer)
  const changedClass = kind === 'remove'
    ? 'font-semibold text-red-700 bg-red-100 rounded px-0.5'
    : 'font-semibold text-emerald-700 bg-emerald-100 rounded px-0.5'
  return (
    <>
      <span className={kind === 'remove' ? 'text-red-500' : 'text-emerald-600'}>{prefix}</span>
      {segments.map((segment, index) => (
        segment.changed && active ? (
          <span key={index} className={changedClass}>{segment.text}</span>
        ) : (
          <React.Fragment key={index}>{segment.text}</React.Fragment>
        )
      ))}
    </>
  )
}

// 用于渲染多行 diff 块，并逐行对齐 before/after。
function renderInlineDiffBlock(text: string, peerText: string | undefined, kind: 'remove' | 'add', active = true) {
  const lines = text.split('\n')
  const peerLines = peerText?.split('\n')
  return lines.map((line, index) => (
    <React.Fragment key={`${kind}-${index}`}>
      {index > 0 && '\n'}
      {renderInlineDiffLine(line, peerLines?.[index], kind, active)}
    </React.Fragment>
  ))
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
            <div className="px-2 py-1 rounded bg-red-50 text-gray-700 whitespace-pre-wrap">
              {renderInlineDiffBlock(group.remove, group.add, 'remove')}
            </div>
          )}
          {group.add && (
            <div
              className={`px-2 py-1 rounded whitespace-pre-wrap ${
                isConfirmed === false ? 'bg-gray-100 text-gray-400' : 'bg-green-50 text-gray-700'
              }`}
            >
              {renderInlineDiffBlock(group.add, group.remove, 'add', addActive)}
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
