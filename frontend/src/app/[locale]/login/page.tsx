'use client'

export const dynamic = 'force-dynamic'

import { Suspense, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useSearchParams } from 'next/navigation'
import { useAuth } from '@/lib/auth'
import { getOAuthErrorKey } from '@/lib/oauthErrors'
import toast from 'react-hot-toast'
import { EyeIcon, EyeSlashIcon } from '@heroicons/react/24/solid'
import { useTranslations } from 'next-intl'
import { isAppLocale } from '@/i18n/routing'
import AuthLayout, { AuthRole } from '@/components/auth/AuthLayout'
import { Link } from '@/i18n/navigation'

interface LoginForm {
  email: string
  password: string
}

function getSafeNextPath(role: AuthRole): string {
  const nextPath = new URLSearchParams(window.location.search).get('next')
  if (!nextPath || !nextPath.startsWith('/') || nextPath.startsWith('//')) {
    if (role === 'enterprise') return '/enterprise/dashboard'
    if (role === 'school') return '/school/dashboard'
    return '/dashboard'
  }
  return stripLocaleFromPath(nextPath)
}

function stripLocaleFromPath(path: string): string {
  const [pathname, query = ''] = path.split('?')
  const segments = pathname.split('/')
  if (!isAppLocale(segments[1])) return path

  const strippedPathname = `/${segments.slice(2).join('/')}` || '/'
  return query ? `${strippedPathname}?${query}` : strippedPathname
}

function navigateAfterLogin(path: string) {
  window.location.assign(path)
}

export default function LoginPage() {
  const [role, setRole] = useState<AuthRole>('candidate')
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
        // Use the selected role as a hint for where to route if no explicit nextPath
        navigateAfterLogin(getSafeNextPath(role))
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : t('login.fallbackError')
      toast.error(message, { id: 'login' })
    }
  }

  return (
    <AuthLayout
      type="login"
      role={role}
      onRoleChange={setRole}
      title={t('login.title')}
      subtitle={t('login.subtitle')}
    >
      <div className="bg-white dark:bg-[#0a0a0a]">
        <Suspense fallback={null}>
          <OAuthErrorAlert />
        </Suspense>

        <form className="space-y-5" onSubmit={handleSubmit(onSubmit)}>
          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">{t('fields.email')}</label>
            <input
              {...register('email', {
                required: t('validation.emailRequired'),
                pattern: { value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i, message: t('validation.emailInvalid') }
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
                className={`${errors.password ? 'input-error' : 'input bg-transparent border-gray-300 dark:border-gray-700 focus:border-primary-500 dark:focus:border-primary-500 text-gray-900 dark:text-white rounded-xl'} pr-12`}
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
      </div>
    </AuthLayout>
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
}