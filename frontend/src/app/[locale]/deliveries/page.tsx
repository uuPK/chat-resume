'use client'

import { useEffect, useState } from 'react'
import { enterpriseApi, type JobDeliveryDetails } from '@/lib/api'
import CandidateSidebar from '@/components/layout/CandidateSidebar'
import { AcademicCapIcon, MapPinIcon, ClockIcon, CheckCircleIcon, XCircleIcon } from '@heroicons/react/24/outline'

export default function DeliveriesPage() {
  const [deliveries, setDeliveries] = useState<JobDeliveryDetails[]>([])
  const [isLoading, setIsLoading] = useState(true)

  useEffect(() => {
    enterpriseApi.getMyDeliveries()
      .then(setDeliveries)
      .catch(console.error)
      .finally(() => setIsLoading(false))
  }, [])

  return (
    <div className="flex h-screen bg-gray-50 dark:bg-[#0a0a0a]">
      <CandidateSidebar />
      <main className="flex-1 overflow-y-auto p-8">
        <div className="max-w-5xl mx-auto">
          <div className="mb-8">
            <h1 className="text-3xl font-bold text-gray-900 dark:text-white flex items-center gap-2">
              <AcademicCapIcon className="w-8 h-8 text-primary-600" />
              我的投递
            </h1>
            <p className="text-gray-500 mt-2">查看您的简历投递记录及面试邀约。</p>
          </div>

          {isLoading ? (
            <div className="flex justify-center py-20">
              <div className="w-8 h-8 rounded-full border-2 border-transparent animate-spin border-t-primary-600 border-r-primary-600" />
            </div>
          ) : deliveries.length === 0 ? (
            <div className="text-center py-20 bg-white dark:bg-gray-900 rounded-2xl border border-gray-200 dark:border-gray-800">
              <p className="text-gray-500">您还没有任何投递记录。</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4">
              {deliveries.map(delivery => (
                <div key={delivery.id} className="bg-white dark:bg-gray-900 rounded-2xl p-6 border border-gray-200 dark:border-gray-800 shadow-sm flex flex-col md:flex-row justify-between gap-6">
                  <div>
                    <h3 className="text-xl font-bold text-gray-900 dark:text-white mb-2">
                      {delivery.job_title}
                    </h3>
                    <p className="text-sm text-gray-500 mb-4">
                      投递简历: <span className="font-medium text-gray-700 dark:text-gray-300">{delivery.resume_title}</span>
                    </p>
                    
                    {delivery.status === 'interview_invited' && (
                      <div className="bg-emerald-50 dark:bg-emerald-900/20 border border-emerald-100 dark:border-emerald-800 rounded-xl p-4 mt-4">
                        <h4 className="text-emerald-800 dark:text-emerald-400 font-bold mb-3 flex items-center gap-2">
                          <CheckCircleIcon className="w-5 h-5" />
                          企业向您发起了面试邀约！
                        </h4>
                        <div className="space-y-2 text-sm text-emerald-700 dark:text-emerald-300">
                          <p className="flex items-center gap-2">
                            <ClockIcon className="w-4 h-4" /> 
                            <strong>时间：</strong> {delivery.interview_time || '未指定'}
                          </p>
                          <p className="flex items-center gap-2">
                            <MapPinIcon className="w-4 h-4" />
                            <strong>地点/链接：</strong> {delivery.interview_location || '未指定'}
                          </p>
                        </div>
                      </div>
                    )}
                    
                    {delivery.status === 'rejected' && (
                      <div className="bg-red-50 dark:bg-red-900/20 border border-red-100 dark:border-red-800 rounded-xl p-4 mt-4">
                        <h4 className="text-red-800 dark:text-red-400 font-bold flex items-center gap-2">
                          <XCircleIcon className="w-5 h-5" />
                          很遗憾，您的简历未能通过初步筛选
                        </h4>
                      </div>
                    )}
                  </div>
                  
                  <div className="flex flex-col items-end min-w-[120px]">
                    <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                      delivery.status === 'interview_invited' ? 'bg-emerald-100 text-emerald-700' :
                      delivery.status === 'rejected' ? 'bg-red-100 text-red-700' :
                      'bg-blue-100 text-blue-700'
                    }`}>
                      {delivery.status === 'interview_invited' ? '约面' :
                       delivery.status === 'rejected' ? '已淘汰' :
                       '处理中'}
                    </span>
                    <span className="text-xs text-gray-400 mt-2">
                      {new Date(delivery.created_at).toLocaleDateString()}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </main>
    </div>
  )
}
