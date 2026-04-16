import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

interface StreamingMessageProps {
  content: string
  isComplete?: boolean
  className?: string
}

export default function StreamingMessage({ 
  content, 
  isComplete = false, 
  className = '' 
}: StreamingMessageProps) {
  return (
    <div className={`markdown-content ${className}`}>
      <ReactMarkdown
        remarkPlugins={[remarkGfm]}
        components={{
          h1: ({ children }) => <h1 className="text-[18px] font-bold text-gray-900 mb-3">{children}</h1>,
          h2: ({ children }) => <h2 className="text-[16px] font-semibold text-gray-900 mb-2">{children}</h2>,
          h3: ({ children }) => <h3 className="text-[15px] font-medium text-gray-900 mb-2">{children}</h3>,
          p: ({ children }) => <p className="text-[14px] text-gray-700 mb-2 last:mb-0">{children}</p>,
          ul: ({ children }) => <ul className="list-disc list-inside text-[14px] text-gray-700 mb-2 space-y-1">{children}</ul>,
          ol: ({ children }) => <ol className="list-decimal list-inside text-[14px] text-gray-700 mb-2 space-y-1">{children}</ol>,
          li: ({ children }) => <li className="text-[14px]">{children}</li>,
          code: ({ children, ...props }) => 
            (props as any).inline ? (
              <code className="bg-gray-100 text-gray-800 px-1 py-0.5 rounded text-xs font-mono">
                {children}
              </code>
            ) : (
              <code className="block bg-gray-100 text-gray-800 p-3 rounded-lg text-xs font-mono overflow-x-auto">
                {children}
              </code>
            ),
          pre: ({ children }) => <pre className="bg-gray-100 p-3 rounded-lg overflow-x-auto mb-2">{children}</pre>,
          blockquote: ({ children }) => (
            <blockquote className="border-l-4 border-gray-300 pl-4 py-2 bg-gray-50 text-[14px] text-gray-600 mb-2 rounded-r">
              {children}
            </blockquote>
          ),
          strong: ({ children }) => <strong className="font-semibold text-gray-900">{children}</strong>,
          em: ({ children }) => <em className="italic text-gray-700">{children}</em>,
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
          table: ({ children }) => (
            <div className="mb-2 w-full overflow-x-auto rounded-lg border border-gray-200">
              <table className="min-w-full border-collapse text-xs">
                {children}
              </table>
            </div>
          ),
          th: ({ children }) => (
            <th className="border border-gray-200 bg-gray-50 px-3 py-2 text-left font-medium text-gray-700 whitespace-nowrap">
              {children}
            </th>
          ),
          td: ({ children }) => (
            <td className="border border-gray-200 px-3 py-2 align-top text-gray-700">
              {children}
            </td>
          ),
          img: ({ src = '', alt = '' }) => (
            <img
              src={src}
              alt={alt as string}
              className="my-2 max-w-[240px] border border-gray-200 rounded-lg shadow-sm"
            />
          ),
        }}
      >
        {content}
      </ReactMarkdown>
      
      {/* 显示流式传输光标 */}
      {!isComplete && content && (
        <span className="inline-block w-0.5 h-4 bg-blue-600 animate-pulse ml-1" />
      )}
    </div>
  )
}
