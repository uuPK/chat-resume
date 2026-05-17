// 用于提供 lib/httpClient.ts 模块。
export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

// 用于安全拼接 API 地址，避免重复或缺失斜杠。
function joinApiUrl(baseUrl: string, path: string): string {
  const normalizedBase = baseUrl.replace(/\/+$/, '')
  const normalizedPath = path.startsWith('/') ? path : `/${path}`
  return `${normalizedBase}${normalizedPath}`
}

// 用于处理API地址。
export function apiUrl(path: string, baseUrl = API_BASE_URL): string {
  return joinApiUrl(baseUrl, path)
}

// 统一通过 HttpOnly Cookie 发起带登录态的请求。
export function apiFetch(path: string, init: RequestInit = {}, baseUrl = API_BASE_URL) {
  const url = apiUrl(path, baseUrl)
  return fetch(url, {
    ...init,
    credentials: 'include',
  }).catch((error) => {
    const message = error instanceof Error ? error.message : String(error)
    throw new Error(`API请求失败: ${url} (${message})`)
  })
}

// 给外部供应商代理请求设置前端超时，避免 UI 长时间停在连接中。
export async function fetchWithTimeout(
  path: string,
  init: RequestInit = {},
  timeoutMs = 45000,
  baseUrl = API_BASE_URL,
) {
  const controller = new AbortController()
  const timeoutId = setTimeout(() => controller.abort(), timeoutMs)
  try {
    return await apiFetch(path, { ...init, signal: controller.signal }, baseUrl)
  } finally {
    clearTimeout(timeoutId)
  }
}

// 处理 API 响应，并保留后端 detail 作为用户可见错误。
export async function handleApiResponse<T>(
  response: Response,
  fallbackMessage = `API请求失败: ${response.status}`,
): Promise<T> {
  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}))
    const detail = errorData.detail
    const message =
      typeof detail === 'string'
        ? detail
        : Array.isArray(detail)
          ? detail.map((e: { msg?: string }) => e.msg ?? String(e)).join('; ')
          : fallbackMessage
    throw new Error(message)
  }

  if (response.status === 204) {
    return undefined as T
  }
  const body = await response.text()
  if (!body) {
    return undefined as T
  }
  return JSON.parse(body) as T
}
