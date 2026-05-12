import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import Providers from '../providers'
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

export default function PrintRootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="zh" data-scroll-behavior="smooth">
      <body className={inter.className}>
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
