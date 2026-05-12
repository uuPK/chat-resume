import { defineRouting } from 'next-intl/routing'

export const locales = ['zh', 'en'] as const
export type AppLocale = (typeof locales)[number]

export const defaultLocale: AppLocale = 'zh'
export const localeCookieName = 'NEXT_LOCALE'

// Central locale routing contract for UI routes and proxy negotiation.
export const routing = defineRouting({
  locales,
  defaultLocale,
  localePrefix: 'always',
  localeDetection: true,
})

export function isAppLocale(value: string | undefined): value is AppLocale {
  return locales.includes(value as AppLocale)
}

export function toInterviewLanguage(locale: AppLocale): 'zh-CN' | 'en-US' {
  return locale === 'zh' ? 'zh-CN' : 'en-US'
}
