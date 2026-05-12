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
}

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
  themeColor: '#2563eb',
}

export const dynamicParams = true

export default function RootLayout({
  children,
  params,
}: {
  children: React.ReactNode
  params: Promise<{ locale: string }>
}) {
  return <LocaleRootLayout params={params}>{children}</LocaleRootLayout>
}

export function generateStaticParams() {
  return routing.locales.map((locale) => ({ locale }))
}

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
    <html lang={locale as AppLocale} data-scroll-behavior="smooth">
      <body className={inter.className}>
        <NextIntlClientProvider>
          <Providers>{children}</Providers>
        </NextIntlClientProvider>
      </body>
    </html>
  )
}
