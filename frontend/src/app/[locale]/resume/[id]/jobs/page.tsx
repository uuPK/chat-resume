'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { jobsApi } from '@/lib/api'
import MatchReportView from '@/components/jobs/MatchReportView'

export default function JobsPage() {
  const params = useParams()
  const router = useRouter()
  const resumeId = Number(params.id)

  const [loading, setLoading] = useState(true)
  const [recommendations, setRecommendations] = useState<any[]>([])
  const [selectedJob, setSelectedJob] = useState<any | null>(null)
  
  const [reportLoading, setReportLoading] = useState(false)
  const [matchReport, setMatchReport] = useState<any | null>(null)
  const [customJd, setCustomJd] = useState('')

  useEffect(() => {
    fetchRecommendations()
  }, [resumeId])

  const fetchRecommendations = async () => {
    setLoading(true)
    try {
      const data = await jobsApi.getRecommendations(resumeId)
      if (data && data.recommendations) {
        setRecommendations(data.recommendations)
      }
    } catch (e) {
      // If not found, we can try to generate it
      generateRecommendations()
    } finally {
      setLoading(false)
    }
  }

  const generateRecommendations = async () => {
    setLoading(true)
    try {
      const data = await jobsApi.generateRecommendations(resumeId)
      if (data && data.recommendations) {
        setRecommendations(data.recommendations)
      }
    } catch (e) {
      console.error(e)
      alert('生成岗位推荐失败，请重试。')
    } finally {
      setLoading(false)
    }
  }

  const handleGenerateReport = async (jdText: string) => {
    if (!jdText || jdText.length < 10) {
      alert('请输入有效的职位描述 (JD)')
      return
    }
    setReportLoading(true)
    try {
      const data = await jobsApi.generateMatchReport(resumeId, jdText)
      setMatchReport(data.analysis_result)
    } catch (e) {
      console.error(e)
      alert('生成匹配报告失败。')
    } finally {
      setReportLoading(false)
    }
  }

  return (
    <div className="min-h-screen bg-gray-50/50 p-6">
      <div className="max-w-5xl mx-auto space-y-8">
        <header className="flex items-center justify-between">
          <div>
            <button
              onClick={() => router.push('/resumes')}
              className="text-sm text-gray-500 hover:text-gray-900 mb-2 flex items-center gap-1"
            >
              &larr; 返回简历列表
            </button>
            <h1 className="text-2xl font-bold text-gray-900">智能岗位匹配</h1>
            <p className="text-gray-500">AI驱动的职位推荐与深度匹配分析</p>
          </div>
          <button
            onClick={generateRecommendations}
            disabled={loading}
            className="px-4 py-2 bg-white border border-gray-200 text-gray-700 rounded-lg hover:bg-gray-50 font-medium text-sm disabled:opacity-50"
          >
            {loading ? '分析中...' : '重新生成推荐'}
          </button>
        </header>

        {loading && recommendations.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-20 space-y-4">
            <div className="w-8 h-8 border-4 border-blue-600 border-t-transparent rounded-full animate-spin"></div>
            <p className="text-gray-500 font-medium animate-pulse">DeepSeek AI 正在全面分析您的简历...</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            <div className="lg:col-span-1 space-y-4">
              <h2 className="text-lg font-semibold text-gray-900">为您推荐的岗位方向</h2>
              <div className="space-y-3 max-h-[600px] overflow-y-auto pr-2">
                {recommendations.map((rec, i) => (
                  <div
                    key={i}
                    onClick={() => {
                      setSelectedJob(rec)
                      setCustomJd(`职位名称: ${rec.job_title}\n目标公司类型: ${rec.company_type}\n\n这是一份由AI推荐的目标岗位。请将我的简历与该岗位的标准画像进行对比分析。`)
                      setMatchReport(null) // clear previous report
                    }}
                    className={`p-4 rounded-xl border cursor-pointer transition-all ${
                      selectedJob === rec
                        ? 'bg-blue-50 border-blue-200 shadow-sm'
                        : 'bg-white border-gray-100 hover:border-blue-200 hover:shadow-sm'
                    }`}
                  >
                    <div className="flex items-start justify-between mb-2">
                      <h3 className="font-semibold text-gray-900">{rec.job_title}</h3>
                      <span className="text-sm font-bold text-blue-600 bg-white px-2 py-0.5 rounded border border-blue-100 shadow-sm">
                        {rec.match_percentage}%
                      </span>
                    </div>
                    <p className="text-sm text-gray-500 mb-3">{rec.company_type}</p>
                    <div className="flex flex-wrap gap-2">
                      {rec.match_reasons.slice(0, 2).map((reason: string, j: number) => (
                        <span key={j} className="text-[11px] bg-green-50 text-green-700 px-2 py-1 rounded">
                          {reason}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <div className="lg:col-span-2 space-y-6">
              <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6">
                <h2 className="text-lg font-semibold text-gray-900 mb-4">深度匹配分析器</h2>
                <p className="text-sm text-gray-500 mb-4">
                  请在左侧选择一个推荐岗位，或者在下方直接粘贴真实的招聘描述 (JD)，我们将为您生成深度匹配报告。
                </p>
                <textarea
                  value={customJd}
                  onChange={(e) => setCustomJd(e.target.value)}
                  placeholder="在此处粘贴目标职位的招聘描述 (JD)..."
                  className="w-full h-32 p-3 border border-gray-200 rounded-lg text-sm focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none resize-none mb-4"
                ></textarea>
                <button
                  onClick={() => handleGenerateReport(customJd)}
                  disabled={reportLoading || !customJd.trim()}
                  className="w-full py-2.5 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-medium text-sm transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {reportLoading && (
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                  )}
                  {reportLoading ? '正在分析匹配度...' : '生成匹配报告'}
                </button>
              </div>

              {matchReport && (
                <div className="animate-in fade-in slide-in-from-bottom-4 duration-500">
                  <MatchReportView report={matchReport} />
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  )
}
