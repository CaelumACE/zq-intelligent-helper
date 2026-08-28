import { fetchWithRetry, isRetryableError, isRetryableStatus, type RetryOptions } from './retry'

const API_BASE = __API_BASE__
export { API_BASE }

export function authHeaders(): HeadersInit {
  const token = sessionStorage.getItem('token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}

let unauthorizedHandler: (() => void) | null = null

export function setUnauthorizedHandler(handler: (() => void) | null) {
  unauthorizedHandler = handler
}

/** 供SSE等非apiFetch场景手动触发401处理（清token+弹登录） */
export function handleUnauthorized() {
  if (unauthorizedHandler) unauthorizedHandler()
}

export interface ApiFetchOptions extends RequestInit {
  /** 重试配置。设为 false 关闭重试；默认对网络错误/502/503/504 重试最多 2 次 */
  retry?: RetryOptions | false
}

/**
 * 统一请求封装：
 * - 自动携带 Authorization
 * - 网络错误/502/503/504 自动重试（最多 2 次，指数退避）
 * - 401 统一触发登录框
 *
 * SSE 流式接口请传 { retry: false }，由调用方处理；
 * 因为流式请求一旦建立连接就不能安全重试（会重复输出）。
 */
export async function apiFetch(input: RequestInfo | URL, init: ApiFetchOptions = {}): Promise<Response> {
  const { retry, ...fetchInit } = init
  const headers = new Headers(fetchInit.headers || {})
  const token = sessionStorage.getItem('token')
  if (token && !headers.has('Authorization')) {
    headers.set('Authorization', `Bearer ${token}`)
  }

  // SSE/上传/显式关闭 → 不重试
  if (retry === false) {
    const res = await fetch(input, { ...fetchInit, headers })
    if (res.status === 401 && unauthorizedHandler) unauthorizedHandler()
    return res
  }

  const retryOptions: RetryOptions = {
    maxRetries: retry?.maxRetries ?? 2,
    baseDelay: retry?.baseDelay ?? 500,
    signal: (retry?.signal ?? fetchInit.signal) || undefined,
    onRetry: retry?.onRetry,
  }

  const res = await fetchWithRetry(input, { ...fetchInit, headers }, retryOptions)
  if (res.status === 401 && unauthorizedHandler) unauthorizedHandler()
  return res
}

export { isRetryableError, isRetryableStatus }
