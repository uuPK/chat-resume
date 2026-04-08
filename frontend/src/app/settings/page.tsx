'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '@/lib/auth'
import { useRouter } from 'next/navigation'
import { 
  UserIcon, 
  ArrowLeftIcon
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'

export default function SettingsPage() {
  const { user, isLoading: authLoading, updateUser } = useAuth()
  const router = useRouter()
  const [isLoading, setIsLoading] = useState(false)
  const [userLoaded, setUserLoaded] = useState(false)
  
  // 用户设置状态
  const [userSettings, setUserSettings] = useState({
    fullName: '',
    email: ''
  })

  // 当用户信息加载完成后，更新设置状态
  useEffect(() => {
    if (user && !authLoading && !userLoaded) {
      setUserSettings({
        fullName: user.full_name || '',
        email: user.email || ''
      })
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
      if (!token) {
        toast.error('请先登录')
        return
      }

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/auth/me`, {
        method: 'PUT',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${token}`
        },
        body: JSON.stringify({
          full_name: userSettings.fullName.trim()
        })
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || '保存失败')
      }

      const updatedUser = await response.json()
      console.log('后端返回的更新用户信息:', updatedUser)
      
      setUserSettings(prev => ({
        fullName: updatedUser.full_name || '',
        email: updatedUser.email || ''
      }))
      
      // 更新全局用户状态
      updateUser({
        full_name: updatedUser.full_name
      })
      
      console.log('全局用户状态已更新')
      toast.success('设置已保存')
      
    } catch (error) {
      console.error('保存设置错误:', error)
      toast.error(error instanceof Error ? error.message : '保存设置失败')
    } finally {
      setIsLoading(false)
    }
  }

  const renderProfileSection = () => (
    <div className="space-y-6">
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          姓名
        </label>
        <input
          type="text"
          value={userSettings.fullName}
          onChange={(e) => setUserSettings(prev => ({ ...prev, fullName: e.target.value }))}
          className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
          placeholder="请输入您的姓名"
        />
      </div>
      
      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          邮箱地址
        </label>
        <input
          type="email"
          value={userSettings.email}
          readOnly
          className="w-full p-3 border border-gray-300 rounded-lg bg-gray-50 text-gray-600 cursor-not-allowed"
          placeholder="请输入您的邮箱"
        />
      </div>

    </div>
  )

  // 如果认证正在加载或用户信息还未加载，显示加载状态
  if (authLoading || (!user && !authLoading)) {
    return (
      <div className="min-h-screen bg-gray-50 flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-blue-600 mx-auto mb-4"></div>
          <p className="text-gray-600">正在加载用户信息...</p>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gray-50">
      {/* 头部 */}
      <div className="bg-white shadow-sm border-b">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between py-4">
            <div className="flex items-center space-x-4">
              <button
                onClick={() => router.back()}
                className="flex items-center text-gray-600 hover:text-gray-900 transition-colors"
                aria-label="返回"
              >
                <ArrowLeftIcon className="w-5 h-5" />
              </button>
            </div>
            
            <button
              onClick={handleSaveSettings}
              disabled={isLoading}
              className="bg-blue-600 text-white px-4 py-2 rounded-lg hover:bg-blue-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {isLoading ? '保存中...' : '保存设置'}
            </button>
          </div>
        </div>
      </div>

      {/* 主内容 */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
        <div className="grid grid-cols-1 lg:grid-cols-4 gap-8">
          {/* 左侧菜单 */}
          <div className="lg:col-span-1">
            <nav className="space-y-1">
              <div className="w-full flex items-center space-x-3 px-4 py-3 text-left rounded-lg bg-blue-100 text-blue-700 border border-blue-200">
                <UserIcon className="w-5 h-5" />
                <div>
                  <div className="font-medium">个人资料</div>
                  <div className="text-xs text-gray-500">管理您的个人信息</div>
                </div>
              </div>
            </nav>
          </div>

          {/* 右侧内容 */}
          <div className="lg:col-span-3">
            <div className="bg-white rounded-lg shadow-sm border p-6">
              <div className="mb-6">
                <h2 className="text-lg font-semibold text-gray-900">个人资料</h2>
                <p className="text-sm text-gray-500 mt-1">管理您的个人信息</p>
              </div>
              
              {renderProfileSection()}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
