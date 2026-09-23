'use client'
// 用于提供 components/preview/sections/SkillsPreview.tsx 模块。

import type { Skill } from '@/types/resume'
import type { ResumeTemplateStyle } from '@/types/resumeLayout'
import { useTranslations } from 'next-intl'

interface SkillsPreviewProps {
  data: Skill[]
  renderLines?: number[] // 指定渲染哪些行
  templateStyle?: ResumeTemplateStyle
}

// 用于让长段技能描述占满一行，短技能仍以紧凑标签显示。
function isLongSkill(item: string): boolean {
  return item.length > 40 || item.includes('\n')
}

// 用于渲染 SkillsPreview 组件。
export default function SkillsPreview({ data, renderLines, templateStyle = 'classic' }: SkillsPreviewProps) {
  const t = useTranslations('resume.layout.modules')
  if (!data || !Array.isArray(data) || data.length === 0) {
    return null
  }

  // 用于处理shouldrender行。
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
          {templateStyle === 'emerald' ? (
            <span className="resume-emerald-heading-label">{t('skills')}</span>
          ) : t('skills')}
        </h2>
      )}

      {/* 每个技能类别作为独立的行 */}
      {data.map((group, categoryIndex) => {
        const lineIndex = categoryIndex + 1
        const isFormal = templateStyle === 'formal'
        const isEmerald = templateStyle === 'emerald'
        const items = (group.items || []).filter(item => item.trim())
        const category = group.category.trim()
        return shouldRenderLine(lineIndex) ? (
          isFormal || isEmerald ? (
            <ul
              key={group.id || `${group.category}-${categoryIndex}`}
              data-line-index={lineIndex}
              className={isEmerald ? 'resume-emerald-list text-sm' : 'list-disc text-sm text-gray-900'}
              style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 8px)', paddingLeft: 18, lineHeight: isEmerald ? '1.64' : '1.72' }}
            >
              <li className="whitespace-pre-wrap break-words [overflow-wrap:anywhere]">
                {category && <span className="font-semibold">{category}： </span>}
                {items.join(isEmerald ? '、 ' : '、')}
              </li>
            </ul>
          ) : (
            <div
              key={group.id || `${group.category}-${categoryIndex}`}
              data-line-index={lineIndex}
              className="flex flex-wrap items-start gap-2 text-sm text-gray-700"
              style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 6px)' }}
            >
              {category && (
                <span className="flex-shrink-0 font-semibold text-gray-800">
                  {category}
                </span>
              )}
              <div className="flex min-w-0 flex-1 flex-wrap items-start gap-1.5">
                {items.map((skill, index) => (
                  <span
                    key={`${group.id || group.category}-${index}-${skill}`}
                    className={isLongSkill(skill)
                      ? 'w-full whitespace-pre-wrap break-words text-sm leading-relaxed text-gray-800 [overflow-wrap:anywhere]'
                      : 'max-w-full whitespace-pre-wrap break-words rounded-full bg-gray-50 px-2.5 py-0.5 text-xs text-gray-800 [overflow-wrap:anywhere]'}
                  >
                    {skill}
                  </span>
                ))}
              </div>
            </div>
          )
        ) : null
      })}
    </div>
  )
}
