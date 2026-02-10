'use client'

import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useRouter } from 'next/navigation'
import { Database, Loader2, Search } from 'lucide-react'
import {
  getKnowledgeBases,
  KnowledgeBaseItem,
  PaginatedResponse,
} from '@/apis/daily'

// Format mode name
function formatModeName(mode: string, t: (key: string) => string): string {
  const modeKey = `ragMode.${mode}`
  return t(modeKey) || mode
}

export default function KnowledgeBasesPage() {
  const { t } = useTranslation()
  const router = useRouter()

  const [data, setData] = useState<PaginatedResponse<KnowledgeBaseItem> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [sortBy, setSortBy] = useState<'queries' | 'name'>('queries')
  const pageSize = 20

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await getKnowledgeBases({
        page,
        page_size: pageSize,
        sort_by: sortBy,
      })
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data')
    } finally {
      setLoading(false)
    }
  }, [page, sortBy])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Determine primary mode for a KB
  const getPrimaryMode = (kb: KnowledgeBaseItem): string => {
    const modes = {
      rag_retrieval: kb.rag_retrieval_count,
      direct_injection: kb.direct_injection_count,
      selected_documents: kb.selected_documents_count,
    }
    return Object.entries(modes).reduce((a, b) => (b[1] > modes[a as keyof typeof modes] ? b[0] : a), 'rag_retrieval')
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
          <Database className="h-6 w-6 text-primary" />
          <h1 className="text-2xl font-semibold">{t('knowledgeBase.title')}</h1>
        </div>
        <div className="flex items-center gap-2">
          <span className="text-sm text-muted-foreground">Sort by:</span>
          <select
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as 'queries' | 'name')}
            className="rounded-md border px-3 py-1.5 text-sm"
          >
            <option value="queries">{t('dashboard.queries')}</option>
            <option value="name">{t('dashboard.knowledgeBaseName')}</option>
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
          <div className="rounded-lg border bg-card overflow-hidden">
            <table className="w-full">
              <thead className="bg-muted/50">
                <tr className="text-left text-sm text-muted-foreground">
                  <th className="px-4 py-3">{t('dashboard.knowledgeBaseName')}</th>
                  <th className="px-4 py-3">{t('dashboard.namespace')}</th>
                  <th className="px-4 py-3 text-right">{t('dashboard.totalQueries')}</th>
                  <th className="px-4 py-3 text-right">{t('dashboard.ragRetrieval')}</th>
                  <th className="px-4 py-3 text-right">{t('dashboard.directInjection')}</th>
                  <th className="px-4 py-3 text-right">{t('dashboard.selectedDocuments')}</th>
                  <th className="px-4 py-3">{t('dashboard.primaryMode')}</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((kb) => {
                  const primaryMode = getPrimaryMode(kb)
                  return (
                    <tr
                      key={kb.knowledge_id}
                      className="border-t hover:bg-muted/50 cursor-pointer"
                      onClick={() => router.push(`/knowledge-bases/${kb.knowledge_id}`)}
                    >
                      <td className="px-4 py-3 font-medium">
                        {kb.knowledge_name || `KB-${kb.knowledge_id}`}
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {kb.namespace || 'default'}
                      </td>
                      <td className="px-4 py-3 text-right font-medium">
                        {kb.total_queries}
                      </td>
                      <td className="px-4 py-3 text-right text-green-600">
                        {kb.rag_retrieval_count}
                      </td>
                      <td className="px-4 py-3 text-right text-purple-600">
                        {kb.direct_injection_count}
                      </td>
                      <td className="px-4 py-3 text-right text-orange-600">
                        {kb.selected_documents_count}
                      </td>
                      <td className="px-4 py-3">
                        <span
                          className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                            primaryMode === 'rag_retrieval'
                              ? 'bg-green-100 text-green-700'
                              : primaryMode === 'direct_injection'
                              ? 'bg-purple-100 text-purple-700'
                              : 'bg-orange-100 text-orange-700'
                          }`}
                        >
                          {formatModeName(primaryMode, t)}
                        </span>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {data.total > pageSize && (
            <div className="flex items-center justify-between">
              <span className="text-sm text-muted-foreground">
                Showing {(page - 1) * pageSize + 1} - {Math.min(page * pageSize, data.total)} of {data.total}
              </span>
              <div className="flex gap-2">
                <button
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                  disabled={page === 1}
                  className="px-3 py-1.5 text-sm rounded-md bg-muted disabled:opacity-50"
                >
                  Previous
                </button>
                <span className="px-3 py-1.5 text-sm">
                  Page {page} of {Math.ceil(data.total / pageSize)}
                </span>
                <button
                  onClick={() => setPage((p) => p + 1)}
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
          <Database className="mx-auto h-12 w-12 text-muted-foreground" />
          <p className="mt-4 text-muted-foreground">{t('common.noData')}</p>
        </div>
      )}
    </div>
  )
}
