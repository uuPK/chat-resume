import type { NextRequest } from 'next/server'
import { NextResponse } from 'next/server'

const PROTECTED_PREFIXES = ['/dashboard', '/settings', '/interviews', '/resume']
const PUBLIC_PATHS = new Set(['/login', '/register', '/'])

export function middleware(request: NextRequest) {
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

  if (accessToken) {
    return NextResponse.next()
  }

  const loginUrl = new URL('/login', request.url)
  const nextPath = `${pathname}${search}`
  loginUrl.searchParams.set('next', nextPath)
  return NextResponse.redirect(loginUrl)
}

export const config = {
  matcher: ['/((?!api|_next/static|_next/image|favicon.ico).*)'],
}
