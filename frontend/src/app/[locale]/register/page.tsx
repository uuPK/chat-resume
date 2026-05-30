'use client'

export const dynamic = 'force-dynamic'

import { useEffect, useState } from 'react'
import { useForm } from 'react-hook-form'
import { useRouter } from '@/i18n/navigation'
import { useAuth } from '@/lib/auth'
import { EyeIcon, EyeSlashIcon } from '@heroicons/react/24/solid'
import { useTranslations } from 'next-intl'
import AuthLayout, { AuthRole } from '@/components/auth/AuthLayout'

interface RegisterForm {
  email: string
  password: string
  confirmPassword: string
}

export default function RegisterPage() {
  const [role, setRole] = useState<AuthRole>('candidate')
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const { register: registerUser, isLoading } = useAuth()
  const { register, handleSubmit, watch, trigger, formState: { errors } } = useForm<RegisterForm>({
    mode: 'onChange',
    reValidateMode: 'onChange',
  })
  const router = useRouter()
  const password = watch('password')
  const confirmPassword = watch('confirmPassword')
  const t = useTranslations('auth')

  useEffect(() => {
    if (confirmPassword) void trigger('confirmPassword')
  }, [confirmPassword, password, trigger])

  const onSubmit = async (data: RegisterForm) => {
    try {
      const success = await registerUser(data.email, data.password, role)
      if (success) {
        if (role === 'enterprise') {
          router.push('/enterprise/dashboard')
        } else if (role === 'school') {
          router.push('/school/dashboard')
        } else {
          router.push('/dashboard')
        }
      }
    } catch (error) {
      console.error('register failed:', error)
    }
  }

  return (
    <AuthLayout
      type="register"
      role={role}
      onRoleChange={setRole}
      title={t('register.title')}
      subtitle={t('register.subtitle')}
    >
      <div className="bg-white dark:bg-[#0a0a0a]">
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
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">{t('fields.password')}</label>
            <div className="relative">
              <input
                {...register('password', {
                  required: t('validation.passwordRequired'),
                  minLength: { value: 6, message: t('validation.passwordMin') }
                })}
                type={showPassword ? 'text' : 'password'}
                className={`${errors.password ? 'input-error' : 'input bg-transparent border-gray-300 dark:border-gray-700 focus:border-primary-500 dark:focus:border-primary-500 text-gray-900 dark:text-white rounded-xl'} pr-12`}
                placeholder={t('placeholders.newPassword')}
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

          <div>
            <label className="block text-sm font-medium text-gray-700 dark:text-gray-300 mb-1.5">{t('fields.confirmPassword')}</label>
            <div className="relative">
              <input
                {...register('confirmPassword', {
                  required: t('validation.confirmPasswordRequired'),
                  validate: value => value === password || t('validation.passwordMismatch')
                })}
                type={showConfirmPassword ? 'text' : 'password'}
                className={`${errors.confirmPassword ? 'input-error' : 'input bg-transparent border-gray-300 dark:border-gray-700 focus:border-primary-500 dark:focus:border-primary-500 text-gray-900 dark:text-white rounded-xl'} pr-12`}
                placeholder={t('placeholders.confirmPassword')}
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="absolute inset-y-0 right-0 px-4 flex items-center text-gray-400 hover:text-gray-600 dark:hover:text-gray-300 transition-colors"
              >
                {showConfirmPassword ? <EyeSlashIcon className="h-5 w-5" /> : <EyeIcon className="h-5 w-5" />}
              </button>
            </div>
            {errors.confirmPassword && (
              <p className="mt-1.5 text-sm text-red-500">{errors.confirmPassword.message}</p>
            )}
          </div>

          <div className="flex items-start gap-2.5 pt-1">
            <input
              id="agree-terms"
              type="checkbox"
              required
              className="h-4 w-4 mt-0.5 rounded text-primary-600 focus:ring-primary-500 border-gray-300"
            />
            <label htmlFor="agree-terms" className="text-sm text-gray-500">
              {t('register.termsPrefix')}{' '}
              <span className="font-medium text-primary-600 hover:text-primary-500">{t('register.terms')}</span>
              {' '}{t('register.termsJoiner')}{' '}
              <span className="font-medium text-primary-600 hover:text-primary-500">{t('register.privacy')}</span>
            </label>
          </div>

          <button
            type="submit"
            disabled={isLoading}
            className="btn-primary w-full py-3 rounded-xl text-base font-semibold transition-all hover:scale-[1.02] active:scale-[0.98]"
          >
            {isLoading ? t('register.submitting') : t('register.submit')}
          </button>
        </form>
      </div>
    </AuthLayout>
  )
}