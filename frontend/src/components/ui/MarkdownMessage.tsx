// 用于提供 components/ui/MarkdownMessage.tsx 模块。
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { useState } from 'react'
import { DocumentDuplicateIcon, CheckIcon } from '@heroicons/react/24/outline'
import { useTranslations } from 'next-intl'
import { normalizeAiMarkdown } from '@/lib/markdown'

interface MarkdownMessageProps {
  content: string
  className?: string
}

// 用于渲染 MarkdownMessage 组件。
export default function MarkdownMessage({ content, className = '' }: MarkdownMessageProps) {
  const [copied, setCopied] = useState(false)
  const t = useTranslations('resume.preview')
  const displayContent = normalizeAiMarkdown(content)

  // 用于处理复制。
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(content)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    } catch (err) {
      console.error('Failed to copy text: ', err)
    }
  }

  return (
    <div className={`markdown-content relative group ${className}`}>
      {/* 复制按钮 */}
      <button
        onClick={handleCopy}
        className="absolute top-2 right-2 p-1.5 rounded-md bg-white shadow-sm border border-gray-200 opacity-0 group-hover:opacity-100 transition-opacity duration-200 hover:bg-gray-50"
        title={copied ? t('copied') : t('copy')}
      >
        {copied ? (
          <CheckIcon className="w-4 h-4 text-green-600" />
        ) : (
          <DocumentDuplicateIcon className="w-4 h-4 text-gray-600" />
        )}
      </button>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          // 自定义标题样式
          h1: ({ children }) => (
            <h1 className="text-[18px] font-bold mb-3 text-gray-900">{children}</h1>
          ),
          // 用于处理h2。
          h2: ({ children }) => (
            <h2 className="text-[16px] font-semibold mb-2 text-gray-800">{children}</h2>
          ),
          // 用于处理h3。
          h3: ({ children }) => (
            <h3 className="text-[15px] font-medium mb-2 text-gray-700">{children}</h3>
          ),
          
          // 自定义段落样式
          p: ({ children }) => (
            <p className="mb-3 leading-relaxed text-[14px] text-gray-700 last:mb-0">{children}</p>
          ),
          
          // 自定义列表样式
          ul: ({ children }) => (
            <ul className="mb-3 ml-4 space-y-1">{children}</ul>
          ),
          // 用于处理ol。
          ol: ({ children }) => (
            <ol className="mb-3 ml-4 space-y-1 list-decimal">{children}</ol>
          ),
          // 用于处理li。
          li: ({ children }) => (
            <li className="text-[14px] text-gray-700 leading-relaxed">{children}</li>
          ),
          
          // 自定义强调样式
          strong: ({ children }) => (
            <strong className="font-semibold text-gray-900">{children}</strong>
          ),
          // 用于处理em。
          em: ({ children }) => (
            <em className="italic text-gray-800">{children}</em>
          ),
          
          // 自定义代码样式
          code: ({ children, className }) => {
            const isInline = !className
            if (isInline) {
              return (
                <code className="px-1.5 py-0.5 bg-gray-100 text-gray-800 rounded text-xs font-mono">
                  {children}
                </code>
              )
            }
            return (
              <code className="block p-3 bg-gray-50 text-gray-800 rounded-md text-xs font-mono whitespace-pre-wrap overflow-x-auto">
                {children}
              </code>
            )
          },
          
          // 自定义引用样式
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-blue-200 pl-4 py-2 mb-3 bg-blue-50 text-gray-700 italic">
              {children}
            </blockquote>
          ),
          
          // 自定义分割线
          hr: () => (
            <hr className="my-4 border-gray-200" />
          ),
          
          // 自定义链接样式
          a: ({ children, href }) => (
            <a 
              href={href} 
              className="text-blue-600 hover:text-blue-800 underline"
              target="_blank"
              rel="noopener noreferrer"
            >
              {children}
            </a>
          ),
          // 用于处理table。
          table: ({ children }) => (
            <div className="mb-3 w-full overflow-x-auto rounded-lg border border-gray-200">
              <table className="min-w-full border-collapse text-xs">
                {children}
              </table>
            </div>
          ),
          // 用于处理th。
          th: ({ children }) => (
            <th className="border border-gray-200 bg-gray-50 px-3 py-2 text-left font-medium text-gray-700 whitespace-nowrap">
              {children}
            </th>
          ),
          // 用于处理td。
          td: ({ children }) => (
            <td className="border border-gray-200 px-3 py-2 align-top text-gray-700">
              {children}
            </td>
          ),
          // 用于处理img。
          img: ({ src = '', alt = '' }) => (
            <img
              src={src}
              alt={alt as string}
              className="my-2 max-w-[240px] border border-gray-200 rounded-lg shadow-sm"
            />
          ),
        }}
      >
        {displayContent}
      </ReactMarkdown>
    </div>
  )
}
