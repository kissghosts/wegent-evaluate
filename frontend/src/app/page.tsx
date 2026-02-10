'use client'

import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import { useRouter } from 'next/navigation'
import {
  Activity,
  ArrowDown,
  ArrowRight,
  ArrowUp,
  BookOpen,
  Database,
  FileSearch,
  FileText,
  Loader2,
  RefreshCw,
  TrendingUp,
  Users,
} from 'lucide-react'
import {
  getDailyOverview,
  getDailyTrends,
  getTopKnowledgeBases,
  getSyncStatus,
  triggerSync,
  DailyOverviewResponse,
  TrendsResponse,
  KnowledgeBaseItem,
  SyncStatus,
} from '@/apis/daily'
import {
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  AreaChart,
  Area,
} from 'recharts'

// Stat card component
function StatCard({
  title,
  value,
  change,
  icon: Icon,
  color = 'blue',
}: {
  title: string
  value: number | string
  change?: number | null
  icon: React.ElementType
  color?: string
}) {
  const colorClasses: Record<string, { bg: string; text: string; iconBg: string }> = {
    blue: { bg: 'bg-blue-50', text: 'text-blue-600', iconBg: 'bg-blue-100' },
    green: { bg: 'bg-green-50', text: 'text-green-600', iconBg: 'bg-green-100' },
    purple: { bg: 'bg-purple-50', text: 'text-purple-600', iconBg: 'bg-purple-100' },
    orange: { bg: 'bg-orange-50', text: 'text-orange-600', iconBg: 'bg-orange-100' },
    cyan: { bg: 'bg-cyan-50', text: 'text-cyan-600', iconBg: 'bg-cyan-100' },
  }

  const colors = colorClasses[color] || colorClasses.blue

  return (
    <div className={`rounded-lg border p-4 ${colors.bg}`}>
      <div className="flex items-center justify-between">
        <div>
          <p className="text-sm text-muted-foreground">{title}</p>
          <p className="text-2xl font-bold mt-1">{value}</p>
          {change !== undefined && change !== null && (
            <div className="flex items-center mt-1 text-sm">
              {change > 0 ? (
                <ArrowUp className="h-3 w-3 text-green-500 mr-1" />
              ) : change < 0 ? (
                <ArrowDown className="h-3 w-3 text-red-500 mr-1" />
              ) : (
                <ArrowRight className="h-3 w-3 text-gray-500 mr-1" />
              )}
              <span className={change > 0 ? 'text-green-600' : change < 0 ? 'text-red-600' : 'text-gray-500'}>
                {Math.abs(change).toFixed(1)}%
              </span>
            </div>
          )}
        </div>
        <div className={`rounded-full p-3 ${colors.iconBg}`}>
          <Icon className={`h-6 w-6 ${colors.text}`} />
        </div>
      </div>
    </div>
  )
}

// Format mode name
function formatModeName(mode: string, t: (key: string) => string): string {
  const modeKey = `ragMode.${mode}`
  return t(modeKey) || mode
}

export default function DashboardPage() {
  const { t } = useTranslation()
  const router = useRouter()

  const [overview, setOverview] = useState<DailyOverviewResponse | null>(null)
  const [trends, setTrends] = useState<TrendsResponse | null>(null)
  const [topKbs, setTopKbs] = useState<KnowledgeBaseItem[]>([])
  const [syncStatus, setSyncStatus] = useState<SyncStatus | null>(null)
  const [loading, setLoading] = useState(true)
  const [syncing, setSyncing] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [trendDays, setTrendDays] = useState(7)

  const fetchData = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const [overviewData, trendsData, topKbsData, syncStatusData] = await Promise.all([
        getDailyOverview(),
        getDailyTrends({ days: trendDays }),
        getTopKnowledgeBases({ limit: 10 }),
        getSyncStatus(),
      ])

      setOverview(overviewData)
      setTrends(trendsData)
      setTopKbs(topKbsData.items)
      setSyncStatus(syncStatusData)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch data')
    } finally {
      setLoading(false)
    }
  }, [trendDays])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  const handleTriggerSync = async () => {
    setSyncing(true)
    try {
      await triggerSync('hourly')
      // Refresh data after sync
      await fetchData()
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to trigger sync')
    } finally {
      setSyncing(false)
    }
  }

  if (loading) {
    return (
      <div className="flex h-96 items-center justify-center">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
        <span className="ml-2">{t('common.loading')}</span>
      </div>
    )
  }

  const hasData = overview && overview.summary.total_queries > 0

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t('dashboard.title')}</h1>
        <div className="flex items-center gap-2">
          {syncStatus && (
            <span className="text-sm text-muted-foreground">
              {syncStatus.hourly?.last_sync_time && (
                <>
                  {t('dashboard.lastSync')}: {new Date(syncStatus.hourly.last_sync_time).toLocaleString()}
                </>
              )}
            </span>
          )}
          <button
            onClick={handleTriggerSync}
            disabled={syncing}
            className="inline-flex items-center gap-2 rounded-md bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:bg-primary/90 disabled:opacity-50"
          >
            <RefreshCw className={`h-4 w-4 ${syncing ? 'animate-spin' : ''}`} />
            {syncing ? t('dashboard.syncing') : t('dashboard.triggerSync')}
          </button>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 p-4 text-red-700">
          {error}
        </div>
      )}

      {!hasData ? (
        <div className="rounded-lg border bg-card p-8 text-center">
          <Database className="mx-auto h-12 w-12 text-muted-foreground" />
          <p className="mt-4 text-muted-foreground">{t('dashboard.noDataYet')}</p>
          {!syncStatus?.raw_db_configured && (
            <p className="mt-2 text-sm text-muted-foreground">
              Raw DB: Not configured
            </p>
          )}
        </div>
      ) : (
        <>
          {/* Stats Cards */}
          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-5">
            <StatCard
              title={t('dashboard.totalQueries')}
              value={overview.summary.total_queries}
              change={overview.comparison?.total_queries_change}
              icon={Activity}
              color="blue"
            />
            <StatCard
              title={t('dashboard.ragRetrieval')}
              value={overview.summary.rag_retrieval_count}
              change={overview.comparison?.rag_retrieval_change}
              icon={FileSearch}
              color="green"
            />
            <StatCard
              title={t('dashboard.directInjection')}
              value={overview.summary.direct_injection_count}
              icon={FileText}
              color="purple"
            />
            <StatCard
              title={t('dashboard.selectedDocuments')}
              value={overview.summary.selected_documents_count}
              icon={BookOpen}
              color="orange"
            />
            <StatCard
              title={t('dashboard.activeKnowledgeBases')}
              value={overview.summary.active_kb_count}
              icon={Users}
              color="cyan"
            />
          </div>

          {/* Trend Chart */}
          <div className="rounded-lg border bg-card p-4">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <TrendingUp className="h-5 w-5 text-primary" />
                <h2 className="text-lg font-semibold">{t('dashboard.queryTrend')}</h2>
              </div>
              <div className="flex gap-2">
                <button
                  onClick={() => setTrendDays(7)}
                  className={`px-3 py-1 text-sm rounded ${
                    trendDays === 7 ? 'bg-primary text-primary-foreground' : 'bg-muted'
                  }`}
                >
                  {t('dashboard.last7Days')}
                </button>
                <button
                  onClick={() => setTrendDays(30)}
                  className={`px-3 py-1 text-sm rounded ${
                    trendDays === 30 ? 'bg-primary text-primary-foreground' : 'bg-muted'
                  }`}
                >
                  {t('dashboard.last30Days')}
                </button>
              </div>
            </div>

            {trends && trends.data.length > 0 ? (
              <ResponsiveContainer width="100%" height={300}>
                <AreaChart data={trends.data}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis
                    dataKey="date"
                    tickFormatter={(value) => {
                      const date = new Date(value)
                      return `${date.getMonth() + 1}/${date.getDate()}`
                    }}
                  />
                  <YAxis />
                  <Tooltip
                    labelFormatter={(value) => new Date(value).toLocaleDateString()}
                  />
                  <Legend />
                  <Area
                    type="monotone"
                    dataKey="rag_retrieval_count"
                    name={t('dashboard.ragRetrieval')}
                    stackId="1"
                    stroke="#22c55e"
                    fill="#22c55e"
                    fillOpacity={0.6}
                  />
                  <Area
                    type="monotone"
                    dataKey="direct_injection_count"
                    name={t('dashboard.directInjection')}
                    stackId="1"
                    stroke="#a855f7"
                    fill="#a855f7"
                    fillOpacity={0.6}
                  />
                  <Area
                    type="monotone"
                    dataKey="selected_documents_count"
                    name={t('dashboard.selectedDocuments')}
                    stackId="1"
                    stroke="#f97316"
                    fill="#f97316"
                    fillOpacity={0.6}
                  />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <div className="flex h-[300px] items-center justify-center text-muted-foreground">
                {t('common.noData')}
              </div>
            )}
          </div>

          {/* Top Knowledge Bases */}
          <div className="rounded-lg border bg-card p-4">
            <div className="flex items-center gap-2 mb-4">
              <Database className="h-5 w-5 text-primary" />
              <h2 className="text-lg font-semibold">{t('dashboard.topKnowledgeBases')}</h2>
            </div>

            {topKbs.length > 0 ? (
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b text-left text-sm text-muted-foreground">
                      <th className="pb-3 pr-4">{t('dashboard.rank')}</th>
                      <th className="pb-3 pr-4">{t('dashboard.knowledgeBaseName')}</th>
                      <th className="pb-3 pr-4">{t('dashboard.namespace')}</th>
                      <th className="pb-3 pr-4 text-right">{t('dashboard.queries')}</th>
                      <th className="pb-3 pr-4">{t('dashboard.primaryMode')}</th>
                      <th className="pb-3"></th>
                    </tr>
                  </thead>
                  <tbody>
                    {topKbs.map((kb) => (
                      <tr
                        key={kb.knowledge_id}
                        className="border-b last:border-0 hover:bg-muted/50 cursor-pointer"
                        onClick={() => router.push(`/knowledge-bases/${kb.knowledge_id}`)}
                      >
                        <td className="py-3 pr-4">
                          <span className="inline-flex h-6 w-6 items-center justify-center rounded-full bg-primary/10 text-sm font-medium">
                            {kb.rank}
                          </span>
                        </td>
                        <td className="py-3 pr-4 font-medium">
                          {kb.knowledge_name || `KB-${kb.knowledge_id}`}
                        </td>
                        <td className="py-3 pr-4 text-muted-foreground">
                          {kb.namespace || 'default'}
                        </td>
                        <td className="py-3 pr-4 text-right font-medium">
                          {kb.total_queries}
                        </td>
                        <td className="py-3 pr-4">
                          <span className={`inline-flex items-center rounded-full px-2 py-1 text-xs font-medium ${
                            kb.primary_mode === 'rag_retrieval'
                              ? 'bg-green-100 text-green-700'
                              : kb.primary_mode === 'direct_injection'
                              ? 'bg-purple-100 text-purple-700'
                              : 'bg-orange-100 text-orange-700'
                          }`}>
                            {formatModeName(kb.primary_mode || 'unknown', t)}
                          </span>
                        </td>
                        <td className="py-3">
                          <button
                            className="text-sm text-primary hover:underline"
                            onClick={(e) => {
                              e.stopPropagation()
                              router.push(`/knowledge-bases/${kb.knowledge_id}`)
                            }}
                          >
                            {t('dashboard.viewDetail')} →
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            ) : (
              <div className="py-8 text-center text-muted-foreground">
                {t('common.noData')}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
