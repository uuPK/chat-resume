'use client'
// 用于提供 components/i18n/LocaleSwitcher.tsx 模块。

import { useLocale, useTranslations } from 'next-intl'
import { useTransition } from 'react'
import { usePathname, useRouter } from '@/i18n/navigation'
import { localeCookieName, type AppLocale } from '@/i18n/routing'
import { LanguageIcon } from '@heroicons/react/24/outline'

const COOKIE_MAX_AGE_SECONDS = 60 * 60 * 24 * 365

// Lets users change UI language without leaving the current route.
// 用于渲染 LocaleSwitcher 组件。
export default function LocaleSwitcher({ compact = false }: { compact?: boolean }) {
  const locale = useLocale() as AppLocale
  const pathname = usePathname()
  const router = useRouter()
  const t = useTranslations('common.localeSwitcher')
  const [isPending, startTransition] = useTransition()
  const nextLocale: AppLocale = locale === 'zh' ? 'en' : 'zh'

  // 用于切换语言环境。
  const switchLocale = () => {
    document.cookie = `${localeCookieName}=${nextLocale}; path=/; max-age=${COOKIE_MAX_AGE_SECONDS}; SameSite=Lax`
    startTransition(() => {
      router.replace(pathname, { locale: nextLocale })
    })
  }

  return (
    <button
      type="button"
      aria-label={t(`aria.${nextLocale}`)}
      disabled={isPending}
      onClick={switchLocale}
      className="inline-flex items-center justify-center gap-1.5 text-sm font-semibold transition-colors disabled:opacity-60"
      style={{
        minWidth: compact ? '54px' : '66px',
        height: compact ? '34px' : '38px',
        padding: compact ? '0 10px' : '0 12px',
        borderRadius: '56px',
        color: '#3f4654',
        border: '1px solid rgba(91,97,110,0.16)',
        backgroundColor: '#f7f8fa',
      }}
    >
      <LanguageIcon className="h-4 w-4" />
      <span>{t(`label.${nextLocale}`)}</span>
    </button>
  )
}
