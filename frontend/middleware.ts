import type { NextRequest } from 'next/server'
import { NextResponse } from 'next/server'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'
const PROTECTED_PREFIXES = ['/dashboard', '/settings', '/interviews', '/resume', '/resumes']
const PUBLIC_PATHS = new Set(['/login', '/register', '/'])

// 这里通过后端 /auth/me 校验 token 真伪，避免只凭 cookie 存在就放行受保护页面。
async function hasValidSession(accessToken: string): Promise<boolean> {
  try {
    const response = await fetch(`${API_BASE_URL}/api/auth/me`, {
      headers: { Authorization: `Bearer ${accessToken}` },
      cache: 'no-store',
    })
    return response.ok
  } catch {
    return false
  }
}

export async function middleware(request: NextRequest) {
  const { pathname, search } = request.nextUrl
  const accessToken = request.cookies.get('access_token')?.value

  if (PUBLIC_PATHS.has(pathname)) {
    return NextResponse.next()
  }

  const requiresAuth = PROTECTED_PREFIXES.some(
    (prefix) => pathname === prefix || pathname.startsWith(`${prefix}/`)
  )

  if (!requiresAuth) {
    return NextResponse.next()
  }

  if (accessToken && await hasValidSession(accessToken)) {
    return NextResponse.next()
  }

  const loginUrl = new URL('/login', request.url)
  const nextPath = `${pathname}${search}`
  loginUrl.searchParams.set('next', nextPath)
  const response = NextResponse.redirect(loginUrl)
  response.cookies.delete('access_token')
  return response
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)'],
}
