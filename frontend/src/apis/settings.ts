/**
 * API client for settings configuration endpoints
 */

import { apiUrl } from './base'

export interface SyncConfig {
  external_api_base_url: string
  external_api_username: string
  sync_cron_expression: string
}

export interface EvaluationConfig {
  ragas_llm_model: string
  ragas_embedding_model: string
  evaluation_cron_expression: string
  evaluation_batch_size: number
}

export interface SettingsConfig {
  sync: SyncConfig
  evaluation: EvaluationConfig
}

export interface SetExternalApiBaseUrlResponse {
  success: boolean
  message: string
  external_api_base_url: string
}

export interface SetExternalApiCredentialsResponse {
  success: boolean
  message: string
  username: string
}

export async function getSettingsConfig(): Promise<SettingsConfig> {
  const response = await fetch(apiUrl('/settings/config'))
  if (!response.ok) throw new Error('Failed to get settings config')
  return response.json()
}

export async function setExternalApiBaseUrl(url: string): Promise<SetExternalApiBaseUrlResponse> {
  const response = await fetch(apiUrl('/settings/external-api-base-url'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ external_api_base_url: url }),
  })
  if (!response.ok) throw new Error('Failed to set external API base URL')
  return response.json()
}

export async function setExternalApiCredentials(username: string, password: string): Promise<SetExternalApiCredentialsResponse> {
  const response = await fetch(apiUrl('/settings/external-api-credentials'), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify({ username, password }),
  })
  if (!response.ok) throw new Error('Failed to set external API credentials')
  return response.json()
}
