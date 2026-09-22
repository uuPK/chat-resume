// 用于提供简历内联加粗标记的解析和编辑工具。

export interface InlineTextSegment {
  text: string
  bold: boolean
}

export interface BoldSelectionResult {
  value: string
  selectionStart: number
  selectionEnd: number
}

/** 把简历文本中的 **加粗** 标记拆成可安全渲染的文本片段。 */
export function parseInlineBold(text: string): InlineTextSegment[] {
  const segments: InlineTextSegment[] = []
  const pattern = /\*\*([\s\S]+?)\*\*/g
  let cursor = 0
  let match = pattern.exec(text)

  while (match) {
    const index = match.index
    if (index > cursor) {
      segments.push({ text: text.slice(cursor, index), bold: false })
    }
    segments.push({ text: match[1], bold: true })
    cursor = index + match[0].length
    match = pattern.exec(text)
  }

  if (cursor < text.length) {
    segments.push({ text: text.slice(cursor), bold: false })
  }

  return segments.length > 0 ? segments : [{ text, bold: false }]
}

/** 为文本框选区添加或移除 **加粗** 标记，并返回新的光标范围。 */
export function toggleBoldSelection(
  value: string,
  selectionStart: number,
  selectionEnd: number,
): BoldSelectionResult {
  const start = Math.max(0, Math.min(selectionStart, value.length))
  const end = Math.max(start, Math.min(selectionEnd, value.length))
  if (start === end) {
    return { value, selectionStart: start, selectionEnd: end }
  }

  const selected = value.slice(start, end)
  if (selected.startsWith('**') && selected.endsWith('**') && selected.length > 4) {
    const unwrapped = selected.slice(2, -2)
    return {
      value: `${value.slice(0, start)}${unwrapped}${value.slice(end)}`,
      selectionStart: start,
      selectionEnd: end - 4,
    }
  }

  const hasAdjacentMarkers = value.slice(start - 2, start) === '**'
    && value.slice(end, end + 2) === '**'
  if (hasAdjacentMarkers) {
    return {
      value: `${value.slice(0, start - 2)}${selected}${value.slice(end + 2)}`,
      selectionStart: start - 2,
      selectionEnd: end - 2,
    }
  }

  return {
    value: `${value.slice(0, start)}**${selected}**${value.slice(end)}`,
    selectionStart: start + 2,
    selectionEnd: end + 2,
  }
}
