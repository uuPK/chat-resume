'use client'

import { useEffect, useState } from 'react'
import MainNavigation from '@/components/layout/MainNavigation'
import SchoolSidebar from '@/components/layout/SchoolSidebar'
import { schoolApi, type AICourse } from '@/lib/api'
import { CheckCircleIcon, XCircleIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'

export default function CoursesManagement() {
  const [courses, setCourses] = useState<AICourse[]>([])
  const [loading, setLoading] = useState(true)
  const [publishingId, setPublishingId] = useState<number | null>(null)

  useEffect(() => {
    fetchCourses()
  }, [])

  const fetchCourses = async () => {
    try {
      const data = await schoolApi.getCourses()
      setCourses(data)
    } finally {
      setLoading(false)
    }
  }

  const handlePublish = async (id: number) => {
    setPublishingId(id)
    try {
      await schoolApi.publishCourse(id)
      toast.success('发布成功，课程已推送到市场！')
      fetchCourses()
    } catch {
      toast.error('发布失败')
    } finally {
      setPublishingId(null)
    }
  }

  return (
    <div className="flex h-screen flex-col bg-gray-50 dark:bg-gray-900">
      <MainNavigation />
      
      <div className="flex flex-1 overflow-hidden">
        <aside className="w-64 border-r border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900 hidden md:block">
          <SchoolSidebar />
        </aside>

        <main className="flex-1 overflow-y-auto p-8">
          <div className="max-w-5xl mx-auto">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">课程管理</h1>
            
            {loading ? (
              <div className="animate-pulse space-y-4">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-24 bg-gray-200 dark:bg-gray-800 rounded-xl" />
                ))}
              </div>
            ) : courses.length === 0 ? (
              <div className="text-center py-12 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
                <p className="text-gray-500">暂无课程，请前往「智能生成大纲」创建。</p>
              </div>
            ) : (
              <div className="space-y-4">
                {courses.map(course => {
                  let parsedOutline: any = null;
                  try {
                    parsedOutline = course.outline ? JSON.parse(course.outline) : null;
                  } catch (e) {}

                  return (
                    <div key={course.id} className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700 flex flex-col">
                      <div className="flex items-center justify-between">
                        <div>
                          <div className="flex items-center gap-3 mb-2">
                            <h2 className="text-lg font-semibold text-gray-900 dark:text-white">{course.title}</h2>
                            {course.published ? (
                              <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-green-700 bg-green-50 border border-green-200 rounded-full dark:bg-green-900/30 dark:text-green-400 dark:border-green-800">
                                <CheckCircleIcon className="w-3.5 h-3.5" /> 已发布
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 px-2 py-1 text-xs font-medium text-gray-600 bg-gray-100 border border-gray-200 rounded-full dark:bg-gray-800 dark:text-gray-400 dark:border-gray-700">
                                <XCircleIcon className="w-3.5 h-3.5" /> 草稿
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-gray-500 line-clamp-2 max-w-2xl">{course.description}</p>
                          {course.target_skills && (
                            <div className="mt-3 flex gap-2">
                              {course.target_skills.split(',').map(s => (
                                <span key={s} className="px-2 py-0.5 bg-indigo-50 text-indigo-600 dark:bg-indigo-900/30 dark:text-indigo-400 text-xs rounded border border-indigo-100 dark:border-indigo-800">
                                  {s.trim()}
                                </span>
                              ))}
                            </div>
                          )}
                        </div>
                        
                        <div>
                          {!course.published && (
                            <button
                              onClick={() => handlePublish(course.id)}
                              disabled={publishingId === course.id}
                              className="px-4 py-2 bg-primary-600 hover:bg-primary-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
                            >
                              {publishingId === course.id ? '发布中...' : '发布到大盘'}
                            </button>
                          )}
                        </div>
                      </div>

                      {/* 课程大纲展示 */}
                      {parsedOutline && parsedOutline.weeks && (
                        <div className="mt-6 pt-6 border-t border-gray-100 dark:border-gray-700">
                          <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">课程大纲</h3>
                          <div className="space-y-4">
                            {parsedOutline.weeks.map((week: any, idx: number) => (
                              <div key={idx} className="bg-gray-50 dark:bg-gray-700/30 rounded-lg p-4">
                                <div className="flex items-start justify-between">
                                  <div>
                                    <span className="text-xs font-bold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">
                                      Week {week.week_number}
                                    </span>
                                    <h4 className="text-md font-medium text-gray-900 dark:text-white mt-1">{week.theme}</h4>
                                    <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">🎯 {week.goal}</p>
                                  </div>
                                </div>
                                <div className="mt-3 space-y-2">
                                  {week.tasks.map((task: any, tIdx: number) => (
                                    <div key={tIdx} className="text-sm bg-white dark:bg-gray-800 p-3 rounded border border-gray-200 dark:border-gray-600">
                                      <div className="font-medium text-gray-900 dark:text-gray-200">{task.name}</div>
                                      <div className="text-gray-500 dark:text-gray-400 mt-1">{task.description}</div>
                                    </div>
                                  ))}
                                </div>
                                <div className="mt-3 text-xs font-medium text-orange-600 dark:text-orange-400 bg-orange-50 dark:bg-orange-900/20 p-2 rounded">
                                  考核标准: {week.passing_criteria}
                                </div>
                              </div>
                            ))}
                          </div>
                        </div>
                      )}
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        </main>
      </div>
    </div>
  )
}
