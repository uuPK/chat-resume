'use client'

import { useEffect } from 'react'
import PaginatedResumePreview, { ModuleConfig } from './PaginatedResumePreview'

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
  id?: string
  school: string
  major: string
  degree: string
  duration: string
  description?: string
  highlights?: Array<{ id?: string; text: string }>
}

interface WorkExperience {
  id?: string
  company: string
  position: string
  duration: string
  description?: string
  summary?: string
  highlights?: Array<{ id?: string; text: string }>
}

interface Skill {
  id?: string
  name: string
  level: string
  category: string
}

interface Project {
  id?: string
  name: string
  description?: string
  summary?: string
  technologies?: string[]
  role: string
  duration: string
  github_url?: string
  demo_url?: string
  achievements?: string[]
  highlights?: Array<{ id?: string; text: string }>
}

interface ResumeContent {
  personal_info?: PersonalInfo
  education?: Education[]
  work_experience?: WorkExperience[]
  skills?: Skill[]
  projects?: Project[]
}

interface ResumePreviewProps {
  content: ResumeContent
  moduleOrder?: ModuleConfig[]  // 可选的自定义模块顺序
}

export default function ResumePreview({ content, moduleOrder }: ResumePreviewProps) {
  // 加载打印样式
  useEffect(() => {
    // 动态加载打印样式
    const loadPrintStyles = () => {
      if (typeof document !== 'undefined') {
        const existingLink = document.getElementById('resume-print-styles')
        if (!existingLink) {
          const link = document.createElement('link')
          link.id = 'resume-print-styles'
          link.rel = 'stylesheet'
          link.href = '/styles/resume-print.css'
          document.head.appendChild(link)
        }
      }
    }

    loadPrintStyles()
  }, [])

  return (
    <div className="h-full overflow-hidden bg-gray-50 p-1 print:h-auto print:p-0 print:bg-white">
      <PaginatedResumePreview content={content} moduleOrder={moduleOrder} />
    </div>
  )
}
