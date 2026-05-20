'use client'
// 用于提供 components/layout/MainNavigation.tsx 模块。

import { Link } from '@/i18n/navigation'
import { useRouter, usePathname } from '@/i18n/navigation'
import { ChevronDownIcon, Cog6ToothIcon, ArrowLeftOnRectangleIcon, SparklesIcon } from '@heroicons/react/24/outline'
import { useAuth } from '@/lib/auth'
import { useState, useRef, useEffect } from 'react'
import type { ReactNode } from 'react'
import Logo from '@/components/ui/Logo'
import { billingApi, type BillingStatus } from '@/lib/api'
import LocaleSwitcher from '@/components/i18n/LocaleSwitcher'
import { useTranslations } from 'next-intl'

interface MainNavigationProps {
  actions?: ReactNode
}

// 顶部主导航栏，Coinbase 风格：白底、蓝色品牌色、pill 形激活态
export default function MainNavigation({ actions }: MainNavigationProps) {
  const router = useRouter()
  const pathname = usePathname()
  const { user, logout } = useAuth()
  const t = useTranslations('common')
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const [billingStatus, setBillingStatus] = useState<BillingStatus | null>(null)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    // 用于处理clickoutside。
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => {
    if (!user) {
      setBillingStatus(null)
      return
    }

    billingApi.getStatus()
      .then(setBillingStatus)
      .catch(() => setBillingStatus(null))
  }, [user])

  const isResumesActive =
    pathname === '/' || pathname === '/dashboard' ||
    pathname?.startsWith('/resumes') || pathname?.startsWith('/resume/')
  const isInterviewsActive = pathname?.startsWith('/interviews')
  const planName = billingStatus?.is_active ? 'Plus' : 'Free'

  return (
    <header className="bg-white border-b" style={{ borderColor: 'rgba(91,97,110,0.15)' }}>
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex justify-between items-center h-16">
          {/* Logo + nav */}
          <div className="flex items-center gap-8">
            <Logo size="sm" />

            <nav className="hidden sm:flex items-center gap-1">
              <Link
                href="/resumes"
                className="px-4 py-2 text-sm font-semibold transition-colors"
                style={{
                  borderRadius: '56px',
                  backgroundColor: isResumesActive ? '#eef0f3' : 'transparent',
                  color: isResumesActive ? '#0052ff' : '#0a0b0d',
                }}
              >
                {t('nav.resumes')}
              </Link>
              <Link
                href="/interviews"
                className="px-4 py-2 text-sm font-semibold transition-colors"
                style={{
                  borderRadius: '56px',
                  backgroundColor: isInterviewsActive ? '#eef0f3' : 'transparent',
                  color: isInterviewsActive ? '#0052ff' : '#0a0b0d',
                }}
              >
                {t('nav.interviews')}
              </Link>
            </nav>
          </div>

          <div className="flex items-center gap-2">
            {actions && (
              <div className="mr-3 hidden items-center gap-3 md:flex">
                {actions}
              </div>
            )}

            <LocaleSwitcher compact />

            {/* User menu */}
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                className="flex items-center gap-2 px-3 py-2 transition-colors"
                style={{ borderRadius: '56px' }}
                onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#eef0f3')}
                onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
              >
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-semibold text-white flex-shrink-0"
                  style={{ backgroundColor: '#0052ff' }}
                >
                  {(user?.full_name || 'U')[0].toUpperCase()}
                </div>
                <span className="hidden sm:flex flex-col items-start leading-tight">
                  <span className="text-sm font-semibold" style={{ color: '#0a0b0d' }}>
                    {user?.full_name || 'User'}
                  </span>
                  <span className="text-xs font-medium" style={{ color: '#5b616e' }}>
                    {planName}
                  </span>
                </span>
                <ChevronDownIcon
                  className={`w-4 h-4 transition-transform flex-shrink-0`}
                  style={{ color: '#5b616e', transform: isDropdownOpen ? 'rotate(180deg)' : 'rotate(0deg)' }}
                />
              </button>

              {isDropdownOpen && (
                <div
                  className="absolute right-0 mt-2 w-64 bg-white py-2 z-50"
                  style={{
                    borderRadius: '16px',
                    border: '1px solid rgba(91,97,110,0.2)',
                    boxShadow: '0 8px 24px rgba(0,0,0,0.08)',
                  }}
                >
                  <button
                    onClick={() => { setIsDropdownOpen(false); router.push('/pricing') }}
                    className="flex items-center gap-2.5 w-full text-left px-4 py-2.5 text-sm font-medium transition-colors"
                    style={{ color: '#0a0b0d' }}
                    onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#eef0f3')}
                    onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <SparklesIcon className="w-4 h-4" />
                    <span>{t('nav.pricing')}</span>
                  </button>
                  <button
                    onClick={() => { setIsDropdownOpen(false); router.push('/settings') }}
                    className="flex items-center gap-2.5 w-full text-left px-4 py-2.5 text-sm font-medium transition-colors"
                    style={{ color: '#0a0b0d' }}
                    onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#eef0f3')}
                    onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <Cog6ToothIcon className="w-4 h-4" />
                    <span>{t('nav.settings')}</span>
                  </button>
                  <button
                    onClick={() => { setIsDropdownOpen(false); logout() }}
                    className="flex items-center gap-2.5 w-full text-left px-4 py-2.5 text-sm font-medium transition-colors"
                    style={{ color: '#0a0b0d' }}
                    onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#eef0f3')}
                    onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                  >
                    <ArrowLeftOnRectangleIcon className="w-4 h-4" />
                    <span>{t('nav.logout')}</span>
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </header>
  )
}
