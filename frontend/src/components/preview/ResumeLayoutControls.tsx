'use client'

import { useState } from 'react'
import { 
  AdjustmentsHorizontalIcon,
  Bars3BottomLeftIcon,
  EyeIcon,
  EyeSlashIcon
} from '@heroicons/react/24/outline'
import { 
  LayoutDensity, 
  ResumeModule,
  MODULE_LABELS,
  ResumeLayoutConfig
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
  const [activeTab, setActiveTab] = useState<'density' | 'modules' | 'order'>('density')

  const handleDensityChange = (density: LayoutDensity) => {
    // 创建全新的配置对象以确保React检测到变化
    onConfigChange({
      density,
      moduleOrder: [...config.moduleOrder],
      visibleModules: new Set(config.visibleModules)
    })
  }

  const toggleModuleVisibility = (module: ResumeModule) => {
    const newVisible = new Set(config.visibleModules)
    if (newVisible.has(module)) {
      newVisible.delete(module)
    } else {
      newVisible.add(module)
    }
    // 创建全新的配置对象以确保React检测到变化
    onConfigChange({
      density: config.density,
      moduleOrder: [...config.moduleOrder],
      visibleModules: newVisible
    })
  }

  const moveModule = (module: ResumeModule, direction: 'up' | 'down') => {
    const currentIndex = config.moduleOrder.indexOf(module)
    if (currentIndex === -1) return

    const newOrder = [...config.moduleOrder]
    const targetIndex = direction === 'up' ? currentIndex - 1 : currentIndex + 1

    if (targetIndex < 0 || targetIndex >= newOrder.length) return

    // 交换位置
    ;[newOrder[currentIndex], newOrder[targetIndex]] =
    [newOrder[targetIndex], newOrder[currentIndex]]

    // 创建全新的配置对象以确保React检测到变化
    onConfigChange({
      density: config.density,
      moduleOrder: newOrder,
      visibleModules: new Set(config.visibleModules)
    })
  }

  return (
    <div className={`relative ${className}`}>
      {/* 控制按钮 */}
      <button
        onClick={() => setShowControls(!showControls)}
        className="flex items-center gap-2 px-4 py-2 bg-white border border-gray-300 rounded-lg hover:bg-gray-50 transition-colors shadow-sm"
      >
        <AdjustmentsHorizontalIcon className="w-5 h-5" />
        <span className="text-sm font-medium">布局设置</span>
      </button>

      {/* 控制面板 */}
      {showControls && (
        <>
          {/* 遮罩 */}
          <div 
            className="fixed inset-0 z-40" 
            onClick={() => setShowControls(false)}
          />
          
          {/* 面板 */}
          <div className="absolute right-0 mt-2 w-80 bg-white border border-gray-200 rounded-lg shadow-xl z-50">
            {/* 标签页 */}
            <div className="flex border-b border-gray-200">
              <button
                onClick={() => setActiveTab('density')}
                className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
                  activeTab === 'density'
                    ? 'text-blue-600 border-b-2 border-blue-600'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                密度
              </button>
              <button
                onClick={() => setActiveTab('modules')}
                className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
                  activeTab === 'modules'
                    ? 'text-blue-600 border-b-2 border-blue-600'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                显示
              </button>
              <button
                onClick={() => setActiveTab('order')}
                className={`flex-1 px-4 py-3 text-sm font-medium transition-colors ${
                  activeTab === 'order'
                    ? 'text-blue-600 border-b-2 border-blue-600'
                    : 'text-gray-600 hover:text-gray-900'
                }`}
              >
                顺序
              </button>
            </div>

            {/* 内容区域 */}
            <div className="p-4 max-h-96 overflow-y-auto">
              {/* 密度选项 */}
              {activeTab === 'density' && (
                <div className="space-y-3">
                  <p className="text-xs text-gray-500 mb-4">
                    调整简历的信息密度，紧凑模式可在一页纸放入更多内容
                  </p>
                  {(['comfortable', 'normal', 'compact'] as LayoutDensity[]).map((density) => (
                    <label
                      key={density}
                      className="flex items-start gap-3 p-3 border rounded-lg cursor-pointer hover:bg-gray-50 transition-colors"
                    >
                      <input
                        type="radio"
                        name="density"
                        checked={config.density === density}
                        onChange={() => handleDensityChange(density)}
                        className="mt-1"
                      />
                      <div className="flex-1">
                        <div className="font-medium text-sm">
                          {density === 'comfortable' && '舒适'}
                          {density === 'normal' && '标准'}
                          {density === 'compact' && '紧凑'}
                        </div>
                        <div className="text-xs text-gray-500 mt-1">
                          {density === 'comfortable' && '大字号，宽松间距，适合内容较少的简历'}
                          {density === 'normal' && '平衡的字号和间距，推荐使用'}
                          {density === 'compact' && '小字号，紧凑间距，适合内容丰富的简历'}
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              )}

              {/* 模块显示控制 */}
              {activeTab === 'modules' && (
                <div className="space-y-2">
                  <p className="text-xs text-gray-500 mb-4">
                    控制哪些模块在简历中显示
                  </p>
                  {config.moduleOrder.map((module) => (
                    <label
                      key={module}
                      className="flex items-center gap-3 p-3 border rounded-lg cursor-pointer hover:bg-gray-50 transition-colors"
                    >
                      <input
                        type="checkbox"
                        checked={config.visibleModules.has(module)}
                        onChange={() => toggleModuleVisibility(module)}
                        className="rounded"
                      />
                      <div className="flex-1">
                        <div className="font-medium text-sm flex items-center gap-2">
                          {config.visibleModules.has(module) ? (
                            <EyeIcon className="w-4 h-4 text-green-600" />
                          ) : (
                            <EyeSlashIcon className="w-4 h-4 text-gray-400" />
                          )}
                          {MODULE_LABELS[module]}
                        </div>
                      </div>
                    </label>
                  ))}
                </div>
              )}

              {/* 模块顺序控制 */}
              {activeTab === 'order' && (
                <div className="space-y-2">
                  <p className="text-xs text-gray-500 mb-4">
                    拖动或使用按钮调整模块显示顺序
                  </p>
                  {config.moduleOrder.map((module, index) => (
                    <div
                      key={module}
                      className="flex items-center gap-2 p-3 border rounded-lg bg-white"
                    >
                      <Bars3BottomLeftIcon className="w-5 h-5 text-gray-400" />
                      <div className="flex-1 font-medium text-sm">
                        {MODULE_LABELS[module]}
                      </div>
                      <div className="flex gap-1">
                        <button
                          onClick={() => moveModule(module, 'up')}
                          disabled={index === 0}
                          className="p-1 text-gray-600 hover:bg-gray-100 rounded disabled:opacity-30 disabled:cursor-not-allowed"
                          title="上移"
                        >
                          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
                          </svg>
                        </button>
                        <button
                          onClick={() => moveModule(module, 'down')}
                          disabled={index === config.moduleOrder.length - 1}
                          className="p-1 text-gray-600 hover:bg-gray-100 rounded disabled:opacity-30 disabled:cursor-not-allowed"
                          title="下移"
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

            {/* 底部提示 */}
            <div className="p-3 bg-gray-50 border-t border-gray-200 rounded-b-lg">
              <p className="text-xs text-gray-500">
                💡 提示：设置会自动保存到浏览器
              </p>
            </div>
          </div>
        </>
      )}
    </div>
  )
}

