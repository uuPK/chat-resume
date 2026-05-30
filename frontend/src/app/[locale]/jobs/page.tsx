'use client'

import { useEffect, useState } from 'react'
// Force Turbopack to re-evaluate this module
import { enterpriseApi, type EnterpriseJob, resumeApi, type ResumeListItem } from '@/lib/api'
import { BriefcaseIcon, BuildingOfficeIcon, CurrencyDollarIcon, MapPinIcon } from '@heroicons/react/24/outline'
import CandidateSidebar from '@/components/layout/CandidateSidebar'
import { motion, AnimatePresence } from 'framer-motion'

export default function JobBoard() {
  const [jobs, setJobs] = useState<EnterpriseJob[]>([])
  const [resumes, setResumes] = useState<ResumeListItem[]>([])
  const [isLoading, setIsLoading] = useState(true)
  
  const [selectedJob, setSelectedJob] = useState<EnterpriseJob | null>(null)
  const [selectedResumeId, setSelectedResumeId] = useState<number | null>(null)
  const [isDelivering, setIsDelivering] = useState(false)
  const [deliverSuccess, setDeliverSuccess] = useState(false)
  const [deliverError, setDeliverError] = useState('')

  useEffect(() => {
    Promise.all([
      enterpriseApi.getAllActiveJobs(),
      resumeApi.getResumes()
    ]).then(([jobsData, resumesData]) => {
      setJobs(jobsData)
      setResumes(resumesData)
      setIsLoading(false)
    }).catch(err => {
      console.error(err)
      setIsLoading(false)
    })
  }, [])

  const handleDeliver = async () => {
    if (!selectedJob || !selectedResumeId) return
    setIsDelivering(true)
    setDeliverError('')
    try {
      await enterpriseApi.deliverResume(selectedJob.id, selectedResumeId)
      setDeliverSuccess(true)
      setTimeout(() => {
        setDeliverSuccess(false)
        setSelectedJob(null)
      }, 2000)
    } catch (err: any) {
      setDeliverError(err.message || '投递失败')
    } finally {
      setIsDelivering(false)
    }
  }

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-[#0a0a0a]">
      <CandidateSidebar />
      <main className="flex-1 overflow-y-auto p-8">
        <div className="max-w-5xl mx-auto">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <BriefcaseIcon className="w-8 h-8 text-primary-600" />
              发现机会
            </h1>
            <p className="text-gray-500 mt-2">浏览企业发布的最新岗位，一键投递您的专属简历。</p>
          </div>

          {isLoading ? (
            <div className="flex justify-center py-20">
              <div className="w-8 h-8 rounded-full border-2 border-transparent animate-spin border-t-primary-600 border-r-primary-600" />
            </div>
          ) : jobs.length === 0 ? (
            <div className="text-center py-20 bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800">
              <BuildingOfficeIcon className="w-16 h-16 text-gray-300 mx-auto mb-4" />
              <h3 className="text-lg font-medium text-gray-900 dark:text-white">暂无开放岗位</h3>
              <p className="text-gray-500 mt-2">企业暂时还没有发布新的招聘需求。</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              {jobs.map(job => (
                <div key={job.id} className="bg-white dark:bg-gray-900 rounded-2xl p-6 border border-gray-200 dark:border-gray-800 hover:shadow-lg transition-all group">
                  <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2 group-hover:text-primary-600 transition-colors">
                    {job.title}
                  </h3>
                  <div className="flex flex-wrap items-center gap-4 text-sm text-gray-600 dark:text-gray-400 mb-4">
                    <span className="flex items-center gap-1">
                      <MapPinIcon className="w-4 h-4" /> {job.location || '不限地点'}
                    </span>
                    <span className="flex items-center gap-1 text-orange-600 dark:text-orange-400 font-medium">
                      <CurrencyDollarIcon className="w-4 h-4" /> {job.salary_range || '面议'}
                    </span>
                  </div>
                  <p className="text-gray-600 dark:text-gray-400 text-sm line-clamp-3 mb-4">
                    {job.description}
                  </p>
                  <div className="flex flex-wrap gap-2 mb-6">
                    {job.skills_required.map(skill => (
                      <span key={skill} className="px-2 py-1 bg-gray-100 dark:bg-gray-800 text-gray-600 dark:text-gray-300 rounded text-xs">
                        {skill}
                      </span>
                    ))}
                  </div>
                  <button
                    onClick={() => setSelectedJob(job)}
                    className="w-full btn-primary py-2"
                  >
                    投递简历
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>

      {/* 投递弹窗 */}
      <AnimatePresence>
        {selectedJob && (
          <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-gray-900/50 backdrop-blur-sm">
            <motion.div
              initial={{ opacity: 0, scale: 0.95 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.95 }}
              className="bg-white dark:bg-gray-900 rounded-2xl shadow-xl w-full max-w-md overflow-hidden"
            >
              <div className="p-6">
                <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                  投递简历至 {selectedJob.title}
                </h3>
                <p className="text-sm text-gray-500 mb-6">请选择一份您已创建的简历进行投递。企业将通过 AI 对您的简历进行匹配分析。</p>
                
                <div className="space-y-3 mb-6 max-h-[300px] overflow-y-auto">
                  {resumes.length === 0 ? (
                    <p className="text-center text-sm text-gray-500 py-4">您还没有简历，请先去创建简历。</p>
                  ) : (
                    resumes.map(resume => (
                      <label
                        key={resume.id}
                        className={`block p-4 rounded-xl border-2 cursor-pointer transition-colors ${
                          selectedResumeId === resume.id
                            ? 'border-primary-600 bg-primary-50 dark:bg-primary-900/20'
                            : 'border-gray-200 dark:border-gray-700 hover:border-primary-300'
                        }`}
                      >
                        <div className="flex items-center justify-between">
                          <span className="font-medium text-gray-900 dark:text-white">{resume.title || '未命名简历'}</span>
                          <input
                            type="radio"
                            name="resume"
                            className="w-4 h-4 text-primary-600 border-gray-300 focus:ring-primary-600"
                            checked={selectedResumeId === resume.id}
                            onChange={() => setSelectedResumeId(resume.id)}
                          />
                        </div>
                      </label>
                    ))
                  )}
                </div>

                {deliverError && (
                  <p className="text-sm text-red-600 mb-4">{deliverError}</p>
                )}
                {deliverSuccess && (
                  <p className="text-sm text-emerald-600 mb-4 text-center font-medium">投递成功！</p>
                )}

                <div className="flex gap-3 mt-6">
                  <button
                    onClick={() => {
                      setSelectedJob(null)
                      setSelectedResumeId(null)
                      setDeliverError('')
                    }}
                    className="flex-1 btn-secondary"
                    disabled={isDelivering || deliverSuccess}
                  >
                    取消
                  </button>
                  <button
                    onClick={handleDeliver}
                    disabled={!selectedResumeId || isDelivering || deliverSuccess}
                    className="flex-1 btn-primary"
                  >
                    {isDelivering ? '投递中...' : '确认投递'}
                  </button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </AnimatePresence>
    </div>
  )
}
