'use client'
// 用于提供 app/[locale]/login/page.tsx 模块。

export const dynamic = 'force-dynamic'

import { motion } from 'framer-motion'
import { Link } from '@/i18n/navigation'
import { Suspense, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useSearchParams } from 'next/navigation'
import { useAuth } from '@/lib/auth'
import { getOAuthErrorKey } from '@/lib/oauthErrors'
import toast from 'react-hot-toast'
import { EyeIcon, EyeSlashIcon } from '@heroicons/react/24/outline'
import Logo from '@/components/ui/Logo'
import GoogleContinueLink from '@/components/auth/GoogleContinueLink'
import LocaleSwitcher from '@/components/i18n/LocaleSwitcher'
import { useTranslations } from 'next-intl'
import { isAppLocale } from '@/i18n/routing'

interface LoginForm {
  email: string
  password: string
}

// 只允许站内 next 路径，避免登录后跳到外部地址。
function getSafeNextPath(): string {
  const nextPath = new URLSearchParams(window.location.search).get('next')
  if (!nextPath || !nextPath.startsWith('/') || nextPath.startsWith('//')) {
    return '/dashboard'
  }
  return stripLocaleFromPath(nextPath)
}

// 用于去除语言环境from路径。
function stripLocaleFromPath(path: string): string {
  // Keeps legacy localized next params compatible with the locale-aware router.
  const [pathname, query = ''] = path.split('?')
  const segments = pathname.split('/')
  if (!isAppLocale(segments[1])) return path

  const strippedPathname = `/${segments.slice(2).join('/')}` || '/'
  return query ? `${strippedPathname}?${query}` : strippedPathname
}

// 用于登录成功后跨认证边界做完整页面跳转。
function navigateAfterLogin(path: string) {
  window.location.assign(path)
}

// 登录页，Coinbase 风格：白底深色文字，蓝色 pill 按钮
export default function LoginPage() {
  const [showPassword, setShowPassword] = useState(false)
  const { login, isLoading } = useAuth()
  const { register, handleSubmit, formState: { errors } } = useForm<LoginForm>()
  const t = useTranslations('auth')

  // 用于处理onsubmit。
  const onSubmit = async (data: LoginForm) => {
    try {
      toast.loading(t('login.loadingToast'), { id: 'login' })
      const success = await login(data.email, data.password)
      if (success) {
        toast.success(t('login.successToast'), { id: 'login' })
        navigateAfterLogin(getSafeNextPath())
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : t('login.fallbackError')
      toast.error(message, { id: 'login' })
    }
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: '#ffffff' }}>
      {/* Top bar */}
      <div className="flex items-center justify-between px-8 h-16" style={{ borderBottom: '1px solid rgba(91,97,110,0.15)' }}>
        <Logo size="sm" />
        <LocaleSwitcher compact />
      </div>

      {/* Form section */}
      <div className="flex-1 flex items-center justify-center px-4 py-16">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="w-full max-w-md"
        >
          <div className="mb-10">
            <h1 className="text-5xl font-semibold mb-3" style={{ color: '#0a0b0d', lineHeight: '1.00' }}>
              {t('login.title')}
            </h1>
            <p className="text-lg" style={{ color: '#5b616e', lineHeight: '1.56' }}>
              {t('login.subtitle')}
            </p>
          </div>

          <div
            className="p-8"
            style={{
              background: '#ffffff',
              border: '1px solid rgba(91,97,110,0.2)',
              borderRadius: '24px',
            }}
          >
            <Suspense fallback={null}>
              <OAuthErrorAlert />
            </Suspense>

            <GoogleContinueLink />

            <div className="my-6 flex items-center gap-3">
              <div className="h-px flex-1" style={{ backgroundColor: 'rgba(91,97,110,0.2)' }} />
              <span className="text-sm" style={{ color: '#5b616e' }}>{t('oauth.divider')}</span>
              <div className="h-px flex-1" style={{ backgroundColor: 'rgba(91,97,110,0.2)' }} />
            </div>

            <form className="space-y-5" onSubmit={handleSubmit(onSubmit)}>
              <div>
                <label className="label">{t('fields.email')}</label>
                <input
                  {...register('email', {
                    required: t('validation.emailRequired'),
                    pattern: { value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i, message: t('validation.emailInvalid') }
                  })}
                  type="email"
                  className={errors.email ? 'input-error' : 'input'}
                  placeholder={t('placeholders.email')}
                />
                {errors.email && <p className="mt-1.5 text-sm text-red-600">{errors.email.message}</p>}
              </div>

              <div>
                <div className="flex items-center justify-between gap-4">
                  <label className="label">{t('fields.password')}</label>
                  <Link href="/reset-password" className="text-sm font-semibold" style={{ color: '#0052ff' }}>
                    {t('login.forgotPassword')}
                  </Link>
                </div>
                <div className="relative">
                  <input
                    {...register('password', {
                      required: t('validation.passwordRequired'),
                      minLength: { value: 6, message: t('validation.passwordMin') }
                    })}
                    type={showPassword ? 'text' : 'password'}
                    autoComplete="current-password"
                    className={`${errors.password ? 'input-error' : 'input'} pr-12`}
                    placeholder={t('placeholders.password')}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 px-4 flex items-center"
                    style={{ color: '#9ca3af' }}
                  >
                    {showPassword ? <EyeSlashIcon className="h-5 w-5" /> : <EyeIcon className="h-5 w-5" />}
                  </button>
                </div>
                {errors.password && <p className="mt-1.5 text-sm text-red-600">{errors.password.message}</p>}
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="btn-primary w-full btn-lg"
              >
                {isLoading ? t('login.submitting') : t('login.submit')}
              </button>
            </form>

            <div className="mt-6 text-center text-sm" style={{ color: '#5b616e' }}>
              {t('login.noAccount')}{' '}
              <Link href="/register" className="font-semibold" style={{ color: '#0052ff' }}>
                {t('login.registerNow')}
              </Link>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}

// 用于渲染 OAuthErrorAlert 组件。
function OAuthErrorAlert() {
  const searchParams = useSearchParams()
  const t = useTranslations('auth.oauth.errors')
  const oauthErrorKey = getOAuthErrorKey(searchParams.get('oauth_error'))

  if (!oauthErrorKey) return null

  return (
    <div
      role="alert"
      className="mb-5 rounded-xl px-4 py-3 text-sm font-medium"
      style={{ backgroundColor: '#fff4f2', color: '#b42318', border: '1px solid #ffdad5' }}
    >
      {t(oauthErrorKey)}
    </div>
  )
}
