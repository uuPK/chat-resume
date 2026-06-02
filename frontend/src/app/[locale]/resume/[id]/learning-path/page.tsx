'use client'

import { useParams, useSearchParams } from 'next/navigation'
import { useRouter } from '@/i18n/navigation'
import { useEffect, useState, useCallback, useRef } from 'react'
import { resumeApi, resumesApi, chatApi, schoolApi, learningApi, type LearningPathVersion } from '@/lib/api'
import { ArrowLeftIcon, ArrowDownTrayIcon, ArrowPathIcon, DocumentTextIcon, SparklesIcon } from '@heroicons/react/24/solid'
import toast from 'react-hot-toast'

export default function LearningPathPage() {
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()
  const resumeId = Number(params.id)
  const sessionId = searchParams.get('session') ? Number(searchParams.get('session')) : null
  
  const [versions, setVersions] = useState<LearningPathVersion[]>([])
  const [schoolCourses, setSchoolCourses] = useState<any[]>([])
  const [loading, setLoading] = useState(true)
  const [generating, setGenerating] = useState(false)
  const [selectedVersionId, setSelectedVersionId] = useState<number | null>(null)
  const [enrollingId, setEnrollingId] = useState<number | null>(null)

  const autoGenerate = searchParams.get('autoGenerate') === 'true'
  const autoGenerateAttempted = useRef(false)

  const fetchVersions = useCallback(async () => {
    try {
      setLoading(true)
      const [data, courses, myPlan] = await Promise.all([
        resumeApi.getLearningPaths(resumeId),
        schoolApi.getCourses().catch(() => []),
        learningApi.getLearningPlan().catch(() => [])
      ])
      setVersions(data)
      const enrolledIds = new Set(myPlan.map(c => c.id))
      setSchoolCourses(courses.filter(c => !enrolledIds.has(c.id)))
      if (data.length > 0 && selectedVersionId === null) {
        setSelectedVersionId(data[0].id)
      }
      return data
    } catch (err) {
      console.error(err)
      return []
    } finally {
      setLoading(false)
    }
  }, [resumeId, selectedVersionId])

  useEffect(() => {
    let mounted = true
    fetchVersions().then((data) => {
      if (!mounted) return
      if (autoGenerate && !autoGenerateAttempted.current) {
        autoGenerateAttempted.current = true
        // 如果是从面试页面过来的，且还没有对应这个 sessionId 的版本，就自动触发生成
        const hasSessionVersion = sessionId ? data.some(v => v.interview_session_id === sessionId) : data.length > 0
        if (!hasSessionVersion) {
          // 不在这里直接用 handleGenerate，因为依赖闭包，我们直接在这里调 API
          setGenerating(true)
          const genPromise = sessionId ? chatApi.generateLearningPath(sessionId) : resumeApi.generateLearningPath(resumeId)
          genPromise.then(() => {
            if (mounted) fetchVersions()
          }).catch(err => {
            console.error('自动生成失败', err)
          }).finally(() => {
            if (mounted) setGenerating(false)
          })
        }
      }
    })
    return () => { mounted = false }
  }, [fetchVersions, autoGenerate, sessionId, resumeId])

  const handleGenerate = async (triggerType?: string) => {
    try {
      setGenerating(true)
      if (sessionId) {
        await chatApi.generateLearningPath(sessionId, triggerType)
      } else {
        await resumeApi.generateLearningPath(resumeId, triggerType)
      }
      await fetchVersions()
    } catch (err) {
      console.error(err)
      alert('生成失败')
    } finally {
      setGenerating(false)
    }
  }

  const handleEnrollAndRegenerate = async (courseId: number) => {
    try {
      setEnrollingId(courseId)
      await learningApi.enrollCourse(courseId)
      toast.success('已加入学习计划，正在重新生成路线...')
      await handleGenerate('course_enroll')
    } catch {
      toast.error('加入失败，您可能已经加入过该课程')
    } finally {
      setEnrollingId(null)
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
                onClick={() => handleGenerate()}
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
                        {v.trigger_type === 'resume_update' ? '由简历更新触发' : v.trigger_type === 'course_enroll' ? '由高校优选课程触发' : '由面试结果触发'}
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

                  {schoolCourses.length > 0 && (
                    <div className="mb-10 bg-indigo-50 dark:bg-indigo-900/20 rounded-xl p-6 border border-indigo-100 dark:border-indigo-800">
                      <div className="flex items-center gap-2 mb-4">
                        <SparklesIcon className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                        <h3 className="text-lg font-semibold text-indigo-900 dark:text-indigo-300">高校优选课程</h3>
                      </div>
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                        {schoolCourses.map(course => {
                          let parsedOutline: any = null;
                          try {
                            parsedOutline = course.outline ? JSON.parse(course.outline) : null;
                          } catch (e) {}

                          return (
                            <div key={course.id} className="bg-white dark:bg-gray-800 p-4 rounded-lg shadow-sm border border-indigo-100 dark:border-gray-700">
                              <h4 className="font-medium text-gray-900 dark:text-white mb-1">{course.title}</h4>
                              <p className="text-sm text-gray-500 dark:text-gray-400 line-clamp-2 mb-3">{course.description}</p>
                              <div className="flex flex-wrap gap-2 mb-4">
                                {course.target_skills?.split(',').map((skill: string) => (
                                  <span key={skill} className="px-2 py-0.5 bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 text-xs rounded">
                                    {skill.trim()}
                                  </span>
                                ))}
                              </div>
                              
                              {/* 课程大纲展示 */}
                              {parsedOutline && parsedOutline.weeks && (
                                <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-700">
                                  <h5 className="text-xs font-semibold text-gray-900 dark:text-white mb-3">课程大纲</h5>
                                  <div className="space-y-3">
                                    {parsedOutline.weeks.map((week: any, idx: number) => (
                                      <div key={idx} className="bg-gray-50 dark:bg-gray-700/30 rounded p-3">
                                        <div className="text-xs font-bold text-indigo-600 dark:text-indigo-400 uppercase">
                                          Week {week.week_number}
                                        </div>
                                        <h6 className="text-sm font-medium text-gray-900 dark:text-white mt-0.5">{week.theme}</h6>
                                        <div className="mt-2 space-y-1.5">
                                          {week.tasks.map((task: any, tIdx: number) => (
                                            <div key={tIdx} className="text-xs bg-white dark:bg-gray-800 p-2 rounded border border-gray-200 dark:border-gray-600">
                                              <span className="font-medium text-gray-800 dark:text-gray-200">{task.name}: </span>
                                              <span className="text-gray-500 dark:text-gray-400">{task.description}</span>
                                            </div>
                                          ))}
                                        </div>
                                      </div>
                                    ))}
                                  </div>
                                </div>
                              )}

                              <button
                                onClick={() => handleEnrollAndRegenerate(course.id)}
                                disabled={enrollingId === course.id || generating}
                                className="mt-4 w-full py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded transition-colors disabled:opacity-50"
                              >
                                {enrollingId === course.id ? '加入中...' : '加入计划并更新路线'}
                              </button>
                            </div>
                          );
                        })}
                      </div>
                    </div>
                  )}

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
