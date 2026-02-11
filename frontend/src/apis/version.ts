/**
 * API client for version endpoints
 */
import type { DataVersion } from '@/types'

import { apiUrl } from './base'

export interface VersionListResponse {
  items: DataVersion[]
  total: number
}

export async function getVersions(): Promise<VersionListResponse> {
  const response = await fetch(apiUrl('/versions'))
  if (!response.ok) throw new Error('Failed to get versions')
  return response.json()
}

export async function getLatestVersion(): Promise<DataVersion> {
  const response = await fetch(apiUrl('/versions/latest'))
  if (!response.ok) throw new Error('Failed to get latest version')
  return response.json()
}

export async function getVersion(versionId: number): Promise<DataVersion> {
  const response = await fetch(apiUrl(`/versions/${versionId}`))
  if (!response.ok) throw new Error('Failed to get version')
  return response.json()
}
