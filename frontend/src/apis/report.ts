/**
 * API client for report endpoints
 */
import type { WeeklyReportRequest, WeeklyReportResponse } from '@/types'

import { apiUrl } from './base'

export async function generateWeeklyReport(params: WeeklyReportRequest): Promise<WeeklyReportResponse> {
  const response = await fetch(apiUrl('/reports/weekly'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || 'Failed to generate report')
  }
  return response.json()
}
