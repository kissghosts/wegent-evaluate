/**
 * API client for sync endpoints
 */
import type { SyncTriggerRequest } from '@/types'

import { apiUrl } from './base'

export async function triggerSync(params: SyncTriggerRequest) {
  const response = await fetch(apiUrl('/sync/trigger'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to trigger sync')
  }
  return response.json()
}

export async function getSyncStatus(syncId: string) {
  const response = await fetch(apiUrl(`/sync/status/${syncId}`))
  if (!response.ok) throw new Error('Failed to get sync status')
  return response.json()
}

export async function getSyncHistory(params: {
  page?: number
  page_size?: number
}) {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined) {
      searchParams.append(key, String(value))
    }
  })

  const response = await fetch(apiUrl(`/sync/history?${searchParams.toString()}`))
  if (!response.ok) throw new Error('Failed to get sync history')
  return response.json()
}
