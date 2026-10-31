import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { Icon } from '../components/icons'
import { useToast } from '../components/toast'
import { Button, Card, EmptyState, ErrorBanner, Table } from '../components/ui'
import { date } from '../format'
import { useList } from '../hooks'

interface UpcomingRenewal {
  id: number
  number: string
  customer_name: string
  plan_name: string
  status: string
  expiry_date: string
  days_left: number
  renewable: boolean
  reminders_sent: number[]
}

const THRESHOLDS = [30, 7, 1]

function dueLabel(days: number): string {
  if (days === 0) return 'Today'
  if (days === 1) return 'Tomorrow'
  return `In ${days} days`
}

/** Subscriptions expiring in the next 30 days, which 30/7/1-day reminders went out, and a manual send. */
export function RenewalsCard() {
  const nav = useNavigate()
  const toast = useToast()
  const list = useList<UpcomingRenewal>('/renewals', { days: 30, page_size: 8 })
  const [busy, setBusy] = useState(false)

  const sendNow = async () => {
    setBusy(true)
    try {
      const r = await api.action<{ sent: number; skipped: number }>('/renewals/send-reminders')
      toast.success(r.sent ? `${r.sent} reminder(s) sent` : 'No reminders were due; everyone due has been reminded')
      list.reload()
    } catch (e) {
      toast.error(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Card
      title={`Upcoming renewals${list.count ? ` (${list.count})` : ''}`}
      pad={false}
      actions={
        <Button size="sm" icon={<Icon.send />} loading={busy} onClick={sendNow}>
          Send due reminders
        </Button>
      }
    >
      <ErrorBanner error={list.error} onRetry={list.reload} />
      <Table<UpcomingRenewal>
        rows={list.rows}
        loading={list.loading && !list.rows}
        rowKey={(r) => r.id}
        page={list.page}
        count={list.count}
        pageSize={8}
        onPage={list.setPage}
        onRowClick={(r) => nav(`/subscriptions/${r.id}`)}
        columns={[
          { key: 'n', header: 'Subscription', render: (r) => <strong className="mono">{r.number}</strong> },
          { key: 'c', header: 'Customer', render: (r) => r.customer_name },
          { key: 'p', header: 'Plan', render: (r) => r.plan_name },
          {
            key: 'e',
            header: 'Expires',
            render: (r) => (
              <span title={date(r.expiry_date)} style={{ color: r.days_left <= 7 ? 'var(--danger)' : undefined, fontWeight: r.days_left <= 7 ? 600 : undefined }}>
                {dueLabel(r.days_left)}
              </span>
            ),
          },
          {
            key: 'r',
            header: 'Reminders',
            render: (r) => (
              <span style={{ display: 'inline-flex', gap: 4 }}>
                {THRESHOLDS.map((t) => (
                  <span
                    key={t}
                    className={`pill ${r.reminders_sent.includes(t) ? 'pill-active' : 'pill-draft'}`}
                    title={r.reminders_sent.includes(t) ? `${t}-day reminder sent` : `${t}-day reminder not sent`}
                  >
                    {t}d
                  </span>
                ))}
              </span>
            ),
          },
        ]}
        empty={<EmptyState icon={<Icon.calendar />} title="No renewals in the next 30 days" body="Subscriptions with an expiry date show up here a month ahead." />}
      />
    </Card>
  )
}
