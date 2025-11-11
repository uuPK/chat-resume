'use client'

import { useState } from 'react'
import { ModuleConfig, DEFAULT_MODULE_ORDER } from '@/components/preview/PaginatedResumePreview'
import { 
  ArrowUpIcon, 
  ArrowDownIcon,
  EyeIcon,
  EyeSlashIcon 
} from '@heroicons/react/24/outline'

interface ModuleOrderEditorProps {
  moduleOrder?: ModuleConfig[]
  onChange: (newOrder: ModuleConfig[]) => void
}

export default function ModuleOrderEditor({ 
  moduleOrder = DEFAULT_MODULE_ORDER, 
  onChange 
}: ModuleOrderEditorProps) {
  const [modules, setModules] = useState<ModuleConfig[]>(moduleOrder)

  // 移动模块位置
  const moveModule = (index: number, direction: 'up' | 'down') => {
    const newModules = [...modules]
    const targetIndex = direction === 'up' ? index - 1 : index + 1
    
    if (targetIndex < 0 || targetIndex >= modules.length) return
    
    // 交换order值
    const temp = newModules[index].order
    newModules[index] = { ...newModules[index], order: newModules[targetIndex].order }
    newModules[targetIndex] = { ...newModules[targetIndex], order: temp }
    
    // 按order排序
    newModules.sort((a, b) => a.order - b.order)
    
    setModules(newModules)
    onChange(newModules)
  }

  // 切换模块可见性
  const toggleVisibility = (index: number) => {
    const newModules = [...modules]
    newModules[index] = { 
      ...newModules[index], 
      visible: !newModules[index].visible 
    }
    setModules(newModules)
    onChange(newModules)
  }

  // 重置为默认顺序
  const resetToDefault = () => {
    setModules(DEFAULT_MODULE_ORDER)
    onChange(DEFAULT_MODULE_ORDER)
  }

  // 应用预设配置
  const applyPreset = (preset: 'fresh-graduate' | 'senior-engineer' | 'tech-expert') => {
    let newOrder: ModuleConfig[] = []
    
    switch (preset) {
      case 'fresh-graduate':
        // 应届生：突出教育和项目
        newOrder = [
          { type: 'personal', visible: true, order: 0, label: '个人信息' },
          { type: 'education', visible: true, order: 1, label: '教育背景' },
          { type: 'projects', visible: true, order: 2, label: '项目经验' },
          { type: 'skills', visible: true, order: 3, label: '技能专长' },
          { type: 'work', visible: true, order: 4, label: '实习经验' },
        ]
        break
      
      case 'senior-engineer':
        // 资深工程师：突出工作经验
        newOrder = [
          { type: 'personal', visible: true, order: 0, label: '个人信息' },
          { type: 'work', visible: true, order: 1, label: '工作经验' },
          { type: 'skills', visible: true, order: 2, label: '技能专长' },
          { type: 'projects', visible: true, order: 3, label: '核心项目' },
          { type: 'education', visible: true, order: 4, label: '教育背景' },
        ]
        break
      
      case 'tech-expert':
        // 技术专家：突出技能和项目
        newOrder = [
          { type: 'personal', visible: true, order: 0, label: '个人信息' },
          { type: 'skills', visible: true, order: 1, label: '技术栈' },
          { type: 'projects', visible: true, order: 2, label: '开源项目' },
          { type: 'work', visible: true, order: 3, label: '工作经历' },
          { type: 'education', visible: false, order: 4, label: '教育背景' },
        ]
        break
    }
    
    setModules(newOrder)
    onChange(newOrder)
  }

  return (
    <div className="space-y-4">
      {/* 预设模板 */}
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          快速应用预设
        </label>
        <div className="grid grid-cols-3 gap-2">
          <button
            onClick={() => applyPreset('fresh-graduate')}
            className="px-3 py-2 text-sm bg-blue-50 hover:bg-blue-100 text-blue-700 rounded-lg transition-colors"
          >
            应届生模板
          </button>
          <button
            onClick={() => applyPreset('senior-engineer')}
            className="px-3 py-2 text-sm bg-purple-50 hover:bg-purple-100 text-purple-700 rounded-lg transition-colors"
          >
            资深工程师
          </button>
          <button
            onClick={() => applyPreset('tech-expert')}
            className="px-3 py-2 text-sm bg-green-50 hover:bg-green-100 text-green-700 rounded-lg transition-colors"
          >
            技术专家
          </button>
        </div>
      </div>

      {/* 模块列表 */}
      <div>
        <div className="flex items-center justify-between mb-2">
          <label className="block text-sm font-medium text-gray-700">
            自定义模块顺序
          </label>
          <button
            onClick={resetToDefault}
            className="text-xs text-gray-600 hover:text-gray-900 underline"
          >
            重置默认
          </button>
        </div>
        
        <div className="space-y-2">
          {modules.map((module, index) => (
            <div
              key={module.type}
              className={`flex items-center gap-2 p-3 rounded-lg border ${
                module.visible 
                  ? 'bg-white border-gray-200' 
                  : 'bg-gray-50 border-gray-200 opacity-60'
              }`}
            >
              {/* 排序序号 */}
              <div className="flex-shrink-0 w-8 h-8 rounded-full bg-blue-100 text-blue-700 flex items-center justify-center text-sm font-semibold">
                {index + 1}
              </div>

              {/* 模块名称 */}
              <div className="flex-1">
                <span className={`text-sm font-medium ${
                  module.visible ? 'text-gray-900' : 'text-gray-500'
                }`}>
                  {module.label}
                </span>
              </div>

              {/* 控制按钮 */}
              <div className="flex items-center gap-1">
                {/* 上移 */}
                <button
                  onClick={() => moveModule(index, 'up')}
                  disabled={index === 0}
                  className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  title="上移"
                >
                  <ArrowUpIcon className="w-4 h-4 text-gray-600" />
                </button>

                {/* 下移 */}
                <button
                  onClick={() => moveModule(index, 'down')}
                  disabled={index === modules.length - 1}
                  className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  title="下移"
                >
                  <ArrowDownIcon className="w-4 h-4 text-gray-600" />
                </button>

                {/* 显示/隐藏 */}
                <button
                  onClick={() => toggleVisibility(index)}
                  disabled={module.type === 'personal'} // 个人信息不允许隐藏
                  className="p-1.5 rounded hover:bg-gray-100 disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
                  title={module.visible ? '隐藏模块' : '显示模块'}
                >
                  {module.visible ? (
                    <EyeIcon className="w-4 h-4 text-gray-600" />
                  ) : (
                    <EyeSlashIcon className="w-4 h-4 text-gray-600" />
                  )}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* 提示信息 */}
      <div className="text-xs text-gray-500 bg-gray-50 p-3 rounded-lg">
        <p className="mb-1">💡 <strong>使用提示：</strong></p>
        <ul className="list-disc list-inside space-y-1 ml-2">
          <li>使用上下箭头调整模块显示顺序</li>
          <li>点击眼睛图标隐藏/显示模块</li>
          <li>个人信息模块始终保持在顶部</li>
          <li>更改会实时反映在右侧预览中</li>
        </ul>
      </div>
    </div>
  )
}

