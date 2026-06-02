'use client'

import { useState } from 'react'
import MainNavigation from '@/components/layout/MainNavigation'
import SchoolSidebar from '@/components/layout/SchoolSidebar'
import { schoolApi, type AICourse } from '@/lib/api'
import { PlusIcon, SparklesIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'
import { useRouter } from '@/i18n/navigation'

export default function NewCurriculum() {
  const [skills, setSkills] = useState('')
  const [generating, setGenerating] = useState(false)
  const router = useRouter()

  const handleGenerate = async () => {
    if (!skills.trim()) {
      toast.error('请输入至少一个技能名称')
      return
    }

    setGenerating(true)
    try {
      const targetSkills = skills.split(',').map(s => s.trim()).filter(Boolean)
      const course = await schoolApi.generateCourse(targetSkills)
      toast.success('大纲生成成功！')
      router.push('/school/courses') // 跳转到课程列表
    } catch (err) {
      toast.error('生成失败，请重试')
    } finally {
      setGenerating(false)
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
          <div className="max-w-3xl mx-auto">
            <h1 className="text-2xl font-bold text-gray-900 dark:text-white mb-2">智能教研工作台</h1>
            <p className="text-gray-500 mb-8">输入缺口的技能点，AI 将自动生成教学大纲与课程安排。</p>
            
            <div className="bg-white dark:bg-gray-800 rounded-xl shadow-sm border border-gray-200 dark:border-gray-700 p-6">
              <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-2">
                目标技能 (用逗号分隔)
              </label>
              <input
                type="text"
                className="w-full px-4 py-2 border border-gray-300 dark:border-gray-600 rounded-lg focus:ring-2 focus:ring-primary-500 dark:bg-gray-700 dark:text-white mb-6"
                placeholder="例如: Agent Orchestration, RAG, Next.js"
                value={skills}
                onChange={(e) => setSkills(e.target.value)}
              />

              <div className="flex justify-end">
                <button
                  onClick={handleGenerate}
                  disabled={generating}
                  className="flex items-center gap-2 px-6 py-2 bg-primary-600 hover:bg-primary-700 text-white rounded-lg font-medium transition-colors disabled:opacity-50"
                >
                  {generating ? (
                    <div className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                  ) : (
                    <SparklesIcon className="w-5 h-5" />
                  )}
                  {generating ? '正在生成...' : '开始生成课程大纲'}
                </button>
              </div>
            </div>
          </div>
        </main>
      </div>
    </div>
  )
}
