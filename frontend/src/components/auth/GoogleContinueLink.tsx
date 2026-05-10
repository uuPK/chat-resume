'use client'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export function getGoogleLoginUrl() {
  return `${API_BASE_URL}/api/auth/google/login`
}

export default function GoogleContinueLink() {
  return (
    <a
      href={getGoogleLoginUrl()}
      aria-label="使用 Google 继续"
      className="flex h-12 w-full items-center justify-center gap-3 rounded-full border text-base font-semibold transition-colors hover:bg-gray-50"
      style={{ borderColor: 'rgba(91,97,110,0.28)', color: '#0a0b0d' }}
    >
      <span
        aria-hidden="true"
        className="flex h-6 w-6 items-center justify-center rounded-full text-sm font-bold"
        style={{ border: '1px solid rgba(91,97,110,0.28)', color: '#0052ff' }}
      >
        G
      </span>
      <span>使用 Google 继续</span>
    </a>
  )
}
