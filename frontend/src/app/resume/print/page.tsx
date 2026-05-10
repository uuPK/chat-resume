import ResumePreview from '@/components/preview/ResumePreview'
import type { ResumeTemplateStyle } from '@/types/resumeLayout'

export const dynamic = 'force-dynamic'

interface PageProps {
  searchParams?: {
    data?: string
  }
}

function decodePayload(data?: string) {
  if (!data) {
    return null
  }

  try {
    const json = Buffer.from(data, 'base64url').toString('utf-8')
    return JSON.parse(json) as {
      content?: Record<string, unknown>
      template?: string
    }
  } catch {
    return null
  }
}

function normalizeTemplateStyle(template?: string): ResumeTemplateStyle {
  return template === 'modern' ? 'modern' : 'classic'
}

export default function ResumePrintPage({ searchParams }: PageProps) {
  const payload = decodePayload(searchParams?.data)
  const content = payload?.content
  const templateStyle = normalizeTemplateStyle(payload?.template)

  if (!content) {
    return (
      <main className="bg-white flex items-center justify-center text-gray-500">
        <p>打印数据无效</p>
      </main>
    )
  }

  return (
    <main className="bg-white">
      <ResumePreview content={content} templateStyle={templateStyle} />
    </main>
  )
}
