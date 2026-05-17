import assert from 'node:assert/strict'

// 用于在无 window 环境验证 fetchWithTimeout 超时行为。
globalThis.fetch = async (_url, init = {}) => {
  await new Promise((resolve, reject) => {
    if (init.signal) {
      init.signal.addEventListener('abort', () => {
        const error = new Error('The operation was aborted')
        error.name = 'AbortError'
        reject(error)
      })
    }
  })
}

const { fetchWithTimeout } = await import('../src/lib/httpClient.ts')

let caughtError
try {
  await fetchWithTimeout('/health', {}, 5, 'http://localhost:8000')
} catch (error) {
  caughtError = error
}

assert.ok(caughtError instanceof Error)
assert.match(caughtError.message, /API请求超时/)
assert.match(caughtError.message, /\/health/)
assert.match(caughtError.message, /5ms/)

console.log('fetchWithTimeout no-window check passed')
