// 用于提供 app/(print)/layout.tsx 模块。
import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import { NextIntlClientProvider } from 'next-intl'
import '../globals.css'
import '../../styles/markdown.css'

const inter = Inter({
  subsets: ['latin'],
  fallback: ['system-ui', 'arial'],
  display: 'swap',
})

export const metadata: Metadata = {
  title: 'Chat Resume',
  description: 'AI resume optimization and mock interview platform',
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#2563eb',
}

// 用于渲染 PrintRootLayout 组件。
export default function PrintRootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh" data-scroll-behavior="smooth">
      <body className={inter.className}>
        <NextIntlClientProvider>{children}</NextIntlClientProvider>
      </body>
    </html>
  )
}
