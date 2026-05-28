const fs = require('fs');

const content = `'use client'
// 用于提供 components/layout/MainNavigation.tsx 模块

import { useRouter } from '@/i18n/navigation'
import { ChevronDownIcon, Cog6ToothIcon, ArrowLeftOnRectangleIcon } from '@heroicons/react/24/solid'
import { useAuth } from '@/lib/auth'
import { useState, useRef, useEffect } from 'react'
import Logo from '@/components/ui/Logo'
import LocaleSwitcher from '@/components/i18n/LocaleSwitcher'
import { useTranslations } from 'next-intl'

export default function MainNavigation() {
  const router = useRouter()
  const { user, logout } = useAuth()
  const t = useTranslations('common')
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const dropdownRef = useRef(null)

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  return (
    <header className="bg-white/80 dark:bg-[#0a0a0a]/80 backdrop-blur-md border-b border-gray-200 dark:border-gray-800 sticky top-0 z-40 transition-colors duration-300">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex h-16 items-center justify-between">
          <div className="flex min-w-0 items-center gap-8">
            <Logo size="sm" />
          </div>

          <div className="flex items-center justify-end gap-3">
            <LocaleSwitcher compact />
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                className="flex items-center gap-2 px-2 py-1.5 rounded-full border border-gray-200 dark:border-gray-800 bg-white dark:bg-[#0a0a0a] hover:bg-gray-50 dark:hover:bg-gray-900 transition-colors shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500/50"
              >
                <div className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white bg-primary-600 flex-shrink-0 shadow-inner">
                  {(user?.full_name || 'U')[0].toUpperCase()}
                </div>
                <span className="hidden pr-2 sm:flex flex-col items-start leading-tight">
                  <span className="text-sm font-semibold text-gray-900 dark:text-gray-100">
                    {user?.full_name || 'User'}
                  </span>
                </span>
                <ChevronDownIcon
                  className={\`w-4 h-4 text-gray-500 transition-transform duration-200 flex-shrink-0 \${isDropdownOpen ? 'rotate-180' : ''}\`}
                />
              </button>

              {isDropdownOpen && (
                <div className="absolute right-0 mt-2 w-56 bg-white dark:bg-[#0a0a0a] rounded-2xl border border-gray-200 dark:border-gray-800 shadow-xl py-2 z-50 origin-top-right">
                  <button
                    onClick={() => { setIsDropdownOpen(false); router.push('/settings') }}
                    className="flex items-center gap-3 w-full text-left px-4 py-2.5 text-sm font-medium text-gray-700 dark:text-gray-300 hover:bg-gray-50 dark:hover:bg-gray-900 transition-colors"
                  >
                    <Cog6ToothIcon className="w-4 h-4 text-gray-500 dark:text-gray-400" />
                    <span>{t('nav.settings')}</span>
                  </button>
                  <button
                    onClick={() => { setIsDropdownOpen(false); logout() }}
                    className="flex items-center gap-3 w-full text-left px-4 py-2.5 text-sm font-medium text-red-600 dark:text-red-400 hover:bg-red-50 dark:hover:bg-red-950/30 transition-colors"
                  >
                    <ArrowLeftOnRectangleIcon className="w-4 h-4 text-red-500 dark:text-red-400" />
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
}`;

fs.writeFileSync('src/components/layout/MainNavigation.tsx', content, 'utf8');
