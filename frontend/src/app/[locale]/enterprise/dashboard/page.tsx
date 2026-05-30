'use client'

import { useEffect, useState } from 'react'
import { motion } from 'framer-motion'
import { useAuth } from '@/lib/auth'
import { enterpriseApi, type EnterpriseJob, type JobDeliveryDetails } from '@/lib/api'
import MainNavigation from '@/components/layout/MainNavigation'
import { Link } from '@/i18n/navigation'
import {
  InboxArrowDownIcon,
  BriefcaseIcon,
  PlusIcon,
  CheckBadgeIcon,
  ClockIcon,
  FireIcon
} from '@heroicons/react/24/outline'

export default function EnterpriseDashboard() {
  const { user, isAuthenticated, isLoading } = useAuth()
  const [activeTab, setActiveTab] = useState<'inbox' | 'jobs'>('inbox')
  
  const [jobs, setJobs] = useState<EnterpriseJob[]>([])
  const [deliveries, setDeliveries] = useState<JobDeliveryDetails[]>([])
  const [dataLoading, setDataLoading] = useState(true)

  const [isCreateModalOpen, setIsCreateModalOpen] = useState(false)
  const [newJob, setNewJob] = useState({
    title: '',
    description: '',
    skills_required: '',
    location: '',
    salary_range: ''
  })
  const [isCreating, setIsCreating] = useState(false)

  const handleCreateJob = async () => {
    if (!newJob.title || !newJob.description) return
    setIsCreating(true)
    try {
      const skills = newJob.skills_required.split(',').map(s => s.trim()).filter(Boolean)
      const created = await enterpriseApi.createJob({
        ...newJob,
        skills_required: skills,
        is_active: true
      })
      setJobs([created, ...jobs])
      setIsCreateModalOpen(false)
      setNewJob({ title: '', description: '', skills_required: '', location: '', salary_range: '' })
      setActiveTab('jobs')
    } catch (err) {
      console.error(err)
      alert('发布失败，请重试')
    } finally {
      setIsCreating(false)
    }
  }

  useEffect(() => {
    if (isAuthenticated) {
      Promise.all([
        enterpriseApi.getMyJobs(),
        enterpriseApi.getInbox()
      ]).then(([jobsData, deliveriesData]) => {
        setJobs(jobsData)
        setDeliveries(deliveriesData)
        setDataLoading(false)
      }).catch(() => {
        setDataLoading(false)
      })
    }
  }, [isAuthenticated])

  if (isLoading || dataLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-[#0a0a0a]">
        <div className="w-8 h-8 rounded-full border-2 border-transparent animate-spin border-t-primary-600 border-r-primary-600" />
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50 dark:bg-[#0a0a0a]">
      <MainNavigation />
      
      <main className="max-w-7xl mx-auto px-6 py-8 md:py-12">
        {/* Header */}
        <div className="flex flex-col md:flex-row md:items-center justify-between mb-8 gap-4">
          <div>
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white">企业端工作台</h1>
            <p className="text-gray-500 mt-1">您好，{user?.full_name}（企业代表）。欢迎来到招聘管理中心。</p>
          </div>
          <button 
            onClick={() => setIsCreateModalOpen(true)}
            className="btn-primary inline-flex items-center gap-2"
          >
            <PlusIcon className="w-5 h-5" />
            发布新职位
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-8 border-b border-gray-200 dark:border-gray-800 mb-8">
          <button
            onClick={() => setActiveTab('inbox')}
            className={`pb-4 text-sm font-medium transition-colors relative ${activeTab === 'inbox' ? 'text-primary-600' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'}`}
          >
            <div className="flex items-center gap-2">
              <InboxArrowDownIcon className="w-5 h-5" />
              收件箱
              {deliveries.length > 0 && (
                <span className="bg-red-500 text-white text-[10px] px-2 py-0.5 rounded-full">{deliveries.length}</span>
              )}
            </div>
            {activeTab === 'inbox' && (
              <motion.div layoutId="activeTab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary-600" />
            )}
          </button>
          
          <button
            onClick={() => setActiveTab('jobs')}
            className={`pb-4 text-sm font-medium transition-colors relative ${activeTab === 'jobs' ? 'text-primary-600' : 'text-gray-500 hover:text-gray-700 dark:hover:text-gray-300'}`}
          >
            <div className="flex items-center gap-2">
              <BriefcaseIcon className="w-5 h-5" />
              岗位管理
            </div>
            {activeTab === 'jobs' && (
              <motion.div layoutId="activeTab" className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary-600" />
            )}
          </button>
        </div>

        {/* Content */}
        {activeTab === 'inbox' && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
            {deliveries.length === 0 ? (
              <div className="text-center py-20 bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800">
                <InboxArrowDownIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 dark:text-white">收件箱空空如也</h3>
                <p className="text-gray-500 mt-2">暂未收到新的求职者投递。</p>
              </div>
            ) : (
              deliveries.map(delivery => (
                <Link key={delivery.id} href={`/enterprise/resume/${delivery.id}`} className="block">
                  <div className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-6 hover:shadow-md transition-shadow group">
                    <div className="flex items-start justify-between">
                      <div className="flex items-center gap-4">
                        <div className="w-12 h-12 rounded-full bg-primary-50 dark:bg-primary-900/20 text-primary-600 dark:text-primary-400 flex items-center justify-center text-xl font-bold">
                          {delivery.candidate_name.charAt(0)}
                        </div>
                        <div>
                          <h3 className="text-lg font-bold text-gray-900 dark:text-white group-hover:text-primary-600 transition-colors">
                            {delivery.candidate_name} <span className="text-gray-400 font-normal text-sm ml-2">投递了</span> {delivery.job_title}
                          </h3>
                          <div className="flex items-center gap-4 mt-2 text-sm text-gray-500">
                            <span className="flex items-center gap-1">
                              <DocumentTextIcon className="w-4 h-4" /> {delivery.resume_title}
                            </span>
                            <span className="flex items-center gap-1">
                              <ClockIcon className="w-4 h-4" /> {new Date(delivery.created_at).toLocaleDateString()}
                            </span>
                          </div>
                        </div>
                      </div>
                      <div className="text-right">
                        {delivery.match_score ? (
                          <div className="flex flex-col items-end">
                            <span className="flex items-center gap-1 text-sm font-medium text-orange-500 bg-orange-50 px-2 py-1 rounded-md">
                              <FireIcon className="w-4 h-4" /> AI契合度 {delivery.match_score}%
                            </span>
                          </div>
                        ) : (
                          <span className="text-sm text-gray-400">未进行 AI 筛查</span>
                        )}
                      </div>
                    </div>
                  </div>
                </Link>
              ))
            )}
          </motion.div>
        )}

        {activeTab === 'jobs' && (
          <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="space-y-4">
            {jobs.length === 0 ? (
              <div className="text-center py-20 bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800">
                <BriefcaseIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
                <h3 className="text-lg font-medium text-gray-900 dark:text-white">暂无发布的岗位</h3>
                <p className="text-gray-500 mt-2">快去发布您的第一个招聘岗位，吸引优秀人才吧。</p>
              </div>
            ) : (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {jobs.map(job => (
                  <div key={job.id} className="bg-white dark:bg-gray-900 border border-gray-200 dark:border-gray-800 rounded-2xl p-6">
                    <div className="flex justify-between items-start mb-4">
                      <h3 className="text-xl font-bold text-gray-900 dark:text-white">{job.title}</h3>
                      {job.is_active ? (
                        <span className="flex items-center gap-1 text-xs font-medium text-emerald-600 bg-emerald-50 px-2 py-1 rounded-md">
                          <CheckBadgeIcon className="w-4 h-4" /> 招聘中
                        </span>
                      ) : (
                        <span className="text-xs font-medium text-gray-500 bg-gray-100 px-2 py-1 rounded-md">已关闭</span>
                      )}
                    </div>
                    <p className="text-gray-600 dark:text-gray-400 text-sm line-clamp-2 mb-4">{job.description}</p>
                    <div className="flex flex-wrap gap-2 mb-4">
                      {job.skills_required.map(skill => (
                        <span key={skill} className="text-xs bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 px-2 py-1 rounded-md">
                          {skill}
                        </span>
                      ))}
                    </div>
                    <div className="flex justify-between items-center text-sm text-gray-500 pt-4 border-t border-gray-100 dark:border-gray-800">
                      <span>{job.location || '不限地点'} · {job.salary_range || '薪资面议'}</span>
                      <span>发布于 {new Date(job.created_at).toLocaleDateString()}</span>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </motion.div>
        )}

        {/* Create Job Modal */}
        {isCreateModalOpen && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-gray-900/50 backdrop-blur-sm overflow-y-auto">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              className="bg-white dark:bg-gray-900 rounded-2xl shadow-xl w-full max-w-2xl overflow-hidden my-8"
            >
              <div className="p-6 border-b border-gray-100 dark:border-gray-800">
                <h3 className="text-xl font-bold text-gray-900 dark:text-white">发布新职位</h3>
              </div>
              <div className="p-6 space-y-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">职位名称 *</label>
                  <input
                    type="text"
                    value={newJob.title}
                    onChange={e => setNewJob({ ...newJob, title: e.target.value })}
                    className="w-full rounded-lg border-gray-300 dark:border-gray-700 dark:bg-gray-800 dark:text-white shadow-sm focus:border-primary-500 focus:ring-primary-500"
                    placeholder="例如：高级前端工程师"
                  />
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">技能要求（逗号分隔）</label>
                  <input
                    type="text"
                    value={newJob.skills_required}
                    onChange={e => setNewJob({ ...newJob, skills_required: e.target.value })}
                    className="w-full rounded-lg border-gray-300 dark:border-gray-700 dark:bg-gray-800 dark:text-white shadow-sm focus:border-primary-500 focus:ring-primary-500"
                    placeholder="例如：React, TypeScript, Next.js"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">工作地点</label>
                    <input
                      type="text"
                      value={newJob.location}
                      onChange={e => setNewJob({ ...newJob, location: e.target.value })}
                      className="w-full rounded-lg border-gray-300 dark:border-gray-700 dark:bg-gray-800 dark:text-white shadow-sm focus:border-primary-500 focus:ring-primary-500"
                      placeholder="例如：北京 / 远程"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">薪资范围</label>
                    <input
                      type="text"
                      value={newJob.salary_range}
                      onChange={e => setNewJob({ ...newJob, salary_range: e.target.value })}
                      className="w-full rounded-lg border-gray-300 dark:border-gray-700 dark:bg-gray-800 dark:text-white shadow-sm focus:border-primary-500 focus:ring-primary-500"
                      placeholder="例如：20k-40k"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1">职位描述 *</label>
                  <textarea
                    rows={6}
                    value={newJob.description}
                    onChange={e => setNewJob({ ...newJob, description: e.target.value })}
                    className="w-full rounded-lg border-gray-300 dark:border-gray-700 dark:bg-gray-800 dark:text-white shadow-sm focus:border-primary-500 focus:ring-primary-500"
                    placeholder="请详细描述该职位的工作职责和任职要求..."
                  />
                </div>
              </div>
              <div className="p-6 border-t border-gray-100 dark:border-gray-800 flex justify-end gap-3 bg-gray-50 dark:bg-gray-800/50">
                <button
                  onClick={() => setIsCreateModalOpen(false)}
                  className="px-4 py-2 text-sm font-medium text-gray-700 dark:text-gray-300 hover:text-gray-900 dark:hover:text-white"
                  disabled={isCreating}
                >
                  取消
                </button>
                <button
                  onClick={handleCreateJob}
                  disabled={!newJob.title || !newJob.description || isCreating}
                  className="btn-primary"
                >
                  {isCreating ? '发布中...' : '确认发布'}
                </button>
              </div>
            </motion.div>
          </div>
        )}
      </main>
    </div>
  )
}

function DocumentTextIcon(props: React.ComponentProps<'svg'>) {
  return (
    <svg fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor" {...props}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z" />
    </svg>
  )
}
