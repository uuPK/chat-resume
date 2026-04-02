import ResumePreview from '@/components/preview/ResumePreview'

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
    }
  } catch {
    return null
  }
}

export default function ResumePrintPage({ searchParams }: PageProps) {
  const payload = decodePayload(searchParams?.data)
  const content = payload?.content

  if (!content) {
    return (
      <main className="bg-white flex items-center justify-center text-gray-500">
        <p>打印数据无效</p>
      </main>
    )
  }

  return (
    <main className="bg-white">
      <ResumePreview content={content} />
    </main>
  )
}
