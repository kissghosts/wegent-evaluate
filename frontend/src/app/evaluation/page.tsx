'use client'

import { useState, useEffect, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import {
  CheckCircle2,
  XCircle,
  HelpCircle,
  TrendingUp,
  TrendingDown,
  Minus,
  RefreshCcw,
  ChevronDown,
} from 'lucide-react'
import {
  getEvaluationTrends,
  compareEvaluationPeriods,
  getLowScoreQueries,
  getLowScoreKnowledgeBases,
  triggerRagEvaluation,
  getRagEvaluationStatus,
  type EvaluationTrendsResponse,
  type EvaluationCompareResponse,
  type LowScoreQueryItem,
  type LowScoreKnowledgeBaseItem,
} from '@/apis/ragEvaluation'
import { TrendChart } from '@/components/charts/trend-chart'

// Helper to format date to YYYY-MM-DD
const formatDate = (date: Date): string => {
  return date.toISOString().split('T')[0]
}

// Get default date range (last 7 days)
const getDefaultDateRange = () => {
  const end = new Date()
  const start = new Date()
  start.setDate(end.getDate() - 6)
  return { start: formatDate(start), end: formatDate(end) }
}

// Get previous period (7 days before the start)
const getPreviousPeriod = (startDate: string, endDate: string) => {
  const start = new Date(startDate)
  const end = new Date(endDate)
  const days = Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24))
  const prevEnd = new Date(start)
  prevEnd.setDate(prevEnd.getDate() - 1)
  const prevStart = new Date(prevEnd)
  prevStart.setDate(prevStart.getDate() - days)
  return { start: formatDate(prevStart), end: formatDate(prevEnd) }
}

export default function EvaluationOverviewPage() {
  const { t } = useTranslation()
  const [dateRange, setDateRange] = useState(getDefaultDateRange())
  const [trendsData, setTrendsData] = useState<EvaluationTrendsResponse | null>(null)
  const [compareData, setCompareData] = useState<EvaluationCompareResponse | null>(null)
  const [lowScoreQueries, setLowScoreQueries] = useState<LowScoreQueryItem[]>([])
  const [lowScoreKBs, setLowScoreKBs] = useState<LowScoreKnowledgeBaseItem[]>([])
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<'queries' | 'kbs'>('queries')
  const [isEvaluating, setIsEvaluating] = useState(false)
  const [showTriggerModal, setShowTriggerModal] = useState(false)

  const fetchData = useCallback(async () => {
    setLoading(true)
    try {
      // Calculate days from date range
      const start = new Date(dateRange.start)
      const end = new Date(dateRange.end)
      const days = Math.ceil((end.getTime() - start.getTime()) / (1000 * 60 * 60 * 24)) + 1

      // Fetch trends
      const trends = await getEvaluationTrends({ days })
      setTrendsData(trends)

      // Fetch comparison
      const prevPeriod = getPreviousPeriod(dateRange.start, dateRange.end)
      const compare = await compareEvaluationPeriods({
        period1_start: prevPeriod.start,
        period1_end: prevPeriod.end,
        period2_start: dateRange.start,
        period2_end: dateRange.end,
      })
      setCompareData(compare)

      // Fetch low score queries
      const queries = await getLowScoreQueries({
        start_date: dateRange.start,
        end_date: dateRange.end,
        limit: 10,
      })
      setLowScoreQueries(queries.records)

      // Fetch low score KBs
      const kbs = await getLowScoreKnowledgeBases({
        start_date: dateRange.start,
        end_date: dateRange.end,
        limit: 10,
      })
      setLowScoreKBs(kbs.knowledge_bases)
    } catch (error) {
      console.error('Failed to fetch evaluation data:', error)
    } finally {
      setLoading(false)
    }
  }, [dateRange])

  useEffect(() => {
    fetchData()
  }, [fetchData])

  // Calculate summary stats from trends
  const summary = trendsData?.trends.reduce(
    (acc, day) => ({
      totalRagQueries: acc.totalRagQueries + day.total_rag_queries,
      evaluatedCount: acc.evaluatedCount + day.evaluated_count,
      passCount: acc.passCount + day.pass_count,
      failCount: acc.failCount + day.fail_count,
      undeterminedCount: acc.undeterminedCount + day.undetermined_count,
    }),
    { totalRagQueries: 0, evaluatedCount: 0, passCount: 0, failCount: 0, undeterminedCount: 0 }
  ) || { totalRagQueries: 0, evaluatedCount: 0, passCount: 0, failCount: 0, undeterminedCount: 0 }

  const coverage = summary.totalRagQueries > 0
    ? (summary.evaluatedCount / summary.totalRagQueries * 100).toFixed(1)
    : '0.0'
  const passRate = summary.evaluatedCount > 0
    ? (summary.passCount / summary.evaluatedCount * 100).toFixed(1)
    : '0.0'

  // Trigger evaluation handler
  const handleTriggerEvaluation = async () => {
    setIsEvaluating(true)
    try {
      const result = await triggerRagEvaluation({
        mode: 'by_date_range',
        start_date: dateRange.start,
        end_date: dateRange.end,
      })

      // Poll for status
      const pollStatus = async () => {
        const status = await getRagEvaluationStatus(result.job_id)
        if (status.status === 'completed' || status.status === 'failed') {
          setIsEvaluating(false)
          fetchData()
        } else {
          setTimeout(pollStatus, 2000)
        }
      }
      pollStatus()
    } catch (error) {
      console.error('Failed to trigger evaluation:', error)
      setIsEvaluating(false)
    }
    setShowTriggerModal(false)
  }

  // Render change indicator
  const renderChange = (change: number | null | undefined, isPercentage = false) => {
    if (change === null || change === undefined) return <Minus className="h-4 w-4 text-muted-foreground" />
    const formatted = isPercentage ? `${(change * 100).toFixed(1)}%` : change.toFixed(1)
    if (change > 0) {
      return (
        <span className="flex items-center text-green-600">
          <TrendingUp className="h-4 w-4 mr-1" />
          +{formatted}
        </span>
      )
    } else if (change < 0) {
      return (
        <span className="flex items-center text-red-600">
          <TrendingDown className="h-4 w-4 mr-1" />
          {formatted}
        </span>
      )
    }
    return <Minus className="h-4 w-4 text-muted-foreground" />
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-muted-foreground">{t('common.loading')}</div>
      </div>
    )
  }

  return (
    <div className="space-y-6 p-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">{t('evaluation.title', 'Evaluation Overview')}</h1>
        <div className="flex items-center gap-4">
          {/* Date Range Selector */}
          <div className="flex items-center gap-2">
            <input
              type="date"
              value={dateRange.start}
              onChange={(e) => setDateRange((prev) => ({ ...prev, start: e.target.value }))}
              className="px-3 py-2 border rounded-md text-sm"
            />
            <span className="text-muted-foreground">~</span>
            <input
              type="date"
              value={dateRange.end}
              onChange={(e) => setDateRange((prev) => ({ ...prev, end: e.target.value }))}
              className="px-3 py-2 border rounded-md text-sm"
            />
          </div>
          <button
            onClick={() => setShowTriggerModal(true)}
            disabled={isEvaluating}
            className="px-4 py-2 bg-primary text-primary-foreground rounded-md hover:bg-primary/90 disabled:opacity-50"
          >
            {isEvaluating ? (
              <span className="flex items-center gap-2">
                <RefreshCcw className="h-4 w-4 animate-spin" />
                {t('evaluation.evaluating', 'Evaluating...')}
              </span>
            ) : (
              t('evaluation.triggerEvaluation', 'Trigger Evaluation')
            )}
          </button>
        </div>
      </div>

      {/* Summary Cards */}
      <div className="grid grid-cols-3 gap-4">
        {/* RAG Evaluation Summary */}
        <div className="rounded-lg border bg-card p-4">
          <h3 className="text-sm font-medium text-muted-foreground mb-3">
            {t('evaluation.ragOverview', 'RAG Evaluation Overview')}
          </h3>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-sm">{t('evaluation.evaluated', 'Evaluated')}</span>
              <span className="font-medium">{summary.evaluatedCount} / {summary.totalRagQueries}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm">{t('evaluation.coverage', 'Coverage')}</span>
              <span className="font-medium">{coverage}%</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm">{t('evaluation.passRate', 'Pass Rate')}</span>
              <span className="font-medium text-green-600">{passRate}%</span>
            </div>
          </div>
        </div>

        {/* Non-RAG Stats */}
        <div className="rounded-lg border bg-card p-4">
          <h3 className="text-sm font-medium text-muted-foreground mb-3">
            {t('evaluation.nonRagStats', 'Non-RAG Usage')}
          </h3>
          <div className="space-y-2">
            <div className="flex justify-between">
              <span className="text-sm">{t('evaluation.directInjection', 'Direct Injection')}</span>
              <span className="font-medium">{trendsData?.non_rag_stats?.direct_injection_count || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm">{t('evaluation.selectedDocs', 'Selected Documents')}</span>
              <span className="font-medium">{trendsData?.non_rag_stats?.selected_documents_count || 0}</span>
            </div>
            <div className="flex justify-between">
              <span className="text-sm">{t('evaluation.nonRagRatio', 'Non-RAG Ratio')}</span>
              <span className="font-medium">
                {((trendsData?.non_rag_stats?.non_rag_ratio || 0) * 100).toFixed(1)}%
              </span>
            </div>
          </div>
        </div>

        {/* Comparison */}
        <div className="rounded-lg border bg-card p-4">
          <h3 className="text-sm font-medium text-muted-foreground mb-3">
            {t('evaluation.effectChange', 'Effect Change')}
          </h3>
          <div className="space-y-2">
            <div className="flex justify-between items-center">
              <span className="text-sm">{t('evaluation.dayOverDay', 'Day over Day')}</span>
              {renderChange(trendsData?.comparison?.day_over_day?.pass_rate_change, true)}
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">{t('evaluation.weekOverWeek', 'Week over Week')}</span>
              {renderChange(trendsData?.comparison?.week_over_week?.pass_rate_change, true)}
            </div>
            <div className="flex justify-between items-center">
              <span className="text-sm">{t('evaluation.scoreChange', 'Score Change')}</span>
              {renderChange(compareData?.changes.avg_score_change)}
            </div>
          </div>
        </div>
      </div>

      {/* Trends Chart */}
      <div className="rounded-lg border bg-card p-4">
        <h3 className="text-sm font-medium text-muted-foreground mb-4">
          {t('evaluation.trendChart', 'Evaluation Trend')}
        </h3>
        {trendsData?.trends && trendsData.trends.length > 0 ? (
          <TrendChart
            data={trendsData.trends.map(d => ({
              date: d.date,
              total_queries: d.total_rag_queries,
              rag_retrieval_count: d.evaluated_count,
              direct_injection_count: d.pass_count,
              selected_documents_count: d.fail_count,
            }))}
            height={300}
          />
        ) : (
          <div className="h-[300px] flex items-center justify-center text-muted-foreground">
            {t('common.noData')}
          </div>
        )}
      </div>

      {/* Period Comparison */}
      {compareData && (
        <div className="rounded-lg border bg-card p-4">
          <h3 className="text-sm font-medium text-muted-foreground mb-4">
            {t('evaluation.periodComparison', 'Period Comparison')}
          </h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="py-2 text-left font-medium">{t('evaluation.metric', 'Metric')}</th>
                  <th className="py-2 text-right font-medium">{compareData.period1.date_range}</th>
                  <th className="py-2 text-right font-medium">{compareData.period2.date_range}</th>
                  <th className="py-2 text-right font-medium">{t('evaluation.change', 'Change')}</th>
                </tr>
              </thead>
              <tbody>
                <tr className="border-b">
                  <td className="py-2">{t('evaluation.evaluatedCount', 'Evaluated Count')}</td>
                  <td className="py-2 text-right">{compareData.period1.evaluated_count}</td>
                  <td className="py-2 text-right">{compareData.period2.evaluated_count}</td>
                  <td className="py-2 text-right">
                    {compareData.period2.evaluated_count - compareData.period1.evaluated_count}
                  </td>
                </tr>
                <tr className="border-b">
                  <td className="py-2">{t('evaluation.passRate', 'Pass Rate')}</td>
                  <td className="py-2 text-right">
                    {compareData.period1.pass_rate !== null
                      ? `${(compareData.period1.pass_rate * 100).toFixed(1)}%`
                      : '-'}
                  </td>
                  <td className="py-2 text-right">
                    {compareData.period2.pass_rate !== null
                      ? `${(compareData.period2.pass_rate * 100).toFixed(1)}%`
                      : '-'}
                  </td>
                  <td className="py-2 text-right">{renderChange(compareData.changes.pass_rate_change, true)}</td>
                </tr>
                <tr>
                  <td className="py-2">{t('evaluation.avgScore', 'Avg Score')}</td>
                  <td className="py-2 text-right">
                    {compareData.period1.avg_total_score?.toFixed(1) || '-'}
                  </td>
                  <td className="py-2 text-right">
                    {compareData.period2.avg_total_score?.toFixed(1) || '-'}
                  </td>
                  <td className="py-2 text-right">{renderChange(compareData.changes.avg_score_change)}</td>
                </tr>
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Low Score Rankings */}
      <div className="rounded-lg border bg-card p-4">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-medium text-muted-foreground">
            {t('evaluation.lowScoreRanking', 'Low Score Ranking')}
          </h3>
          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab('queries')}
              className={`px-3 py-1 text-sm rounded-md ${
                activeTab === 'queries'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-secondary-foreground'
              }`}
            >
              {t('evaluation.byQuery', 'By Query')}
            </button>
            <button
              onClick={() => setActiveTab('kbs')}
              className={`px-3 py-1 text-sm rounded-md ${
                activeTab === 'kbs'
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-secondary text-secondary-foreground'
              }`}
            >
              {t('evaluation.byKB', 'By Knowledge Base')}
            </button>
          </div>
        </div>

        {activeTab === 'queries' ? (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="py-2 text-left font-medium">#</th>
                  <th className="py-2 text-left font-medium">{t('evaluation.query', 'Query')}</th>
                  <th className="py-2 text-left font-medium">{t('evaluation.knowledgeBase', 'KB')}</th>
                  <th className="py-2 text-right font-medium">{t('evaluation.totalScore', 'Score')}</th>
                  <th className="py-2 text-center font-medium">{t('evaluation.judgment', 'Judgment')}</th>
                </tr>
              </thead>
              <tbody>
                {lowScoreQueries.map((query, index) => (
                  <tr key={query.rag_record_ref_id} className="border-b hover:bg-muted/50">
                    <td className="py-2">{index + 1}</td>
                    <td className="py-2 max-w-xs truncate">{query.user_prompt || '-'}</td>
                    <td className="py-2">{query.knowledge_name || `KB-${query.knowledge_id}`}</td>
                    <td className="py-2 text-right">{query.total_score?.toFixed(1) || '-'}</td>
                    <td className="py-2 text-center">
                      {query.evaluation_judgment === 'pass' && (
                        <CheckCircle2 className="h-4 w-4 text-green-600 mx-auto" />
                      )}
                      {query.evaluation_judgment === 'fail' && (
                        <XCircle className="h-4 w-4 text-red-600 mx-auto" />
                      )}
                      {query.evaluation_judgment === 'undetermined' && (
                        <HelpCircle className="h-4 w-4 text-yellow-600 mx-auto" />
                      )}
                    </td>
                  </tr>
                ))}
                {lowScoreQueries.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-muted-foreground">
                      {t('common.noData')}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b">
                  <th className="py-2 text-left font-medium">#</th>
                  <th className="py-2 text-left font-medium">{t('evaluation.knowledgeBase', 'KB')}</th>
                  <th className="py-2 text-right font-medium">{t('evaluation.evaluated', 'Evaluated')}</th>
                  <th className="py-2 text-right font-medium">{t('evaluation.passRate', 'Pass Rate')}</th>
                  <th className="py-2 text-right font-medium">{t('evaluation.avgScore', 'Avg Score')}</th>
                </tr>
              </thead>
              <tbody>
                {lowScoreKBs.map((kb, index) => (
                  <tr key={kb.knowledge_id} className="border-b hover:bg-muted/50">
                    <td className="py-2">{index + 1}</td>
                    <td className="py-2">{kb.knowledge_name || `KB-${kb.knowledge_id}`}</td>
                    <td className="py-2 text-right">{kb.evaluated_count}</td>
                    <td className="py-2 text-right">
                      {kb.pass_rate !== null ? `${(kb.pass_rate * 100).toFixed(1)}%` : '-'}
                    </td>
                    <td className="py-2 text-right">{kb.avg_total_score?.toFixed(1) || '-'}</td>
                  </tr>
                ))}
                {lowScoreKBs.length === 0 && (
                  <tr>
                    <td colSpan={5} className="py-8 text-center text-muted-foreground">
                      {t('common.noData')}
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Trigger Evaluation Modal */}
      {showTriggerModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-card rounded-lg p-6 max-w-md w-full mx-4">
            <h3 className="text-lg font-semibold mb-4">
              {t('evaluation.triggerEvaluation', 'Trigger Evaluation')}
            </h3>
            <p className="text-sm text-muted-foreground mb-4">
              {t('evaluation.triggerDescription', 'This will evaluate all RAG retrieval records in the selected date range.')}
            </p>
            <div className="flex justify-end gap-2">
              <button
                onClick={() => setShowTriggerModal(false)}
                className="px-4 py-2 text-sm border rounded-md hover:bg-muted"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={handleTriggerEvaluation}
                className="px-4 py-2 text-sm bg-primary text-primary-foreground rounded-md hover:bg-primary/90"
              >
                {t('evaluation.startEvaluation', 'Start Evaluation')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
