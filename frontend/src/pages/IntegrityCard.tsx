import { useState } from 'react'
import { api } from '../api'
import { useAuth } from '../auth'
import { useToast } from '../components/toast'
import { Button, Card, ErrorBanner, Skeleton } from '../components/ui'
import { dateTime } from '../format'
import { useAsync } from '../hooks'

interface IntegrityCheck {
  id: number
  finished_at: string
  issue_count: number
  issues: { check: string; ref: string; detail: string }[]
  counts: Record<string, number>
}

const CHECK_LABELS: Record<string, string> = {
  invoice_total_vs_lines: 'Invoice total ≠ its lines',
  invoice_paid_vs_payments: 'Paid amount ≠ payments',
  invoice_status: 'Status out of date',
  discount_usage: 'Discount usage drifted',
  billing_behind: 'Billing behind schedule',
}

/** Latest nightly reconciliation result; admins can run a check on demand. */
export function IntegrityCard() {
  const { isAdmin } = useAuth()
  const toast = useToast()
  const latest = useAsync(() => api.list<IntegrityCheck>('/integrity/checks', { page_size: 1 }), [])
  const [busy, setBusy] = useState(false)
  const check = latest.data?.results[0]

  const runNow = async () => {
    setBusy(true)
    try {
      const r = await api.action<IntegrityCheck>('/integrity/checks/run')
      toast.success(r.issue_count ? `${r.issue_count} issue(s) found` : 'All figures reconcile')
      latest.reload()
    } catch (e) {
      toast.error(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card
      title="Data integrity"
      actions={
        isAdmin && (
          <Button size="sm" loading={busy} onClick={runNow}>
            Run check
          </Button>
        )
      }
    >
      <ErrorBanner error={latest.error} onRetry={latest.reload} />
      {latest.loading && !latest.data ? (
        <Skeleton h={48} />
      ) : !check ? (
        <p className="muted">No check has run yet. It runs every night after billing.</p>
      ) : check.issue_count === 0 ? (
        <p>
          <span className="pill pill-active">All figures reconcile</span>{' '}
          <span className="muted">
            {check.counts.invoices?.toLocaleString('en-IN')} invoices and {check.counts.payments?.toLocaleString('en-IN')}{' '}
            payments checked · {dateTime(check.finished_at)}
          </span>
        </p>
      ) : (
        <>
          <p>
            <span className="pill pill-overdue">{check.issue_count} issue(s)</span>{' '}
            <span className="muted">found {dateTime(check.finished_at)}</span>
          </p>
          <ul style={{ margin: '8px 0 0', paddingLeft: 18 }}>
            {check.issues.slice(0, 8).map((i, n) => (
              <li key={n}>
                <strong>{CHECK_LABELS[i.check] ?? i.check}</strong> · {i.ref}: <span className="muted">{i.detail}</span>
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  )
}
