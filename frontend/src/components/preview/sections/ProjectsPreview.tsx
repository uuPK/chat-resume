'use client'

import { LinkIcon } from '@heroicons/react/24/outline'

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

interface ProjectsPreviewProps {
  data: Project[]
  renderLines?: number[] // 指定渲染哪些行
}

// 单个项目项组件
export function ProjectItem({ project, lineIndex }: { project: Project; lineIndex: number }) {
  return (
    <div data-line-index={lineIndex} className="relative print:break-inside-avoid mb-4">
      <div className="flex justify-between items-start mb-2">
        <div className="flex-1 flex flex-wrap items-center gap-2">
          <h3 className="font-semibold text-gray-900 text-base">
            {project.name}
          </h3>
          {project.role && (
            <>
              <span className="w-px h-4 bg-gray-300" />
              <span className="text-sm text-gray-600">{project.role}</span>
            </>
          )}
        </div>
        <div className="text-sm text-gray-600 ml-4 whitespace-nowrap">
          {project.duration}
        </div>
      </div>

      {(project.github_url || project.demo_url) && (
        <div className="flex gap-4 text-sm text-blue-600 mb-2">
          {project.github_url && (
            <a
              href={project.github_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 hover:underline"
            >
              <LinkIcon className="w-4 h-4" />
              Github
            </a>
          )}
          {project.demo_url && (
            <a
              href={project.demo_url}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1 hover:underline"
            >
              <LinkIcon className="w-4 h-4" />
              Demo
            </a>
          )}
        </div>
      )}

      {project.description && (
        <p className="text-sm text-gray-600 mb-2 leading-relaxed">
          {project.description}
        </p>
      )}

      {/* 项目成果 */}
      {project.achievements && project.achievements.length > 0 && (
        <div className="mb-2">
          <span className="text-sm font-medium text-gray-700">主要成果:</span>
          <ul className="list-disc list-inside text-sm text-gray-600 mt-1">
            {project.achievements.map((achievement, achIndex) => (
              <li key={achIndex}>{achievement}</li>
            ))}
          </ul>
        </div>
      )}

    </div>
  )
}

export default function ProjectsPreview({
  data,
  renderLines
}: ProjectsPreviewProps) {
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
          项目经验
        </h2>
      )}

      {/* 每个项目作为独立的行 */}
      {data.map((project, index) => {
        const lineIndex = index + 1
        return shouldRenderLine(lineIndex) ? (
          <ProjectItem key={project.id || index} project={project} lineIndex={lineIndex} />
        ) : null
      })}
    </div>
  )
}
