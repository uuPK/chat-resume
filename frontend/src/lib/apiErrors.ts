// 用于提供 lib/apiErrors.ts 模块。

interface ApiErrorMessages {
  activeSubscriptionRequired: string
}

// 用于把后端错误码转换成用户可读文案。
export function formatApiErrorMessage(
  error: unknown,
  messages: ApiErrorMessages,
  fallbackMessage: string,
) {
  if (!(error instanceof Error)) return fallbackMessage
  if (error.message === 'active_subscription_required') {
    return messages.activeSubscriptionRequired
  }
  return error.message || fallbackMessage
}
