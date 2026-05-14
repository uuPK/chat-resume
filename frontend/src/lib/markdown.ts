// 用于提供 AI Markdown 内容归一化工具。
export function normalizeAiMarkdown(content: string): string {
  let fenceMarker: string | null = null

  return content
    .split('\n')
    .map((line) => {
      const fenceMatch = line.match(/^\s*(```|~~~)/)
      if (fenceMatch) {
        const marker = fenceMatch[1]
        if (!fenceMarker) {
          fenceMarker = marker
        } else if (fenceMarker === marker) {
          fenceMarker = null
        }
        return line
      }

      if (fenceMarker) {
        return line
      }

      return line.replace(/^( {4,}|\t+)(?=\S)/, '')
    })
    .join('\n')
}
