'use client'

import { 
  EnvelopeIcon, 
  PhoneIcon,
  LinkIcon,
  MapPinIcon
} from '@heroicons/react/24/outline'

interface PersonalInfo {
  name?: string
  email?: string
  phone?: string
  position?: string
  github?: string
  linkedin?: string
  website?: string
  address?: string
}

interface PersonalInfoPreviewProps {
  data: PersonalInfo
  renderLines?: number[] // 指定渲染哪些行，undefined表示全部
}

export default function PersonalInfoPreview({ data, renderLines }: PersonalInfoPreviewProps) {
  if (!data || (!data.name && !data.email && !data.phone)) {
    return null
  }

  const shouldRenderLine = (lineIndex: number) => {
    return !renderLines || renderLines.includes(lineIndex)
  }

  return (
    <div className="mb-5">
      {/* 姓名和职位 */}
      {shouldRenderLine(0) && (
        <div data-line-index={0} className="text-center mb-4">
          <h1 className="text-2xl font-bold text-gray-900 mb-1">
            {data.name || '姓名'}
          </h1>
          {data.position && (
            <p className="text-lg text-gray-600 font-medium">
              {data.position}
            </p>
          )}
        </div>
      )}

      {/* 联系方式 */}
      {shouldRenderLine(1) && (
        <div data-line-index={1} className="flex flex-wrap justify-center gap-4 text-xs text-gray-600 pb-3">
          {data.email && (
            <div className="inline-flex items-center gap-1">
              <EnvelopeIcon className="w-3.5 h-3.5 shrink-0" style={{ transform: 'translateY(2px)' }} />
              <span>{data.email}</span>
            </div>
          )}
          
          {data.phone && (
            <div className="inline-flex items-center gap-1">
              <PhoneIcon className="w-3.5 h-3.5 shrink-0" style={{ transform: 'translateY(2px)' }} />
              <span>{data.phone}</span>
            </div>
          )}
          
          {data.address && (
            <div className="inline-flex items-center gap-1">
              <MapPinIcon className="w-3.5 h-3.5 shrink-0" style={{ transform: 'translateY(2px)' }} />
              <span>{data.address}</span>
            </div>
          )}

          {(data.github || data.linkedin || data.website) && (
            <>
              {data.github && (
                <div className="inline-flex items-center gap-1 text-blue-600">
                  <LinkIcon className="w-3.5 h-3.5 shrink-0" style={{ transform: 'translateY(2px)' }} />
                  <a href={data.github} target="_blank" rel="noopener noreferrer" className="hover:underline">
                    GitHub
                  </a>
                </div>
              )}
              
              {data.linkedin && (
                <div className="inline-flex items-center gap-1 text-blue-600">
                  <LinkIcon className="w-3.5 h-3.5 shrink-0" style={{ transform: 'translateY(2px)' }} />
                  <a href={data.linkedin} target="_blank" rel="noopener noreferrer" className="hover:underline">
                    LinkedIn
                  </a>
                </div>
              )}
              
              {data.website && (
                <div className="inline-flex items-center gap-1 text-blue-600">
                  <LinkIcon className="w-3.5 h-3.5 shrink-0" style={{ transform: 'translateY(2px)' }} />
                  <a href={data.website} target="_blank" rel="noopener noreferrer" className="hover:underline">
                    个人网站
                  </a>
                </div>
              )}
            </>
          )}
        </div>
      )}

      {/* 在线链接占位行保留，避免分页引用 */}
      {(data.github || data.linkedin || data.website) && shouldRenderLine(2) && (
        <div data-line-index={2} className="hidden" />
      )}
    </div>
  )
}
