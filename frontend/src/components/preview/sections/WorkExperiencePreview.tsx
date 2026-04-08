'use client'

interface WorkExperience {
  id?: string
  company: string
  position: string
  duration: string
  description?: string
  highlights?: Array<{
    id?: string
    text: string
  }>
}

interface WorkExperiencePreviewProps {
  data: WorkExperience[]
  renderLines?: number[] // 指定渲染哪些行
}

// 单个工作经验项组件
export function WorkExperienceItem({ work, lineIndex }: { work: WorkExperience; lineIndex: number }) {
  const highlights = work.highlights && work.highlights.length > 0
    ? work.highlights.map(item => item.text)
    : []

  return (
    <div data-line-index={lineIndex} className="relative print:break-inside-avoid mb-4">
      <div className="flex justify-between items-start mb-1.5">
        <div className="flex-1 flex flex-wrap items-center gap-2">
          {work.company && (
            <h3 className="font-semibold text-gray-900 text-base">
              {work.company}
            </h3>
          )}
          {work.position && (
            <>
              <span className="w-px h-4 bg-gray-300" />
              <span className="text-sm text-gray-700 font-medium">
                {work.position}
              </span>
            </>
          )}
        </div>
        <div className="text-sm text-gray-600 ml-4 whitespace-nowrap">
          {work.duration}
        </div>
      </div>

      {highlights.length > 0 && (
        <div className="text-sm text-gray-600 mt-2 leading-relaxed">
          <ul className="list-disc list-inside">
            {highlights.map((line, itemIndex) => (
              <li key={itemIndex} className="mb-0.5">{line}</li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}

export default function WorkExperiencePreview({
  data,
  renderLines
}: WorkExperiencePreviewProps) {
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
          工作经验
        </h2>
      )}

      {/* 每个工作项作为独立的行 */}
      {data.map((work, index) => {
        const lineIndex = index + 1
        return shouldRenderLine(lineIndex) ? (
          <WorkExperienceItem key={work.id || index} work={work} lineIndex={lineIndex} />
        ) : null
      })}
    </div>
  )
}
