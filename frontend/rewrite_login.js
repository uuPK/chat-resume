const fs = require('fs');

const content = `'use client'
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
import { EyeIcon, EyeSlashIcon } from '@heroicons/react/24/solid'
import Logo from '@/components/ui/Logo'
import GoogleContinueLink from '@/components/auth/GoogleContinueLink'
import LocaleSwitcher from '@/components/i18n/LocaleSwitcher'
import { useTranslations } from 'next-intl'
import { isAppLocale } from '@/i18n/routing'

interface LoginForm {
  email: string
  password: string
}

function getSafeNextPath(): string {
  const nextPath = new URLSearchParams(window.location.search).get('next')
  if (!nextPath || !nextPath.startsWith('/') || nextPath.startsWith('//')) {
    return '/dashboard'
  }
  return stripLocaleFromPath(nextPath)
}

function stripLocaleFromPath(path: string): string {
  const [pathname, query = ''] = path.split('?')
  const segments = pathname.split('/')
  if (!isAppLocale(segments[1])) return path

  const strippedPathname = \`/\${segments.slice(2).join('/')}\` || '/'
  return query ? \`\${strippedPathname}?\${query}\` : strippedPathname
}

function navigateAfterLogin(path: string) {
  window.location.assign(path)
}

export default function LoginPage() {
  const [showPassword, setShowPassword] = useState(false)
  const { login, isLoading } = useAuth()
  const { register, handleSubmit, formState: { errors } } = useForm<LoginForm>()
  const t = useTranslations('auth')

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
    <div className="min-h-screen flex flex-col bg-transparent">
      {/* Top bar */}
      <div className="flex items-center justify-between px-8 h-16">
        <Logo size="sm" />
        <LocaleSwitcher compact />
      </div>

      {/* Form section */}
      <div className="flex-1 flex items-center justify-center px-4 py-16">
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5, ease: "easeOut" }}
          className="w-full max-w-md"
        >
          <div className="mb-8 text-center">
            <h1 className="text-4xl font-bold tracking-tight text-gray-900 dark:text-gray-100 mb-3">
              {t('login.title')}
            </h1>
            <p className="text-gray-500 dark:text-gray-400">
              {t('login.subtitle')}
            </p>
          </div>

          <div className="p-8 bg-white dark:bg-[#0a0a0a] border border-gray-200 dark:border-gray-800 rounded-3xl shadow-sm">
            <Suspense fallback={null}>
              <OAuthErrorAlert />
            </Suspense>

            <GoogleContinueLink />

            <div className="my-6 flex items-center gap-3">
              <div className="h-px flex-1 bg-gray-200 dark:bg-gray-800" />
              <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">{t('oauth.divider')}</span>
              <div className="h-px flex-1 bg-gray-200 dark:bg-gray-800" />
            </div>

            <form className="space-y-5" onSubmit={handleSubmit(onSubmit)}>
              <div>
                <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">{t('fields.email')}</label>
                <input
                  {...register('email', {
                    required: t('validation.emailRequired'),
                    pattern: { value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\\.[A-Z]{2,}$/i, message: t('validation.emailInvalid') }
                  })}
                  type="email"
                  className={errors.email ? 'input-error' : 'input bg-transparent border-gray-300 dark:border-gray-700 focus:border-primary-500 dark:focus:border-primary-500 text-gray-900 dark:text-white rounded-xl'}
                  placeholder={t('placeholders.email')}
                />
                {errors.email && <p className="mt-1.5 text-sm text-red-500">{errors.email.message}</p>}
              </div>

              <div>
                <div className="flex items-center justify-between gap-4 mb-1.5">
                  <label className="block text-sm font-medium text-gray-700 dark:text-gray-300">{t('fields.password')}</label>
                  <Link href="/reset-password" className="text-sm font-medium text-primary-600 hover:text-primary-500 transition-colors">
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
                    className={\`\${errors.password ? 'input-error' : 'input bg-transparent border-gray-300 dark:border-gray-700 focus:border-primary-500 dark:focus:border-primary-500 text-gray-900 dark:text-white rounded-xl'} pr-12\`}
                    placeholder={t('placeholders.password')}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    className="absolute inset-y-0 right-0 px-4 flex items-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
                  >
                    {showPassword ? <EyeSlashIcon className="h-5 w-5" /> : <EyeIcon className="h-5 w-5" />}
                  </button>
                </div>
                {errors.password && <p className="mt-1.5 text-sm text-red-500">{errors.password.message}</p>}
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="btn-primary w-full py-3 rounded-xl text-base font-semibold transition-all hover:scale-[1.02] active:scale-[0.98]"
              >
                {isLoading ? t('login.submitting') : t('login.submit')}
              </button>
            </form>

            <div className="mt-6 text-center text-sm text-gray-500">
              {t('login.noAccount')}{' '}
              <Link href="/register" className="font-semibold text-primary-600 hover:text-primary-500 transition-colors">
                {t('login.registerNow')}
              </Link>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}

function OAuthErrorAlert() {
  const searchParams = useSearchParams()
  const t = useTranslations('auth.oauth.errors')
  const oauthErrorKey = getOAuthErrorKey(searchParams.get('oauth_error'))

  if (!oauthErrorKey) return null

  return (
    <div
      role="alert"
      className="mb-5 rounded-xl px-4 py-3 text-sm font-medium bg-red-50 dark:bg-red-950/30 text-red-600 dark:text-red-400 border border-red-200 dark:border-red-900/50"
    >
      {t(oauthErrorKey)}
    </div>
  )
}`;

fs.writeFileSync('src/app/[locale]/login/page.tsx', content, 'utf8');
