/**
 * 网络请求重试封装
 * - 默认仅对 GET 请求的网络错误（TypeError/failed）和 502/503/504 重试
 * - POST/PUT/DELETE/PATCH 等写操作默认不重试（避免重复提交副作用）
 * - 4xx 不重试（业务错误）
 * - SSE 流一旦开始接收数据，调用方应停止重试
 */

const RETRY_STATUS = new Set([502, 503, 504])
const MAX_RETRIES = 2
const BASE_DELAY = 500

/** 安全可重试的 HTTP 方法（幂等） */
const IDEMPOTENT_METHODS = new Set(['GET', 'HEAD', 'OPTIONS'])

export function isRetryableError(err: unknown): boolean {
  if (!err) return false
  // AbortError 不重试
  if ((err as Error)?.name === 'AbortError') return false
  // 网络层错误（fetch reject 通常是 TypeError）
  if (err instanceof TypeError) return true
  const msg = (err as Error)?.message?.toLowerCase() ?? ''
  return msg.includes('failed to fetch') || msg.includes('networkerror') || msg.includes('load failed')
}

export function isRetryableStatus(status: number): boolean {
  return RETRY_STATUS.has(status)
}

/**
 * 判断给定 HTTP method 是否默认允许重试。
 * 只有幂等方法（GET/HEAD/OPTIONS）默认重试；写操作需显式开启。
 */
export function isMethodIdempotent(method?: string): boolean {
  if (!method) return true // fetch 默认 GET
  return IDEMPOTENT_METHODS.has(method.toUpperCase())
}

function delay(ms: number, signal?: AbortSignal | null): Promise<void> {
  return new Promise((resolve, reject) => {
    if (signal?.aborted) {
      reject(new DOMException('Aborted', 'AbortError'))
      return
    }
    const timer = setTimeout(resolve, ms)
    signal?.addEventListener('abort', () => {
      clearTimeout(timer)
      reject(new DOMException('Aborted', 'AbortError'))
    }, { once: true })
  })
}

export interface RetryOptions {
  maxRetries?: number
  baseDelay?: number
  signal?: AbortSignal
  /**
   * 是否强制重试（忽略 method 判断）。
   * 默认 false：仅 GET/HEAD/OPTIONS 重试。
   * 写操作只有在调用方确认具备幂等键/可安全重放时才应设为 true。
   */
  forceRetry?: boolean
  /** 每次重试前回调，可用于提示用户 */
  onRetry?: (attempt: number, error: unknown) => void
}

/**
 * 带重试的 fetch。
 * 默认仅对幂等方法（GET）在「尚未获得 response」或「response 状态为 502/503/504」时重试；
 * 写操作默认不重试。一旦拿到 2xx/4xx 等正常响应就返回，由调用方处理。
 */
export async function fetchWithRetry(
  input: RequestInfo | URL,
  init: RequestInit = {},
  options: RetryOptions = {}
): Promise<Response> {
  const method = (init.method || 'GET').toUpperCase()
  const retryAllowed = options.forceRetry || isMethodIdempotent(method)

  // 写操作且未显式强制重试：直接走一次 fetch，不做任何重试
  if (!retryAllowed) {
    return fetch(input, { ...init, signal: options.signal ?? init.signal })
  }

  const maxRetries = options.maxRetries ?? MAX_RETRIES
  const baseDelay = options.baseDelay ?? BASE_DELAY
  const signal = options.signal ?? init.signal

  let lastError: unknown = null

  for (let attempt = 0; attempt <= maxRetries; attempt++) {
    try {
      // 每次尝试都需要独立的 Request 对象（body 可能被消耗）
      const res = await fetch(input, { ...init, signal })
      if (isRetryableStatus(res.status) && attempt < maxRetries) {
        options.onRetry?.(attempt + 1, new Error(`HTTP ${res.status}`))
        await delay(baseDelay * Math.pow(2, attempt), signal)
        continue
      }
      return res
    } catch (err) {
      lastError = err
      if ((err as Error)?.name === 'AbortError') throw err
      if (attempt >= maxRetries || !isRetryableError(err)) throw err
      options.onRetry?.(attempt + 1, err)
      await delay(baseDelay * Math.pow(2, attempt), signal)
    }
  }
  throw lastError ?? new Error('fetch failed')
}
