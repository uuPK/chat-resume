import os

content = """'use client'

import MatchRadarChart from './MatchRadarChart'

interface MatchReportViewProps {
  report: {
    radar_scores: Record<string, number>
    overall_match_percentage: number
    pros: string[]
    cons: string[]
    action_items: string[]
  }
}

export default function MatchReportView({ report }: MatchReportViewProps) {
  return (
    <div className="bg-white rounded-xl shadow-sm border border-gray-100 p-6 overflow-hidden">
      <div className="flex flex-col md:flex-row items-center gap-8 border-b border-gray-100 pb-6 mb-6">
        <div className="flex-shrink-0">
          <div className="relative w-32 h-32 flex items-center justify-center rounded-full bg-violet-50">
            <span className="text-3xl font-bold text-violet-600">
              {report.overall_match_percentage}%
            </span>
            <svg className="absolute inset-0 w-full h-full transform -rotate-90">
              <circle cx="64" cy="64" r="60" fill="none" stroke="#f5f3ff" strokeWidth="8" />
              <circle
                cx="64"
                cy="64"
                r="60"
                fill="none"
                stroke="#7c3aed"
                strokeWidth="8"
                strokeDasharray={`${(report.overall_match_percentage / 100) * 377} 377`}
                strokeLinecap="round"
              />
            </svg>
          </div>
          <p className="text-center mt-2 text-sm font-medium text-gray-500">综合匹配度</p>
        </div>
        <div className="flex-grow w-full max-w-[300px] mx-auto md:mx-0">
          <MatchRadarChart scores={report.radar_scores} />
        </div>
      </div>

      <div className="space-y-6">
        <div>
          <h3 className="text-base font-semibold text-gray-900 flex items-center gap-2 mb-3">
            <span className="w-2 h-2 rounded-full bg-green-500"></span>
            核心优势
          </h3>
          <ul className="space-y-2">
            {report.pros.map((pro, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                <span className="text-green-500 mt-0.5">✓</span>
                {pro}
              </li>
            ))}
          </ul>
        </div>

        <div>
          <h3 className="text-base font-semibold text-gray-900 flex items-center gap-2 mb-3">
            <span className="w-2 h-2 rounded-full bg-red-500"></span>
            能力缺口
          </h3>
          <ul className="space-y-2">
            {report.cons.map((con, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-gray-600">
                <span className="text-red-500 mt-0.5">✗</span>
                {con}
              </li>
            ))}
          </ul>
        </div>

        <div className="bg-violet-50 rounded-lg p-4">
          <h3 className="text-base font-semibold text-violet-900 flex items-center gap-2 mb-3">
            <span className="text-violet-600">⚡</span>
            行动建议 (冲刺)
          </h3>
          <ul className="space-y-2">
            {report.action_items.map((item, i) => (
              <li key={i} className="flex items-start gap-2 text-sm text-violet-800">
                <span className="bg-violet-200 text-violet-800 rounded-full w-5 h-5 flex items-center justify-center text-xs font-bold shrink-0 mt-0.5">
                  {i + 1}
                </span>
                {item}
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  )
}
"""

with open('src/components/jobs/MatchReportView.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
