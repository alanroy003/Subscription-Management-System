import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { api } from '../../api'
import { useAuth } from '../../auth'
import { Icon } from '../../components/icons'
import { useToast } from '../../components/toast'
import { Button, Card, ConfirmDialog, EmptyState, ErrorBanner, Skeleton, StatusPill, Table } from '../../components/ui'
import { date, money, num, periodUnit } from '../../format'
import { useAsync } from '../../hooks'
import type { Invoice, SubAction, Subscription } from '../../types'
import { InvoicePill } from '../Invoices'
import { actionMeta } from '../subscriptionParts'
import { ConvertTrialModal, TrialBanner } from '../Trial'

export function PortalHomePage() {
  const { user } = useAuth()
  const toast = useToast()
  const nav = useNavigate()
  const subs = useAsync(() => api.list<Subscription>('/subscriptions', { page_size: 50 }), [])
  const invs = useAsync(() => api.list<Invoice>('/invoices', { page_size: 10 }), [])
  const [pending, setPending] = useState<{ sub: Subscription; action: SubAction } | null>(null)
  const [busy, setBusy] = useState<string | null>(null)
  const [converting, setConverting] = useState<number | null>(null)

  const list = subs.data?.results ?? []
  const active = list.filter((s) => s.status === 'active')
  const due = (invs.data?.results ?? []).filter((i) => i.status === 'confirmed').reduce((a, i) => a + num(i.balance), 0)
  const quotes = list.filter((s) => s.status === 'quotation')

  const run = async (s: Subscription, action: SubAction) => {
    setBusy(`${s.id}:${action}`)
    try {
      await api.action(`/subscriptions/${s.id}/transition`, { action })
      toast.success(`${actionMeta[action]?.portalLabel ?? actionMeta[action]?.label ?? action}: done`)
      setPending(null)
      subs.reload()
      invs.reload()
    } catch (e) {
      toast.error(e)
    } finally {
      setBusy(null)
    }
  }

  return (
    <>
      <TrialBanner
        onChanged={() => {
          subs.reload()
          invs.reload()
        }}
      />
      {converting !== null && (
        <ConvertTrialModal subscriptionId={converting} open onClose={() => setConverting(null)} portal />
      )}
      <section className="portal-hero">
        <div style={{ flex: '1 1 260px' }}>
          <div className="stat-label">Welcome back</div>
          <h1>{user?.name || user?.email}</h1>
        </div>
        <div>
          <div className="stat">{subs.loading ? '…' : active.length}</div>
          <div className="stat-label">Active plans</div>
        </div>
        <div>
          <div className="stat">{invs.loading ? '…' : money(due)}</div>
          <div className="stat-label">Balance due</div>
        </div>
        <div>
          <div className="stat">{subs.loading ? '…' : quotes.length}</div>
          <div className="stat-label">Open quotations</div>
        </div>
      </section>

      <ErrorBanner error={subs.error} onRetry={subs.reload} />
      <div className="row" style={{ marginBottom: 12 }}>
        <h2 style={{ fontSize: 'var(--fs-lg)' }}>Your subscriptions</h2>
        <div className="spacer" />
        <Link to="/portal/subscriptions" className="btn btn-sm">
          View all
        </Link>
      </div>
      {subs.loading && !subs.data ? (
        <div className="sub-cards">
          {[0, 1, 2].map((i) => (
            <div className="card sub-card" key={i}>
              <Skeleton w="50%" h={18} />
              <Skeleton w="80%" />
              <Skeleton w="40%" h={24} />
            </div>
          ))}
        </div>
      ) : list.length === 0 ? (
        <Card>
          <EmptyState icon={<Icon.loop />} title="No subscriptions yet" body="When we send you a quotation, it appears here for you to accept." />
        </Card>
      ) : (
        <div className="sub-cards">
          {list
            .filter((s) => s.status !== 'closed')
            .slice(0, 6)
            .map((s) => (
              <article className="card sub-card" key={s.id}>
                <div className="row">
                  <Link to={`/portal/subscriptions/${s.id}`} className="mono" style={{ fontWeight: 600 }}>
                    {s.number}
                  </Link>
                  <div className="spacer" />
                  <StatusPill status={s.status} />
                </div>
                <div>
                  <div style={{ fontWeight: 600 }}>{s.plan_name}</div>
                  <div className="muted" style={{ fontSize: 'var(--fs-sm)' }}>
                    {s.number} · started {date(s.start_date)}
                  </div>
                </div>
                <div>
                  <span className="amount">{money(s.recurring_total)}</span>
                  <span className="muted"> / {periodUnit[s.billing_period] ?? s.billing_period}</span>
                </div>
                <div className="muted" style={{ fontSize: 'var(--fs-sm)' }}>
                  {s.status === 'quotation'
                    ? `Quotation valid until ${date(s.quotation_valid_until)}`
                    : s.next_invoice_date
                      ? `Next invoice ${date(s.next_invoice_date)}`
                      : `Starts ${date(s.start_date)}`}
                </div>
                {s.available_actions?.length > 0 && (
                  <div className="row wrap">
                    {s.available_actions.map((a) => {
                      const m = actionMeta[a]
                      return (
                        <Button
                          key={a}
                          size="sm"
                          variant={m?.variant ?? 'default'}
                          loading={busy === `${s.id}:${a}`}
                          disabled={!!busy}
                          onClick={() =>
                            a === 'convert'
                              ? setConverting(s.id)
                              : m?.confirm
                                ? setPending({ sub: s, action: a })
                                : run(s, a)
                          }
                        >
                          {m?.portalLabel ?? m?.label ?? a}
                        </Button>
                      )
                    })}
                  </div>
                )}
              </article>
            ))}
        </div>
      )}

      <div style={{ height: 24 }} />
      <Card title="Recent invoices" pad={false} actions={<Link to="/portal/invoices" className="btn btn-sm">View all</Link>}>
        <Table<Invoice>
          rows={invs.data?.results ?? null}
          loading={invs.loading && !invs.data}
          rowKey={(i) => i.id}
          onRowClick={(i) => nav(`/portal/invoices/${i.id}`)}
          columns={[
            { key: 'n', header: 'Number', render: (i) => <strong className="mono">{i.number || 'Draft'}</strong> },
            { key: 'd', header: 'Date', render: (i) => date(i.invoice_date) },
            { key: 'due', header: 'Due', render: (i) => date(i.due_date) },
            { key: 't', header: 'Total', align: 'right', render: (i) => money(i.total) },
            { key: 's', header: 'Status', render: (i) => <InvoicePill inv={i} /> },
          ]}
          empty={<EmptyState icon={<Icon.invoice />} title="No invoices yet" />}
        />
      </Card>

      <ConfirmDialog
        open={!!pending}
        title={pending ? `${actionMeta[pending.action]?.label} ${pending.sub.number}?` : ''}
        body={pending ? actionMeta[pending.action]?.confirm : undefined}
        confirmLabel={pending ? actionMeta[pending.action]?.label : 'Confirm'}
        danger={pending?.action === 'close'}
        onConfirm={() => (pending ? run(pending.sub, pending.action) : undefined)}
        onClose={() => setPending(null)}
      />
    </>
  )
}
