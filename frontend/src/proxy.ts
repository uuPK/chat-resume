// 用于提供 proxy.ts 模块。
import type { NextRequest } from 'next/server'
import { NextResponse } from 'next/server'
import createIntlProxy from 'next-intl/middleware'
import { isAppLocale, routing } from './i18n/routing'
import { apiUrl } from '@/lib/httpClient'
const PROTECTED_PREFIXES = ['/dashboard', '/settings', '/interviews', '/resume', '/resumes', '/enterprise', '/school']
const PUBLIC_PATHS = new Set(['/login', '/register', '/', '/resume/print'])
const CANONICAL_ORIGIN = 'https://www.chatresume.tech'
const CANONICAL_REDIRECT_HOSTS = new Set(['chatresu.vercel.app', 'chatresume.tech'])
const intlProxy = createIntlProxy(routing)

// 这里通过后端 /auth/me 获取当前用户信息，包括角色。
async function getValidUser(accessToken: string): Promise<any | null> {
  try {
    const response = await fetch(apiUrl('/api/auth/me'), {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: 'no-store',
    })
    if (!response.ok) return null;
    return await response.json()
  } catch {
    return null
  }
}

// 用于处理proxy。
export async function proxy(request: NextRequest) {
  const canonicalRedirect = getCanonicalRedirect(request)
  if (canonicalRedirect) {
    return canonicalRedirect
  }

  const { pathname, search } = request.nextUrl
  const accessToken = request.cookies.get('access_token')?.value
  const refreshToken = request.cookies.get('refresh_token')?.value
  const locale = getPathLocale(pathname)
  const pathnameWithoutLocale = stripLocalePrefix(pathname)

  if (pathname.startsWith('/resume/print')) {
    return NextResponse.next()
  }

  if (!locale) {
    const preferredLocale = getPreferredLocale(request)
    const localizedPathname = pathname === '/' ? '' : pathname
    const redirectUrl = new URL(`/${preferredLocale}${localizedPathname}${search}`, request.url)
    const response = NextResponse.redirect(redirectUrl)
    response.cookies.set('NEXT_LOCALE', preferredLocale, {
      path: '/',
      sameSite: 'lax',
      maxAge: 60 * 60 * 24 * 365,
    })
    return response
  }

  const intlResponse = intlProxy(request)
  if (isRedirect(intlResponse)) {
    return intlResponse
  }

  if (PUBLIC_PATHS.has(pathnameWithoutLocale)) {
    return intlResponse
  }

  const requiresAuth = PROTECTED_PREFIXES.some(
    (prefix) => pathnameWithoutLocale === prefix || pathnameWithoutLocale.startsWith(`${prefix}/`)
  )

  if (!requiresAuth) {
    return intlResponse
  }

  let user = null;
  if (accessToken) {
    user = await getValidUser(accessToken)
  }

  if (!user && !refreshToken) {
    const loginUrl = new URL(`/${locale || routing.defaultLocale}/login`, request.url)
    const nextPath = `${pathnameWithoutLocale}${search}`
    loginUrl.searchParams.set('next', nextPath)
    const response = NextResponse.redirect(loginUrl)
    response.cookies.delete('access_token')
    return response
  }

  if (!user && refreshToken) {
    // 允许带有 refreshToken 的请求进入，以便客户端尝试刷新
    return intlResponse
  }

  if (user) {
    const role = user.role || 'candidate'

    // 企业端路由保护
    if (pathnameWithoutLocale.startsWith('/enterprise') && role !== 'enterprise') {
      return NextResponse.redirect(new URL(`/${locale || routing.defaultLocale}/dashboard`, request.url))
    }

    // 高校端路由保护
    if (pathnameWithoutLocale.startsWith('/school') && role !== 'school') {
      return NextResponse.redirect(new URL(`/${locale || routing.defaultLocale}/dashboard`, request.url))
    }

    // 求职者路由保护
    const candidatePrefixes = ['/resumes', '/interviews', '/resume']
    const isCandidatePath = candidatePrefixes.some(p => pathnameWithoutLocale === p || pathnameWithoutLocale.startsWith(`${p}/`)) || pathnameWithoutLocale === '/dashboard'
    
    if (isCandidatePath && role !== 'candidate') {
      if (role === 'enterprise') return NextResponse.redirect(new URL(`/${locale || routing.defaultLocale}/enterprise/dashboard`, request.url))
      if (role === 'school') return NextResponse.redirect(new URL(`/${locale || routing.defaultLocale}/school/dashboard`, request.url))
    }

    return intlResponse
  }

  return NextResponse.redirect(new URL(`/${locale || routing.defaultLocale}/login`, request.url))
}

// 用于将线上旧域名规范化到正式域名。
function getCanonicalRedirect(request: NextRequest) {
  const host = getRequestHost(request)
  if (!CANONICAL_REDIRECT_HOSTS.has(host)) {
    return undefined
  }

  const redirectUrl = new URL(`${request.nextUrl.pathname}${request.nextUrl.search}`, CANONICAL_ORIGIN)
  return NextResponse.redirect(redirectUrl, 308)
}

// 用于读取代理后的真实请求host。
function getRequestHost(request: NextRequest) {
  const forwardedHost = request.headers.get('x-forwarded-host') || ''
  const host = forwardedHost || request.headers.get('host') || request.nextUrl.hostname
  return host.split(',')[0].trim().toLowerCase().replace(/:\d+$/, '')
}

// 用于获取路径语言环境。
function getPathLocale(pathname: string) {
  // Reads the first URL segment and treats it as locale only when supported.
  const firstSegment = pathname.split('/')[1]
  return isAppLocale(firstSegment) ? firstSegment : undefined
}

// 用于获取preferred语言环境。
function getPreferredLocale(request: NextRequest) {
  // Prefers an explicit user cookie, then falls back to browser language.
  const cookieLocale = request.cookies.get('NEXT_LOCALE')?.value
  if (isAppLocale(cookieLocale)) return cookieLocale

  const acceptLanguage = request.headers.get('accept-language')?.toLowerCase() || ''
  return acceptLanguage.includes('zh') ? 'zh' : 'en'
}

// 用于去除语言环境prefix。
function stripLocalePrefix(pathname: string) {
  // Normalizes localized paths so auth checks can keep their old route list.
  const locale = getPathLocale(pathname)
  if (!locale) return pathname
  const stripped = pathname.slice(locale.length + 1)
  return stripped || '/'
}

// 用于判断redirect。
function isRedirect(response: NextResponse) {
  // Identifies next-intl redirect responses before running auth checks.
  return response.status >= 300 && response.status < 400
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico|.*\\..*).*)'],
}
