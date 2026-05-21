// 用于提供 lib/apiErrors.ts 模块。

interface ApiErrorMessages {
  activeSubscriptionRequired?: string
}

// 用于把后端错误码转换成用户可读文案。
// 处理 Error 实例（含特殊错误码）和 Axios 风格的响应错误。
export function formatApiErrorMessage(
  error: unknown,
  messages: ApiErrorMessages,
  fallbackMessage: string,
): string {
  if (error instanceof Error) {
    if (error.message === 'active_subscription_required' && messages.activeSubscriptionRequired) {
      return messages.activeSubscriptionRequired
    }
    return error.message || fallbackMessage
  }
  const detail = (error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
  return detail || fallbackMessage
}
