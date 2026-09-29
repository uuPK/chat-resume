// 用于提供 app/(print)/resume/print/page.tsx 模块。
import { getTranslations } from 'next-intl/server'
import PrintResumeClient, { type PrintPayload } from './PrintResumeClient'

export const dynamic = 'force-dynamic'

interface PageProps {
  searchParams?: Promise<{
    data?: string
  }>
}

// 用于解码载荷。
function decodePayload(data?: string) {
  if (!data) {
    return null
  }

  try {
    const json = Buffer.from(data, 'base64url').toString('utf-8')
    return JSON.parse(json) as PrintPayload
  } catch {
    return null
  }
}

// 用于渲染 ResumePrintPage 组件。
export default async function ResumePrintPage({ searchParams }: PageProps) {
  const t = await getTranslations({ locale: 'zh', namespace: 'resume.preview' })
  const resolvedSearchParams = await searchParams
  const payload = decodePayload(resolvedSearchParams?.data)
  return <PrintResumeClient initialPayload={payload} invalidMessage={t('invalidPrintData')} />
}
