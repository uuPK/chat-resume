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
  return groups
}

function groupDiffItems(items: DiffItem[]): DiffGroup[] {
  return items
    .map((item) => {
      const group: DiffGroup = {}
      if (item.before) group.remove = `- ${item.before}`
      if (item.after) group.add = `+ ${item.after}`
      if (item.reason) group.reason = item.reason
      return group
    })
    .filter((group) => group.remove || group.add || group.reason)
}

const NUMBER_SPLIT_RE = /(\d[\d,，]*(?:\.\d+)?(?:%|％|万|亿|千|百|倍|x|X|次|人|个|项|天|月|年|ms|GB|MB|TB|KB)?)/

/**
 * 将文本中的数字和量化词高亮，帮助用户快速看出量化优化结果。
 */
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
