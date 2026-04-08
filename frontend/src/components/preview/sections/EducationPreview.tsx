'use client'

interface Education {
  id?: string
  school: string
  major: string
  degree: string
  duration: string
  description?: string
  highlights?: Array<{
    id?: string
    text: string
  }>
}

interface EducationPreviewProps {
  data: Education[]
  renderLines?: number[] // 指定渲染哪些行
}

// 单个教育项组件
export function EducationItem({ edu, lineIndex }: { edu: Education; lineIndex: number }) {
  const highlights = edu.highlights && edu.highlights.length > 0
    ? edu.highlights.map(item => item.text)
    : []

  return (
    <div data-line-index={lineIndex} className="relative print:break-inside-avoid mb-3">
      <div className="flex justify-between items-start mb-1">
        <div className="flex-1 flex flex-wrap items-center gap-2">
          <h3 className="font-semibold text-gray-900">
            {edu.school}
          </h3>
          {(edu.major || edu.degree) && (
            <span className="flex items-center gap-2 text-sm text-gray-700">
              <span className="w-px h-4 bg-gray-300" />
              {[edu.major, edu.degree].filter(Boolean).join(' · ')}
            </span>
          )}
        </div>
        <div className="text-sm text-gray-600 ml-4">
          {edu.duration}
        </div>
      </div>

      {highlights.length > 0 && (
        <ul className="list-disc list-inside text-sm text-gray-600 mt-1">
          {highlights.map((item, index) => (
            <li key={index}>{item}</li>
          ))}
        </ul>
      )}
    </div>
  )
}

export default function EducationPreview({
  data,
  renderLines
}: EducationPreviewProps) {
  if (!data || !Array.isArray(data) || data.length === 0) {
    return null
  }

  const shouldRenderLine = (lineIndex: number) => {
    return !renderLines || renderLines.includes(lineIndex)
  }

  return (
    <div className="mb-5">
      {/* 标题作为第0行 */}
      {shouldRenderLine(0) && (
        <h2 data-line-index={0} className="text-lg font-bold text-gray-900 mb-3 pb-1.5 border-b border-gray-300">
          教育背景
        </h2>
      )}

      {/* 每个教育项作为独立的行 */}
      {data.map((edu, index) => {
        const lineIndex = index + 1 // 标题占第0行，项从第1行开始
        return shouldRenderLine(lineIndex) ? (
          <EducationItem key={edu.id || index} edu={edu} lineIndex={lineIndex} />
        ) : null
      })}
    </div>
  )
}
