import os

content = """'use client'

import { useMemo } from 'react'

export default function MatchRadarChart({ scores }: { scores: Record<string, number> }) {
  const data = useMemo(() => {
    return [
      { subject: '技术深度', A: scores.technical_skills || 0, fullMark: 100 },
      { subject: '业务理解', A: scores.business_domain || 0, fullMark: 100 },
      { subject: '经验水平', A: scores.experience_level || 0, fullMark: 100 },
      { subject: '软技能', A: scores.soft_skills || 0, fullMark: 100 },
    ]
  }, [scores])

  // A very simple SVG radar chart implementation to avoid extra dependencies like recharts
  const size = 200
  const center = size / 2
  const radius = size * 0.4

  const getPoint = (value: number, index: number, total: number) => {
    const angle = (Math.PI * 2 * index) / total - Math.PI / 2
    const distance = (value / 100) * radius
    return {
      x: center + Math.cos(angle) * distance,
      y: center + Math.sin(angle) * distance
    }
  }

  const polygonPoints = data.map((d, i) => {
    const p = getPoint(d.A, i, data.length)
    return `${p.x},${p.y}`
  }).join(' ')

  return (
    <div className="flex flex-col items-center justify-center py-4">
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        {/* Background webs */}
        {[0.25, 0.5, 0.75, 1].map((scale, i) => (
          <polygon
            key={i}
            points={data.map((_, idx) => {
              const p = getPoint(100 * scale, idx, data.length)
              return `${p.x},${p.y}`
            }).join(' ')}
            fill="none"
            stroke="#e5e7eb"
            strokeWidth="1"
          />
        ))}
        {/* Axis lines */}
        {data.map((_, i) => {
          const p = getPoint(100, i, data.length)
          return (
            <line
              key={i}
              x1={center}
              y1={center}
              x2={p.x}
              y2={p.y}
              stroke="#e5e7eb"
              strokeWidth="1"
            />
          )
        })}
        {/* Data polygon */}
        <polygon
          points={polygonPoints}
          fill="rgba(124, 58, 237, 0.2)"
          stroke="#7c3aed"
          strokeWidth="2"
        />
        {/* Data points */}
        {data.map((d, i) => {
          const p = getPoint(d.A, i, data.length)
          return (
            <circle
              key={i}
              cx={p.x}
              cy={p.y}
              r="4"
              fill="#7c3aed"
            />
          )
        })}
        {/* Labels */}
        {data.map((d, i) => {
          const p = getPoint(115, i, data.length) // Place labels slightly outside
          let anchor = 'middle'
          if (p.x < center - 10) anchor = 'end'
          if (p.x > center + 10) anchor = 'start'
          return (
            <text
              key={i}
              x={p.x}
              y={p.y + 4} // slight vertical adjustment
              textAnchor={anchor}
              fontSize="10"
              fill="#52525b"
              className="font-medium"
            >
              {d.subject} ({d.A})
            </text>
          )
        })}
      </svg>
    </div>
  )
}
"""

with open('src/components/jobs/MatchRadarChart.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
