// 用于将简历详情根路径统一跳转到编辑页。
import { redirect } from 'next/navigation'

interface ResumeDetailPageProps {
  params: Promise<{
    id: string
    locale: string
  }>
}

// 用于兼容访问简历详情根路径的旧入口。
export default async function ResumeDetailPage({ params }: ResumeDetailPageProps) {
  const { id, locale } = await params

  redirect(`/${locale}/resume/${encodeURIComponent(id)}/edit`)
}
