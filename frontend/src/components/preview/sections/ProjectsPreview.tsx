'use client'

interface Project {
  id?: string
  name: string
  overview?: string
  technologies?: string[]
  role: string
  duration: string
  github_url?: string
  demo_url?: string
  highlights?: Array<{
    id?: string
    text: string
  }>
}

interface ProjectsPreviewProps {
  data: Project[]
  renderLines?: number[]
}

/* 链接图标包装器：使用 flex 对齐，避免导出时基线计算偏差 */
const iconWrap: React.CSSProperties = {
  display: 'inline-flex',
  alignItems: 'center',
  justifyContent: 'center',
  width: 12,
  height: 12,
  marginRight: 3,
  flexShrink: 0,
}

const GithubIcon = () => (
  <span style={iconWrap}>
    <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor">
      <path d="M12 2C6.477 2 2 6.484 2 12.017c0 4.425 2.865 8.18 6.839 9.504.5.092.682-.217.682-.483 0-.237-.008-.868-.013-1.703-2.782.605-3.369-1.343-3.369-1.343-.454-1.158-1.11-1.466-1.11-1.466-.908-.62.069-.608.069-.608 1.003.07 1.531 1.032 1.531 1.032.892 1.53 2.341 1.088 2.91.832.092-.647.35-1.088.636-1.338-2.22-.253-4.555-1.113-4.555-4.951 0-1.093.39-1.988 1.029-2.688-.103-.253-.446-1.272.098-2.65 0 0 .84-.27 2.75 1.026A9.564 9.564 0 0 1 12 6.844a9.59 9.59 0 0 1 2.504.337c1.909-1.296 2.747-1.027 2.747-1.027.546 1.379.202 2.398.1 2.651.64.7 1.028 1.595 1.028 2.688 0 3.848-2.339 4.695-4.566 4.943.359.309.678.92.678 1.855 0 1.338-.012 2.419-.012 2.747 0 .268.18.58.688.482A10.02 10.02 0 0 0 22 12.017C22 6.484 17.522 2 12 2z"/>
    </svg>
  </span>
)

const DemoIcon = () => (
  <span style={iconWrap}>
    <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="10"/>
      <path d="M2 12h20M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z"/>
    </svg>
  </span>
)

// 单个项目项组件
export function ProjectItem({ project, lineIndex }: { project: Project; lineIndex: number }) {
  const highlights = project.highlights && project.highlights.length > 0
    ? project.highlights.map(item => item.text)
    : []

  return (
    <div data-line-index={lineIndex} className="relative print:break-inside-avoid" style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 16px)' }}>
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
              className="inline-flex items-center gap-1 leading-none hover:underline"
            >
              <GithubIcon />
              <span className="inline-block leading-none">Github</span>
            </a>
          )}
          {project.demo_url && (
            <a
              href={project.demo_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 leading-none hover:underline"
            >
              <DemoIcon />
              <span className="inline-block leading-none">Demo</span>
            </a>
          )}
        </div>
      )}

      {project.overview && (
        <p className="text-sm text-gray-600 mb-2 leading-relaxed">
          {project.overview}
        </p>
      )}

      {highlights.length > 0 && (
        <div className="mb-2">
          <span className="text-sm font-medium text-gray-700">关键亮点:</span>
          <ul className="list-disc list-inside text-sm text-gray-600 mt-1">
            {highlights.map((achievement, achIndex) => (
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
    <div style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 20px)' }}>
      {/* 标题作为第0行 */}
      {shouldRenderLine(0) && (
        <h2 data-line-index={0} className="text-lg font-bold text-gray-900 pb-1.5 border-b border-gray-300" style={{ marginBottom: 'calc(var(--spacing-scale, 1) * 12px)' }}>
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
