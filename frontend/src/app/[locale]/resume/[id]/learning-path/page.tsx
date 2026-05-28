'use client'

import { useParams, useSearchParams } from 'next/navigation'
import { useRouter } from '@/i18n/navigation'
import { useEffect, useState, useCallback } from 'react'
import { resumeApi, resumesApi, chatApi, type LearningPathVersion } from '@/lib/api'
import { ArrowLeftIcon, ArrowDownTrayIcon, ArrowPathIcon, DocumentTextIcon } from '@heroicons/react/24/solid'

export default function LearningPathPage() {
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()
  const resumeId = Number(params.id)
  const sessionId = searchParams.get('session') ? Number(searchParams.get('session')) : null
  
  const [versions, setVersions] = useState<LearningPathVersion[]>([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null)

  const fetchVersions = useCallback(async () => {
    try {
      setLoading(true)
      const data = await resumeApi.getLearningPaths(resumeId)
      setVersions(data)
      if (data.length > 0 && selectedVersionId === null) {
        setSelectedVersionId(data[0].id)
      }
    } catch (err) {
      console.error(err)
    } finally {
      setLoading(false)
    }
  }, [resumeId, selectedVersionId])

  useEffect(() => {
    fetchVersions()
  }, [fetchVersions])

  const handleGenerate = async () => {
    try {
      setGenerating(true)
      if (sessionId) {
        await chatApi.generateLearningPath(sessionId)
      } else {
        await resumeApi.generateLearningPath(resumeId)
      }
      await fetchVersions()
    } catch (err) {
      console.error(err)
      alert('生成失败')
    } finally {
      setGenerating(false)
    }
  }

  const handleExport = async (format: 'pdf' | 'docx') => {
    if (!selectedVersionId) return
    try {
      await resumesApi.exportLearningPath(selectedVersionId, format)
    } catch (err) {
      console.error('Export failed:', err)
      alert('导出失败')
    }
  }

  const selectedVersion = versions.find(v => v.id === selectedVersionId)

  if (loading) {
    return <div className="p-8 text-center">加载中...</div>
  }

  return (
    <div className="min-h-screen bg-gray-50/30">
      <div className="border-b bg-white">
        <div className="container mx-auto px-4 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                type="button"
                onClick={() => router.push('/resumes')}
                className="p-2 hover:bg-gray-100 rounded-full transition-colors text-gray-600"
              >
                <ArrowLeftIcon className="h-5 w-5" />
              </button>
              <h1 className="text-xl font-semibold">个性化学习路线</h1>
            </div>
            
            <div className="flex gap-2">
              <button
                type="button"
                onClick={handleGenerate}
                disabled={generating}
                className="inline-flex h-9 items-center justify-center gap-2 rounded-lg bg-blue-600 px-4 text-[13px] font-medium text-white transition-colors hover:bg-blue-700 disabled:opacity-50"
              >
                <ArrowPathIcon className={`h-4 w-4 ${generating ? 'animate-spin' : ''}`} />
                {generating ? '生成中...' : (sessionId ? '根据本次面试生成路线' : '根据当前简历生成路线')}
              </button>
              {selectedVersion && (
                <>
                  <button type="button" onClick={() => handleExport('pdf')} className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-gray-300 bg-white px-4 text-[13px] font-medium text-gray-700 transition-colors hover:bg-gray-50">
                    <ArrowDownTrayIcon className="h-4 w-4" /> PDF
                  </button>
                  <button type="button" onClick={() => handleExport('docx')} className="inline-flex h-9 items-center justify-center gap-2 rounded-lg border border-gray-300 bg-white px-4 text-[13px] font-medium text-gray-700 transition-colors hover:bg-gray-50">
                    <DocumentTextIcon className="h-4 w-4" /> Word
                  </button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      <div className="container mx-auto px-4 py-8 max-w-6xl">
        {versions.length === 0 ? (
          <div className="text-center py-20 bg-white rounded-lg border border-dashed">
            <h2 className="text-lg font-medium text-gray-900 mb-2">暂无学习路线</h2>
            <p className="text-gray-500 mb-6">点击右上角按钮，基于您的简历生成一份 4 周专属成长计划</p>
          </div>
        ) : (
          <div className="flex gap-6">
            <div className="w-64 flex-shrink-0">
              <div className="bg-white rounded-xl border p-4">
                <h3 className="font-medium text-sm text-gray-500 uppercase mb-4">历史版本</h3>
                <div className="space-y-2">
                  {versions.map((v) => (
                    <button
                      key={v.id}
                      onClick={() => setSelectedVersionId(v.id)}
                      className={`w-full text-left px-3 py-2 rounded-md text-sm transition-colors ${
                        v.id === selectedVersionId
                          ? 'bg-blue-50 text-blue-700 font-medium'
                          : 'hover:bg-gray-50 text-gray-600'
                      }`}
                    >
                      <div className="truncate">
                        {new Date(v.created_at).toLocaleString('zh-CN', {
                          month: 'numeric',
                          day: 'numeric',
                          hour: '2-digit',
                          minute: '2-digit'
                        })}
                      </div>
                      <div className="text-xs mt-1 opacity-70">
                        {v.trigger_type === 'resume_update' ? '由简历更新触发' : '由面试结果触发'}
                      </div>
                    </button>
                  ))}
                </div>
              </div>
            </div>

            <div className="flex-1 bg-white rounded-xl border p-8">
              {selectedVersion && (
                <div className="max-w-3xl mx-auto">
                  <div className="mb-10 text-center">
                    <h2 className="text-2xl font-bold text-gray-900 mb-4">学习路线概览</h2>
                    <p className="text-lg text-gray-600 bg-blue-50/50 p-4 rounded-lg inline-block text-left w-full">
                      {selectedVersion.plan_data.summary}
                    </p>
                  </div>

                  <div className="space-y-12">
                    {selectedVersion.plan_data.weeks.map((week, idx) => (
                      <div key={idx} className="relative pl-8">
                        {/* Timeline line */}
                        <div className="absolute left-3 top-2 bottom-0 w-0.5 bg-blue-100" />
                        
                        {/* Timeline dot */}
                        <div className="absolute left-[9px] top-2 w-3 h-3 rounded-full bg-blue-500 ring-4 ring-white" />

                        <div className="mb-4">
                          <span className="text-sm font-bold tracking-wider text-blue-600 uppercase">
                            Week {week.week_number}
                          </span>
                          <h3 className="text-xl font-bold text-gray-900 mt-1">{week.theme}</h3>
                          <div className="inline-block mt-2 px-3 py-1 bg-green-50 text-green-700 rounded-md text-sm font-medium">
                            🎯 {week.goal}
                          </div>
                        </div>

                        <div className="space-y-4 mb-6">
                          {week.tasks.map((task, tIdx) => (
                            <div key={tIdx} className="bg-gray-50 rounded-lg p-4 border border-gray-100">
                              <h4 className="font-medium text-gray-900 mb-2">{task.name}</h4>
                              <p className="text-gray-600 text-sm mb-3">{task.description}</p>
                              
                              {task.resource_links && task.resource_links.length > 0 && (
                                <div className="mt-3 pt-3 border-t border-gray-200/60">
                                  <div className="text-xs font-medium text-gray-500 mb-2">推荐资源</div>
                                  <ul className="list-disc list-inside text-sm text-gray-600 space-y-1">
                                    {task.resource_links.map((link, lIdx) => (
                                      <li key={lIdx}>{link}</li>
                                    ))}
                                  </ul>
                                </div>
                              )}
                            </div>
                          ))}
                        </div>

                        <div className="bg-orange-50/50 border border-orange-100 rounded-lg p-4 flex items-start gap-3">
                          <div className="text-orange-500 mt-0.5">✅</div>
                          <div>
                            <div className="text-sm font-medium text-orange-800 mb-1">达标标准</div>
                            <div className="text-sm text-orange-700">{week.passing_criteria}</div>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
