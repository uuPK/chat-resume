'use client'

import { useEffect, useState } from 'react'
import {
  FolderIcon,
  PlusIcon,
  TrashIcon,
  LinkIcon,
  CalendarIcon
} from '@heroicons/react/24/outline'
import type { Project, ResumeBullet as Bullet } from '@/types/resume'

interface ProjectsEditorProps {
  data: Project[]
  onChange: (data: Project[]) => void
}

function normalizeBullets(project: Project): Bullet[] {
  if (project.highlights && project.highlights.length > 0) {
    return project.highlights
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
          overview: project.overview || '',
          highlights: normalizeBullets(project)
        }))
      : []
    setProjectsList(next)
  }, [data])

  const commit = (next: Project[]) => {
    setProjectsList(next)
    onChange(next)
  }

  const addProject = () => {
    commit([
      ...projectsList,
      {
        id: `proj_${Date.now()}`,
        name: '',
        overview: '',
        role: '',
        duration: '',
        github_url: '',
        demo_url: '',
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

  const addBullet = (projectId: string) => {
    const project = projectsList.find(item => item.id === projectId)
    if (!project) return
    updateProject(projectId, 'highlights', [
      ...(project.highlights || []),
      { id: `hl_${Date.now()}`, text: '' }
    ])
  }

  const updateBullet = (projectId: string, index: number, value: string) => {
    const project = projectsList.find(item => item.id === projectId)
    if (!project) return
    const next = [...(project.highlights || [])]
    next[index] = { ...next[index], text: value }
    updateProject(projectId, 'highlights', next)
  }

  const removeBullet = (projectId: string, index: number) => {
    const project = projectsList.find(item => item.id === projectId)
    if (!project) return
    const current = project.highlights || []
    if (current.length <= 1) return
    updateProject(projectId, 'highlights', current.filter((_, itemIndex) => itemIndex !== index))
  }

  return (
    <div className="space-y-6">
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
            <div key={project.id || index} className="bg-white rounded-lg p-6 border">
              <div className="flex items-center justify-end mb-1">
                {projectsList.length > 1 && (
                  <button
                    onClick={() => removeProject(project.id!)}
                    className="text-gray-400 hover:text-gray-600 p-1 transition-colors"
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
                      项目名称
                    </label>
                    <input
                      type="text"
                      value={project.name}
                      onChange={(e) => updateProject(project.id!, 'name', e.target.value)}
                      placeholder="智能简历生成系统"
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      项目周期
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
                        className="w-full pl-10 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-1">
                      项目角色
                    </label>
                    <input
                      type="text"
                      value={project.role}
                      onChange={(e) => updateProject(project.id!, 'role', e.target.value)}
                      placeholder="前端开发工程师"
                      className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
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
                        className="w-full pl-10 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
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
                        className="w-full pl-10 pr-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
                      />
                    </div>
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-1">
                    简介
                  </label>
                  <textarea
                    value={project.overview || ''}
                    onChange={(e) => updateProject(project.id!, 'overview', e.target.value)}
                    placeholder="一句话说明项目背景、目标或你的角色..."
                    rows={1}
                    className="w-full px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none [field-sizing:content]"
                  />
                </div>

                <div>
                  <div className="flex items-center justify-between mb-2">
                    <label className="block text-sm font-medium text-gray-700">
                      主要成果
                    </label>
                    <button
                      onClick={() => addBullet(project.id!)}
                      className="text-primary-600 hover:text-primary-800 text-sm flex items-center space-x-1"
                    >
                      <PlusIcon className="w-3 h-3" />
                      <span>添加成果</span>
                    </button>
                  </div>
                  <div className="space-y-2">
                    {(project.highlights || []).map((highlight, highlightIndex) => (
                      <div key={highlight.id || highlightIndex} className="flex items-center space-x-2">
                        <textarea
                          value={highlight.text}
                          onChange={(e) => updateBullet(project.id!, highlightIndex, e.target.value)}
                          placeholder="实现了用户友好的拖拽式简历编辑界面，提升编辑效率50%"
                          rows={1}
                          className="flex-1 px-3 py-2 text-sm border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent resize-none [field-sizing:content]"
                        />
                        {(project.highlights || []).length > 1 && (
                          <button
                            onClick={() => removeBullet(project.id!, highlightIndex)}
                            className="text-gray-400 hover:text-gray-600 p-1 transition-colors"
                          >
                            <TrashIcon className="w-4 h-4" />
                          </button>
                        )}
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          ))}
          <button
            onClick={addProject}
            className="w-full py-4 rounded-lg border-2 border-dashed border-gray-300 text-gray-500 hover:text-primary-600 hover:border-primary-400 transition-colors flex items-center justify-center space-x-2"
          >
            <PlusIcon className="w-4 h-4" />
            <span>添加项目</span>
          </button>
        </div>
      )}
    </div>
  )
}
