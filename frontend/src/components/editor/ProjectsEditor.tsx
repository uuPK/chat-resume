'use client'

import { useEffect, useState } from 'react'
import {
  FolderIcon,
  PlusIcon,
  TrashIcon,
  LinkIcon,
  CalendarIcon
} from '@heroicons/react/24/outline'

interface Highlight {
  id?: string
  text: string
}

interface Project {
  id?: string
  name: string
  description?: string
  summary?: string
  role: string
  duration: string
  github_url?: string
  demo_url?: string
  achievements?: string[]
  highlights?: Highlight[]
  technologies?: string[]
}

interface ProjectsEditorProps {
  data: Project[]
  onChange: (data: Project[]) => void
}

function normalizeHighlights(project: Project): Highlight[] {
  if (project.highlights && project.highlights.length > 0) {
    return project.highlights
  }
  if (project.achievements && project.achievements.length > 0) {
    return project.achievements.map((text, index) => ({
      id: `${project.id || 'proj'}_hl_${index}`,
      text
    }))
  }
  return [{ id: `${project.id || 'proj'}_hl_0`, text: '' }]
}

export default function ProjectsEditor({ data, onChange }: ProjectsEditorProps) {
  const [projectsList, setProjectsList] = useState<Project[]>(Array.isArray(data) ? data : [])

  useEffect(() => {
    const next = Array.isArray(data)
      ? data.map((project, index) => ({
          ...project,
          id: project.id || `proj_${Date.now()}_${index}`,
          summary: project.summary || project.description || '',
          description: project.description || project.summary || '',
          highlights: normalizeHighlights(project)
        }))
      : []
    setProjectsList(next)
  }, [data])

  const commit = (next: Project[]) => {
    setProjectsList(next)
    onChange(next.map(project => ({
      ...project,
      description: project.summary || project.description || '',
      achievements: (project.highlights || []).map(item => item.text)
    })))
  }

  const addProject = () => {
    commit([
      ...projectsList,
      {
        id: `proj_${Date.now()}`,
        name: '',
        description: '',
        summary: '',
        role: '',
        duration: '',
        github_url: '',
        demo_url: '',
        achievements: [''],
        highlights: [{ id: `hl_${Date.now()}`, text: '' }],
        technologies: []
      }
    ])
  }

  const removeProject = (id: string) => {
    commit(projectsList.filter(project => project.id !== id))
  }

  const updateProject = (id: string, field: keyof Project, value: unknown) => {
    commit(projectsList.map(project => (
      project.id === id ? { ...project, [field]: value } : project
    )))
  }

  const addHighlight = (projectId: string) => {
    const project = projectsList.find(item => item.id === projectId)
    if (!project) return
    updateProject(projectId, 'highlights', [
      ...(project.highlights || []),
      { id: `hl_${Date.now()}`, text: '' }
    ])
  }

  const updateHighlight = (projectId: string, index: number, value: string) => {
    const project = projectsList.find(item => item.id === projectId)
    if (!project) return
    const next = [...(project.highlights || [])]
    next[index] = { ...next[index], text: value }
    updateProject(projectId, 'highlights', next)
  }

  const removeHighlight = (projectId: string, index: number) => {
    const project = projectsList.find(item => item.id === projectId)
    if (!project) return
    const current = project.highlights || []
    if (current.length <= 1) return
    updateProject(projectId, 'highlights', current.filter((_, itemIndex) => itemIndex !== index))
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold text-gray-900 flex items-center">
          <FolderIcon className="w-5 h-5 mr-2" />
          项目经验
        </h3>
        <button
          onClick={addProject}
          className="btn-secondary flex items-center space-x-1 text-sm"
        >
          <PlusIcon className="w-4 h-4" />
          <span>添加项目</span>
        </button>
      </div>

      {projectsList.length === 0 ? (
        <div className="text-center py-8 bg-gray-50 rounded-lg border-2 border-dashed border-gray-300">
          <FolderIcon className="w-12 h-12 text-gray-400 mx-auto mb-2" />
          <p className="text-gray-500 mb-4">还没有添加项目经验</p>
          <button
            onClick={addProject}
            className="btn-primary flex items-center space-x-2 mx-auto"
          >
            <PlusIcon className="w-4 h-4" />
            <span>添加第一个项目</span>
          </button>
        </div>
      ) : (
        <div className="space-y-6">
          {projectsList.map((project, index) => (
            <div key={project.id || index} className="bg-gray-50 rounded-lg p-6 border">
              <div className="flex items-center justify-between mb-6">
                <h4 className="font-medium text-gray-900">项目 {index + 1}</h4>
                {projectsList.length > 1 && (
                  <button
                    onClick={() => removeProject(project.id!)}
                    className="text-red-600 hover:text-red-800 p-1"
                    title="删除此项目"
                  >
                    <TrashIcon className="w-4 h-4" />
                  </button>
                )}
              </div>

              <div className="space-y-6">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      项目名称 <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={project.name}
                      onChange={(e) => updateProject(project.id!, 'name', e.target.value)}
                      placeholder="智能简历生成系统"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      项目周期 <span className="text-red-500">*</span>
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <CalendarIcon className="h-5 w-5 text-gray-400" />
                      </div>
                      <input
                        type="text"
                        value={project.duration}
                        onChange={(e) => updateProject(project.id!, 'duration', e.target.value)}
                        placeholder="2023.03 - 2023.08"
                        className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      项目角色 <span className="text-red-500">*</span>
                    </label>
                    <input
                      type="text"
                      value={project.role}
                      onChange={(e) => updateProject(project.id!, 'role', e.target.value)}
                      placeholder="前端开发工程师"
                      className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      GitHub 地址
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <LinkIcon className="h-5 w-5 text-gray-400" />
                      </div>
                      <input
                        type="url"
                        value={project.github_url || ''}
                        onChange={(e) => updateProject(project.id!, 'github_url', e.target.value)}
                        placeholder="https://github.com/username/project"
                        className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      />
                    </div>
                  </div>

                  <div className="md:col-span-2">
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      演示地址
                    </label>
                    <div className="relative">
                      <div className="absolute inset-y-0 left-0 pl-3 flex items-center pointer-events-none">
                        <LinkIcon className="h-5 w-5 text-gray-400" />
                      </div>
                      <input
                        type="url"
                        value={project.demo_url || ''}
                        onChange={(e) => updateProject(project.id!, 'demo_url', e.target.value)}
                        placeholder="https://your-project-demo.com"
                        className="w-full pl-10 pr-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      />
                    </div>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    项目概述 <span className="text-red-500">*</span>
                  </label>
                  <textarea
                    value={project.summary || ''}
                    onChange={(e) => updateProject(project.id!, 'summary', e.target.value)}
                    placeholder="简要描述项目背景、目标和主要功能..."
                    rows={3}
                    className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-gray-700">
                      项目成果与亮点 <span className="text-red-500">*</span>
                    </label>
                    <button
                      onClick={() => addHighlight(project.id!)}
                      className="text-primary-600 hover:text-primary-800 text-sm flex items-center space-x-1"
                    >
                      <PlusIcon className="w-3 h-3" />
                      <span>添加成果</span>
                    </button>
                  </div>
                  <div className="space-y-2">
                    {(project.highlights || []).map((highlight, highlightIndex) => (
                      <div key={highlight.id || highlightIndex} className="flex items-start space-x-2">
                        <span className="text-gray-400 mt-2">•</span>
                        <textarea
                          value={highlight.text}
                          onChange={(e) => updateHighlight(project.id!, highlightIndex, e.target.value)}
                          placeholder="实现了用户友好的拖拽式简历编辑界面，提升编辑效率50%"
                          rows={2}
                          className="flex-1 px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none"
                        />
                        {(project.highlights || []).length > 1 && (
                          <button
                            onClick={() => removeHighlight(project.id!, highlightIndex)}
                            className="text-red-600 hover:text-red-800 p-1 mt-1"
                          >
                            <TrashIcon className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                  <p className="text-xs text-gray-500 mt-1">
                    💡 建议包含具体数据和指标，突出个人贡献和技术难点
                  </p>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
