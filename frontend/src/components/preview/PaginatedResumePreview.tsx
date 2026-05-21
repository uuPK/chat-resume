'use client'
// 用于提供 components/preview/PaginatedResumePreview.tsx 模块。

import React, { ReactNode, useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useLineBasedPagination, measureRenderableLines, A4_WIDTH, PAGE_PADDING } from './hooks/useLineBasedPagination'
import { useSmartFit } from './hooks/useSmartFit'
import ResumePage from './ResumePage'
import PersonalInfoPreview from './sections/PersonalInfoPreview'
import SummaryPreview from './sections/SummaryPreview'
import EducationPreview from './sections/EducationPreview'
import WorkExperiencePreview from './sections/WorkExperiencePreview'
import SkillsPreview from './sections/SkillsPreview'
import ProjectsPreview from './sections/ProjectsPreview'
import type { ResumeContent } from '@/types/resume'
import type { ModuleConfig, ResumeModule, ResumeTemplateStyle } from '@/types/resumeLayout'
import { DEFAULT_MODULE_CONFIG } from '@/lib/resumeLayoutConfig'
import { useTranslations } from 'next-intl'

const SECTION_ID_MAP: Record<ResumeModule, string> = {
  personal: 'personal-info-section',
  summary: 'summary-section',
  education: 'education-section',
  work: 'work-experience-section',
  skills: 'skills-section',
  projects: 'projects-section'
}

const SECTION_ID_TO_MODULE = Object.entries(SECTION_ID_MAP).reduce(
  (acc, [moduleType, sectionId]) => {
    acc[sectionId] = moduleType as ResumeModule
    return acc
  },
  {} as Record<string, ResumeModule>
)

interface PaginatedResumePreviewProps {
  content: ResumeContent
  moduleOrder?: ModuleConfig[]
  spacingScale?: number
  templateStyle?: ResumeTemplateStyle
  onSpacingScaleChange?: (scale: number) => void
  onTotalPagesChange?: (n: number) => void
  smartFitTriggerRef?: React.MutableRefObject<(() => Promise<import('./hooks/useSmartFit').SmartFitResult>) | null>
  viewportPadding?: number
}

// 用于渲染 PaginatedResumePreview 组件。
export default function PaginatedResumePreview({
  content,
  moduleOrder = DEFAULT_MODULE_CONFIG,
  spacingScale = 1,
  templateStyle = 'classic',
  onSpacingScaleChange,
  onTotalPagesChange,
  smartFitTriggerRef,
  viewportPadding = 8
}: PaginatedResumePreviewProps) {
  const t = useTranslations('resume.layout')
  const containerRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const smartFitContentRef = useRef<HTMLDivElement>(null)
  const [scale, setScale] = React.useState(1)

  // 独立的测量容器 scale state，仅供 SmartFit 二分搜索时切换，不影响实际渲染
  // spacingScale prop 变化时（包括 SmartFit 完成后 onComplete 触发的更新）同步重置
  const [measureScale, setMeasureScale] = useState(spacingScale)
  const measureScaleRef = useRef(spacingScale)
  useEffect(() => {
    setMeasureScale(spacingScale)
  }, [spacingScale])
  // 每次 measureScale 变化后 resolve 所有等待中的 Promise
  const measureScaleResolversRef = useRef<Array<() => void>>([])
  useEffect(() => {
    measureScaleRef.current = measureScale
    const resolvers = measureScaleResolversRef.current.splice(0)
    resolvers.forEach(r => r())
  }, [measureScale])
  // SmartFit 调用：切换 measureScale 并等待 React 渲染完成
  // 若目标 scale 与当前相同（无 state 变化），用 rAF 等 DOM 稳定后直接 resolve
  const waitForMeasureScale = useCallback((targetScale: number): Promise<void> => {
    if (measureScaleRef.current === targetScale) {
      return new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(() => resolve())))
    }
    return new Promise(resolve => {
      measureScaleResolversRef.current.push(resolve)
    })
  }, [])

  // 按order排序并过滤可见模块
  const moduleOrderKey = JSON.stringify(moduleOrder.map(m => ({ type: m.type, visible: m.visible, order: m.order })))
  const visibleModules = useMemo(() => {
    return [...moduleOrder]
      .filter(m => m.visible)
      .sort((a, b) => a.order - b.order)
  }, [moduleOrderKey])

  const { pages, totalPages, isCalculating } = useLineBasedPagination({
    containerRef,
    contentRef,
    spacingScale
  })

  const handleSmartFitComplete = useCallback((newScale: number) => {
    onSpacingScaleChange?.(newScale)
  }, [onSpacingScaleChange])

  const measureSmartFitLines = useCallback(() => {
    return measureRenderableLines(smartFitContentRef.current)
  }, [])

  const { runSmartFit } = useSmartFit({
    currentScale: spacingScale,
    onComplete: handleSmartFitComplete,
    setMeasureScale,
    waitForMeasureScale,
    measureLines: measureSmartFitLines,
  })

  // 将 runSmartFit 暴露给父组件
  React.useEffect(() => {
    if (smartFitTriggerRef) {
      smartFitTriggerRef.current = runSmartFit
    }
  }, [smartFitTriggerRef, runSmartFit])

  // 将 totalPages 回调给父组件
  React.useEffect(() => {
    onTotalPagesChange?.(totalPages)
  }, [totalPages, onTotalPagesChange])

  // 计算合适的缩放比例
  React.useEffect(() => {
    // 用于计算缩放。
    const calculateScale = () => {
      if (!containerRef.current) return

      const container = containerRef.current
      const containerWidth = container.clientWidth
      const A4_WIDTH = 816
      const padding = viewportPadding

      const availableWidth = containerWidth - padding * 2
      const rawScale = availableWidth / A4_WIDTH
      const calculatedScale = Math.min(3.0, Math.max(0.3, rawScale))

      setScale(calculatedScale)
    }

    calculateScale()

    // 用于处理尺寸变化。
    const handleResize = () => calculateScale()
    window.addEventListener('resize', handleResize)

    const resizeObserver = new ResizeObserver(calculateScale)
    if (containerRef.current) {
      resizeObserver.observe(containerRef.current)
    }

    return () => {
      window.removeEventListener('resize', handleResize)
      resizeObserver.disconnect()
    }
  }, [viewportPadding])

  // 根据模块类型渲染组件
  const renderSection = (sectionId: string, children: ReactNode): JSX.Element => (
    <section
      data-section-id={sectionId}
      style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 24px)' }}
    >
      {children}
    </section>
  )

  // 用于渲染模块。
  const renderModule = (moduleType: ResumeModule, renderLines?: number[]): JSX.Element | null => {
    const sectionId = SECTION_ID_MAP[moduleType]

    switch (moduleType) {
      case 'personal':
        return content.personal_info
          ? renderSection(sectionId, <PersonalInfoPreview data={content.personal_info} renderLines={renderLines} templateStyle={templateStyle} />)
          : null
      case 'summary':
        return content.summary?.text
          ? renderSection(sectionId, <SummaryPreview data={content.summary} renderLines={renderLines} templateStyle={templateStyle} />)
          : null
      case 'education':
        return content.education && content.education.length > 0
          ? renderSection(sectionId, <EducationPreview data={content.education} renderLines={renderLines} templateStyle={templateStyle} />)
          : null
      case 'work':
        return content.work_experience && content.work_experience.length > 0
          ? renderSection(sectionId, <WorkExperiencePreview data={content.work_experience} renderLines={renderLines} templateStyle={templateStyle} />)
          : null
      case 'skills':
        return content.skills && content.skills.length > 0
          ? renderSection(sectionId, <SkillsPreview data={content.skills} renderLines={renderLines} templateStyle={templateStyle} />)
          : null
      case 'projects':
        return content.projects && content.projects.length > 0
          ? renderSection(sectionId, <ProjectsPreview data={content.projects} renderLines={renderLines} templateStyle={templateStyle} />)
          : null
      default:
        return null
    }
  }

  // 渲染所有内容用于正式分页测量
  const paginationMeasurementContent = useMemo(() => (
    <div
      ref={contentRef}
      className={`resume-template-${templateStyle} invisible absolute -top-[9999px] left-0 pointer-events-none`}
      style={{
        width: `${A4_WIDTH}px`,
        paddingTop: `${PAGE_PADDING * spacingScale}px`,
        paddingBottom: `${PAGE_PADDING * spacingScale}px`,
        paddingLeft: `${PAGE_PADDING}px`,
        paddingRight: `${PAGE_PADDING}px`,
        boxSizing: 'border-box',
        ['--spacing-scale' as string]: String(spacingScale)
      }}
    >
      {visibleModules.map((module) => {
        const sectionElement = renderModule(module.type)
        if (!sectionElement) {
          return null
        }
        return React.cloneElement(sectionElement, { key: module.type })
      })}
    </div>
  // eslint-disable-next-line react-hooks/exhaustive-deps
  ), [content, visibleModules, moduleOrderKey, spacingScale, templateStyle])

  // 智能一页试算专用测量容器；二分搜索时会频繁切换 scale，不参与正式分页。
  const smartFitMeasurementContent = useMemo(() => (
    <div
      ref={smartFitContentRef}
      className={`resume-template-${templateStyle} invisible absolute -top-[9999px] left-0 pointer-events-none`}
      style={{
        width: `${A4_WIDTH}px`,
        paddingTop: `${PAGE_PADDING * measureScale}px`,
        paddingBottom: `${PAGE_PADDING * measureScale}px`,
        paddingLeft: `${PAGE_PADDING}px`,
        paddingRight: `${PAGE_PADDING}px`,
        boxSizing: 'border-box',
        ['--spacing-scale' as string]: String(measureScale)
      }}
    >
      {visibleModules.map((module) => {
        const sectionElement = renderModule(module.type)
        if (!sectionElement) {
          return null
        }
        return React.cloneElement(sectionElement, { key: module.type })
      })}
    </div>
  // eslint-disable-next-line react-hooks/exhaustive-deps
  ), [content, visibleModules, moduleOrderKey, measureScale, templateStyle])

  // 根据分页信息渲染页面内容
  const renderPageContent = (pageIndex: number) => {
    const page = pages[pageIndex]
    if (!page || page.lines.length === 0) {
      return null
    }

    // 按section分组行
    const linesBySection = page.lines.reduce((acc, line) => {
      if (!acc[line.sectionType]) {
        acc[line.sectionType] = []
      }
      acc[line.sectionType].push(line.lineIndex)
      return acc
    }, {} as Record<string, number[]>)

    // 渲染每个section
    const orderedSectionIds = visibleModules
      .map(module => SECTION_ID_MAP[module.type])
      .filter(sectionId => sectionId && linesBySection[sectionId])

    const remainingSectionIds = Object.keys(linesBySection).filter(
      sectionId => !orderedSectionIds.includes(sectionId)
    )

    const finalSectionOrder = [...orderedSectionIds, ...remainingSectionIds]

    return finalSectionOrder
      .map(sectionId => {
        const moduleType = SECTION_ID_TO_MODULE[sectionId]
        const lineIndices = linesBySection[sectionId]

        if (!moduleType || !lineIndices) {
          return null
        }

        const sectionElement = renderModule(moduleType, lineIndices)
        if (!sectionElement) {
          return null
        }

        return React.cloneElement(sectionElement, { key: sectionId })
      })
      .filter(Boolean)
  }

  // 检查是否有任何内容
  const hasContent = content.personal_info ||
    content.summary?.text ||
    (content.education && content.education.length > 0) ||
    (content.work_experience && content.work_experience.length > 0) ||
    (content.skills && content.skills.length > 0) ||
    (content.projects && content.projects.length > 0)

  if (!hasContent) {
    return (
      <div className="h-full flex items-center justify-center text-gray-500">
        <div className="text-center">
          <div className="text-6xl mb-4">📄</div>
          <p className="text-lg font-medium mb-2">{t('emptyTitle')}</p>
          <p className="text-sm">{t('emptyDescription')}</p>
        </div>
      </div>
    )
  }

  return (
    <div id="resume-preview-content" ref={containerRef} className="w-full h-full flex flex-col items-center">
      {/* 用于测量的隐藏内容 */}
      {paginationMeasurementContent}
      {smartFitMeasurementContent}

      {/* 加载状态 */}
      {isCalculating && (
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
          <span className="ml-2 text-sm text-gray-600">{t('calculatingPages')}</span>
        </div>
      )}

      {/* 分页显示 */}
      {!isCalculating && pages.length > 0 && (
        <div className="flex-1 w-full overflow-x-hidden overflow-y-auto hide-scrollbar relative">
          <div className="w-full flex justify-center">
            <div
              id="resume-export-content"
              className="flex flex-col items-center print:transform-none"
              style={{
                transform: `scale(${scale})`,
                transformOrigin: 'top center',
                ['--spacing-scale' as string]: String(spacingScale)
              }}
            >
              {pages.map((_, pageIndex) => (
                <ResumePage
                  key={pageIndex}
                  pageNumber={pageIndex + 1}
                  totalPages={totalPages}
                  className="print:break-after-page"
                  templateStyle={templateStyle}
                >
                  {renderPageContent(pageIndex)}
                </ResumePage>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* 简单回退：如果分页计算失败，显示原始内容 */}
      {!isCalculating && pages.length === 0 && (
        <div className="flex-1 w-full overflow-x-hidden overflow-y-auto hide-scrollbar">
          <div className="w-full flex justify-center">
            <div
              className="flex flex-col items-center"
              style={{
                transform: `scale(${scale})`,
                transformOrigin: 'top center',
                ['--spacing-scale' as string]: String(spacingScale)
              }}
            >
              <ResumePage pageNumber={1} totalPages={1} templateStyle={templateStyle}>
                <div className="space-y-6">
                  {visibleModules.map((module) => (
                    <React.Fragment key={module.type}>
                      {renderModule(module.type)}
                    </React.Fragment>
                  ))}
                </div>
              </ResumePage>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
