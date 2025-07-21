'use client'

import { useState, useEffect } from 'react'
import { useAuth } from '@/lib/auth'
import { useRouter } from 'next/navigation'
import { 
  UserIcon, 
  BellIcon, 
  ShieldCheckIcon, 
  GlobeAltIcon,
  MoonIcon,
  SunIcon,
  ComputerDesktopIcon,
  ArrowLeftIcon
} from '@heroicons/react/24/outline'
import toast from 'react-hot-toast'

interface SettingsSection {
  id: string
  title: string
  description: string
  icon: React.ComponentType<any>
}

interface ThemeOption {
  id: 'light' | 'dark' | 'system'
  name: string
  icon: React.ComponentType<any>
}

export default function SettingsPage() {
  const { user, isLoading: authLoading, updateUser } = useAuth()
  const router = useRouter()
  const [activeSection, setActiveSection] = useState('profile')
  const [isLoading, setIsLoading] = useState(false)
  const [userLoaded, setUserLoaded] = useState(false)
  
  // 用户设置状态
  const [userSettings, setUserSettings] = useState({
    fullName: '',
    email: '',
    language: 'zh-CN',
    theme: 'system' as 'light' | 'dark' | 'system',
    emailNotifications: true,
    interviewReminders: true,
    autoSave: true
  })

  // 当用户信息加载完成后，更新设置状态
  useEffect(() => {
    if (user && !authLoading && !userLoaded) {
      setUserSettings(prev => ({
        ...prev,
        fullName: user.full_name || '',
        email: user.email || ''
      }))
      setUserLoaded(true)
    }
  }, [user, authLoading, userLoaded])

  const sections: SettingsSection[] = [
    {
      id: 'profile',
      title: '个人资料',
      description: '管理您的个人信息',
      icon: UserIcon
    },
    {
      id: 'notifications',
      title: '通知设置',
      description: '配置通知偏好',
      icon: BellIcon
    },
    {
      id: 'privacy',
      title: '隐私安全',
      description: '账户安全设置',
      icon: ShieldCheckIcon
    },
    {
      id: 'appearance',
      title: '外观设置',
      description: '主题和显示偏好',
      icon: GlobeAltIcon
    }
  ]

  const themeOptions: ThemeOption[] = [
    { id: 'light', name: '浅色模式', icon: SunIcon },
    { id: 'dark', name: '深色模式', icon: MoonIcon },
    { id: 'system', name: '跟随系统', icon: ComputerDesktopIcon }
  ]

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

      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/api/v1/auth/me`, {
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
      
      // 更新本地用户状态
      setUserSettings(prev => ({
        ...prev,
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

      <div>
        <label className="block text-sm font-medium text-gray-700 mb-2">
          语言设置
        </label>
        <select
          value={userSettings.language}
          onChange={(e) => setUserSettings(prev => ({ ...prev, language: e.target.value }))}
          className="w-full p-3 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
        >
          <option value="zh-CN">中文（简体）</option>
          <option value="zh-TW">中文（繁體）</option>
          <option value="en-US">English</option>
        </select>
      </div>
    </div>
  )

  const renderNotificationsSection = () => (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-sm font-medium text-gray-900">邮件通知</h4>
          <p className="text-sm text-gray-500">接收重要更新和消息</p>
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={userSettings.emailNotifications}
            onChange={(e) => setUserSettings(prev => ({ ...prev, emailNotifications: e.target.checked }))}
            className="sr-only peer"
          />
          <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
        </label>
      </div>

      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-sm font-medium text-gray-900">面试提醒</h4>
          <p className="text-sm text-gray-500">面试前发送提醒通知</p>
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={userSettings.interviewReminders}
            onChange={(e) => setUserSettings(prev => ({ ...prev, interviewReminders: e.target.checked }))}
            className="sr-only peer"
          />
          <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
        </label>
      </div>

      <div className="flex items-center justify-between">
        <div>
          <h4 className="text-sm font-medium text-gray-900">自动保存</h4>
          <p className="text-sm text-gray-500">自动保存编辑内容</p>
        </div>
        <label className="relative inline-flex items-center cursor-pointer">
          <input
            type="checkbox"
            checked={userSettings.autoSave}
            onChange={(e) => setUserSettings(prev => ({ ...prev, autoSave: e.target.checked }))}
            className="sr-only peer"
          />
          <div className="w-11 h-6 bg-gray-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-blue-300 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600"></div>
        </label>
      </div>
    </div>
  )

  const renderPrivacySection = () => (
    <div className="space-y-6">
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
        <h4 className="text-sm font-medium text-yellow-800 mb-2">账户安全</h4>
        <p className="text-sm text-yellow-700 mb-3">
          定期更新密码可以提高账户安全性
        </p>
        <button
          onClick={() => toast('密码修改功能正在开发中')}
          className="text-sm bg-yellow-100 text-yellow-800 px-3 py-1 rounded-md hover:bg-yellow-200 transition-colors"
        >
          修改密码
        </button>
      </div>

      <div className="bg-red-50 border border-red-200 rounded-lg p-4">
        <h4 className="text-sm font-medium text-red-800 mb-2">危险操作</h4>
        <p className="text-sm text-red-700 mb-3">
          删除账户将永久删除所有数据，此操作不可恢复
        </p>
        <button
          onClick={() => toast.error('账户删除功能正在开发中')}
          className="text-sm bg-red-100 text-red-800 px-3 py-1 rounded-md hover:bg-red-200 transition-colors"
        >
          删除账户
        </button>
      </div>
    </div>
  )

  const renderAppearanceSection = () => (
    <div className="space-y-6">
      <div>
        <h4 className="text-sm font-medium text-gray-900 mb-3">主题设置</h4>
        <div className="grid grid-cols-1 gap-3">
          {themeOptions.map((option) => {
            const Icon = option.icon
            return (
              <label
                key={option.id}
                className={`flex items-center p-3 border rounded-lg cursor-pointer transition-colors ${
                  userSettings.theme === option.id
                    ? 'border-blue-500 bg-blue-50'
                    : 'border-gray-200 hover:bg-gray-50'
                }`}
              >
                <input
                  type="radio"
                  name="theme"
                  value={option.id}
                  checked={userSettings.theme === option.id}
                  onChange={(e) => setUserSettings(prev => ({ ...prev, theme: e.target.value as any }))}
                  className="sr-only"
                />
                <Icon className="w-5 h-5 text-gray-600 mr-3" />
                <span className="text-sm font-medium text-gray-900">
                  {option.name}
                </span>
              </label>
            )
          })}
        </div>
      </div>
    </div>
  )

  const renderSectionContent = () => {
    switch (activeSection) {
      case 'profile':
        return renderProfileSection()
      case 'notifications':
        return renderNotificationsSection()
      case 'privacy':
        return renderPrivacySection()
      case 'appearance':
        return renderAppearanceSection()
      default:
        return renderProfileSection()
    }
  }

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
                className="flex items-center space-x-2 text-gray-600 hover:text-gray-900 transition-colors"
              >
                <ArrowLeftIcon className="w-5 h-5" />
                <span>返回</span>
              </button>
              <div className="h-6 border-l border-gray-300"></div>
              <h1 className="text-2xl font-bold text-gray-900">设置</h1>
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
              {sections.map((section) => {
                const Icon = section.icon
                return (
                  <button
                    key={section.id}
                    onClick={() => setActiveSection(section.id)}
                    className={`w-full flex items-center space-x-3 px-4 py-3 text-left rounded-lg transition-colors ${
                      activeSection === section.id
                        ? 'bg-blue-100 text-blue-700 border border-blue-200'
                        : 'text-gray-600 hover:text-gray-900 hover:bg-gray-50'
                    }`}
                  >
                    <Icon className="w-5 h-5" />
                    <div>
                      <div className="font-medium">{section.title}</div>
                      <div className="text-xs text-gray-500">{section.description}</div>
                    </div>
                  </button>
                )
              })}
            </nav>
          </div>

          {/* 右侧内容 */}
          <div className="lg:col-span-3">
            <div className="bg-white rounded-lg shadow-sm border p-6">
              <div className="mb-6">
                <h2 className="text-lg font-semibold text-gray-900">
                  {sections.find(s => s.id === activeSection)?.title}
                </h2>
                <p className="text-sm text-gray-500 mt-1">
                  {sections.find(s => s.id === activeSection)?.description}
                </p>
              </div>
              
              {renderSectionContent()}
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}