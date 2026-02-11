/**
 * RAG Evaluation API client
 * Based on the new RagRecordRef architecture
 */

import { apiUrl } from './base'

// ============ Types ============

export interface RagEvaluationTriggerRequest {
  mode: 'by_kb' | 'by_date_range'
  knowledge_id?: number
  start_date?: string
  end_date?: string
  force?: boolean
}

export interface RagEvaluationTriggerResponse {
  job_id: string
  total_records: number
  pending_evaluation: number
}

export interface RagEvaluationStatusResponse {
  job_id: string
  status: string
  total: number
  completed: number
  failed: number
  skipped: number
}

export interface TrendDataPoint {
  date: string
  total_rag_queries: number
  evaluated_count: number
  evaluation_coverage: number
  pass_count: number
  fail_count: number
  undetermined_count: number
  pass_rate: number | null
  avg_total_score: number | null
  avg_retrieval_score: number | null
  avg_generation_score: number | null
}

export interface TrendComparison {
  pass_rate_change: number | null
  avg_score_change: number | null
}

export interface NonRagStats {
  direct_injection_count: number
  selected_documents_count: number
  non_rag_ratio: number
}

export interface EvaluationTrendsResponse {
  trends: TrendDataPoint[]
  comparison: {
    day_over_day?: TrendComparison
    week_over_week?: TrendComparison
  } | null
  non_rag_stats: NonRagStats | null
}

export interface PeriodStats {
  date_range: string
  evaluated_count: number
  pass_rate: number | null
  avg_total_score: number | null
}

export interface EvaluationCompareResponse {
  period1: PeriodStats
  period2: PeriodStats
  changes: {
    pass_rate_change: number | null
    avg_score_change: number | null
    improvement: boolean
  }
}

export interface LowScoreQueryItem {
  rag_record_ref_id: number
  raw_id: number
  record_date: string | null
  knowledge_id: number | null
  knowledge_name: string | null
  user_prompt: string | null
  evaluation_judgment: string | null
  total_score: number | null
  faithfulness_score: number | null
  trulens_groundedness: number | null
  ragas_query_context_relevance: number | null
  trulens_context_relevance: number | null
  evaluated_at: string | null
}

export interface LowScoreQueriesResponse {
  records: LowScoreQueryItem[]
  total: number
  filters_applied: Record<string, unknown>
}

export interface LowScoreKnowledgeBaseItem {
  knowledge_id: number
  knowledge_name: string | null
  namespace: string | null
  evaluated_count: number
  pass_count: number
  fail_count: number
  undetermined_count: number
  pass_rate: number | null
  fail_rate: number | null
  avg_total_score: number | null
  avg_faithfulness_score: number | null
  avg_trulens_groundedness: number | null
  avg_ragas_query_context_relevance: number | null
  avg_trulens_context_relevance: number | null
}

export interface LowScoreKnowledgeBasesResponse {
  knowledge_bases: LowScoreKnowledgeBaseItem[]
  total: number
}

export interface CoreMetrics {
  faithfulness_score: number | null
  trulens_groundedness: number | null
  ragas_query_context_relevance: number | null
  trulens_context_relevance: number | null
  ragas_context_precision_emb: number | null
}

export interface EvaluationResultData {
  id: number
  evaluation_judgment: string | null
  total_score: number | null
  retrieval_score: number | null
  generation_score: number | null
  core_metrics: CoreMetrics
  threshold: number
  evaluated_at: string | null
}

export interface RawDataPreview {
  user_prompt: string | null
  chunks_count: number | null
  chunks_preview: string[] | null
}

export interface RagRecordEvaluationDetailResponse {
  rag_record_ref_id: number
  raw_id: number
  evaluation_status: string
  evaluation_result: EvaluationResultData | null
  raw_data: RawDataPreview | null
}

export interface KnowledgeBaseEvaluationStats {
  rag_retrieval_count: number
  evaluated_count: number
  evaluation_coverage: number
  pass_count: number
  fail_count: number
  undetermined_count: number
  pass_rate: number | null
  avg_total_score: number | null
}

// ============ API Functions ============

/**
 * Trigger RAG evaluation job
 */
export async function triggerRagEvaluation(
  request: RagEvaluationTriggerRequest
): Promise<RagEvaluationTriggerResponse> {
  const url = apiUrl('/daily/evaluation/trigger')
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(request),
  })
  if (!response.ok) throw new Error('Failed to trigger evaluation')
  return response.json()
}

/**
 * Get RAG evaluation job status
 */
export async function getRagEvaluationStatus(
  jobId: string
): Promise<RagEvaluationStatusResponse> {
  const url = apiUrl(`/daily/evaluation/status/${jobId}`)
  const response = await fetch(url)
  if (!response.ok) throw new Error('Failed to get evaluation status')
  return response.json()
}

/**
 * Get evaluation trends
 */
export async function getEvaluationTrends(params?: {
  days?: number
  granularity?: string
  knowledge_id?: number
}): Promise<EvaluationTrendsResponse> {
  const searchParams = new URLSearchParams()
  if (params?.days) searchParams.set('days', params.days.toString())
  if (params?.granularity) searchParams.set('granularity', params.granularity)
  if (params?.knowledge_id) searchParams.set('knowledge_id', params.knowledge_id.toString())

  const url = apiUrl(`/daily/evaluation/trends${searchParams.toString() ? `?${searchParams}` : ''}`)
  const response = await fetch(url)
  if (!response.ok) throw new Error('Failed to get evaluation trends')
  return response.json()
}

/**
 * Compare evaluation periods
 */
export async function compareEvaluationPeriods(params: {
  period1_start: string
  period1_end: string
  period2_start: string
  period2_end: string
  knowledge_id?: number
}): Promise<EvaluationCompareResponse> {
  const searchParams = new URLSearchParams()
  searchParams.set('period1_start', params.period1_start)
  searchParams.set('period1_end', params.period1_end)
  searchParams.set('period2_start', params.period2_start)
  searchParams.set('period2_end', params.period2_end)
  if (params.knowledge_id) searchParams.set('knowledge_id', params.knowledge_id.toString())

  const url = apiUrl(`/daily/evaluation/compare?${searchParams}`)
  const response = await fetch(url)
  if (!response.ok) throw new Error('Failed to compare evaluation periods')
  return response.json()
}

/**
 * Get low score queries
 */
export async function getLowScoreQueries(params?: {
  start_date?: string
  end_date?: string
  knowledge_id?: number
  judgment?: string
  sort_by?: string
  limit?: number
  offset?: number
}): Promise<LowScoreQueriesResponse> {
  const searchParams = new URLSearchParams()
  if (params?.start_date) searchParams.set('start_date', params.start_date)
  if (params?.end_date) searchParams.set('end_date', params.end_date)
  if (params?.knowledge_id) searchParams.set('knowledge_id', params.knowledge_id.toString())
  if (params?.judgment) searchParams.set('judgment', params.judgment)
  if (params?.sort_by) searchParams.set('sort_by', params.sort_by)
  if (params?.limit) searchParams.set('limit', params.limit.toString())
  if (params?.offset) searchParams.set('offset', params.offset.toString())

  const url = apiUrl(`/daily/evaluation/low-score/queries${searchParams.toString() ? `?${searchParams}` : ''}`)
  const response = await fetch(url)
  if (!response.ok) throw new Error('Failed to get low score queries')
  return response.json()
}

/**
 * Get low score knowledge bases
 */
export async function getLowScoreKnowledgeBases(params?: {
  start_date?: string
  end_date?: string
  judgment?: string
  sort_by?: string
  limit?: number
  offset?: number
}): Promise<LowScoreKnowledgeBasesResponse> {
  const searchParams = new URLSearchParams()
  if (params?.start_date) searchParams.set('start_date', params.start_date)
  if (params?.end_date) searchParams.set('end_date', params.end_date)
  if (params?.judgment) searchParams.set('judgment', params.judgment)
  if (params?.sort_by) searchParams.set('sort_by', params.sort_by)
  if (params?.limit) searchParams.set('limit', params.limit.toString())
  if (params?.offset) searchParams.set('offset', params.offset.toString())

  const url = apiUrl(`/daily/evaluation/low-score/knowledge-bases${searchParams.toString() ? `?${searchParams}` : ''}`)
  const response = await fetch(url)
  if (!response.ok) throw new Error('Failed to get low score knowledge bases')
  return response.json()
}

/**
 * Get RAG record evaluation detail
 */
export async function getRagRecordEvaluationDetail(
  ragRecordRefId: number
): Promise<RagRecordEvaluationDetailResponse> {
  const url = apiUrl(`/daily/evaluation/rag-records/${ragRecordRefId}/evaluation`)
  const response = await fetch(url)
  if (!response.ok) throw new Error('Failed to get RAG record evaluation detail')
  return response.json()
}

/**
 * Get knowledge base evaluation stats
 */
export async function getKnowledgeBaseEvaluationStats(
  kbId: number
): Promise<KnowledgeBaseEvaluationStats> {
  const url = apiUrl(`/daily/evaluation/knowledge-bases/${kbId}/evaluation-stats`)
  const response = await fetch(url)
  if (!response.ok) throw new Error('Failed to get knowledge base evaluation stats')
  return response.json()
}
