'use client'

import React, { createContext, useContext, useEffect, useState, ReactNode } from 'react'

// 用户接口定义
interface User {
  id: number
  email: string
  full_name?: string
  is_active: boolean
  created_at: string
}

// 登录响应接口
interface LoginResponse {
  token_type: string
  user: User
}

// 注册请求接口
interface RegisterRequest {
  email: string
  password: string
  full_name: string
}

// 认证上下文接口
interface AuthContextType {
  user: User | null
  isAuthenticated: boolean
  isLoading: boolean
  login: (email: string, password: string) => Promise<boolean>
  register: (email: string, password: string, fullName: string) => Promise<boolean>
  logout: () => void
  updateUser: (userData: Partial<User>) => void
  refreshUser: () => Promise<void>
}

// 创建认证上下文
const AuthContext = createContext<AuthContextType | undefined>(undefined)

// API基础URL
const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const USER_STORAGE_KEY = 'auth_user'

function readStoredUser(): User | null {
  try {
    const raw = localStorage.getItem(USER_STORAGE_KEY)
    if (!raw) return null
    return JSON.parse(raw) as User
  } catch {
    return null
  }
}

function writeStoredUser(user: User | null) {
  if (!user) {
    localStorage.removeItem(USER_STORAGE_KEY)
    return
  }
  localStorage.setItem(USER_STORAGE_KEY, JSON.stringify(user))
}

// 认证相关API调用
class AuthAPI {
  static async login(email: string, password: string): Promise<LoginResponse> {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: new URLSearchParams({
        username: email,
        password: password,
      }),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || '登录失败')
    }

    return response.json()
  }

  static async register(data: RegisterRequest): Promise<User> {
    const response = await fetch(`${API_BASE_URL}/api/auth/register`, {
      method: 'POST',
      credentials: 'include',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(data),
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || '注册失败')
    }

    return response.json()
  }

  static async getCurrentUser(): Promise<User> {
    const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
      credentials: 'include',
    })

    if (!response.ok) {
      throw new Error('获取用户信息失败')
    }

    return response.json()
  }

  static async refresh(): Promise<LoginResponse> {
    const response = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
      method: 'POST',
      credentials: 'include',
    })

    if (!response.ok) {
      throw new Error('刷新登录状态失败')
    }

    return response.json()
  }

  static async logout(): Promise<void> {
    const response = await fetch(`${API_BASE_URL}/api/auth/logout`, {
      method: 'POST',
      credentials: 'include',
    })

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}))
      throw new Error(errorData.detail || '退出登录失败')
    }
  }
}

// 认证提供者组件
export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [isLoading, setIsLoading] = useState(true)

  const isAuthenticated = !!user

  // 登录函数
  const login = async (email: string, password: string): Promise<boolean> => {
    try {
      const response = await AuthAPI.login(email, password)

      // 设置用户信息
      setUser(response.user)
      writeStoredUser(response.user)
      
      return true
    } catch (error) {
      console.error('Login error:', error)
      // 抛出错误以便上层处理
      throw error
    }
  }

  // 注册函数
  const register = async (email: string, password: string, fullName: string): Promise<boolean> => {
    try {
      const user = await AuthAPI.register({
        email,
        password,
        full_name: fullName,
      })
      
      // 注册成功后自动登录
      return await login(email, password)
    } catch (error) {
      console.error('Register error:', error)
      return false
    }
  }

  // 登出函数
  const logout = () => {
    localStorage.removeItem(USER_STORAGE_KEY)
    setUser(null)
    AuthAPI.logout().catch((error) => {
      console.error('Logout error:', error)
    })
  }

  const refreshSession = async (): Promise<boolean> => {
    try {
      const response = await AuthAPI.refresh()
      setUser(response.user)
      writeStoredUser(response.user)
      return true
    } catch (error) {
      console.error('Refresh session error:', error)
      return false
    }
  }

  // 更新用户信息
  const updateUser = (userData: Partial<User>) => {
    if (user) {
      const nextUser = { ...user, ...userData }
      setUser(nextUser)
      writeStoredUser(nextUser)
    }
  }

  // 刷新用户信息
  const refreshUser = async () => {
    try {
      const freshUser = await AuthAPI.getCurrentUser().catch(async () => {
        const refreshed = await refreshSession()
        if (!refreshed) {
          throw new Error('获取用户信息失败')
        }
        return AuthAPI.getCurrentUser()
      })
      setUser(freshUser)
      writeStoredUser(freshUser)
    } catch (error) {
      console.error('Refresh user error:', error)
      localStorage.removeItem(USER_STORAGE_KEY)
      setUser(null)
    }
  }

  // 检查认证状态
  const checkAuth = async () => {
    try {
      const cachedUser = readStoredUser()
      if (cachedUser) {
        setUser(cachedUser)
      }

      const user = await AuthAPI.getCurrentUser().catch(async () => {
        const refreshed = await refreshSession()
        if (!refreshed) {
          throw new Error('获取用户信息失败')
        }
        return AuthAPI.getCurrentUser()
      })
      setUser(user)
      writeStoredUser(user)
    } catch (error) {
      console.error('Auth check error:', error)
      localStorage.removeItem(USER_STORAGE_KEY)
      setUser(null)
    } finally {
      setIsLoading(false)
    }
  }

  // 组件挂载时检查认证状态
  useEffect(() => {
    checkAuth()
  }, [])

  const value: AuthContextType = {
    user,
    isAuthenticated,
    isLoading,
    login,
    register,
    logout,
    updateUser,
    refreshUser,
  }

  return (
    <AuthContext.Provider value={value}>
      {children}
    </AuthContext.Provider>
  )
}

// 使用认证的Hook
export function useAuth(): AuthContextType {
  const context = useContext(AuthContext)
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider')
  }
  return context
}
