'use client'

import { useState } from 'react'
import { CheckIcon, ArrowRightIcon } from '@heroicons/react/24/outline'

interface Suggestion {
  suggestion_type: string  // "content_change" | "structure_advice" | "general_feedback"
  section: string         // "work_experience" | "education" | "projects" | "skills" | "general"
  original_content?: string  // 原始内容
  suggested_content: string  // 建议内容
  reasoning: string      // 建议理由
  apply_action?: string  // 应用操作类型
}

interface SuggestionCardProps {
  suggestion: Suggestion
  onApply: (suggestion: Suggestion) => Promise<void>
  onDismiss?: (suggestion: Suggestion) => void
}

export default function SuggestionCard({ 
  suggestion, 
  onApply, 
  onDismiss 
}: SuggestionCardProps) {
  const [isApplying, setIsApplying] = useState(false)
  const [isApplied, setIsApplied] = useState(false)

  const handleApply = async () => {
    if (isApplying || isApplied) return
    
    setIsApplying(true)
    try {
      await onApply(suggestion)
      setIsApplied(true)
    } catch (error) {
      console.error('Failed to apply suggestion:', error)
      // 可以添加错误提示
    } finally {
      setIsApplying(false)
    }
  }

  const getSectionDisplayName = (section: string) => {
    const names = {
      'work_experience': '工作经历',
      'projects': '项目经验',
      'education': '教育背景',
      'skills': '技能清单',
      'general': '通用建议'
    }
    return names[section as keyof typeof names] || section
  }

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'content_change':
        return '✏️'
      case 'structure_advice':
        return '🏗️'
      case 'general_feedback':
        return '💡'
      default:
        return '📝'
    }
  }

  if (suggestion.suggestion_type === 'content_change' && suggestion.original_content) {
    // 内容修改建议卡片
    return (
      <div className="bg-gradient-to-r from-blue-50 to-indigo-50 border border-blue-200 rounded-lg p-4 my-3 shadow-sm">
        <div className="flex items-start justify-between mb-3">
          <div>
            <span className="text-xs bg-blue-100 text-blue-700 px-2 py-1 rounded-full">
              {getTypeIcon(suggestion.suggestion_type)} {getSectionDisplayName(suggestion.section)}
            </span>
          </div>
          {onDismiss && !isApplied && (
            <button
              onClick={() => onDismiss(suggestion)}
              className="text-gray-400 hover:text-gray-600 text-sm"
            >
              ✕
            </button>
          )}
        </div>

        <div className="space-y-3">
          {/* 原文显示 */}
          <div>
            <p className="text-xs text-gray-500 mb-1">原文：</p>
            <div className="bg-gray-100 p-3 rounded text-sm text-gray-700 border-l-4 border-gray-300">
              {suggestion.original_content}
            </div>
          </div>

          {/* 箭头指示 */}
          <div className="flex justify-center">
            <ArrowRightIcon className="w-5 h-5 text-blue-500" />
          </div>

          {/* 建议内容 */}
          <div>
            <p className="text-xs text-gray-500 mb-1">建议改为：</p>
            <div className="bg-white p-3 rounded text-sm text-gray-900 border-l-4 border-blue-400 shadow-sm">
              {suggestion.suggested_content}
            </div>
          </div>

          {/* 理由说明 */}
          {suggestion.reasoning && (
            <div className="bg-blue-50 p-2 rounded text-xs text-blue-700">
              <strong>💡 优化理由：</strong>{suggestion.reasoning}
            </div>
          )}

          {/* 操作按钮 */}
          <div className="flex space-x-2 pt-2">
            {!isApplied ? (
              <button
                onClick={handleApply}
                disabled={isApplying}
                className={`flex-1 flex items-center justify-center space-x-2 py-2 px-4 rounded-lg text-sm font-medium transition-colors ${
                  isApplying
                    ? 'bg-gray-300 text-gray-500 cursor-not-allowed'
                    : 'bg-blue-600 text-white hover:bg-blue-700'
                }`}
              >
                {isApplying ? (
                  <>
                    <div className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin"></div>
                    <span>应用中...</span>
                  </>
                ) : (
                  <>
                    <CheckIcon className="w-4 h-4" />
                    <span>采纳并应用</span>
                  </>
                )}
              </button>
            ) : (
              <div className="flex-1 flex items-center justify-center space-x-2 py-2 px-4 rounded-lg text-sm bg-green-100 text-green-700">
                <CheckIcon className="w-4 h-4" />
                <span>已应用</span>
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  // 通用建议卡片（结构建议、一般反馈等）
  return (
    <div className="bg-gradient-to-r from-yellow-50 to-orange-50 border border-yellow-200 rounded-lg p-4 my-3 shadow-sm">
      <div className="flex items-start justify-between mb-3">
        <div>
          <span className="text-xs bg-yellow-100 text-yellow-700 px-2 py-1 rounded-full">
            {getTypeIcon(suggestion.suggestion_type)} {getSectionDisplayName(suggestion.section)}
          </span>
        </div>
        {onDismiss && (
          <button
            onClick={() => onDismiss(suggestion)}
            className="text-gray-400 hover:text-gray-600 text-sm"
          >
            ✕
          </button>
        )}
      </div>

      <div className="space-y-3">
        {/* 建议内容 */}
        <div className="bg-white p-3 rounded text-sm text-gray-900 border-l-4 border-yellow-400 shadow-sm">
          {suggestion.suggested_content}
        </div>

        {/* 理由说明 */}
        {suggestion.reasoning && (
          <div className="bg-yellow-50 p-2 rounded text-xs text-yellow-700">
            <strong>💡 建议理由：</strong>{suggestion.reasoning}
          </div>
        )}

        {/* 这类建议通常不需要"应用"按钮，因为它们是指导性的 */}
        <div className="text-xs text-gray-500 text-center pt-2">
          这是一条指导性建议，请根据具体情况调整简历内容
        </div>
      </div>
    </div>
  )
}