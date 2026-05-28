'use client'

import React from 'react'
import ReactECharts from 'echarts-for-react'

interface RadarChartProps {
  data: {
    title: string
    score?: number
  }[]
}

export function RadarChart({ data }: RadarChartProps) {
  // 确保数据顺序为：专业技能, 逻辑思维, 沟通表达, 项目经验
  const order = ['专业技能', '逻辑思维', '沟通表达', '项目经验']
  
  // 生成排序后的数据，如果缺失则默认0
  const orderedData = order.map(dim => {
    const found = data.find(d => d.title === dim)
    return found ? (found.score || 0) : 0
  })

  const option = {
    radar: {
      indicator: order.map(dim => ({ name: dim, max: 100 })),
      splitNumber: 4,
      axisName: {
        color: '#52525b',
        fontSize: 14,
        fontWeight: 600,
      },
      splitArea: {
        areaStyle: {
          color: ['rgba(124, 58, 237, 0.02)', 'rgba(124, 58, 237, 0.04)', 'rgba(124, 58, 237, 0.06)', 'rgba(124, 58, 237, 0.08)'],
          shadowColor: 'rgba(0, 0, 0, 0.05)',
          shadowBlur: 10
        }
      },
      axisLine: {
        lineStyle: {
          color: 'rgba(91, 97, 110, 0.15)'
        }
      },
      splitLine: {
        lineStyle: {
          color: 'rgba(91, 97, 110, 0.15)'
        }
      }
    },
    series: [
      {
        name: '能力画像',
        type: 'radar',
        data: [
          {
            value: orderedData,
            name: '候选人得分',
            symbol: 'circle',
            symbolSize: 6,
            itemStyle: {
              color: '#7c3aed',
            },
            lineStyle: {
              color: '#7c3aed',
              width: 2,
            },
            areaStyle: {
              color: 'rgba(124, 58, 237, 0.2)',
            },
          }
        ]
      }
    ]
  }

  return (
    <div className="w-full h-[400px] flex items-center justify-center p-4">
      <ReactECharts 
        option={option} 
        style={{ height: '100%', width: '100%' }}
        opts={{ renderer: 'svg' }}
      />
    </div>
  )
}
