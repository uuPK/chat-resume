'use client'

import Link from 'next/link'
import { useRouter, usePathname } from 'next/navigation'
import { ChevronDownIcon, Cog6ToothIcon, ArrowLeftOnRectangleIcon } from '@heroicons/react/24/outline'
import { useAuth } from '@/lib/auth'
import { useState, useRef, useEffect } from 'react'
import Logo from '@/components/ui/Logo'

// 顶部主导航栏，Coinbase 风格：白底、蓝色品牌色、pill 形激活态
export default function MainNavigation() {
  const router = useRouter()
  const pathname = usePathname()
  const { user, logout } = useAuth()
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  const isResumesActive =
    pathname === '/' || pathname === '/dashboard' ||
    pathname?.startsWith('/resumes') || pathname?.startsWith('/resume/')
  const isInterviewsActive = pathname?.startsWith('/interviews')

  return (
    <header className="bg-white border-b" style={{ borderColor: 'rgba(91,97,110,0.15)' }}>
      <div className="max-w-7xl mx-auto px-6">
        <div className="flex justify-between items-center h-16">
          {/* Logo + nav */}
          <div className="flex items-center gap-8">
            <Logo size="md" />

            <nav className="hidden sm:flex items-center gap-1">
              <Link
                href="/resumes"
                className="px-5 py-2.5 text-base font-semibold transition-colors"
                style={{
                  borderRadius: '56px',
                  backgroundColor: isResumesActive ? '#eef0f3' : 'transparent',
                  color: isResumesActive ? '#0052ff' : '#0a0b0d',
                }}
              >
                简历中心
              </Link>
              <Link
                href="/interviews"
                className="px-5 py-2.5 text-base font-semibold transition-colors"
                style={{
                  borderRadius: '56px',
                  backgroundColor: isInterviewsActive ? '#eef0f3' : 'transparent',
                  color: isInterviewsActive ? '#0052ff' : '#0a0b0d',
                }}
              >
                面试中心
              </Link>
            </nav>
          </div>

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
                className="w-10 h-10 rounded-full flex items-center justify-center text-base font-semibold text-white flex-shrink-0"
                style={{ backgroundColor: '#0052ff' }}
              >
                {(user?.full_name || 'U')[0].toUpperCase()}
              </div>
              <span className="hidden sm:block text-base font-semibold" style={{ color: '#0a0b0d' }}>
                {user?.full_name || 'User'}
              </span>
              <ChevronDownIcon
                className={`w-4 h-4 transition-transform flex-shrink-0`}
                style={{ color: '#5b616e', transform: isDropdownOpen ? 'rotate(180deg)' : 'rotate(0deg)' }}
              />
            </button>

            {isDropdownOpen && (
              <div
                className="absolute right-0 mt-2 w-48 bg-white py-1 z-50"
                style={{
                  borderRadius: '16px',
                  border: '1px solid rgba(91,97,110,0.2)',
                  boxShadow: '0 8px 24px rgba(0,0,0,0.08)',
                }}
              >
                <button
                  onClick={() => { setIsDropdownOpen(false); router.push('/settings') }}
                  className="flex items-center gap-2.5 w-full text-left px-4 py-2.5 text-sm font-medium transition-colors"
                  style={{ color: '#0a0b0d' }}
                  onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#eef0f3')}
                  onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  <Cog6ToothIcon className="w-4 h-4" />
                  <span>设置</span>
                </button>
                <button
                  onClick={() => { setIsDropdownOpen(false); logout() }}
                  className="flex items-center gap-2.5 w-full text-left px-4 py-2.5 text-sm font-medium transition-colors"
                  style={{ color: '#0a0b0d' }}
                  onMouseEnter={e => (e.currentTarget.style.backgroundColor = '#eef0f3')}
                  onMouseLeave={e => (e.currentTarget.style.backgroundColor = 'transparent')}
                >
                  <ArrowLeftOnRectangleIcon className="w-4 h-4" />
                  <span>退出登录</span>
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
    </header>
  )
}
