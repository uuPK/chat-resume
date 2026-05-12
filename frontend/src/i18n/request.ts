import { hasLocale } from 'next-intl'
import { getRequestConfig } from 'next-intl/server'
import { routing } from './routing'

const namespaces = ['common', 'auth', 'dashboard', 'interview', 'resume'] as const

async function loadMessages(locale: string) {
  // Loads all configured namespaces into the shape expected by next-intl.
  const entries = await Promise.all(
    namespaces.map(async (namespace) => [
      namespace,
      (await import(`../../locales/${locale}/${namespace}.json`)).default,
    ])
  )
  return Object.fromEntries(entries)
}

export default getRequestConfig(async ({ requestLocale }) => {
  const requested = await requestLocale
  const locale = hasLocale(routing.locales, requested)
    ? requested
    : routing.defaultLocale

  return {
    locale,
    messages: await loadMessages(locale),
  }
})
