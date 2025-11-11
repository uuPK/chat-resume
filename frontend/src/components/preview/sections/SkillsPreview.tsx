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

  const getLevelColor = (level: string) => {
    if (!level) return 'bg-gray-100 text-gray-800'
    
    switch (level.toLowerCase()) {
      case '精通':
      case 'expert':
        return 'bg-green-100 text-green-800'
      case '熟练':
      case 'proficient':
        return 'bg-blue-100 text-blue-800'
      case '了解':
      case 'familiar':
        return 'bg-gray-100 text-gray-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="mb-5">
      {/* 标题作为第0行 */}
      {shouldRenderLine(0) && (
        <h2 data-line-index={0} className="text-lg font-bold text-gray-900 mb-3 pb-1.5 border-b border-gray-300">
          技能专长
        </h2>
      )}
      
      {/* 每个技能类别作为独立的行 */}
      {Object.entries(skillsByCategory).map(([category, skills], categoryIndex) => {
        const lineIndex = categoryIndex + 1
        return shouldRenderLine(lineIndex) ? (
          <div key={category} data-line-index={lineIndex} className="mb-3">
            <h3 className="font-semibold text-gray-800 mb-1.5 text-sm">
              {category}
            </h3>
            <div className="flex flex-wrap gap-1.5">
              {skills.map((skill, index) => (
                <div 
                  key={skill.id || index}
                  className="flex items-center space-x-2"
                >
                  <span className="px-2.5 py-0.5 text-xs font-medium text-gray-700 bg-gray-100 rounded-full">
                    {skill.name}
                  </span>
                  <span className={`px-1.5 py-0.5 text-xs rounded ${getLevelColor(skill.level)}`}>
                    {skill.level}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ) : null
      })}
    </div>
  )
}