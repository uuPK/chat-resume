'use client'

import { useEffect } from 'react'
import Link from 'next/link'
import { useParams, useRouter, useSearchParams } from 'next/navigation'

export default function InterviewReportPage() {
  const params = useParams()
  const router = useRouter()
  const searchParams = useSearchParams()
  const reportId = params?.id as string
  const resumeId = searchParams?.get('resume_id')

  useEffect(() => {
    if (!resumeId) {
      router.replace('/dashboard')
      return
    }
    router.replace(`/resume/${resumeId}/interview?from_report=${reportId}`)
  }, [reportId, resumeId, router])

  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-6">
      <div className="max-w-md rounded-2xl border border-gray-200 bg-white p-6 text-center shadow-sm">
        <h1 className="text-xl font-semibold text-gray-900">面试报告页已停用</h1>
        <p className="mt-2 text-sm text-gray-600">
          旧报告链路已下线，请回到统一的模拟面试工作台。
        </p>
        <Link
          href={resumeId ? `/resume/${resumeId}/interview` : '/dashboard'}
          className="mt-4 inline-flex rounded-lg bg-gray-900 px-4 py-2 text-sm font-medium text-white"
        >
          前往面试工作台
        </Link>
      </div>
    </div>
  )
}
