'use client'

import { useState, useEffect, useCallback } from 'react'
import { useDebouncedValue } from '@/hooks/useDebouncedValue'
import { useTranslation } from 'react-i18next'
import { useRouter } from 'next/navigation'
import { Database, Loader2, Search } from 'lucide-react'
import {
  getKnowledgeBases,
  KnowledgeBaseItem,
  PaginatedResponse,
} from '@/apis/daily'

export default function KnowledgeBasesPage() {
  const { t } = useTranslation()
  const router = useRouter()

  const [data, setData] = useState<PaginatedResponse<KnowledgeBaseItem> | null>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [page, setPage] = useState(1)
  const [keyword, setKeyword] = useState('')
  const debouncedKeyword = useDebouncedValue(keyword, 500)
  const pageSize = 20

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const result = await getKnowledgeBases({
        page,
        page_size: pageSize,
        q: debouncedKeyword.trim() || undefined,
      })
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data')
    } finally {
      setLoading(false)
    }
  }, [page, debouncedKeyword])

  useEffect(() => {
    fetchData()
  }, [fetchData])


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
        <div className="flex items-center gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <input
              value={keyword}
              onChange={(e) => {
                setPage(1)
                setKeyword(e.target.value)
              }}
              placeholder={t('knowledgeBase.search_placeholder', 'Search by id / name / creator')}
              className="w-72 rounded-md border bg-background pl-9 pr-3 py-1.5 text-sm"
            />
          </div>
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
                  <th className="px-4 py-3">{t('knowledgeBase.creator', 'Creator')}</th>
                  <th className="px-4 py-3">{t('knowledgeBase.description', 'Description')}</th>
                  <th className="px-4 py-3">{t('knowledgeBase.type', 'Type')}</th>
                  <th className="px-4 py-3">{t('knowledgeBase.createdAt', 'Created')}</th>
                  <th className="px-4 py-3">{t('knowledgeBase.recent7dUsage', '7d Usage')}</th>
                </tr>
              </thead>
              <tbody>
                {data.items.map((kb) => {
                  const recent7d = kb.recent_7d_queries ?? 0

                  return (
                    <tr
                      key={kb.knowledge_id}
                      className="border-t hover:bg-muted/50 cursor-pointer"
                      onClick={() => router.push(`/knowledge-bases/${kb.knowledge_id}`)}
                    >
                      <td className="px-4 py-3 font-medium">
                        <span>{kb.knowledge_name || `KB-${kb.knowledge_id}`}</span>
                      </td>
                      <td className="px-4 py-3 text-muted-foreground">
                        {kb.namespace || 'default'}
                      </td>
                      <td className="px-4 py-3">
                        {kb.created_by_user_name ? (
                          <span className="text-sm text-muted-foreground">@{kb.created_by_user_name}</span>
                        ) : kb.created_by_user_id ? (
                          <span className="text-sm text-muted-foreground">UID-{kb.created_by_user_id}</span>
                        ) : (
                          <span className="text-sm text-muted-foreground">-</span>
                        )}
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-sm text-muted-foreground line-clamp-2">{kb.description || '-'}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-sm text-muted-foreground">{kb.kb_type || '-'}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className="text-sm text-muted-foreground">{kb.created_at || '-'}</span>
                      </td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium ${
                          recent7d > 0
                            ? 'bg-green-100 text-green-700'
                            : 'bg-gray-100 text-gray-500'
                        }`}>
                          {recent7d}
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
