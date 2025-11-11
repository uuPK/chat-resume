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
}

export default function PersonalInfoPreview({ data }: PersonalInfoPreviewProps) {
  if (!data || (!data.name && !data.email && !data.phone)) {
    return null
  }

  return (
    <div className="mb-5">
      {/* 姓名和职位 */}
      <div className="text-center mb-4">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">
          {data.name || '姓名'}
        </h1>
        {data.position && (
          <p className="text-lg text-gray-600 font-medium">
            {data.position}
          </p>
        )}
      </div>

      {/* 联系方式 */}
      <div className="flex flex-wrap justify-center gap-3 text-xs text-gray-600 pb-4 border-b border-gray-200">
        {data.email && (
          <div className="flex items-center gap-1">
            <EnvelopeIcon className="w-4 h-4" />
            <span>{data.email}</span>
          </div>
        )}
        
        {data.phone && (
          <div className="flex items-center gap-1">
            <PhoneIcon className="w-4 h-4" />
            <span>{data.phone}</span>
          </div>
        )}
        
        {data.address && (
          <div className="flex items-center gap-1">
            <MapPinIcon className="w-4 h-4" />
            <span>{data.address}</span>
          </div>
        )}
      </div>

      {/* 在线链接 */}
      {(data.github || data.linkedin || data.website) && (
        <div className="flex flex-wrap justify-center gap-3 text-xs text-blue-600 pt-3">
          {data.github && (
            <div className="flex items-center gap-1">
              <LinkIcon className="w-4 h-4" />
              <a href={data.github} target="_blank" rel="noopener noreferrer" className="hover:underline">
                GitHub
              </a>
            </div>
          )}
          
          {data.linkedin && (
            <div className="flex items-center gap-1">
              <LinkIcon className="w-4 h-4" />
              <a href={data.linkedin} target="_blank" rel="noopener noreferrer" className="hover:underline">
                LinkedIn
              </a>
            </div>
          )}
          
          {data.website && (
            <div className="flex items-center gap-1">
              <LinkIcon className="w-4 h-4" />
              <a href={data.website} target="_blank" rel="noopener noreferrer" className="hover:underline">
                个人网站
              </a>
            </div>
          )}
        </div>
      )}
    </div>
  )
}