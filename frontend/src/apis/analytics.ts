/**
 * API client for analytics endpoints
 */

import { apiUrl } from './base'

export async function getTrends(params: {
  start_date: string
  end_date: string
  metric?: 'faithfulness' | 'answer_relevancy' | 'context_precision' | 'overall'
  group_by?: 'day' | 'week' | 'month'
  retriever_name?: string
  embedding_model?: string
  version_id?: number
}) {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      searchParams.append(key, String(value))
    }
  })

  const response = await fetch(apiUrl(`/analytics/trends?${searchParams.toString()}`))
  if (!response.ok) throw new Error('Failed to get trends')
  return response.json()
}

export async function getRetrieverComparison(params: {
  start_date: string
  end_date: string
  version_id?: number
}) {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      searchParams.append(key, String(value))
    }
  })

  const response = await fetch(
    apiUrl(`/analytics/comparison/retriever?${searchParams.toString()}`)
  )
  if (!response.ok) throw new Error('Failed to get retriever comparison')
  return response.json()
}

export async function getEmbeddingComparison(params: {
  start_date: string
  end_date: string
  version_id?: number
}) {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      searchParams.append(key, String(value))
    }
  })

  const response = await fetch(
    apiUrl(`/analytics/comparison/embedding?${searchParams.toString()}`)
  )
  if (!response.ok) throw new Error('Failed to get embedding comparison')
  return response.json()
}

export async function getContextComparison(subtaskContextId: number) {
  const response = await fetch(apiUrl(`/analytics/comparison/context/${subtaskContextId}`))
  if (!response.ok) throw new Error('Failed to get context comparison')
  return response.json()
}

export async function getIssuesAnalytics(params: {
  start_date: string
  end_date: string
  version_id?: number
}) {
  const searchParams = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== null) {
      searchParams.append(key, String(value))
    }
  })

  const response = await fetch(apiUrl(`/analytics/issues?${searchParams.toString()}`))
  if (!response.ok) throw new Error('Failed to get issues analytics')
  return response.json()
}
