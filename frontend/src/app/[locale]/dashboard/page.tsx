'use client'

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useTranslations } from 'next-intl'
import { useAuth } from '@/lib/auth'
import { resumeApi, type Resume } from '@/lib/api'
import MainNavigation from '@/components/layout/MainNavigation'
import CandidateSidebar from '@/components/layout/CandidateSidebar'
import { Link } from '@/i18n/navigation'
import {
  DocumentTextIcon,
  ChatBubbleLeftRightIcon,
  SparklesIcon,
  BriefcaseIcon,
  BoltIcon,
  ArrowRightIcon,
} from '@heroicons/react/24/solid'

export default function DashboardPage() {
  const t = useTranslations('common')
  const { user, isAuthenticated, isLoading } = useAuth()
  const [resumes, setResumes] = useState<Resume[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (isAuthenticated) {
      resumeApi.getResumes().then(data => {
        setResumes(data)
        setLoading(false)
      }).catch(() => {
        setLoading(false)
      })
    }
  }, [isAuthenticated])

  if (isLoading || loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-[#0a0a0a]">
        <div className="w-8 h-8 rounded-full border-2 border-transparent animate-spin border-t-primary-600 border-r-primary-600" />
      </div>
    )
  }

  const hasResumes = resumes.length > 0
  const firstResumeId = resumes[0]?.id

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-[#0a0a0a]">
      <MainNavigation />
      
      <div className="flex min-h-[calc(100vh-56px)]">
        <CandidateSidebar hasResumes={hasResumes} firstResumeId={firstResumeId} />
        
        <main className="flex-1 overflow-y-auto px-6 py-8 md:px-10 md:py-10">
          <div className="max-w-5xl mx-auto space-y-8">
            
            {/* Welcome Banner */}
            <motion.div 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="bg-gradient-to-r from-primary-600 to-indigo-600 rounded-3xl p-8 text-white shadow-lg relative overflow-hidden"
            >
              <div className="absolute top-0 right-0 -mt-16 -mr-16 text-white/10">
                <SparklesIcon className="w-64 h-64" />
              </div>
              <div className="relative z-10">
                <h1 className="text-3xl md:text-4xl font-bold mb-2">
                  欢迎回来，{user?.full_name || '探索者'}！
                </h1>
                <p className="text-primary-100 text-lg max-w-xl">
                  {hasResumes 
                    ? "你的简历正在闪闪发光，继续完善它，或者开始一场模拟面试吧！" 
                    : "你还没有创建简历哦，千里之行始于足下，现在就开始打造你的金牌简历吧！"}
                </p>
                <div className="mt-8 flex gap-4">
                  {hasResumes ? (
                    <Link href={`/resume/${firstResumeId}/edit`} className="bg-white text-primary-600 px-6 py-3 rounded-xl font-semibold hover:bg-primary-50 transition-colors shadow-sm flex items-center gap-2">
                      <SparklesIcon className="w-5 h-5" />
                      继续优化简历
                    </Link>
                  ) : (
                    <Link href="/resumes" className="bg-white text-primary-600 px-6 py-3 rounded-xl font-semibold hover:bg-primary-50 transition-colors shadow-sm flex items-center gap-2">
                      <DocumentTextIcon className="w-5 h-5" />
                      创建第一份简历
                    </Link>
                  )}
                </div>
              </div>
            </motion.div>

            {/* Quick Stats & Actions */}
            <motion.div 
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.1 }}
              className="grid grid-cols-1 md:grid-cols-3 gap-4"
            >
              {/* Stat Card 1 */}
              <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex justify-between items-start mb-4">
                  <div className="p-3 bg-blue-50 dark:bg-blue-900/20 text-blue-600 dark:text-blue-400 rounded-xl">
                    <DocumentTextIcon className="w-6 h-6" />
                  </div>
                </div>
                <h3 className="text-gray-500 dark:text-gray-400 text-sm font-medium">我的简历</h3>
                <div className="text-3xl font-bold text-gray-900 dark:text-white mt-1">{resumes.length} <span className="text-sm font-normal text-gray-400">份</span></div>
                <Link href="/resumes" className="mt-4 text-sm text-blue-600 dark:text-blue-400 font-medium flex items-center gap-1 hover:gap-2 transition-all">
                  管理简历 <ArrowRightIcon className="w-3 h-3" />
                </Link>
              </div>

              {/* Stat Card 2 */}
              <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex justify-between items-start mb-4">
                  <div className="p-3 bg-purple-50 dark:bg-purple-900/20 text-purple-600 dark:text-purple-400 rounded-xl">
                    <ChatBubbleLeftRightIcon className="w-6 h-6" />
                  </div>
                </div>
                <h3 className="text-gray-500 dark:text-gray-400 text-sm font-medium">模拟面试</h3>
                <div className="text-3xl font-bold text-gray-900 dark:text-white mt-1">AI <span className="text-sm font-normal text-gray-400">陪练</span></div>
                <Link href="/interviews" className="mt-4 text-sm text-purple-600 dark:text-purple-400 font-medium flex items-center gap-1 hover:gap-2 transition-all">
                  开始面试 <ArrowRightIcon className="w-3 h-3" />
                </Link>
              </div>

              {/* Stat Card 3 */}
              <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-6 shadow-sm hover:shadow-md transition-shadow">
                <div className="flex justify-between items-start mb-4">
                  <div className="p-3 bg-emerald-50 dark:bg-emerald-900/20 text-emerald-600 dark:text-emerald-400 rounded-xl">
                    <BriefcaseIcon className="w-6 h-6" />
                  </div>
                </div>
                <h3 className="text-gray-500 dark:text-gray-400 text-sm font-medium">目标岗位</h3>
                <div className="text-3xl font-bold text-gray-900 dark:text-white mt-1">
                  {hasResumes && resumes[0]?.target_title ? "已设定" : "未设定"}
                </div>
                <Link href={hasResumes ? `/resume/${firstResumeId}/jobs` : '/resumes'} className="mt-4 text-sm text-emerald-600 dark:text-emerald-400 font-medium flex items-center gap-1 hover:gap-2 transition-all">
                  探索机会 <ArrowRightIcon className="w-3 h-3" />
                </Link>
              </div>
            </motion.div>

            {/* Recent Resumes */}
            {hasResumes && (
              <motion.div 
                initial={{ opacity: 0, y: 10 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ delay: 0.2 }}
              >
                <div className="flex items-center justify-between mb-4">
                  <h2 className="text-lg font-bold text-gray-900 dark:text-white flex items-center gap-2">
                    <BoltIcon className="w-5 h-5 text-amber-500" />
                    最近的简历
                  </h2>
                  <Link href="/resumes" className="text-sm text-gray-500 hover:text-primary-600 transition-colors">
                    查看全部
                  </Link>
                </div>
                
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  {resumes.slice(0, 2).map((resume) => (
                    <Link 
                      key={resume.id} 
                      href={`/resume/${resume.id}/edit`}
                      className="group flex flex-col p-5 bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl hover:border-primary-500 dark:hover:border-primary-500 transition-all hover:shadow-md"
                    >
                      <h3 className="font-semibold text-gray-900 dark:text-white group-hover:text-primary-600 transition-colors">
                        {resume.title || '未命名简历'}
                      </h3>
                      <p className="text-sm text-gray-500 dark:text-gray-400 mt-1">
                        {resume.target_title ? `目标: ${resume.target_title}` : '未设定目标岗位'}
                      </p>
                      <div className="mt-4 pt-4 border-t border-gray-100 dark:border-gray-800 flex justify-between items-center text-sm">
                        <span className="text-gray-400">{new Date(resume.created_at).toLocaleDateString()}</span>
                        <span className="text-primary-600 font-medium opacity-0 -translate-x-2 group-hover:opacity-100 group-hover:translate-x-0 transition-all flex items-center gap-1">
                          继续编辑 <ArrowRightIcon className="w-3 h-3" />
                        </span>
                      </div>
                    </Link>
                  ))}
                </div>
              </motion.div>
            )}
            
          </div>
        </main>
      </div>
    </div>
  )
}
