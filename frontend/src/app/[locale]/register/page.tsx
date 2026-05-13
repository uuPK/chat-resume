'use client'

export const dynamic = 'force-dynamic'

import { motion } from 'framer-motion'
import { Link } from '@/i18n/navigation'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useRouter } from '@/i18n/navigation'
import { useAuth } from '@/lib/auth'
import { EyeIcon, EyeSlashIcon } from '@heroicons/react/24/outline'
import Logo from '@/components/ui/Logo'
import GoogleContinueLink from '@/components/auth/GoogleContinueLink'
import LocaleSwitcher from '@/components/i18n/LocaleSwitcher'
import { useTranslations } from 'next-intl'

interface RegisterForm {
  email: string
  password: string
  confirmPassword: string
}

// 注册页，Coinbase 风格
export default function RegisterPage() {
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const { register: registerUser, isLoading } = useAuth()
  const { register, handleSubmit, watch, formState: { errors } } = useForm<RegisterForm>()
  const router = useRouter()
  const password = watch('password')
  const t = useTranslations('auth')

  const onSubmit = async (data: RegisterForm) => {
    try {
      const success = await registerUser(data.email, data.password)
      if (success) router.push('/dashboard')
    } catch (error) {
      console.error('register failed:', error)
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
              {t('register.title')}
            </h1>
            <p className="text-lg" style={{ color: '#5b616e', lineHeight: '1.56' }}>
              {t('register.subtitle')}
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
                <label className="label">{t('fields.password')}</label>
                <div className="relative">
                  <input
                    {...register('password', {
                      required: t('validation.passwordRequired'),
                      minLength: { value: 6, message: t('validation.passwordMin') }
                    })}
                    type={showPassword ? 'text' : 'password'}
                    className={`${errors.password ? 'input-error' : 'input'} pr-12`}
                    placeholder={t('placeholders.newPassword')}
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

              <div>
                <label className="label">{t('fields.confirmPassword')}</label>
                <div className="relative">
                  <input
                    {...register('confirmPassword', {
                      required: t('validation.confirmPasswordRequired'),
                      validate: value => value === password || t('validation.passwordMismatch')
                    })}
                    type={showConfirmPassword ? 'text' : 'password'}
                    className={`${errors.confirmPassword ? 'input-error' : 'input'} pr-12`}
                    placeholder={t('placeholders.confirmPassword')}
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute inset-y-0 right-0 px-4 flex items-center"
                    style={{ color: '#9ca3af' }}
                  >
                    {showConfirmPassword ? <EyeSlashIcon className="h-5 w-5" /> : <EyeIcon className="h-5 w-5" />}
                  </button>
                </div>
                {errors.confirmPassword && (
                  <p className="mt-1.5 text-sm text-red-600">{errors.confirmPassword.message}</p>
                )}
              </div>

              <div className="flex items-start gap-2.5 pt-1">
                <input
                  id="agree-terms"
                  type="checkbox"
                  required
                  className="h-4 w-4 mt-0.5 rounded"
                  style={{ accentColor: '#0052ff' }}
                />
                <label htmlFor="agree-terms" className="text-sm" style={{ color: '#5b616e' }}>
                  {t('register.termsPrefix')}{' '}
                  <span className="font-semibold" style={{ color: '#0052ff' }}>{t('register.terms')}</span>
                  {' '}{t('register.termsJoiner')}{' '}
                  <span className="font-semibold" style={{ color: '#0052ff' }}>{t('register.privacy')}</span>
                </label>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="btn-primary w-full btn-lg"
              >
                {isLoading ? t('register.submitting') : t('register.submit')}
              </button>
            </form>

            <div className="mt-6 text-center text-sm" style={{ color: '#5b616e' }}>
              {t('register.hasAccount')}{' '}
              <Link href="/login" className="font-semibold" style={{ color: '#0052ff' }}>
                {t('register.loginNow')}
              </Link>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
