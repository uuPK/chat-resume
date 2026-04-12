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
  access_token: string
  refresh_token: string
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
const ACCESS_TOKEN_COOKIE_KEY = 'access_token'
const REFRESH_TOKEN_STORAGE_KEY = 'refresh_token'

function setAccessTokenCookie(token: string) {
  document.cookie = `${ACCESS_TOKEN_COOKIE_KEY}=${encodeURIComponent(token)}; Path=/; SameSite=Lax`
}

function clearAccessTokenCookie() {
  document.cookie = `${ACCESS_TOKEN_COOKIE_KEY}=; Path=/; Max-Age=0; SameSite=Lax`
}

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
  private static getAuthHeaders(): Record<string, string> {
    const token = localStorage.getItem('access_token')
    return token ? { Authorization: `Bearer ${token}` } : {}
  }

  static async login(email: string, password: string): Promise<LoginResponse> {
    const response = await fetch(`${API_BASE_URL}/api/auth/login`, {
      method: 'POST',
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
      headers: {
        ...this.getAuthHeaders(),
      },
    })

    if (!response.ok) {
      throw new Error('获取用户信息失败')
    }

    return response.json()
  }

  static async refresh(refreshToken: string): Promise<LoginResponse> {
    const response = await fetch(`${API_BASE_URL}/api/auth/refresh`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ refresh_token: refreshToken }),
    })

    if (!response.ok) {
      throw new Error('刷新登录状态失败')
    }

    return response.json()
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
      
      // 保存token到localStorage
      localStorage.setItem('access_token', response.access_token)
      localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, response.refresh_token)
      setAccessTokenCookie(response.access_token)
      
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
    localStorage.removeItem('access_token')
    localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY)
    localStorage.removeItem(USER_STORAGE_KEY)
    clearAccessTokenCookie()
    setUser(null)
  }

  const refreshSession = async (): Promise<boolean> => {
    const refreshToken = localStorage.getItem(REFRESH_TOKEN_STORAGE_KEY)
    if (!refreshToken) {
      return false
    }

    try {
      const response = await AuthAPI.refresh(refreshToken)
      localStorage.setItem('access_token', response.access_token)
      localStorage.setItem(REFRESH_TOKEN_STORAGE_KEY, response.refresh_token)
      setAccessTokenCookie(response.access_token)
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
      const token = localStorage.getItem('access_token')
      if (token) {
        setAccessTokenCookie(token)
        const freshUser = await AuthAPI.getCurrentUser().catch(async () => {
          const refreshed = await refreshSession()
          if (!refreshed) {
            throw new Error('获取用户信息失败')
          }
          return AuthAPI.getCurrentUser()
        })
        setUser(freshUser)
        writeStoredUser(freshUser)
      }
    } catch (error) {
      console.error('Refresh user error:', error)
    }
  }

  // 检查认证状态
  const checkAuth = async () => {
    try {
      const token = localStorage.getItem('access_token')
      
      if (!token) {
        const refreshed = await refreshSession()
        if (refreshed) {
          setIsLoading(false)
          return
        }
        clearAccessTokenCookie()
        setIsLoading(false)
        return
      }

      setAccessTokenCookie(token)

      const cachedUser = readStoredUser()
      if (cachedUser) {
        setUser(cachedUser)
        setIsLoading(false)
        refreshUser().catch(() => {
          // 后台刷新失败不阻塞首屏，交给后续显式刷新或登录态失效处理
        })
        return
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
      // 如果token无效，清除它
      localStorage.removeItem('access_token')
      localStorage.removeItem(REFRESH_TOKEN_STORAGE_KEY)
      localStorage.removeItem(USER_STORAGE_KEY)
      clearAccessTokenCookie()
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
