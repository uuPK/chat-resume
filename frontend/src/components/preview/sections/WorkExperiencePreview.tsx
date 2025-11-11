'use client'

interface WorkExperience {
  id?: number
  company: string
  position: string
  duration: string
  description: string
}

interface WorkExperiencePreviewProps {
  data: WorkExperience[]
}

export default function WorkExperiencePreview({ data }: WorkExperiencePreviewProps) {
  if (!data || data.length === 0) {
    return null
  }

  return (
    <div className="mb-5 print:break-inside-avoid">
      <h2 className="text-lg font-bold text-gray-900 mb-3 pb-1.5 border-b border-gray-300">
        工作经验
      </h2>
      
      <div className="space-y-4">
        {data.map((work, index) => (
          <div key={work.id || index} className="relative print:break-inside-avoid">
            <div className="flex justify-between items-start mb-1.5">
              <div className="flex-1">
                <h3 className="font-semibold text-gray-900">
                  {work.position}
                </h3>
                <p className="text-gray-700 font-medium">
                  {work.company}
                </p>
              </div>
              <div className="text-sm text-gray-600 ml-4 whitespace-nowrap">
                {work.duration}
              </div>
            </div>
            
            {work.description && (
              <div className="text-sm text-gray-600 mt-2 leading-relaxed">
                {work.description.split('\n').map((line, lineIndex) => (
                  <p key={lineIndex} className="mb-0.5">
                    {line}
                  </p>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}