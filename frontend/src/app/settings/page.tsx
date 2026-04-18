'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '@/lib/auth'
import { useRouter } from 'next/navigation'
import { ArrowLeftIcon } from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'

// 设置页，Coinbase 风格
export default function SettingsPage() {
  const { user, isLoading: authLoading, updateUser } = useAuth()
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const [userLoaded, setUserLoaded] = useState(false)
  const [userSettings, setUserSettings] = useState({ fullName: '', email: '' })

  useEffect(() => {
    if (user && !authLoading && !userLoaded) {
      setUserSettings({ fullName: user.full_name || '', email: user.email || '' })
      setUserLoaded(true)
    }
  }, [user, authLoading, userLoaded])

  const handleSaveSettings = async () => {
    if (!userSettings.fullName.trim()) {
      toast.error('姓名不能为空')
      return
    }
    setIsLoading(true)
    try {
      const token = localStorage.getItem('access_token')
      if (!token) { toast.error('请先登录'); return }
      const response = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/auth/me`,
        {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json', 'Authorization': `Bearer ${token}` },
          body: JSON.stringify({ full_name: userSettings.fullName.trim() })
        }
      )
      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || '保存失败')
      }
      const updatedUser = await response.json()
      setUserSettings({ fullName: updatedUser.full_name || '', email: updatedUser.email || '' })
      updateUser(updatedUser)
      toast.success('设置已保存')
    } catch (error) {
      toast.error(error instanceof Error ? error.message : '保存设置失败')
    } finally {
      setIsLoading(false)
    }
  }

  if (authLoading || (!user && !authLoading)) {
    return (
      <div className="min-h-screen flex items-center justify-center" style={{ backgroundColor: '#ffffff' }}>
        <div
          className="w-10 h-10 rounded-full border-2 border-transparent animate-spin"
          style={{ borderTopColor: '#0052ff', borderRightColor: '#0052ff' }}
        />
      </div>
    )
  }

  return (
    <div className="min-h-screen" style={{ backgroundColor: '#ffffff' }}>
      {/* Header */}
      <header
        className="bg-white"
        style={{ borderBottom: '1px solid rgba(91,97,110,0.15)' }}
      >
        <div className="max-w-7xl mx-auto px-6">
          <div className="flex items-center justify-between h-16">
            <button
              onClick={() => router.back()}
              className="flex items-center gap-2 text-sm font-semibold transition-colors"
              style={{ color: '#0a0b0d' }}
            >
              <ArrowLeftIcon className="w-4 h-4" />
              返回
            </button>
            <button
              onClick={handleSaveSettings}
              disabled={isLoading}
              className="btn-primary btn-sm"
            >
              {isLoading ? '保存中...' : '保存设置'}
            </button>
          </div>
        </div>
      </header>

      {/* Header */}
      <div className="py-10 px-6" style={{ borderBottom: '1px solid rgba(91,97,110,0.12)' }}>
        <div className="max-w-7xl mx-auto">
          <h1 className="text-5xl font-semibold" style={{ lineHeight: '1.00', color: '#0a0b0d' }}>
            设置
          </h1>
          <p className="mt-2 text-lg" style={{ color: '#5b616e', lineHeight: '1.56' }}>
            管理您的个人信息
          </p>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-6 py-10">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* Sidebar */}
          <div className="lg:col-span-1">
            <nav>
              <div
                className="flex items-center gap-3 px-4 py-3 text-sm font-semibold"
                style={{
                  borderRadius: '12px',
                  backgroundColor: '#eef0f3',
                  color: '#0052ff',
                }}
              >
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold text-white flex-shrink-0"
                  style={{ backgroundColor: '#0052ff' }}
                >
                  {(user?.full_name || 'U')[0].toUpperCase()}
                </div>
                <div>
                  <div className="font-semibold">个人资料</div>
                  <div className="text-xs font-normal" style={{ color: '#5b616e' }}>管理您的个人信息</div>
                </div>
              </div>
            </nav>
          </div>

          {/* Main */}
          <div className="lg:col-span-3">
            <div
              className="p-8"
              style={{
                border: '1px solid rgba(91,97,110,0.2)',
                borderRadius: '16px',
                backgroundColor: '#ffffff',
              }}
            >
              <div className="mb-8">
                <h2 className="text-2xl font-semibold" style={{ color: '#0a0b0d', lineHeight: '1.13' }}>
                  个人资料
                </h2>
                <p className="mt-1 text-base" style={{ color: '#5b616e' }}>管理您的个人信息</p>
              </div>

              <div className="space-y-6">
                <div>
                  <label className="label">姓名</label>
                  <input
                    type="text"
                    value={userSettings.fullName}
                    onChange={(e) => setUserSettings(prev => ({ ...prev, fullName: e.target.value }))}
                    className="input"
                    placeholder="请输入您的姓名"
                  />
                </div>
                <div>
                  <label className="label">邮箱地址</label>
                  <input
                    type="email"
                    value={userSettings.email}
                    readOnly
                    className="input"
                    style={{ backgroundColor: '#eef0f3', cursor: 'not-allowed', color: '#5b616e' }}
                  />
                </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
