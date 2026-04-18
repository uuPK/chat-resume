'use client'

import { useState } from 'react'
import { 
  AdjustmentsHorizontalIcon
} from '@heroicons/react/24/outline'
import {
  LayoutDensity,
  ResumeModule,
  MODULE_LABELS,
  ResumeLayoutConfig,
  DENSITY_SPACING_SCALE
} from '@/lib/resumeLayoutConfig'

interface ResumeLayoutControlsProps {
  config: ResumeLayoutConfig
  onConfigChange: (config: ResumeLayoutConfig) => void
  className?: string
}

export default function ResumeLayoutControls({
  config,
  onConfigChange,
  className = ''
}: ResumeLayoutControlsProps) {
  const [showControls, setShowControls] = useState(false)
  const [activeTab, setActiveTab] = useState<'density' | 'modules'>('density')

  const handleDensityChange = (density: LayoutDensity) => {
    const spacingScale = DENSITY_SPACING_SCALE[density as Exclude<LayoutDensity, 'custom'>] ?? config.spacingScale
    onConfigChange({
      density,
      moduleOrder: [...config.moduleOrder],
      visibleModules: new Set(config.visibleModules),
      spacingScale
    })
  }

  const handleSpacingScaleChange = (value: number) => {
    onConfigChange({
      density: 'custom',
      moduleOrder: [...config.moduleOrder],
      visibleModules: new Set(config.visibleModules),
      spacingScale: value
    })
  }

  const handleSpacingScaleReset = () => {
    onConfigChange({
      density: 'normal',
      moduleOrder: [...config.moduleOrder],
      visibleModules: new Set(config.visibleModules),
      spacingScale: 1.0
    })
  }

  const toggleModuleVisibility = (module: ResumeModule) => {
    const newVisible = new Set(config.visibleModules)
    if (newVisible.has(module)) {
      newVisible.delete(module)
    } else {
      newVisible.add(module)
    }
    onConfigChange({
      density: config.density,
      moduleOrder: [...config.moduleOrder],
      visibleModules: newVisible,
      spacingScale: config.spacingScale
    })
  }

  const moveModule = (module: ResumeModule, direction: 'up' | 'down') => {
    const currentIndex = config.moduleOrder.indexOf(module)
    if (currentIndex === -1) return

    const newOrder = [...config.moduleOrder]
    const targetIndex = direction === 'up' ? currentIndex - 1 : currentIndex + 1

    if (targetIndex < 0 || targetIndex >= newOrder.length) return

    ;[newOrder[currentIndex], newOrder[targetIndex]] =
    [newOrder[targetIndex], newOrder[currentIndex]]

    onConfigChange({
      density: config.density,
      moduleOrder: newOrder,
      visibleModules: new Set(config.visibleModules),
      spacingScale: config.spacingScale
    })
  }

  return (
    <div className={`relative ${className}`}>
      {/* 触发按钮 — 56px pill，ghost 样式 */}
      <button
        onClick={() => setShowControls(!showControls)}
        className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-semibold transition-colors"
        style={{
          borderRadius: '56px',
          backgroundColor: '#ffffff',
          border: '1px solid rgba(91,97,110,0.25)',
          color: '#0a0b0d',
        }}
        onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#eef0f3')}
        onMouseLeave={e => (e.currentTarget.style.backgroundColor = '#ffffff')}
      >
        <AdjustmentsHorizontalIcon className="w-4 h-4" />
        <span>布局设置</span>
      </button>

      {/* 控制面板 */}
      {showControls && (
        <>
          <div className="fixed inset-0 z-40" onClick={() => setShowControls(false)} />

          <div
            className="absolute right-0 mt-2 w-80 bg-white z-50"
            style={{
              borderRadius: '16px',
              border: '1px solid rgba(91,97,110,0.18)',
              boxShadow: '0 8px 32px rgba(0,0,0,0.08)',
            }}
          >
            {/* 标签页 */}
            <div className="flex" style={{ borderBottom: '1px solid rgba(91,97,110,0.12)' }}>
              {(['density', 'modules'] as const).map(tab => (
                <button
                  key={tab}
                  onClick={() => setActiveTab(tab)}
                  className="flex-1 px-4 py-3 text-sm font-semibold transition-colors relative"
                  style={{ color: activeTab === tab ? '#0052ff' : '#5b616e' }}
                >
                  {tab === 'density' ? '密度' : '显示'}
                  {activeTab === tab && (
                    <div className="absolute bottom-0 left-4 right-4 h-0.5" style={{ backgroundColor: '#0052ff', borderRadius: '2px 2px 0 0' }} />
                  )}
                </button>
              ))}
            </div>

            <div className="p-4">
              {activeTab === 'density' && (
                <div className="space-y-4">
                  <div className="space-y-2">
                    {(['comfortable', 'normal', 'compact'] as Exclude<LayoutDensity, 'custom'>[]).map((density) => (
                      <label
                        key={density}
                        className="flex items-center gap-3 p-3 cursor-pointer transition-colors"
                        style={{
                          borderRadius: '12px',
                          border: `1px solid ${config.density === density ? '#0052ff' : 'rgba(91,97,110,0.18)'}`,
                          backgroundColor: config.density === density ? 'rgba(0,82,255,0.05)' : '#ffffff',
                        }}
                      >
                        <input
                          type="radio"
                          name="density"
                          checked={config.density === density}
                          onChange={() => handleDensityChange(density)}
                          style={{ accentColor: '#0052ff' }}
                        />
                        <span className="text-sm font-semibold" style={{ color: '#0a0b0d' }}>
                          {density === 'comfortable' ? '舒适' : density === 'normal' ? '标准' : '紧凑'}
                        </span>
                      </label>
                    ))}
                  </div>

                  <div className="pt-3" style={{ borderTop: '1px solid rgba(91,97,110,0.1)' }}>
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-semibold" style={{ color: '#0a0b0d' }}>精细调节</span>
                      <button
                        onClick={handleSpacingScaleReset}
                        className="text-xs font-semibold"
                        style={{ color: '#0052ff' }}
                      >
                        重置
                      </button>
                    </div>
                    <input
                      type="range"
                      min="0.5"
                      max="1.5"
                      step="0.05"
                      value={config.spacingScale ?? 1}
                      onChange={(e) => handleSpacingScaleChange(parseFloat(e.target.value))}
                      className="w-full h-1.5 rounded-full appearance-none cursor-pointer"
                      style={{ accentColor: '#0052ff', backgroundColor: '#eef0f3' }}
                    />
                    <div className="flex justify-between items-center mt-1.5">
                      <span className="text-xs" style={{ color: '#9ca3af' }}>紧</span>
                      <span className="text-xs font-semibold" style={{ color: '#0a0b0d' }}>
                        间距: {(config.spacingScale ?? 1).toFixed(2)}×
                      </span>
                      <span className="text-xs" style={{ color: '#9ca3af' }}>松</span>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === 'modules' && (
                <div className="space-y-2">
                  {config.moduleOrder.map((module, index) => (
                    <div
                      key={module}
                      className="flex items-center gap-3 p-3 transition-colors"
                      style={{
                        borderRadius: '12px',
                        border: '1px solid rgba(91,97,110,0.15)',
                        backgroundColor: '#ffffff',
                      }}
                    >
                      <input
                        type="checkbox"
                        checked={config.visibleModules.has(module)}
                        onChange={() => toggleModuleVisibility(module)}
                        style={{ accentColor: '#0052ff' }}
                      />
                      <div className="flex-1 text-sm font-semibold" style={{ color: '#0a0b0d' }}>
                        {MODULE_LABELS[module]}
                      </div>
                      <div className="flex gap-1">
                        <button
                          onClick={() => moveModule(module, 'up')}
                          disabled={index === 0}
                          className="p-1 transition-colors disabled:opacity-30"
                          style={{ borderRadius: '8px', color: '#5b616e' }}
                          onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#eef0f3')}
                          onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                          </svg>
                        </button>
                        <button
                          onClick={() => moveModule(module, 'down')}
                          disabled={index === config.moduleOrder.length - 1}
                          className="p-1 transition-colors disabled:opacity-30"
                          style={{ borderRadius: '8px', color: '#5b616e' }}
                          onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#eef0f3')}
                          onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                          </svg>
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
