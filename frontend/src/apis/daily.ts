/**
 * Daily report API client
 */

import { apiUrl } from './base'

export interface DailySummary {
  total_queries: number
  rag_retrieval_count: number
  direct_injection_count: number
  selected_documents_count: number
  active_kb_count: number
  active_user_count: number
}

export interface DailyComparison {
  total_queries_change: number
  rag_retrieval_change: number
}

export interface DailyDataPoint {
  date: string
  total_queries: number
  rag_retrieval_count: number
  direct_injection_count: number
  selected_documents_count: number
  active_kb_count?: number
  active_user_count?: number
}

export interface DailyOverviewResponse {
  summary: DailySummary
  comparison: DailyComparison | null
  daily: DailyDataPoint[]
  start_date: string
  end_date: string
}

export interface HourlyDataPoint {
  hour: number
  total_queries: number
  rag_retrieval_count: number
  direct_injection_count: number
  selected_documents_count: number
}

export interface TrendsResponse {
  granularity: 'day' | 'hour'
  data: DailyDataPoint[]
}

export interface KnowledgeBaseItem {
  knowledge_id: number
  knowledge_name: string | null
  namespace: string | null
  created_by_user_id?: number | null
  created_by_user_name?: string | null
  description?: string | null
  kb_type?: string | null
  created_at?: string | null
  updated_at?: string | null
  recent_7d_queries?: number
  recent_7d_used?: boolean
  // 注意：全局列表页当前不展示统计列，这些字段在列表接口中可能为 0
  total_queries: number
  rag_retrieval_count: number
  direct_injection_count: number
  selected_documents_count: number
  rank?: number
  primary_mode?: string
}

export interface KnowledgeBaseDetail {
  id: number
  name: string | null
  namespace: string | null
  kb_type: string | null
  is_active: boolean | null
  created_by_user_id?: number | null
  created_by_user_name?: string | null
  retrieval_config: {
    retriever_name: string | null
    retrieval_mode: string | null
    top_k: number | null
    score_threshold: number | null
    embedding_model: string | null
  } | null
  created_at: string | null
  updated_at: string | null
}

export interface KnowledgeBaseStats {
  summary: {
    knowledge_id: number
    knowledge_name: string | null
    namespace: string | null
    total_queries: number
    rag_retrieval_count: number
    direct_injection_count: number
    selected_documents_count: number
  }
  daily: DailyDataPoint[]
}

export interface QueryItem {
  id: number
  raw_id: number
  record_date: string | null
  context_type: string | null
  injection_mode: string | null
  evaluation_status: string | null
  query: string | null
  chunks_count: number | null
  sources: Array<{ index: number; kb_id: number; title: string }> | null
  created_at: string | null
}

export interface GlobalQueryItem extends QueryItem {
  knowledge_id: number | null
  knowledge_name: string | null
  namespace: string | null
}

export interface RagRecordDetail {
  id: number
  raw_id: number
  knowledge_id: number | null
  context_type: string | null
  injection_mode: string | null
  evaluation_status: string | null
  evaluation_result_id: number | null
  record_date: string | null
  name: string | null
  type_data: Record<string, unknown> | null
  extracted_text: string | null
  created_at: string | null
}

export interface SyncStatus {
  raw_db_configured: boolean
  hourly: {
    last_sync_time: string | null
    last_raw_id: number
    status: string | null
    records_synced: number
    error_message: string | null
  } | null
  daily: {
    last_sync_time: string | null
    status: string | null
    error_message: string | null
  } | null
}

export interface PaginatedResponse<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

/**
 * Get daily overview statistics
 */
export async function getDailyOverview(params?: {
  start_date?: string
  end_date?: string
}): Promise<DailyOverviewResponse> {
  const searchParams = new URLSearchParams()
  if (params?.start_date) searchParams.set('start_date', params.start_date)
  if (params?.end_date) searchParams.set('end_date', params.end_date)

  const url = apiUrl(`/daily/overview${searchParams.toString() ? `?${searchParams}` : ''}`)
  const response = await fetch(url)
  if (!response.ok) throw new Error('Failed to fetch daily overview')
  return response.json()
}

/**
 * Get trend data
 */
export async function getDailyTrends(params?: {
  days?: number
  granularity?: 'day' | 'hour'
}): Promise<TrendsResponse> {
  const searchParams = new URLSearchParams()
  if (params?.days) searchParams.set('days', params.days.toString())
  if (params?.granularity) searchParams.set('granularity', params.granularity)

  const url = apiUrl(`/daily/trends${searchParams.toString() ? `?${searchParams}` : ''}`)
  const response = await fetch(url)
  if (!response.ok) throw new Error('Failed to fetch trends')
  return response.json()
}

/**
 * Get hourly stats for a specific date
 */
export async function getHourlyStats(date: string): Promise<{
  date: string
  hourly: HourlyDataPoint[]
}> {
  const url = apiUrl(`/daily/${date}/hourly`)
  const response = await fetch(url)
  if (!response.ok) throw new Error('Failed to fetch hourly stats')
  return response.json()
}

/**
 * Get top knowledge bases
 */
export async function getTopKnowledgeBases(params?: {
  target_date?: string
  start_date?: string
  end_date?: string
  limit?: number
}): Promise<{ date: string; items: KnowledgeBaseItem[] }> {
  const searchParams = new URLSearchParams()
  if (params?.target_date) searchParams.set('target_date', params.target_date)
  if (params?.start_date) searchParams.set('start_date', params.start_date)
  if (params?.end_date) searchParams.set('end_date', params.end_date)
  if (params?.limit) searchParams.set('limit', params.limit.toString())

  const url = apiUrl(
    `/daily/knowledge-bases/top${searchParams.toString() ? `?${searchParams}` : ''}`
  )
  const response = await fetch(url)
  if (!response.ok) throw new Error('Failed to fetch top knowledge bases')
  return response.json()
}

/**
 * Get knowledge base list
 */
export async function getKnowledgeBases(params?: {
  q?: string
  page?: number
  page_size?: number
}): Promise<PaginatedResponse<KnowledgeBaseItem>> {
  const searchParams = new URLSearchParams()
  if (params?.q) searchParams.set('q', params.q)
  if (params?.page) searchParams.set('page', params.page.toString())
  if (params?.page_size) searchParams.set('page_size', params.page_size.toString())

  const url = apiUrl(
    `/daily/knowledge-bases${searchParams.toString() ? `?${searchParams}` : ''}`
  )
  const response = await fetch(url)
  if (!response.ok) throw new Error('Failed to fetch knowledge bases')
  return response.json()
}

/**
 * Get knowledge base detail
 */
export async function getKnowledgeBaseDetail(kbId: number): Promise<KnowledgeBaseDetail> {
  const url = apiUrl(`/daily/knowledge-bases/${kbId}`)
  const response = await fetch(url)
  if (!response.ok) throw new Error('Failed to fetch knowledge base detail')
  return response.json()
}

/**
 * Get knowledge base stats
 */
export async function getKnowledgeBaseStats(
  kbId: number,
  params?: { days?: number }
): Promise<KnowledgeBaseStats> {
  const searchParams = new URLSearchParams()
  if (params?.days) searchParams.set('days', params.days.toString())

  const url = apiUrl(
    `/daily/knowledge-bases/${kbId}/stats${searchParams.toString() ? `?${searchParams}` : ''}`
  )
  const response = await fetch(url)
  if (!response.ok) throw new Error('Failed to fetch knowledge base stats')
  return response.json()
}

/**
 * Get knowledge base queries
 */
export async function getKnowledgeBaseQueries(
  kbId: number,
  params?: {
    page?: number
    page_size?: number
    injection_mode?: string
    evaluation_status?: string
  }
): Promise<PaginatedResponse<QueryItem>> {
  const searchParams = new URLSearchParams()
  if (params?.page) searchParams.set('page', params.page.toString())
  if (params?.page_size) searchParams.set('page_size', params.page_size.toString())
  if (params?.injection_mode) searchParams.set('injection_mode', params.injection_mode)
  if (params?.evaluation_status) searchParams.set('evaluation_status', params.evaluation_status)

  const url = apiUrl(
    `/daily/knowledge-bases/${kbId}/queries${searchParams.toString() ? `?${searchParams}` : ''}`
  )
  const response = await fetch(url)
  if (!response.ok) throw new Error('Failed to fetch queries')
  return response.json()
}

/**
 * Get RAG record detail
 */
export async function getRagRecordDetail(recordId: number): Promise<RagRecordDetail> {
  const url = apiUrl(`/daily/rag-records/${recordId}`)
  const response = await fetch(url)
  if (!response.ok) throw new Error('Failed to fetch RAG record detail')
  return response.json()
}

/**
 * Get sync status
 */
export async function getSyncStatus(): Promise<SyncStatus> {
  const url = apiUrl('/daily/sync/status')
  const response = await fetch(url)
  if (!response.ok) throw new Error('Failed to fetch sync status')
  return response.json()
}

/**
 * Trigger sync
 */
export async function triggerSync(syncType: 'hourly' | 'daily' | 'full'): Promise<{
  status: string
  message: string
  result: Record<string, unknown> | null
}> {
  const url = apiUrl('/daily/sync/trigger')
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ sync_type: syncType }),
  })
  if (!response.ok) throw new Error('Failed to trigger sync')
  return response.json()
}

/**
 * Get global queries (all queries across all knowledge bases)
 */
export async function getGlobalQueries(params?: {
  page?: number
  page_size?: number
  injection_mode?: string
  start_date?: string
  end_date?: string
}): Promise<PaginatedResponse<GlobalQueryItem>> {
  const searchParams = new URLSearchParams()
  if (params?.page) searchParams.set('page', params.page.toString())
  if (params?.page_size) searchParams.set('page_size', params.page_size.toString())
  if (params?.injection_mode) searchParams.set('injection_mode', params.injection_mode)
  if (params?.start_date) searchParams.set('start_date', params.start_date)
  if (params?.end_date) searchParams.set('end_date', params.end_date)

  const url = apiUrl(
    `/daily/queries${searchParams.toString() ? `?${searchParams}` : ''}`
  )
  const response = await fetch(url)
  if (!response.ok) throw new Error('Failed to fetch global queries')
  return response.json()
}
