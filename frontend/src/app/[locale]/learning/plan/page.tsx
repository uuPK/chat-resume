'use client'

import { useEffect, useState } from 'react'
import MainNavigation from '@/components/layout/MainNavigation'
import CandidateSidebar from '@/components/layout/CandidateSidebar'
import { learningApi, type AICourse } from '@/lib/api'
import { DocumentTextIcon } from '@heroicons/react/24/outline'

export default function LearningPlan() {
  const [courses, setCourses] = useState<AICourse[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchPlan()
  }, [])

  const fetchPlan = async () => {
    try {
      const data = await learningApi.getLearningPlan()
      setCourses(data)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="flex h-screen flex-col bg-gray-50 dark:bg-gray-900">
      <MainNavigation />
      
      <div className="flex flex-1 overflow-hidden">
        <CandidateSidebar hasResumes={true} firstResumeId={1} />

        <main className="flex-1 overflow-y-auto p-8">
          <div className="max-w-5xl mx-auto">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">我的学习计划</h1>
            
            {loading ? (
              <div className="animate-pulse space-y-4">
                {[1, 2].map(i => (
                  <div key={i} className="h-40 bg-gray-200 dark:bg-gray-800 rounded-xl" />
                ))}
              </div>
            ) : courses.length === 0 ? (
              <div className="text-center py-16 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
                <DocumentTextIcon className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                <h3 className="text-lg font-medium text-gray-900 dark:text-white mb-2">计划空空如也</h3>
                <p className="text-gray-500 mb-6">您还没有加入任何课程到学习计划中。</p>
                <a
                  href="/learning/courses"
                  className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-700 text-white font-medium rounded-lg transition-colors"
                >
                  去选课大厅看看
                </a>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-6">
                {courses.map(course => {
                  let parsedOutline: any = null;
                  try {
                    parsedOutline = course.outline ? JSON.parse(course.outline) : null;
                  } catch (e) {}

                  return (
                    <div key={course.id} className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-l-4 border-indigo-500 dark:border-gray-700 dark:border-l-indigo-500">
                      <div className="flex items-start justify-between">
                        <div>
                          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">{course.title}</h2>
                          <p className="text-sm text-gray-500 max-w-2xl">{course.description}</p>
                          <div className="mt-3 flex items-center gap-2">
                            <span className="px-2 py-0.5 bg-green-50 text-green-700 dark:bg-green-900/30 dark:text-green-400 text-xs rounded border border-green-200 dark:border-green-800">
                              学习中
                            </span>
                            {course.target_skills && course.target_skills.split(',').map(s => (
                              <span key={s} className="px-2 py-0.5 bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400 text-xs rounded">
                                {s.trim()}
                              </span>
                            ))}
                          </div>
                        </div>
                        
                        <button className="px-5 py-2.5 bg-indigo-50 text-indigo-700 hover:bg-indigo-100 dark:bg-indigo-900/30 dark:text-indigo-400 dark:hover:bg-indigo-900/50 text-sm font-medium rounded-lg transition-colors border border-indigo-200 dark:border-indigo-800">
                          继续学习
                        </button>
                      </div>

                      {parsedOutline && parsedOutline.weeks && (
                        <div className="mt-6 pt-6 border-t border-gray-100 dark:border-gray-700">
                          <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">学习进度概览</h3>
                          <div className="space-y-4">
                            {parsedOutline.weeks.map((week: any, idx: number) => (
                              <div key={idx} className="bg-gray-50 dark:bg-gray-700/30 rounded-lg p-4">
                                <div className="text-xs font-bold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">
                                  Week {week.week_number}
                                </div>
                                <h4 className="text-md font-medium text-gray-900 dark:text-white mt-1">{week.theme}</h4>
                                <div className="mt-3 space-y-2">
                                  {week.tasks.map((task: any, tIdx: number) => (
                                    <div key={tIdx} className="text-sm bg-white dark:bg-gray-800 p-3 rounded border border-gray-200 dark:border-gray-600 flex items-start gap-3">
                                      <input type="checkbox" className="mt-1 rounded border-gray-300 text-indigo-600 focus:ring-indigo-600" />
                                      <div>
                                        <span className="font-medium text-gray-900 dark:text-gray-200">{task.name}: </span>
                                        <span className="text-gray-500 dark:text-gray-400">{task.description}</span>
                                      </div>
                                    </div>
                                  ))}
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
