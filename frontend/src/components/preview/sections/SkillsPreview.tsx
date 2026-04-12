'use client'

interface Skill {
  id?: string
  category: string
  items: string[]
}

interface SkillsPreviewProps {
  data: Skill[]
  renderLines?: number[] // 指定渲染哪些行
}

export default function SkillsPreview({ data, renderLines }: SkillsPreviewProps) {
  if (!data || !Array.isArray(data) || data.length === 0) {
    return null
  }

  const shouldRenderLine = (lineIndex: number) => {
    return !renderLines || renderLines.includes(lineIndex)
  }

  return (
    <div style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 20px)' }}>
      {/* 标题作为第0行 */}
      {shouldRenderLine(0) && (
        <h2
          data-line-index={0}
          className="text-lg font-bold text-gray-900 pb-1 border-b border-gray-200"
          style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 8px)' }}
        >
          技能专长
        </h2>
      )}

      {/* 每个技能类别作为独立的行 */}
      {data.map((group, categoryIndex) => {
        const lineIndex = categoryIndex + 1
        return shouldRenderLine(lineIndex) ? (
          <div
            key={group.id || `${group.category}-${categoryIndex}`}
            data-line-index={lineIndex}
            className="flex flex-wrap items-center gap-2 text-sm text-gray-700"
            style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 6px)' }}
          >
            <span className="font-semibold text-gray-800 flex-shrink-0">
              {group.category}
            </span>
            <div className="flex flex-wrap items-center gap-1.5">
              {(group.items || []).map((skill, index) => (
                <span
                  key={`${group.id || group.category}-${index}-${skill}`}
                  className="text-xs text-gray-800 bg-gray-50 rounded-full px-2.5 py-0.5"
                >
                  {skill}
                </span>
              ))}
            </div>
          </div>
        ) : null
      })}
    </div>
  )
}
