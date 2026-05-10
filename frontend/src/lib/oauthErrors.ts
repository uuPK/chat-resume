const OAUTH_ERROR_MESSAGES: Record<string, string> = {
  cancelled: '已取消 Google 登录',
  invalid_state: '登录状态已失效，请重试',
  google_exchange_failed: 'Google 登录失败，请重试',
  unverified_email: 'Google 邮箱未验证，无法登录',
  account_conflict: '该邮箱已存在，请先使用邮箱密码登录',
  provider_unavailable: 'Google 登录暂不可用，请稍后重试',
  config_missing: 'Google 登录未配置，请联系管理员',
  unknown: 'Google 登录失败，请重试',
}

export function getOAuthErrorMessage(errorCode: string | null) {
  if (!errorCode) return null
  return OAUTH_ERROR_MESSAGES[errorCode] || OAUTH_ERROR_MESSAGES.unknown
}
