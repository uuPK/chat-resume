import zhAuth from '../../locales/zh/auth.json'
import enAuth from '../../locales/en/auth.json'

const OAUTH_ERROR_KEYS = new Set([
  'cancelled',
  'invalid_state',
  'google_exchange_failed',
  'unverified_email',
  'account_conflict',
  'provider_unavailable',
  'config_missing',
  'unknown',
])

function currentOAuthMessages() {
  // Keeps legacy callers localized while pages use translation keys directly.
  const locale = document.cookie.includes('NEXT_LOCALE=en') ? 'en' : 'zh'
  return locale === 'en' ? enAuth.oauth.errors : zhAuth.oauth.errors
}

export function getOAuthErrorMessage(errorCode: string | null) {
  if (!errorCode) return null
  const messages = currentOAuthMessages()
  const key = OAUTH_ERROR_KEYS.has(errorCode) ? errorCode : 'unknown'
  return messages[key as keyof typeof messages]
}

export function getOAuthErrorKey(errorCode: string | null) {
  if (!errorCode) return null
  return OAUTH_ERROR_KEYS.has(errorCode) ? errorCode : 'unknown'
}
