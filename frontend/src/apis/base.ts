/**
 * Centralized API base URL helpers for the frontend.
 *
 * Convention:
 * - API origin: http(s)://host:port (no trailing /api)
 * - API prefix: /api
 * - Build full URLs via apiUrl('/path')
 */

const DEFAULT_API_ORIGIN = 'http://localhost:8000'

function normalizeOrigin(input: string): string {
  // Trim whitespace and trailing slashes
  let s = input.trim().replace(/\/+$/g, '')
  // If someone provides .../api, normalize back to origin
  if (s.endsWith('/api')) s = s.slice(0, -4)
  return s
}

/**
 * Backend origin (scheme + host + optional port). Example: http://localhost:8000
 */
export const API_ORIGIN = normalizeOrigin(
  process.env.NEXT_PUBLIC_API_BASE_URL || DEFAULT_API_ORIGIN
)

/**
 * Backend API prefix.
 */
export const API_PREFIX = '/api'

/**
 * Build a full API URL with the configured origin + /api prefix.
 */
export function apiUrl(path: string): string {
  const p = path.startsWith('/') ? path : `/${path}`
  return `${API_ORIGIN}${API_PREFIX}${p}`
}
