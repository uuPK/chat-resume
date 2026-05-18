export const runtime = 'nodejs'

const MAX_LOG_CHARS = 2000

// 用于把未知值安全压缩为单行日志文本。
function stringifyLogValue(value: unknown): string {
  if (value === null || value === undefined) return '-'
  try {
    const text = typeof value === 'string' ? value : JSON.stringify(value)
    return text.length > MAX_LOG_CHARS ? `${text.slice(0, MAX_LOG_CHARS)}...` : text
  } catch {
    return String(value)
  }
}

// 用于判断请求体是否是普通对象。
function asLogRecord(value: unknown): Record<string, unknown> | null {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return null
  return value as Record<string, unknown>
}

// 用于接收浏览器侧调试日志并写入 Next dev server stdout。
export async function POST(request: Request) {
  let body: unknown
  try {
    body = await request.json()
  } catch {
    return Response.json({ ok: false }, { status: 400 })
  }

  const record = asLogRecord(body)
  if (!record) {
    return Response.json({ ok: false }, { status: 400 })
  }

  const source = typeof record.source === 'string' ? record.source : 'browser'
  const message = typeof record.message === 'string' ? record.message : 'client_log'
  console.info(
    `[browser-client] ${source} ${message} payload=${stringifyLogValue(record.payload)}`,
  )
  return Response.json({ ok: true })
}
