'use client'

import Link from 'next/link'
import { useRouter, usePathname } from 'next/navigation'
import { UserIcon, ChevronDownIcon, Cog6ToothIcon, ArrowLeftOnRectangleIcon } from '@heroicons/react/24/outline'
import { DocumentIcon } from '@heroicons/react/24/solid'
import { useAuth } from '@/lib/auth'
import { useState, useRef, useEffect } from 'react'

export default function MainNavigation() {
  const router = useRouter()
  const pathname = usePathname()
  const { user, logout } = useAuth()
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const dropdownRef = useRef<HTMLDivElement>(null)

  // 点击外部关闭下拉菜单
  useEffect(() => {
    const handleClickOutside = (event: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target as Node)) {
        setIsDropdownOpen(false)
      }
    }

    document.addEventListener('mousedown', handleClickOutside)
    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [])

  return (
    <header className="bg-white shadow-sm border-b">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center py-4">
          {/* Logo和品牌 */}
          <div className="flex items-center gap-6">
            <Link href="/" className="flex items-center space-x-2">
              <div className="w-8 h-8 bg-gradient-primary rounded-lg flex items-center justify-center">
                <DocumentIcon className="w-5 h-5 text-white" />
              </div>
              <span className="text-xl font-bold text-gray-900">Chat Resume</span>
            </Link>
            <nav className="hidden sm:flex items-center gap-1">
              <Link
                href="/resumes"
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  pathname === '/' || pathname === '/dashboard' || pathname?.startsWith('/resumes') || pathname?.startsWith('/resume/')
                    ? 'bg-blue-50 text-blue-700'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                简历中心
              </Link>
              <Link
                href="/interviews"
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  pathname?.startsWith('/interviews')
                    ? 'bg-green-50 text-green-700'
                    : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                }`}
              >
                面试中心
              </Link>
            </nav>
          </div>

          {/* 用户信息和操作 */}
          <div className="flex items-center space-x-4">
            {/* 用户下拉菜单 */}
            <div className="relative" ref={dropdownRef}>
              <button
                onClick={() => setIsDropdownOpen(!isDropdownOpen)}
                className="flex items-center space-x-2 p-2 rounded-lg hover:bg-gray-50 transition-colors"
              >
                <div className="w-8 h-8 bg-gray-100 rounded-full flex items-center justify-center">
                  <UserIcon className="w-5 h-5 text-gray-600" />
                </div>
                <div className="hidden sm:block text-left">
                  <div className="text-sm font-medium text-gray-900">
                    {user?.full_name || 'User'}
                  </div>
                </div>
                <ChevronDownIcon className={`w-4 h-4 text-gray-500 transition-transform ${
                  isDropdownOpen ? 'rotate-180' : ''
                }`} />
              </button>

              {/* 下拉菜单 */}
              {isDropdownOpen && (
                <div className="absolute right-0 mt-2 w-48 bg-white rounded-lg shadow-lg border border-gray-200 py-1 z-50">
                  <button
                    onClick={() => {
                      setIsDropdownOpen(false)
                      router.push('/settings')
                    }}
                    className="flex items-center space-x-2 w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    <Cog6ToothIcon className="w-4 h-4" />
                    <span>设置</span>
                  </button>
                  <button
                    onClick={() => {
                      setIsDropdownOpen(false)
                      logout()
                    }}
                    className="flex items-center space-x-2 w-full text-left px-4 py-2 text-sm text-gray-700 hover:bg-gray-50 transition-colors"
                  >
                    <ArrowLeftOnRectangleIcon className="w-4 h-4" />
                    <span>退出登录</span>
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
