'use client'

import { useEffect, useState } from 'react'
import { useParams } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import { enterpriseApi, type JobDeliveryDetails, type Resume } from '@/lib/api'
import PaginatedResumePreview from '@/components/preview/PaginatedResumePreview'
import { SparklesIcon, FireIcon, ArrowPathIcon, ExclamationTriangleIcon, LightBulbIcon } from '@heroicons/react/24/outline'
import { DEFAULT_MODULE_CONFIG } from '@/lib/resumeLayoutConfig'

export default function EnterpriseResumeReview() {
  const { id } = useParams()
  const deliveryId = Number(id)
  
  const [delivery, setDelivery] = useState<JobDeliveryDetails | null>(null)
  const [resume, setResume] = useState<Resume | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [isAnalyzing, setIsAnalyzing] = useState(false)
  
  useEffect(() => {
    if (deliveryId) {
      Promise.all([
        enterpriseApi.getDelivery(deliveryId),
        enterpriseApi.getDeliveryResume(deliveryId)
      ]).then(([deliveryData, resumeData]) => {
        setDelivery(deliveryData)
        setResume(resumeData)
        setIsLoading(false)
      }).catch(err => {
        console.error(err)
        setIsLoading(false)
      })
    }
  }, [deliveryId])

  const handleAnalyze = async () => {
    setIsAnalyzing(true)
    try {
      const result = await enterpriseApi.analyzeMatch(deliveryId)
      setDelivery(prev => prev ? {
        ...prev,
        match_score: result.match_score,
        analysis_result: result.analysis_result
      } : null)
    } catch (err) {
      console.error(err)
    } finally {
      setIsAnalyzing(false)
    }
  }

  if (isLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50 dark:bg-[#0a0a0a]">
        <div className="w-8 h-8 rounded-full border-2 border-transparent animate-spin border-t-primary-600 border-r-primary-600" />
      </div>
    )
  }

  if (!delivery || !resume) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-500">无法加载投递详情</p>
      </div>
    )
  }

  const analysis = delivery.analysis_result

  return (
    <div className="h-screen bg-gray-100 dark:bg-[#0a0a0a] flex flex-col md:flex-row overflow-hidden">
      {/* Left Pane: Resume Preview */}
      <div className="flex-1 overflow-y-auto p-4 md:p-8 flex justify-center">
        <div className="w-full max-w-[794px]"> {/* A4 width approx */}
          {resume.content && (
            <div className="pointer-events-none select-none drop-shadow-xl">
              <PaginatedResumePreview
                content={resume.content as any}
                moduleOrder={resume.layout_config?.moduleOrder || DEFAULT_MODULE_CONFIG}
                spacingScale={(resume.layout_config?.spacingScale as number) || 1}
                templateStyle={(resume.layout_config?.templateStyle as string) || 'classic'}
                viewportPadding={0}
              />
            </div>
          )}
        </div>
      </div>

      {/* Right Pane: AI Analysis */}
      <div className="w-full md:w-[400px] lg:w-[450px] bg-white dark:bg-gray-900 border-l border-gray-200 dark:border-gray-800 flex flex-col shrink-0">
        <div className="p-6 border-b border-gray-200 dark:border-gray-800 bg-white dark:bg-gray-900 z-10 sticky top-0">
          <h2 className="text-xl font-bold text-gray-900 dark:text-white mb-2">AI 简历筛查</h2>
          <p className="text-sm text-gray-500">
            候选人: <span className="font-semibold text-gray-900 dark:text-white">{delivery.candidate_name}</span>
            <br/>
            应聘岗位: <span className="font-semibold text-gray-900 dark:text-white">{delivery.job_title}</span>
          </p>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6 bg-gray-50 dark:bg-[#0a0a0a]">
          {!delivery.match_score ? (
            <div className="flex flex-col items-center justify-center h-full text-center space-y-4">
              <div className="w-16 h-16 bg-primary-50 dark:bg-primary-900/20 rounded-full flex items-center justify-center">
                <SparklesIcon className="w-8 h-8 text-primary-600" />
              </div>
              <div>
                <h3 className="text-lg font-medium text-gray-900 dark:text-white">启动 AI 简历初筛</h3>
                <p className="text-sm text-gray-500 mt-2 max-w-[250px] mx-auto">
                  调用大模型分析候选人简历与岗位 JD 的匹配度，生成匹配热力图和探底面试问题。
                </p>
              </div>
              <button
                onClick={handleAnalyze}
                disabled={isAnalyzing}
                className="btn-primary flex items-center gap-2 mt-4"
              >
                {isAnalyzing ? (
                  <>
                    <ArrowPathIcon className="w-5 h-5 animate-spin" />
                    正在分析中...
                  </>
                ) : (
                  <>
                    <SparklesIcon className="w-5 h-5" />
                    一键分析
                  </>
                )}
              </button>
            </div>
          ) : (
            <AnimatePresence>
              <motion.div
                initial={{ opacity: 0, y: 20 }}
                animate={{ opacity: 1, y: 0 }}
                className="space-y-6"
              >
                {/* 匹配热力图 */}
                <div className="bg-white dark:bg-gray-900 rounded-2xl p-5 border border-gray-200 dark:border-gray-800 shadow-sm">
                  <div className="flex items-center justify-between mb-4">
                    <h3 className="text-md font-bold flex items-center gap-2 text-gray-900 dark:text-white">
                      <FireIcon className="w-5 h-5 text-orange-500" />
                      人岗匹配度
                    </h3>
                    <div className="text-3xl font-black text-primary-600">
                      {delivery.match_score}%
                    </div>
                  </div>
                  
                  <div className="w-full bg-gray-100 dark:bg-gray-800 rounded-full h-2 mb-4 overflow-hidden">
                    <motion.div
                      initial={{ width: 0 }}
                      animate={{ width: `${delivery.match_score}%` }}
                      transition={{ duration: 1, ease: "easeOut" }}
                      className="bg-gradient-to-r from-orange-400 to-red-500 h-2 rounded-full"
                    />
                  </div>
                  
                  <div className="bg-orange-50 dark:bg-orange-900/20 p-3 rounded-xl text-sm text-orange-800 dark:text-orange-200 mb-4">
                    {analysis?.summary}
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">匹配亮点</h4>
                      <ul className="space-y-2">
                        {analysis?.strengths?.map((s: string, i: number) => (
                          <li key={i} className="flex items-start gap-2 text-sm text-emerald-700 dark:text-emerald-400">
                            <CheckIcon className="w-4 h-4 mt-0.5 shrink-0" />
                            {s}
                          </li>
                        ))}
                      </ul>
                    </div>
                    <div>
                      <h4 className="text-xs font-semibold text-gray-500 uppercase tracking-wider mb-2">潜在风险</h4>
                      <ul className="space-y-2">
                        {analysis?.weaknesses?.map((w: string, i: number) => (
                          <li key={i} className="flex items-start gap-2 text-sm text-red-700 dark:text-red-400">
                            <ExclamationTriangleIcon className="w-4 h-4 mt-0.5 shrink-0" />
                            {w}
                          </li>
                        ))}
                      </ul>
                    </div>
                  </div>
                </div>

                {/* 探底面试问题 */}
                <div className="bg-white dark:bg-gray-900 rounded-2xl p-5 border border-gray-200 dark:border-gray-800 shadow-sm">
                  <h3 className="text-md font-bold flex items-center gap-2 text-gray-900 dark:text-white mb-4">
                    <LightBulbIcon className="w-5 h-5 text-yellow-500" />
                    建议探底问题
                  </h3>
                  <p className="text-xs text-gray-500 mb-4">
                    基于候选人简历中的薄弱环节或关键经历，AI 生成以下面试提问策略：
                  </p>
                  
                  <div className="space-y-3">
                    {analysis?.interview_questions?.map((q: string, i: number) => (
                      <div key={i} className="bg-gray-50 dark:bg-gray-800 p-3 rounded-xl border border-gray-100 dark:border-gray-700">
                        <div className="flex gap-3">
                          <div className="text-primary-600 font-bold">Q{i+1}</div>
                          <div className="text-sm text-gray-700 dark:text-gray-300">{q}</div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 底部操作区 */}
                <div className="flex gap-3 pt-4">
                  <button 
                    onClick={async () => {
                      try {
                        await enterpriseApi.updateDeliveryStatus(deliveryId, 'rejected')
                        setDelivery({ ...delivery, status: 'rejected' })
                        alert('已标记为淘汰')
                      } catch (e) {
                        alert('操作失败')
                      }
                    }}
                    disabled={delivery.status === 'rejected'}
                    className={`flex-1 font-medium py-3 rounded-xl transition-colors ${
                      delivery.status === 'rejected' 
                        ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                        : 'bg-red-50 hover:bg-red-100 text-red-600'
                    }`}
                  >
                    {delivery.status === 'rejected' ? '已淘汰' : '淘汰'}
                  </button>
                  <button 
                    onClick={async () => {
                      try {
                        await enterpriseApi.updateDeliveryStatus(deliveryId, 'interview_invited')
                        setDelivery({ ...delivery, status: 'interview_invited' })
                        alert('约面成功，已通知求职者！')
                      } catch (e) {
                        alert('操作失败')
                      }
                    }}
                    disabled={delivery.status === 'interview_invited' || delivery.status === 'rejected'}
                    className={`flex-1 font-medium py-3 rounded-xl transition-all ${
                      delivery.status === 'interview_invited'
                        ? 'bg-emerald-100 text-emerald-700 cursor-not-allowed'
                        : delivery.status === 'rejected'
                          ? 'bg-gray-100 text-gray-400 cursor-not-allowed'
                          : 'bg-primary-600 hover:bg-primary-700 text-white shadow-lg shadow-primary-500/30'
                    }`}
                  >
                    {delivery.status === 'interview_invited' ? '已发起约面' : '约面'}
                  </button>
                </div>
              </motion.div>
            </AnimatePresence>
          )}
        </div>
      </div>
    </div>
  )
}

function CheckIcon(props: React.ComponentProps<'svg'>) {
  return (
    <svg fill="none" viewBox="0 0 24 24" strokeWidth={2} stroke="currentColor" {...props}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
    </svg>
  )
}
