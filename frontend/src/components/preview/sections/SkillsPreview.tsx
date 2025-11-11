'use client'

interface Skill {
  id?: number
  name: string
  level: string
  category: string
}

interface SkillsPreviewProps {
  data: Skill[]
  renderLines?: number[] // 指定渲染哪些行
}

export default function SkillsPreview({ data, renderLines }: SkillsPreviewProps) {
  if (!data || data.length === 0) {
    return null
  }

  const shouldRenderLine = (lineIndex: number) => {
    return !renderLines || renderLines.includes(lineIndex)
  }

  // 按技能类别分组
  const skillsByCategory = data.reduce((acc, skill) => {
    if (!acc[skill.category]) {
      acc[skill.category] = []
    }
    acc[skill.category].push(skill)
    return acc
  }, {} as Record<string, Skill[]>)

  return (
    <div className="mb-5">
      {/* 标题作为第0行 */}
      {shouldRenderLine(0) && (
        <h2
          data-line-index={0}
          className="text-lg font-bold text-gray-900 mb-2 pb-1 border-b border-gray-200"
        >
          技能专长
        </h2>
      )}
      
      {/* 每个技能类别作为独立的行 */}
      {Object.entries(skillsByCategory).map(([category, skills], categoryIndex) => {
        const lineIndex = categoryIndex + 1
        return shouldRenderLine(lineIndex) ? (
          <div
            key={category}
            data-line-index={lineIndex}
            className="flex flex-wrap items-center gap-2 text-sm text-gray-700 mb-1.5"
          >
            <span className="font-semibold text-gray-800 flex-shrink-0">
              {category}
            </span>
            <div className="flex flex-wrap items-center gap-1.5">
              {skills.map((skill, index) => (
                <span
                  key={skill.id || index}
                  className="text-xs text-gray-800 bg-gray-50 rounded-full px-2.5 py-0.5"
                >
                  {skill.name}
                </span>
              ))}
            </div>
          </div>
        ) : null
      })}
    </div>
  )
}