'use client'

import { useEffect, useState } from 'react'
import MainNavigation from '@/components/layout/MainNavigation'
import SchoolSidebar from '@/components/layout/SchoolSidebar'
import { schoolApi } from '@/lib/api'
import { ChartBarIcon, LightBulbIcon } from '@heroicons/react/24/outline'

export default function SchoolDashboard() {
  const [gaps, setGaps] = useState<{ top_missing_skills: string[], analysis: string } | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    schoolApi.getMarketGaps().then((data) => {
      setGaps(data)
    }).finally(() => {
      setLoading(false)
    })
  }, [])

  return (
    <div className="flex h-screen flex-col bg-gray-50 dark:bg-gray-900">
      <MainNavigation />
      
      <div className="flex flex-1 overflow-hidden">
        {/* Sidebar */}
        <aside className="w-64 border-r border-gray-200 bg-white dark:border-gray-800 dark:bg-gray-900 hidden md:block">
          <SchoolSidebar />
        </aside>

        {/* Main Content */}
        <main className="flex-1 overflow-y-auto p-8">
          <div className="max-w-4xl mx-auto">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-6">人才供需看板</h1>
            
            {loading ? (
              <div className="space-y-4">
                <div className="flex items-center justify-center p-8 bg-blue-50/50 dark:bg-blue-900/10 rounded-xl border border-blue-100 dark:border-blue-900">
                  <div className="flex flex-col items-center gap-3">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
                    <p className="text-blue-600 dark:text-blue-400 font-medium">正在使用大模型深度分析市场数据...</p>
                  </div>
                </div>
                <div className="animate-pulse space-y-4">
                  <div className="h-40 bg-gray-200 dark:bg-gray-800 rounded-xl"></div>
                  <div className="h-64 bg-gray-200 dark:bg-gray-800 rounded-xl"></div>
                </div>
              </div>
            ) : gaps ? (
              <div className="space-y-6">
                {/* 技能缺口列表 */}
                <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
                  <div className="flex items-center gap-2 mb-4">
                    <ChartBarIcon className="w-6 h-6 text-blue-500" />
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">市场急缺技能 Top 5</h2>
                  </div>
                  <div className="flex flex-wrap gap-3">
                    {gaps.top_missing_skills.map((skill, idx) => (
                      <div key={idx} className="px-4 py-2 bg-blue-50 dark:bg-blue-900/30 text-blue-700 dark:text-blue-300 rounded-lg text-sm font-medium border border-blue-100 dark:border-blue-800">
                        {skill}
                      </div>
                    ))}
                  </div>
                </div>

                {/* 深入分析 */}
                <div className="bg-gradient-to-br from-indigo-50 to-purple-50 dark:from-indigo-900/20 dark:to-purple-900/20 rounded-xl shadow-sm border border-indigo-100 dark:border-indigo-800/50 p-6">
                  <div className="flex items-center gap-2 mb-3">
                    <LightBulbIcon className="w-6 h-6 text-indigo-500" />
                    <h2 className="text-lg font-semibold text-gray-900 dark:text-white">AI 分析报告</h2>
                  </div>
                  <p className="text-gray-700 dark:text-gray-300 leading-relaxed">
                    {gaps.analysis}
                  </p>
                </div>
              </div>
            ) : null}
          </div>
        </main>
      </div>
    </div>
  )
}
