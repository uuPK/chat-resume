'use client'

import React, { ReactNode, useMemo, useRef } from 'react'
import { useLineBasedPagination, A4_WIDTH, PAGE_PADDING } from './hooks/useLineBasedPagination'
import ResumePage from './ResumePage'
import PersonalInfoPreview from './sections/PersonalInfoPreview'
import EducationPreview from './sections/EducationPreview'
import WorkExperiencePreview from './sections/WorkExperiencePreview'
import SkillsPreview from './sections/SkillsPreview'
import ProjectsPreview from './sections/ProjectsPreview'

// 模块类型定义
export type ModuleType = 'personal' | 'education' | 'work' | 'skills' | 'projects'

const SECTION_ID_MAP: Record<ModuleType, string> = {
  personal: 'personal-info-section',
  education: 'education-section',
  work: 'work-experience-section',
  skills: 'skills-section',
  projects: 'projects-section'
}

const SECTION_ID_TO_MODULE = Object.entries(SECTION_ID_MAP).reduce(
  (acc, [moduleType, sectionId]) => {
    acc[sectionId] = moduleType as ModuleType
    return acc
  },
  {} as Record<string, ModuleType>
)

// 模块配置接口
export interface ModuleConfig {
  type: ModuleType
  visible: boolean
  order: number
  label: string
}

// 默认模块顺序配置
export const DEFAULT_MODULE_ORDER: ModuleConfig[] = [
  { type: 'personal', visible: true, order: 0, label: '个人信息' },
  { type: 'education', visible: true, order: 1, label: '教育背景' },
  { type: 'work', visible: true, order: 2, label: '工作经验' },
  { type: 'skills', visible: true, order: 3, label: '技能专长' },
  { type: 'projects', visible: true, order: 4, label: '项目经验' },
]

interface PersonalInfo {
  name?: string
  email?: string
  phone?: string
  position?: string
  github?: string
  linkedin?: string
  website?: string
  address?: string
}

interface Education {
  id?: number
  school: string
  major: string
  degree: string
  duration: string
  description?: string
}

interface WorkExperience {
  id?: number
  company: string
  position: string
  duration: string
  description: string
}

interface Skill {
  id?: number
  name: string
  level: string
  category: string
}

interface Project {
  id?: number
  name: string
  description: string
  technologies: string[]
  role: string
  duration: string
  github_url?: string
  demo_url?: string
  achievements: string[]
}

interface ResumeContent {
  personal_info?: PersonalInfo
  education?: Education[]
  work_experience?: WorkExperience[]
  skills?: Skill[]
  projects?: Project[]
}

interface PaginatedResumePreviewProps {
  content: ResumeContent
  moduleOrder?: ModuleConfig[]
}

export default function PaginatedResumePreview({ content, moduleOrder = DEFAULT_MODULE_ORDER }: PaginatedResumePreviewProps) {
  const containerRef = useRef<HTMLDivElement>(null)
  const contentRef = useRef<HTMLDivElement>(null)
  const [scale, setScale] = React.useState(1)
  
  // 按order排序并过滤可见模块
  const moduleOrderKey = JSON.stringify(moduleOrder.map(m => ({ type: m.type, visible: m.visible, order: m.order })))
  const visibleModules = useMemo(() => {
    return [...moduleOrder]
      .filter(m => m.visible)
      .sort((a, b) => a.order - b.order)
  }, [moduleOrderKey])

  const { pages, totalPages, isCalculating } = useLineBasedPagination({
    containerRef,
    contentRef
  })

  // 计算合适的缩放比例
  React.useEffect(() => {
    const calculateScale = () => {
      if (!containerRef.current) return

      const container = containerRef.current
      const containerWidth = container.clientWidth
      const A4_WIDTH = 816
      const padding = 8

      const availableWidth = containerWidth - padding * 2
      const rawScale = availableWidth / A4_WIDTH
      const calculatedScale = Math.min(3.0, Math.max(0.3, rawScale))
      
      setScale(calculatedScale)
    }

    calculateScale()

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
  }, [])

  // 根据模块类型渲染组件
  const renderSection = (sectionId: string, children: ReactNode): JSX.Element => (
    <section data-section-id={sectionId} className="mb-6 last:mb-0">
      {children}
    </section>
  )

  const renderModule = (moduleType: ModuleType, renderLines?: number[]): JSX.Element | null => {
    const sectionId = SECTION_ID_MAP[moduleType]

    switch (moduleType) {
      case 'personal':
        return content.personal_info
          ? renderSection(sectionId, <PersonalInfoPreview data={content.personal_info} renderLines={renderLines} />)
          : null
      case 'education':
        return content.education && content.education.length > 0
          ? renderSection(sectionId, <EducationPreview data={content.education} renderLines={renderLines} />)
          : null
      case 'work':
        return content.work_experience && content.work_experience.length > 0
          ? renderSection(sectionId, <WorkExperiencePreview data={content.work_experience} renderLines={renderLines} />)
          : null
      case 'skills':
        return content.skills && content.skills.length > 0
          ? renderSection(sectionId, <SkillsPreview data={content.skills} renderLines={renderLines} />)
          : null
      case 'projects':
        return content.projects && content.projects.length > 0
          ? renderSection(sectionId, <ProjectsPreview data={content.projects} renderLines={renderLines} />)
          : null
      default:
        return null
    }
  }

  // 渲染所有内容用于测量
  const measurementContent = useMemo(() => (
    <div
      ref={contentRef}
      className="invisible absolute -top-[9999px] left-0 pointer-events-none"
      style={{
        width: `${A4_WIDTH}px`,
        padding: `${PAGE_PADDING}px`,
        boxSizing: 'border-box'
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
  ), [content, visibleModules, moduleOrderKey])

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
                    (content.education && content.education.length > 0) ||
                    (content.work_experience && content.work_experience.length > 0) ||
                    (content.skills && content.skills.length > 0) ||
                    (content.projects && content.projects.length > 0)

  if (!hasContent) {
    return (
      <div className="h-full flex items-center justify-center text-gray-500">
        <div className="text-center">
          <div className="text-6xl mb-4">📄</div>
          <p className="text-lg font-medium mb-2">开始编辑简历</p>
          <p className="text-sm">在左侧编辑区域填写信息，实时预览将在这里显示</p>
        </div>
      </div>
    )
  }

  return (
    <div ref={containerRef} className="w-full h-full flex flex-col items-center">
      {/* 用于测量的隐藏内容 */}
      {measurementContent}

      {/* 加载状态 */}
      {isCalculating && (
        <div className="flex items-center justify-center py-8">
          <div className="animate-spin rounded-full h-6 w-6 border-b-2 border-blue-600"></div>
          <span className="ml-2 text-sm text-gray-600">正在计算分页...</span>
        </div>
      )}

      {/* 分页显示 */}
      {!isCalculating && pages.length > 0 && (
        <div className="flex-1 w-full overflow-x-hidden overflow-y-auto">
          <div className="w-full flex justify-center">
            <div 
              className="flex flex-col items-center"         
              style={{
                transform: `scale(${scale})`,
                transformOrigin: 'top center'
              }}
            >
              {pages.map((_, pageIndex) => (
                <ResumePage
                  key={pageIndex}
                  pageNumber={pageIndex + 1}
                  totalPages={totalPages}
                  className="print:break-after-page"
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
        <div className="flex-1 w-full overflow-x-hidden overflow-y-auto">
          <div className="w-full flex justify-center">
            <div
              className="flex flex-col items-center"
              style={{
                transform: `scale(${scale})`,
                transformOrigin: 'top center'
              }}
            >
              <ResumePage pageNumber={1} totalPages={1}>
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
