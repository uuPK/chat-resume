'use client'

export const dynamic = 'force-dynamic'

import { motion } from 'framer-motion'
import Link from 'next/link'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth'
import { EyeIcon, EyeSlashIcon } from '@heroicons/react/24/outline'
import Logo from '@/components/ui/Logo'

interface RegisterForm {
  fullName: string
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

  const onSubmit = async (data: RegisterForm) => {
    try {
      const success = await registerUser(data.email, data.password, data.fullName)
      if (success) router.push('/dashboard')
    } catch (error) {
      console.error('注册失败:', error)
    }
  }

  return (
    <div className="min-h-screen flex flex-col" style={{ backgroundColor: '#ffffff' }}>
      {/* Top bar */}
      <div className="flex items-center px-8 h-16" style={{ borderBottom: '1px solid rgba(91,97,110,0.15)' }}>
        <Logo size="sm" />
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
              创建账户
            </h1>
            <p className="text-lg" style={{ color: '#5b616e', lineHeight: '1.56' }}>
              开始您的智能简历优化之旅
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
            <form className="space-y-5" onSubmit={handleSubmit(onSubmit)}>
              <div>
                <label className="label">姓名</label>
                <input
                  {...register('fullName', {
                    required: '请输入您的姓名',
                    minLength: { value: 2, message: '姓名至少需要2个字符' }
                  })}
                  type="text"
                  className={errors.fullName ? 'input-error' : 'input'}
                  placeholder="请输入您的姓名"
                />
                {errors.fullName && <p className="mt-1.5 text-sm text-red-600">{errors.fullName.message}</p>}
              </div>

              <div>
                <label className="label">邮箱地址</label>
                <input
                  {...register('email', {
                    required: '请输入邮箱地址',
                    pattern: { value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i, message: '请输入有效的邮箱地址' }
                  })}
                  type="email"
                  className={errors.email ? 'input-error' : 'input'}
                  placeholder="name@example.com"
                />
                {errors.email && <p className="mt-1.5 text-sm text-red-600">{errors.email.message}</p>}
              </div>

              <div>
                <label className="label">密码</label>
                <div className="relative">
                  <input
                    {...register('password', {
                      required: '请输入密码',
                      minLength: { value: 6, message: '密码至少需要6个字符' }
                    })}
                    type={showPassword ? 'text' : 'password'}
                    className={`${errors.password ? 'input-error' : 'input'} pr-12`}
                    placeholder="至少 6 个字符"
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
                <label className="label">确认密码</label>
                <div className="relative">
                  <input
                    {...register('confirmPassword', {
                      required: '请确认密码',
                      validate: value => value === password || '两次输入的密码不一致'
                    })}
                    type={showConfirmPassword ? 'text' : 'password'}
                    className={`${errors.confirmPassword ? 'input-error' : 'input'} pr-12`}
                    placeholder="再次输入密码"
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
                  我同意{' '}
                  <span className="font-semibold" style={{ color: '#0052ff' }}>服务条款</span>
                  {' '}和{' '}
                  <span className="font-semibold" style={{ color: '#0052ff' }}>隐私政策</span>
                </label>
              </div>

              <button
                type="submit"
                disabled={isLoading}
                className="btn-primary w-full btn-lg"
              >
                {isLoading ? '创建中...' : '创建账户'}
              </button>
            </form>

            <div className="mt-6 text-center text-sm" style={{ color: '#5b616e' }}>
              已有账户？{' '}
              <Link href="/login" className="font-semibold" style={{ color: '#0052ff' }}>
                立即登录
              </Link>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
