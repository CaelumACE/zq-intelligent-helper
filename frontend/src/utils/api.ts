const API_BASE = __API_BASE__
export { API_BASE }

export function authHeaders(): HeadersInit {
  const token = localStorage.getItem('token')
  return token ? { Authorization: `Bearer ${token}` } : {}
}
