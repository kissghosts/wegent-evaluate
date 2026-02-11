'use client'

import { useState, useEffect, useCallback } from 'react'
import { QuickDaysSelector } from '@/components/common/date-range-selector'
import { useTranslation } from 'react-i18next'
import { useParams, useRouter } from 'next/navigation'
import {
  ArrowLeft,
  ChevronDown,
  ChevronRight,
  Database,
  FileSearch,
  Loader2,
  Settings,
  TrendingUp,
} from 'lucide-react'
import {
  getKnowledgeBaseDetail,
  getKnowledgeBaseStats,
  getKnowledgeBaseQueries,
  KnowledgeBaseDetail,
  KnowledgeBaseStats,
  QueryItem,
  PaginatedResponse,
} from '@/apis/daily'
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  LineChart,
  Line,
  PieChart,
  Pie,
  Cell,
} from 'recharts'

// Mode colors
const MODE_COLORS = {
  rag_retrieval: '#22c55e',
  direct_injection: '#a855f7',
  selected_documents: '#f97316',
}

// Format mode name
function formatModeName(mode: string, t: (key: string) => string): string {
  const modeKey = `ragMode.${mode}`
  return t(modeKey) || mode
}

// Format evaluation status
function formatEvalStatus(status: string, t: (key: string) => string): string {
  const statusKey = `evalStatus.${status}`
  return t(statusKey) || status
}

export default function KnowledgeBaseDetailPage() {
  const { t } = useTranslation()
  const router = useRouter()
  const params = useParams()
  const kbId = Number(params.id)

  const [detail, setDetail] = useState<KnowledgeBaseDetail | null>(null)
  const [stats, setStats] = useState<KnowledgeBaseStats | null>(null)
  const [queries, setQueries] = useState<PaginatedResponse<QueryItem> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [trendDays, setTrendDays] = useState(7)
  const [queryPage, setQueryPage] = useState(1)
  const [expandedQuery, setExpandedQuery] = useState<number | null>(null)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [detailData, statsData, queriesData] = await Promise.all([
        getKnowledgeBaseDetail(kbId),
        getKnowledgeBaseStats(kbId, { days: trendDays }),
        getKnowledgeBaseQueries(kbId, { page: queryPage, page_size: 10 }),
      ])

      setDetail(detailData)
      setStats(statsData)
      setQueries(queriesData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data')
    } finally {
      setLoading(false)
    }
  }, [kbId, trendDays, queryPage])

  useEffect(() => {
    if (kbId) {
      fetchData()
    }
  }, [kbId, fetchData])

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <span className="ml-2">{t('common.loading')}</span>
      </div>
    )
  }

  if (error || !detail || !stats) {
    return (
      <div className="space-y-4">
        <button
          onClick={() => router.back()}
          className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="h-4 w-4" />
          {t('common.back')}
        </button>
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
          {error || 'Knowledge base not found'}
        </div>
      </div>
    )
  }

  // Prepare pie chart data
  const pieData = [
    { name: formatModeName('rag_retrieval', t), value: stats.summary.rag_retrieval_count, color: MODE_COLORS.rag_retrieval },
    { name: formatModeName('direct_injection', t), value: stats.summary.direct_injection_count, color: MODE_COLORS.direct_injection },
    { name: formatModeName('selected_documents', t), value: stats.summary.selected_documents_count, color: MODE_COLORS.selected_documents },
  ].filter(d => d.value > 0)

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-4">
        <button
          onClick={() => router.back()}
          className="inline-flex items-center justify-center rounded-full p-2 hover:bg-muted"
        >
          <ArrowLeft className="h-5 w-5" />
        </button>
        <div>
          <h1 className="text-2xl font-semibold">{detail.name || `KB-${detail.id}`}</h1>
          {(detail.created_by_user_name || detail.created_by_user_id) && (
            <p className="text-sm text-muted-foreground">
              {t('knowledgeBase.creator', 'Creator')}: {detail.created_by_user_name || `UID-${detail.created_by_user_id}`}
            </p>
          )}
          <p className="text-sm text-muted-foreground">
            {detail.namespace || 'default'} · {detail.kb_type || 'classic'}
          </p>
        </div>
        <span className={`ml-auto inline-flex items-center rounded-full px-3 py-1 text-sm font-medium ${
          detail.is_active ? 'bg-green-100 text-green-700' : 'bg-gray-100 text-gray-700'
        }`}>
          {detail.is_active ? t('knowledgeBase.active') : t('knowledgeBase.inactive')}
        </span>
      </div>

      {/* Configuration Card */}
      {detail.retrieval_config && (
        <div className="rounded-lg border bg-card p-4">
          <div className="flex items-center gap-2 mb-3">
            <Settings className="h-5 w-5 text-muted-foreground" />
            <h2 className="font-semibold">{t('knowledgeBase.config')}</h2>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm">
            <div>
              <p className="text-muted-foreground">{t('knowledgeBase.retriever')}</p>
              <p className="font-medium">{detail.retrieval_config.retriever_name || '-'}</p>
            </div>
            <div>
              <p className="text-muted-foreground">{t('knowledgeBase.embeddingModel')}</p>
              <p className="font-medium">{detail.retrieval_config.embedding_model || '-'}</p>
            </div>
            <div>
              <p className="text-muted-foreground">{t('knowledgeBase.topK')}</p>
              <p className="font-medium">{detail.retrieval_config.top_k ?? '-'}</p>
            </div>
            <div>
              <p className="text-muted-foreground">{t('knowledgeBase.scoreThreshold')}</p>
              <p className="font-medium">{detail.retrieval_config.score_threshold ?? '-'}</p>
            </div>
          </div>
        </div>
      )}

      {/* Stats Overview */}
      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <div className="rounded-lg border bg-blue-50 p-4">
          <p className="text-sm text-muted-foreground">{t('dashboard.totalQueries')}</p>
          <p className="text-2xl font-bold text-blue-600">{stats.summary.total_queries}</p>
        </div>
        <div className="rounded-lg border bg-green-50 p-4">
          <p className="text-sm text-muted-foreground">{t('dashboard.ragRetrieval')}</p>
          <p className="text-2xl font-bold text-green-600">{stats.summary.rag_retrieval_count}</p>
        </div>
        <div className="rounded-lg border bg-purple-50 p-4">
          <p className="text-sm text-muted-foreground">{t('dashboard.directInjection')}</p>
          <p className="text-2xl font-bold text-purple-600">{stats.summary.direct_injection_count}</p>
        </div>
        <div className="rounded-lg border bg-orange-50 p-4">
          <p className="text-sm text-muted-foreground">{t('dashboard.selectedDocuments')}</p>
          <p className="text-2xl font-bold text-orange-600">{stats.summary.selected_documents_count}</p>
        </div>
      </div>

      {/* Charts Row */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Usage Trend */}
        <div className="lg:col-span-2 rounded-lg border bg-card p-4">
          <div className="flex items-center justify-between mb-4">
            <div className="flex items-center gap-2">
              <TrendingUp className="h-5 w-5 text-primary" />
              <h2 className="font-semibold">{t('knowledgeBase.usageTrend')}</h2>
            </div>
            <QuickDaysSelector
              value={trendDays}
              options={[
                { days: 7, label: t('dashboard.last7Days') },
                { days: 30, label: t('dashboard.last30Days') },
              ]}
              onChange={setTrendDays}
            />
          </div>

          {stats.daily.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={stats.daily}>
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis
                  dataKey="date"
                  tickFormatter={(value) => {
                    const date = new Date(value)
                    return `${date.getMonth() + 1}/${date.getDate()}`
                  }}
                />
                <YAxis />
                <Tooltip labelFormatter={(value) => new Date(value).toLocaleDateString()} />
                <Legend />
                <Line
                  type="monotone"
                  dataKey="total_queries"
                  name={t('dashboard.totalQueries')}
                  stroke="#3b82f6"
                  strokeWidth={2}
                />
              </LineChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-[250px] items-center justify-center text-muted-foreground">
              {t('common.noData')}
            </div>
          )}
        </div>

        {/* Mode Distribution */}
        <div className="rounded-lg border bg-card p-4">
          <div className="flex items-center gap-2 mb-4">
            <Database className="h-5 w-5 text-primary" />
            <h2 className="font-semibold">{t('knowledgeBase.modeDistribution')}</h2>
          </div>

          {pieData.length > 0 ? (
            <ResponsiveContainer width="100%" height={250}>
              <PieChart>
                <Pie
                  data={pieData}
                  dataKey="value"
                  nameKey="name"
                  cx="50%"
                  cy="50%"
                  outerRadius={80}
                  label={({ name, percent }) => `${name} ${(percent * 100).toFixed(0)}%`}
                  labelLine={false}
                >
                  {pieData.map((entry, index) => (
                    <Cell key={`cell-${index}`} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          ) : (
            <div className="flex h-[250px] items-center justify-center text-muted-foreground">
              {t('common.noData')}
            </div>
          )}
        </div>
      </div>

      {/* Recent Queries */}
      <div className="rounded-lg border bg-card p-4">
        <div className="flex items-center gap-2 mb-4">
          <FileSearch className="h-5 w-5 text-primary" />
          <h2 className="font-semibold">{t('knowledgeBase.recentQueries')}</h2>
        </div>

        {queries && queries.items.length > 0 ? (
          <>
            <div className="space-y-2">
              {queries.items.map((query) => (
                <div key={query.id} className="rounded-lg border p-3">
                  <div
                    className="flex items-center justify-between cursor-pointer"
                    onClick={() => setExpandedQuery(expandedQuery === query.id ? null : query.id)}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1">
                        <span className="font-mono text-xs">#{query.id}/{query.raw_id}</span>
                        <span>{query.created_at ? new Date(query.created_at).toLocaleString() : '-'}</span>
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                          query.injection_mode === 'rag_retrieval'
                            ? 'bg-green-100 text-green-700'
                            : query.injection_mode === 'direct_injection'
                            ? 'bg-purple-100 text-purple-700'
                            : 'bg-orange-100 text-orange-700'
                        }`}>
                          {formatModeName(query.injection_mode || 'unknown', t)}
                        </span>
                        <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                          query.evaluation_status === 'completed'
                            ? 'bg-blue-100 text-blue-700'
                            : query.evaluation_status === 'failed'
                            ? 'bg-red-100 text-red-700'
                            : 'bg-gray-100 text-gray-700'
                        }`}>
                          {formatEvalStatus(query.evaluation_status || 'pending', t)}
                        </span>
                      </div>
                      <p className="font-medium truncate">{query.query || '-'}</p>
                    </div>
                    <div className="flex items-center gap-4 ml-4">
                      {query.chunks_count !== null && (
                        <span className="text-sm text-muted-foreground">
                          {query.chunks_count} chunks
                        </span>
                      )}
                      {expandedQuery === query.id ? (
                        <ChevronDown className="h-5 w-5 text-muted-foreground" />
                      ) : (
                        <ChevronRight className="h-5 w-5 text-muted-foreground" />
                      )}
                    </div>
                  </div>

                  {expandedQuery === query.id && query.sources && query.sources.length > 0 && (
                    <div className="mt-3 pt-3 border-t">
                      <p className="text-sm font-medium mb-2">{t('knowledgeBase.sources')}:</p>
                      <ul className="space-y-1 text-sm text-muted-foreground">
                        {query.sources.map((source, idx) => (
                          <li key={idx} className="flex items-center gap-2">
                            <span className="inline-flex h-5 w-5 items-center justify-center rounded-full bg-muted text-xs">
                              {source.index}
                            </span>
                            <span className="truncate">{source.title}</span>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
            </div>

            {/* Pagination */}
            {queries.total > 10 && (
              <div className="flex items-center justify-between mt-4 pt-4 border-t">
                <span className="text-sm text-muted-foreground">
                  {queries.total} total
                </span>
                <div className="flex gap-2">
                  <button
                    onClick={() => setQueryPage(p => Math.max(1, p - 1))}
                    disabled={queryPage === 1}
                    className="px-3 py-1 text-sm rounded bg-muted disabled:opacity-50"
                  >
                    Previous
                  </button>
                  <span className="px-3 py-1 text-sm">
                    Page {queryPage} of {Math.ceil(queries.total / 10)}
                  </span>
                  <button
                    onClick={() => setQueryPage(p => p + 1)}
                    disabled={queryPage >= Math.ceil(queries.total / 10)}
                    className="px-3 py-1 text-sm rounded bg-muted disabled:opacity-50"
                  >
                    Next
                  </button>
                </div>
              </div>
            )}
          </>
        ) : (
          <div className="py-8 text-center text-muted-foreground">
            {t('common.noData')}
          </div>
        )}
      </div>
    </div>
  )
}
