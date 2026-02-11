'use client'

import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useRouter, useSearchParams } from 'next/navigation'
import {
  ChevronDown,
  ChevronRight,
  Database,
  FileSearch,
  Loader2,
} from 'lucide-react'
import {
  getGlobalQueries,
  GlobalQueryItem,
  PaginatedResponse,
} from '@/apis/daily'
import {
  getLastNDaysDateRange,
  QuickDaysSelector,
} from '@/components/common/date-range-selector'

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

export default function QueriesPage() {
  const { t } = useTranslation()
  const router = useRouter()
  const searchParams = useSearchParams()

  // Read initial filter from URL
  const initialMode = searchParams.get('mode') || ''

  const [data, setData] = useState<PaginatedResponse<GlobalQueryItem> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [modeFilter, setModeFilter] = useState(initialMode)
  const [rangeDays, setRangeDays] = useState(7)
  const [expandedQuery, setExpandedQuery] = useState<number | null>(null)
  const pageSize = 20

  const dateRange = getLastNDaysDateRange(rangeDays)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await getGlobalQueries({
        page,
        page_size: pageSize,
        injection_mode: modeFilter || undefined,
        start_date: dateRange.startDate,
        end_date: dateRange.endDate,
      })
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data')
    } finally {
      setLoading(false)
    }
  }, [page, modeFilter, dateRange.startDate, dateRange.endDate])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Update URL when mode filter changes
  const handleModeChange = (mode: string) => {
    setModeFilter(mode)
    setPage(1)
    const url = new URL(window.location.href)
    if (mode) {
      url.searchParams.set('mode', mode)
    } else {
      url.searchParams.delete('mode')
    }
    router.replace(url.pathname + url.search)
  }

  if (loading && !data) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <span className="ml-2">{t('common.loading')}</span>
      </div>
    )
  }

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <FileSearch className="h-6 w-6 text-primary" />
          <h1 className="text-2xl font-semibold">{t('queries.title', 'Query Records')}</h1>
        </div>
        <div className="flex items-center gap-4">
          <QuickDaysSelector
            value={rangeDays}
            options={[
              { days: 7, label: t('dashboard.last7Days') },
              { days: 30, label: t('dashboard.last30Days') },
            ]}
            onChange={(days) => {
              setRangeDays(days)
              setPage(1)
            }}
          />
          <select
            value={modeFilter}
            onChange={(e) => handleModeChange(e.target.value)}
            className="rounded-md border px-3 py-1.5 text-sm"
          >
            <option value="">{t('queries.allModes', 'All Modes')}</option>
            <option value="rag_retrieval">{t('ragMode.rag_retrieval')}</option>
            <option value="direct_injection">{t('ragMode.direct_injection')}</option>
            <option value="selected_documents">{t('ragMode.selected_documents')}</option>
          </select>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
          {error}
        </div>
      )}

      {data && data.items.length > 0 ? (
        <>
          <div className="space-y-2">
            {data.items.map((query) => (
              <div key={query.id} className="rounded-lg border bg-card p-3">
                <div
                  className="flex items-center justify-between cursor-pointer"
                  onClick={() => setExpandedQuery(expandedQuery === query.id ? null : query.id)}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 text-sm text-muted-foreground mb-1 flex-wrap">
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
                      {/* Knowledge Base Info */}
                      {query.knowledge_id && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation()
                            router.push(`/knowledge-bases/${query.knowledge_id}`)
                          }}
                          className="inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium bg-cyan-100 text-cyan-700 hover:bg-cyan-200 transition-colors"
                        >
                          <Database className="h-3 w-3" />
                          {query.knowledge_name || `KB-${query.knowledge_id}`}
                          {query.namespace && (
                            <span className="text-cyan-600">({query.namespace})</span>
                          )}
                        </button>
                      )}
                      {!query.knowledge_id && (
                        <span className="inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium bg-gray-100 text-gray-500">
                          {t('queries.noKnowledgeBase', 'No KB')}
                        </span>
                      )}
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
          {data.total > pageSize && (
            <div className="flex items-center justify-between mt-4 pt-4 border-t">
              <span className="text-sm text-muted-foreground">
                Showing {(page - 1) * pageSize + 1} - {Math.min(page * pageSize, data.total)} of {data.total}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage(p => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1.5 text-sm rounded-md bg-muted disabled:opacity-50"
                >
                  Previous
                </button>
                <span className="px-3 py-1.5 text-sm">
                  Page {page} of {Math.ceil(data.total / pageSize)}
                </span>
                <button
                  onClick={() => setPage(p => p + 1)}
                  disabled={page >= Math.ceil(data.total / pageSize)}
                  className="px-3 py-1.5 text-sm rounded-md bg-muted disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="rounded-lg border bg-card p-8 text-center">
          <FileSearch className="mx-auto h-12 w-12 text-muted-foreground" />
          <p className="mt-4 text-muted-foreground">{t('common.noData')}</p>
        </div>
      )}
    </div>
  )
}
