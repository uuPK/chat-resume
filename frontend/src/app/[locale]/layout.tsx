// 用于提供 app/[locale]/layout.tsx 模块。
import type { Metadata, Viewport } from 'next'
import { Inter } from 'next/font/google'
import { hasLocale } from 'next-intl'
import { NextIntlClientProvider } from 'next-intl'
import { notFound } from 'next/navigation'
import Providers from '../providers'
import { routing, type AppLocale } from '@/i18n/routing'
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
  keywords: 'resume optimization, AI resume, mock interview, job search',
  authors: [{ name: 'Chat Resume Team' }],
  icons: {
    icon: '/favicon.ico',
    apple: '/apple-touch-icon.png',
  },
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#2563eb',
}

export const dynamicParams = true

// 用于渲染 RootLayout 组件。
export default function RootLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ locale: string }>
}) {
  return <LocaleRootLayout params={params}>{children}</LocaleRootLayout>
}

// 用于生成静态参数。
export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }))
}

// 用于渲染 LocaleRootLayout 组件。
async function LocaleRootLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ locale: string }>
}) {
  const { locale } = await params
  if (!hasLocale(routing.locales, locale)) {
    notFound()
  }

  return (
    <html
      lang={locale as AppLocale}
      data-scroll-behavior="smooth"
      suppressHydrationWarning
    >
      <body className={inter.className}>
        <NextIntlClientProvider>
          <Providers>{children}</Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  )
}
