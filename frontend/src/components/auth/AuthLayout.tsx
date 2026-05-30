'use client'

import { motion, AnimatePresence } from 'framer-motion'
import { ReactNode } from 'react'
import Logo from '@/components/ui/Logo'
import LocaleSwitcher from '@/components/i18n/LocaleSwitcher'
import { useTranslations } from 'next-intl'
import { Link } from '@/i18n/navigation'

export type AuthRole = 'candidate' | 'enterprise' | 'school'

interface AuthLayoutProps {
  children: ReactNode
  title: string
  subtitle: string
  role: AuthRole
  onRoleChange: (role: AuthRole) => void
  type: 'login' | 'register'
}

export default function AuthLayout({ children, title, subtitle, role, onRoleChange, type }: AuthLayoutProps) {
  const t = useTranslations('auth')

  const roleConfig = {
    candidate: {
      bgClass: 'bg-primary-900',
      illustration: '👩‍💻',
      headline: '连接你的下一个职业里程碑',
      description: '借助 AI 的力量，获得顶尖企业的面试机会。',
    },
    enterprise: {
      bgClass: 'bg-slate-900',
      illustration: '🏢',
      headline: '精准触达高质量科技人才',
      description: '大模型深度匹配，让招聘如虎添翼，降低面试成本。',
    },
    school: {
      bgClass: 'bg-emerald-900',
      illustration: '🎓',
      headline: '紧跟市场前沿的 AI 教研',
      description: '消除市场技能断层，一键生成贴合企业需求的课程体系。',
    }
  }

  const currentRole = roleConfig[role]

  return (
    <div className="flex min-h-screen bg-white dark:bg-[#0a0a0a]">
      {/* Left side: Brand / Illustration panel (hidden on mobile) */}
      <div className={`hidden lg:flex lg:w-1/2 lg:flex-col relative overflow-hidden transition-colors duration-700 ${currentRole.bgClass}`}>
        <div className="absolute inset-0 bg-gradient-to-br from-black/40 to-transparent z-10" />
        <div className="relative z-20 flex flex-col h-full p-12 lg:p-16 text-white justify-between">
          <Logo size="md" theme="dark" />
          
          <AnimatePresence mode="wait">
            <motion.div
              key={role}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, y: -20 }}
              transition={{ duration: 0.5 }}
              className="mt-auto mb-16"
            >
              <div className="text-7xl mb-8">{currentRole.illustration}</div>
              <h2 className="text-4xl lg:text-5xl font-bold tracking-tight mb-6 leading-tight">
                {currentRole.headline}
              </h2>
              <p className="text-lg lg:text-xl text-white/80 max-w-md leading-relaxed">
                {currentRole.description}
              </p>
            </motion.div>
          </AnimatePresence>

          <div className="text-sm text-white/50 font-medium">
            © {new Date().getFullYear()} OfferMaster AI. All rights reserved.
          </div>
        </div>
      </div>

      {/* Right side: Form panel */}
      <div className="flex-1 flex flex-col items-center justify-center p-6 sm:p-12 lg:p-16 relative">
        {/* Mobile Logo & Language switcher */}
        <div className="absolute top-6 left-6 right-6 flex justify-between items-center lg:justify-end w-full max-w-lg mx-auto lg:max-w-none px-6 lg:px-0">
          <div className="lg:hidden"><Logo size="sm" /></div>
          <LocaleSwitcher compact />
        </div>

        <div className="w-full max-w-md mx-auto">
          {/* Role Tabs */}
          <div className="flex p-1 bg-gray-100 dark:bg-gray-800 rounded-xl mb-10 w-full">
            {(['candidate', 'enterprise', 'school'] as AuthRole[]).map((r) => (
              <button
                key={r}
                type="button"
                onClick={() => onRoleChange(r)}
                className={`flex-1 py-2.5 text-sm font-semibold rounded-lg transition-all duration-200 ${
                  role === r
                    ? 'bg-white dark:bg-gray-700 text-gray-900 dark:text-white shadow-sm'
                    : 'text-gray-500 hover:text-gray-700 dark:text-gray-400 dark:hover:text-gray-300'
                }`}
              >
                {r === 'candidate' ? '求职者' : r === 'enterprise' ? '企业端' : '学校端'}
              </button>
            ))}
          </div>

          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.5 }}
          >
            <div className="mb-8">
              <h1 className="text-3xl font-bold tracking-tight text-gray-900 dark:text-white mb-2">
                {title}
              </h1>
              <p className="text-gray-500 dark:text-gray-400">
                {subtitle}
              </p>
            </div>

            {children}

            <div className="mt-8 text-center text-sm text-gray-500">
              {type === 'login' ? (
                <>
                  {t('login.noAccount')}{' '}
                  <Link href="/register" className="font-semibold text-primary-600 hover:text-primary-500 transition-colors">
                    {t('login.registerNow')}
                  </Link>
                </>
              ) : (
                <>
                  {t('register.hasAccount')}{' '}
                  <Link href="/login" className="font-semibold text-primary-600 hover:text-primary-500 transition-colors">
                    {t('register.loginNow')}
                  </Link>
                </>
              )}
            </div>
          </motion.div>
        </div>
      </div>
    </div>
  )
}
