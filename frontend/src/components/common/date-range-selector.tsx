'use client'

import { useMemo } from 'react'

function toISODate(d: Date): string {
  // YYYY-MM-DD in local time
  const year = d.getFullYear()
  const month = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function getLastNDaysDateRange(days: number): { startDate: string; endDate: string } {
  const end = new Date()
  const start = new Date()
  // inclusive range: last 7 days => today-6 ... today
  start.setDate(start.getDate() - Math.max(days - 1, 0))
  return { startDate: toISODate(start), endDate: toISODate(end) }
}

export type DayOption = { days: number; label: string }

export function QuickDaysSelector({
  value,
  options,
  onChange,
}: {
  value: number
  options: DayOption[]
  onChange: (days: number) => void
}) {
  const normalized = useMemo(() => new Set(options.map((o) => o.days)), [options])

  if (!normalized.has(value) && options.length > 0) {
    // Keep UI stable even if caller passes an unsupported value
    value = options[0].days
  }

  return (
    <div className="flex gap-2">
      {options.map((opt) => (
        <button
          key={opt.days}
          onClick={() => onChange(opt.days)}
          className={`px-3 py-1 text-sm rounded ${
            value === opt.days ? 'bg-primary text-primary-foreground' : 'bg-muted'
          }`}
          type="button"
        >
          {opt.label}
        </button>
      ))}
    </div>
  )
}

export function DateRangeInputs({
  startDate,
  endDate,
  onStartDateChange,
  onEndDateChange,
}: {
  startDate: string
  endDate: string
  onStartDateChange: (value: string) => void
  onEndDateChange: (value: string) => void
}) {
  return (
    <div className="flex items-center gap-2">
      <input
        type="date"
        value={startDate}
        onChange={(e) => onStartDateChange(e.target.value)}
        className="rounded-md border bg-background px-3 py-1.5 text-sm"
      />
      <span className="text-sm text-muted-foreground">-</span>
      <input
        type="date"
        value={endDate}
        onChange={(e) => onEndDateChange(e.target.value)}
        className="rounded-md border bg-background px-3 py-1.5 text-sm"
      />
    </div>
  )
}
