'use client'

import { useEffect, useState } from 'react'
import MainNavigation from '@/components/layout/MainNavigation'
import CandidateSidebar from '@/components/layout/CandidateSidebar'
import { learningApi, type AICourse } from '@/lib/api'
import toast from 'react-hot-toast'
import { AcademicCapIcon } from '@heroicons/react/24/outline'

export default function LearningCourses() {
  const [courses, setCourses] = useState<AICourse[]>([])
  const [loading, setLoading] = useState(true)
  const [enrollingId, setEnrollingId] = useState<number | null>(null)

  useEffect(() => {
    fetchCourses()
  }, [])

  const fetchCourses = async () => {
    try {
      const data = await learningApi.getCourses()
      setCourses(data)
    } finally {
      setLoading(false)
    }
  }

  const handleEnroll = async (id: number) => {
    setEnrollingId(id)
    try {
      await learningApi.enrollCourse(id)
      toast.success('已加入学习计划！')
    } catch {
      toast.error('加入失败，您可能已经加入过该课程')
    } finally {
      setEnrollingId(null)
    }
  }

  return (
    <div className="flex h-screen flex-col bg-gray-50 dark:bg-gray-900">
      <MainNavigation />
      
      <div className="flex flex-1 overflow-hidden">
        <CandidateSidebar hasResumes={true} firstResumeId={1} />

        <main className="flex-1 overflow-y-auto p-8">
          <div className="max-w-5xl mx-auto">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">选课大厅</h1>
            <p className="text-gray-500 mb-8">在这里发现由高校提供的优质实战课程，加入您的个人学习计划。</p>
            
            {loading ? (
              <div className="animate-pulse space-y-4">
                {[1, 2, 3].map(i => (
                  <div key={i} className="h-32 bg-gray-200 dark:bg-gray-800 rounded-xl" />
                ))}
              </div>
            ) : courses.length === 0 ? (
              <div className="text-center py-12 bg-white dark:bg-gray-800 rounded-xl border border-gray-200 dark:border-gray-700">
                <AcademicCapIcon className="w-12 h-12 text-gray-400 mx-auto mb-3" />
                <p className="text-gray-500">目前暂无开放课程</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 gap-6">
                {courses.map(course => {
                  let parsedOutline: any = null;
                  try {
                    parsedOutline = course.outline ? JSON.parse(course.outline) : null;
                  } catch (e) {}

                  return (
                    <div key={course.id} className="bg-white dark:bg-gray-800 rounded-xl p-6 shadow-sm border border-gray-200 dark:border-gray-700">
                      <div className="flex items-start justify-between">
                        <div>
                          <h2 className="text-xl font-semibold text-gray-900 dark:text-white mb-2">{course.title}</h2>
                          <p className="text-sm text-gray-500 max-w-2xl">{course.description}</p>
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
                        
                        <button
                          onClick={() => handleEnroll(course.id)}
                          disabled={enrollingId === course.id}
                          className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white text-sm font-medium rounded-lg transition-colors disabled:opacity-50"
                        >
                          {enrollingId === course.id ? '加入中...' : '加入学习计划'}
                        </button>
                      </div>

                      {parsedOutline && parsedOutline.weeks && (
                        <div className="mt-6 pt-6 border-t border-gray-100 dark:border-gray-700">
                          <h3 className="text-sm font-semibold text-gray-900 dark:text-white mb-4">课程大纲</h3>
                          <div className="space-y-4">
                            {parsedOutline.weeks.map((week: any, idx: number) => (
                              <div key={idx} className="bg-gray-50 dark:bg-gray-700/30 rounded-lg p-4">
                                <div className="text-xs font-bold text-indigo-600 dark:text-indigo-400 uppercase tracking-wider">
                                  Week {week.week_number}
                                </div>
                                <h4 className="text-md font-medium text-gray-900 dark:text-white mt-1">{week.theme}</h4>
                                <div className="mt-3 space-y-2">
                                  {week.tasks.map((task: any, tIdx: number) => (
                                    <div key={tIdx} className="text-sm bg-white dark:bg-gray-800 p-3 rounded border border-gray-200 dark:border-gray-600">
                                      <span className="font-medium text-gray-900 dark:text-gray-200">{task.name}: </span>
                                      <span className="text-gray-500 dark:text-gray-400">{task.description}</span>
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
