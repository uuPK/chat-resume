'use client'

interface Education {
  id?: number
  school: string
  major: string
  degree: string
  duration: string
  description?: string
}

interface EducationPreviewProps {
  data: Education[]
}

export default function EducationPreview({ data }: EducationPreviewProps) {
  if (!data || data.length === 0) {
    return null
  }

  return (
    <div className="mb-5 print:break-inside-avoid">
      <h2 className="text-lg font-bold text-gray-900 mb-3 pb-1.5 border-b border-gray-300">
        教育背景
      </h2>
      
      <div className="space-y-3">
        {data.map((edu, index) => (
          <div key={edu.id || index} className="relative print:break-inside-avoid">
            <div className="flex justify-between items-start mb-1">
              <div className="flex-1">
                <h3 className="font-semibold text-gray-900">
                  {edu.school}
                </h3>
                <p className="text-gray-700">
                  {edu.major} · {edu.degree}
                </p>
              </div>
              <div className="text-sm text-gray-600 ml-4">
                {edu.duration}
              </div>
            </div>
            
            {edu.description && (
              <p className="text-sm text-gray-600 mt-1.5 leading-relaxed">
                {edu.description}
              </p>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}