'use client'

import MainNavigation from '@/components/layout/MainNavigation'

export default function SchoolDashboard() {
  return (
    <div className="min-h-screen bg-emerald-50">
      <MainNavigation />
      <div className="max-w-7xl mx-auto px-6 py-12">
        <h1 className="text-3xl font-bold text-gray-900 mb-4">高校教研工作台 (School Dashboard)</h1>
        <p className="text-gray-600">这里将展示市场技能缺口分析，以及 AI 自动生成的教研大纲和课程。</p>
      </div>
    </div>
  )
}
