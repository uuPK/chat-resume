'use client'
// 用于提供 app/[locale]/reset-password/page.tsx 模块。

export const dynamic = 'force-dynamic'

import { Link, useRouter } from '@/i18n/navigation'
import { apiFetch, handleApiResponse } from '@/lib/httpClient'
import { EyeIcon, EyeSlashIcon } from '@heroicons/react/24/outline'
import { motion } from 'framer-motion'
import { useTranslations } from 'next-intl'
import { useSearchParams } from 'next/navigation'
import type { ReactNode } from 'react'
import { Suspense, useState } from 'react'
import { useForm, type UseFormRegisterReturn } from 'react-hook-form'
import toast from 'react-hot-toast'
import Logo from '@/components/ui/Logo'
import LocaleSwitcher from '@/components/i18n/LocaleSwitcher'

interface ForgotPasswordForm {
  email: string
}

interface ResetPasswordForm {
  password: string
  confirmPassword: string
}

// 用于渲染密码找回或重置页面。
export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordContent />
    </Suspense>
  )
}

// 用于根据URL token切换找回和重置表单。
function ResetPasswordContent() {
  const searchParams = useSearchParams()
  const token = searchParams.get('token') || ''

  return token ? <ResetPasswordFormView token={token} /> : <ForgotPasswordFormView />
}

// 用于渲染忘记密码邮箱提交表单。
function ForgotPasswordFormView() {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { register, handleSubmit, formState: { errors } } = useForm<ForgotPasswordForm>()
  const t = useTranslations('auth')

  const onSubmit = async (data: ForgotPasswordForm) => {
    setIsSubmitting(true)
    try {
      const response = await apiFetch('/api/auth/forgot-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: data.email }),
      })
      await handleApiResponse<{ message: string }>(response)
      toast.success(t('resetPassword.requestSuccess'))
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('resetPassword.requestError'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthShell title={t('resetPassword.requestTitle')} subtitle={t('resetPassword.requestSubtitle')}>
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
        <button type="submit" disabled={isSubmitting} className="btn-primary w-full btn-lg">
          {isSubmitting ? t('resetPassword.requestSubmitting') : t('resetPassword.requestSubmit')}
        </button>
      </form>
      <AuthBackLink />
    </AuthShell>
  )
}

// 用于渲染新密码设置表单。
function ResetPasswordFormView({ token }: { token: string }) {
  const [showPassword, setShowPassword] = useState(false)
  const [showConfirmPassword, setShowConfirmPassword] = useState(false)
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { register, handleSubmit, watch, formState: { errors } } = useForm<ResetPasswordForm>()
  const router = useRouter()
  const t = useTranslations('auth')
  const password = watch('password')

  const onSubmit = async (data: ResetPasswordForm) => {
    setIsSubmitting(true)
    try {
      const response = await apiFetch('/api/auth/reset-password', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ token, password: data.password }),
      })
      await handleApiResponse<{ message: string }>(response)
      toast.success(t('resetPassword.resetSuccess'))
      router.push('/login')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : t('resetPassword.resetError'))
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <AuthShell title={t('resetPassword.resetTitle')} subtitle={t('resetPassword.resetSubtitle')}>
      <form className="space-y-5" onSubmit={handleSubmit(onSubmit)}>
        <PasswordField
          label={t('fields.password')}
          visible={showPassword}
          onToggle={() => setShowPassword(!showPassword)}
          error={errors.password?.message}
          registration={register('password', {
            required: t('validation.passwordRequired'),
            minLength: { value: 6, message: t('validation.passwordMin') }
          })}
          placeholder={t('placeholders.newPassword')}
        />
        <PasswordField
          label={t('fields.confirmPassword')}
          visible={showConfirmPassword}
          onToggle={() => setShowConfirmPassword(!showConfirmPassword)}
          error={errors.confirmPassword?.message}
          registration={register('confirmPassword', {
            required: t('validation.confirmPasswordRequired'),
            validate: value => value === password || t('validation.passwordMismatch')
          })}
          placeholder={t('placeholders.confirmPassword')}
        />
        <button type="submit" disabled={isSubmitting} className="btn-primary w-full btn-lg">
          {isSubmitting ? t('resetPassword.resetSubmitting') : t('resetPassword.resetSubmit')}
        </button>
      </form>
      <AuthBackLink />
    </AuthShell>
  )
}

// 用于渲染认证页面的公共外壳。
function AuthShell({ title, subtitle, children }: { title: string, subtitle: string, children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: '#ffffff' }}>
      <div className="flex items-center justify-between px-8 h-16" style={{ borderBottom: '1px solid rgba(91,97,110,0.15)' }}>
        <Logo size="sm" />
        <LocaleSwitcher compact />
      </div>
      <div className="flex-1 flex items-center justify-center px-4 py-16">
        <motion.div
          initial={{ opacity: 0, y: 24 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6 }}
          className="w-full max-w-md"
        >
          <div className="mb-10">
            <h1 className="text-5xl font-semibold mb-3" style={{ color: '#0a0b0d', lineHeight: '1.00' }}>
              {title}
            </h1>
            <p className="text-lg" style={{ color: '#5b616e', lineHeight: '1.56' }}>
              {subtitle}
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
            {children}
          </div>
        </motion.div>
      </div>
    </div>
  )
}

// 用于渲染可显示隐藏的密码输入框。
function PasswordField({
  label,
  visible,
  onToggle,
  error,
  registration,
  placeholder,
}: {
  label: string
  visible: boolean
  onToggle: () => void
  error?: string
  registration: UseFormRegisterReturn
  placeholder: string
}) {
  return (
    <div>
      <label className="label">{label}</label>
      <div className="relative">
        <input
          {...registration}
          type={visible ? 'text' : 'password'}
          autoComplete="new-password"
          className={`${error ? 'input-error' : 'input'} pr-12`}
          placeholder={placeholder}
        />
        <button
          type="button"
          onClick={onToggle}
          className="absolute inset-y-0 right-0 px-4 flex items-center"
          style={{ color: '#9ca3af' }}
        >
          {visible ? <EyeSlashIcon className="h-5 w-5" /> : <EyeIcon className="h-5 w-5" />}
        </button>
      </div>
      {error && <p className="mt-1.5 text-sm text-red-600">{error}</p>}
    </div>
  )
}

// 用于渲染返回登录链接。
function AuthBackLink() {
  const t = useTranslations('auth')
  return (
    <div className="mt-6 text-center text-sm" style={{ color: '#5b616e' }}>
      <Link href="/login" className="font-semibold" style={{ color: '#0052ff' }}>
        {t('resetPassword.backToLogin')}
      </Link>
    </div>
  )
}
