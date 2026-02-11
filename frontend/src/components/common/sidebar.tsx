'use client'

import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useTranslation } from 'react-i18next'
import { useState } from 'react'
import {
  LayoutDashboard,
  FileSearch,
  TrendingUp,
  GitCompare,
  AlertCircle,
  Settings,
  BookOpen,
  Database,
  ChevronDown,
  ChevronRight,
  FlaskConical,
  ListFilter,
} from 'lucide-react'

// Main nav items
const mainNavItems = [
  { href: '/', labelKey: 'nav.dashboard', icon: LayoutDashboard },
  { href: '/knowledge-bases', labelKey: 'nav.knowledgeBases', icon: Database, matchPrefix: true },
  { href: '/queries', labelKey: 'nav.queries', icon: ListFilter, matchPrefix: true },
]

// Evaluation center sub-items
const evaluationItems = [
  { href: '/results', labelKey: 'nav.results', icon: FileSearch },
  { href: '/trends', labelKey: 'nav.trends', icon: TrendingUp },
  { href: '/comparison', labelKey: 'nav.comparison', icon: GitCompare },
  { href: '/issues', labelKey: 'nav.issues', icon: AlertCircle },
]

// Other nav items
const otherNavItems = [
  { href: '/metrics-docs', labelKey: 'nav.metricsDocs', icon: BookOpen },
  { href: '/settings', labelKey: 'nav.settings', icon: Settings },
]

export function Sidebar() {
  const pathname = usePathname()
  const { t } = useTranslation()
  const [evalExpanded, setEvalExpanded] = useState(() => {
    // Auto-expand if on evaluation pages
    return evaluationItems.some(item => pathname === item.href || pathname.startsWith(item.href + '/'))
  })

  const isItemActive = (item: { href: string; matchPrefix?: boolean }) => {
    if (item.matchPrefix) {
      return pathname === item.href || pathname.startsWith(item.href + '/')
    }
    return pathname === item.href
  }

  return (
    <aside className="flex w-64 flex-col border-r bg-card">
      <div className="flex h-14 items-center border-b px-4">
        <h1 className="text-lg font-semibold text-primary">Wegent Evaluate</h1>
      </div>
      <nav className="flex-1 space-y-1 p-2">
        {/* Main nav items */}
        {mainNavItems.map((item) => {
          const isActive = isItemActive(item)
          const Icon = item.icon
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
              }`}
            >
              <Icon className="h-4 w-4" />
              {t(item.labelKey)}
            </Link>
          )
        })}

        {/* Divider */}
        <div className="my-2 border-t" />

        {/* Evaluation Center (collapsible) */}
        <div>
          <button
            onClick={() => setEvalExpanded(!evalExpanded)}
            className="flex w-full items-center gap-3 rounded-md px-3 py-2 text-sm text-muted-foreground hover:bg-secondary hover:text-foreground transition-colors"
          >
            <FlaskConical className="h-4 w-4" />
            <span className="flex-1 text-left">{t('nav.evaluationCenter')}</span>
            {evalExpanded ? (
              <ChevronDown className="h-4 w-4" />
            ) : (
              <ChevronRight className="h-4 w-4" />
            )}
          </button>

          {evalExpanded && (
            <div className="ml-4 mt-1 space-y-1">
              {evaluationItems.map((item) => {
                const isActive = isItemActive(item)
                const Icon = item.icon
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                      isActive
                        ? 'bg-primary text-primary-foreground'
                        : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
                    }`}
                  >
                    <Icon className="h-4 w-4" />
                    {t(item.labelKey)}
                  </Link>
                )
              })}
            </div>
          )}
        </div>

        {/* Divider */}
        <div className="my-2 border-t" />

        {/* Other nav items */}
        {otherNavItems.map((item) => {
          const isActive = isItemActive(item)
          const Icon = item.icon
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 rounded-md px-3 py-2 text-sm transition-colors ${
                isActive
                  ? 'bg-primary text-primary-foreground'
                  : 'text-muted-foreground hover:bg-secondary hover:text-foreground'
              }`}
            >
              <Icon className="h-4 w-4" />
              {t(item.labelKey)}
            </Link>
          )
        })}
      </nav>
    </aside>
  )
}
