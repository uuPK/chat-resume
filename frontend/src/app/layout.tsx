import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import Providers from './providers'
import './globals.css'
import '../styles/markdown.css'

const inter = Inter({ 
  subsets: ['latin'],
  fallback: ['system-ui', 'arial'],
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'Chat Resume - AI驱动的智能简历优化平台',
  description: '使用AI技术优化简历，提供模拟面试训练，帮助您获得理想工作',
  keywords: '简历优化, AI简历, 模拟面试, 求职, 简历制作',
  authors: [{ name: 'Chat Resume Team' }],
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh-CN">
      <body className={inter.className}>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
