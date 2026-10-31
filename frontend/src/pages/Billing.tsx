import { useState } from 'react'
import { api } from '../api'
import { Icon } from '../components/icons'
import { useToast } from '../components/toast'
import { Button, Card, ConfirmDialog, EmptyState, ErrorBanner, Field, Input, PageHeader, StatusPill, Table } from '../components/ui'
import { date, dateTime, money, num, todayISO } from '../format'
import { useList } from '../hooks'
import type { BillingItem, BillingRun } from '../types'
import { IntegrityCard } from './IntegrityCard'

export function BillingPage() {
  const toast = useToast()
  const [asOf, setAsOf] = useState(todayISO())
  const [busy, setBusy] = useState<'dry' | 'run' | null>(null)
  const [result, setResult] = useState<BillingRun | null>(null)
  const [confirm, setConfirm] = useState(false)
  const history = useList<BillingRun>('/billing/runs')

  const run = async (dry: boolean) => {
    setBusy(dry ? 'dry' : 'run')
    setResult(null)
    try {
      const r = await api.action<BillingRun>('/billing/run', { as_of: asOf, dry_run: dry })
      setResult(r)
      setConfirm(false)
      if (dry) toast.info(`Dry run: ${r.created} invoice${r.created === 1 ? '' : 's'} would be created`)
      else toast.success(`Billing run created ${r.created} invoice${r.created === 1 ? '' : 's'}`)
      if (!dry) history.reload()
    } catch (e) {
      toast.error(e)
    } finally {
      setBusy(null)
    }
  }

  const items = result?.items ?? []
  const totalAmount = items.reduce((s, i) => s + (i.error ? 0 : num(i.total)), 0)
  const processed = (result?.created ?? 0) + (result?.skipped ?? 0) + (result?.failed ?? 0)

  return (
    <>
      <PageHeader title="Billing runs" sub="Create invoices for every period that is due. Safe to run more than once." />
      <Card>
        <div className="row wrap" style={{ alignItems: 'flex-end', gap: 16 }}>
          <Field label="Bill as of" hint="Periods starting on or before this date are invoiced.">
            {(id, d) => <Input id={id} type="date" aria-describedby={d} value={asOf} onChange={(e) => setAsOf(e.target.value)} style={{ width: 180 }} />}
          </Field>
          <div className="spacer" />
          <Button icon={<Icon.search />} loading={busy === 'dry'} disabled={!!busy} onClick={() => run(true)}>
            Dry run
          </Button>
          <Button variant="primary" icon={<Icon.play />} loading={busy === 'run'} disabled={!!busy} onClick={() => setConfirm(true)}>
            Run now
          </Button>
        </div>
        {busy && (
          <div style={{ marginTop: 16 }} role="status" aria-live="polite">
            <div className="skel" style={{ height: 6, borderRadius: 999 }} />
            <div className="muted" style={{ marginTop: 6, fontSize: 'var(--fs-sm)' }}>
              {busy === 'dry' ? 'Checking which periods are due…' : 'Creating invoices…'}
            </div>
          </div>
        )}
      </Card>

      {result && (
        <Card
          className="fade-in"
          title={
            <div className="row">
              <h2>{result.dry_run ? 'Dry run result' : 'Run result'}</h2>
              {result.dry_run && <span className="pill pill-dry">Nothing saved</span>}
            </div>
          }
          pad={false}
        >
          <div className="card-body" style={{ paddingBottom: 0 }}>
            <div className="horizon" style={{ gridTemplateColumns: 'repeat(4, 1fr)' }}>
              <div className="horizon-cell">
                <div className="h-label">{result.dry_run ? 'Would create' : 'Created'}</div>
                <div className="h-value" style={{ color: 'var(--success)' }}>{result.created}</div>
              </div>
              <div className="horizon-cell">
                <div className="h-label">Skipped</div>
                <div className="h-value">{result.skipped}</div>
              </div>
              <div className="horizon-cell">
                <div className="h-label">Failed</div>
                <div className="h-value" style={{ color: result.failed ? 'var(--danger)' : undefined }}>{result.failed}</div>
              </div>
              <div className="horizon-cell">
                <div className="h-label">Amount</div>
                <div className="h-value">{money(totalAmount)}</div>
              </div>
            </div>
            {processed > 0 && (
              <div style={{ display: 'flex', height: 8, borderRadius: 999, overflow: 'hidden', gap: 2, margin: '16px 0' }} aria-hidden="true">
                <div style={{ flex: result.created, background: 'var(--success)' }} />
                <div style={{ flex: result.skipped, background: 'var(--border-strong)' }} />
                <div style={{ flex: result.failed, background: 'var(--danger)' }} />
              </div>
            )}
          </div>
          <Table<BillingItem>
            compact
            rows={items}
            rowKey={(i) => `${i.subscription_number}-${i.period_start}`}
            columns={[
              { key: 's', header: 'Subscription', render: (i) => <span className="mono">{i.subscription_number}</span> },
              { key: 'p', header: 'Period start', render: (i) => date(i.period_start) },
              { key: 't', header: 'Total', align: 'right', render: (i) => money(i.total) },
              { key: 'st', header: 'Result', render: (i) => <StatusPill status={i.error ? 'failed' : i.status} /> },
              { key: 'e', header: 'Detail', render: (i) => (i.error ? <span style={{ color: 'var(--danger)' }}>{i.error}</span> : '—') },
            ]}
            empty={<EmptyState icon={<Icon.check />} title="Nothing due" body="Every active subscription is billed up to this date." />}
          />
        </Card>
      )}

      <div style={{ height: 16 }} />
      <IntegrityCard />

      <div style={{ height: 16 }} />
      <ErrorBanner error={history.error} onRetry={history.reload} />
      <Card title="Run history" pad={false}>
        <Table<BillingRun>
          rows={history.rows}
          loading={history.loading && !history.rows}
          rowKey={(r) => r.id ?? r.run_date}
          page={history.page}
          count={history.count}
          onPage={history.setPage}
          columns={[
            { key: 'd', header: 'Run at', render: (r) => dateTime(r.run_date) },
            { key: 'k', header: 'Type', render: (r) => (r.dry_run ? <span className="pill pill-dry">Dry run</span> : <span className="pill pill-active">Live</span>) },
            { key: 'c', header: 'Created', align: 'right', render: (r) => r.created },
            { key: 's', header: 'Skipped', align: 'right', render: (r) => r.skipped },
            { key: 'f', header: 'Failed', align: 'right', render: (r) => (r.failed ? <strong style={{ color: 'var(--danger)' }}>{r.failed}</strong> : 0) },
          ]}
          empty={<EmptyState icon={<Icon.play />} title="No runs yet" body="Run billing to invoice due periods." />}
        />
      </Card>

      <ConfirmDialog
        open={confirm}
        title="Run billing now?"
        body={`Creates invoices for every period due on or before ${date(asOf)}. Periods already invoiced are skipped.`}
        confirmLabel="Run now"
        onConfirm={() => run(false)}
        onClose={() => setConfirm(false)}
      />
    </>
  )
}
