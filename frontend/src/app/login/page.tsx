'use client'

export const dynamic = 'force-dynamic'

import { motion } from 'framer-motion'
import Link from 'next/link'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useRouter } from 'next/navigation'
import { useAuth } from '@/lib/auth'
import toast from 'react-hot-toast'
import { EyeIcon, EyeSlashIcon } from '@heroicons/react/24/outline'
import Logo from '@/components/ui/Logo'

interface LoginForm {
  email: string
  password: string
}

// 登录页，Coinbase 风格：白底深色文字，蓝色 pill 按钮
export default function LoginPage() {
  const [showPassword, setShowPassword] = useState(false)
  const { login, isLoading } = useAuth()
  const { register, handleSubmit, formState: { errors } } = useForm<LoginForm>()
  const router = useRouter()

  const onSubmit = async (data: LoginForm) => {
    try {
      toast.loading('正在登录...', { id: 'login' })
      const success = await login(data.email, data.password)
      if (success) {
        toast.success('登录成功！', { id: 'login' })
        router.push('/dashboard')
      }
    } catch (error: any) {
      toast.error(error.message || '登录失败，请重试', { id: 'login' })
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
              欢迎回来
            </h1>
            <p className="text-lg" style={{ color: '#5b616e', lineHeight: '1.56' }}>
              登录您的账户继续使用
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
                    placeholder="请输入密码"
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
                {isLoading ? '登录中...' : '登录'}
              </button>
            </form>

            <div className="mt-6 text-center text-sm" style={{ color: '#5b616e' }}>
              还没有账户？{' '}
              <Link href="/register" className="font-semibold" style={{ color: '#0052ff' }}>
                立即注册
              </Link>
            </div>
          </div>
        </motion.div>
      </div>
    </div>
  )
}
