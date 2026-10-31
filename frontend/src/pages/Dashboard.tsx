import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { Area, AreaChart, CartesianGrid, Cell, Pie, PieChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { Icon } from '../components/icons'
import { Button, Card, EmptyState, ErrorBanner, Input, KpiCard, PageHeader, Skeleton, Table } from '../components/ui'
import { addDaysISO, date, money, moneyCompact, monthLabel, num, todayISO } from '../format'
import { useAsync } from '../hooks'
import type { Invoice, SubStatus, Summary } from '../types'
import { InvoicePill } from './Invoices'

const STATUS_COLORS: Record<SubStatus, string> = {
  draft: '#9c95a3',
  quotation: '#175cd3',
  confirmed: '#6b3fb8',
  active: '#1f7a4d',
  paused: '#c98a12',
  closed: '#3f3a44',
}
const STATUS_ORDER: SubStatus[] = ['active', 'paused', 'confirmed', 'quotation', 'draft', 'closed']

const PRESETS = [
  { label: '30 days', days: 30 },
  { label: '90 days', days: 90 },
  { label: '6 months', days: 182 },
  { label: '12 months', days: 365 },
]

function ChartTooltip({ active, payload, label }: { active?: boolean; payload?: { name: string; value: number; color: string }[]; label?: string }) {
  if (!active || !payload?.length) return null
  return (
    <div className="card" style={{ padding: '8px 12px', boxShadow: 'var(--shadow)', fontSize: 'var(--fs-sm)' }}>
      <div style={{ fontWeight: 600, marginBottom: 4 }}>{label ? monthLabel(label) : ''}</div>
      {payload.map((p) => (
        <div key={p.name} className="row" style={{ gap: 8 }}>
          <i style={{ width: 10, height: 10, borderRadius: 3, background: p.color, display: 'inline-block' }} />
          <span style={{ color: 'var(--text-2)' }}>{p.name}</span>
          <span className="spacer" />
          <strong className="num">{money(p.value)}</strong>
        </div>
      ))}
    </div>
  )
}

export function DashboardPage() {
  const [range, setRange] = useState({ from: addDaysISO(todayISO(), -182), to: todayISO() })
  const r = useAsync(() => api.get<Summary>('/reports/summary', { date_from: range.from, date_to: range.to }), [range.from, range.to])
  const s = r.data
  const nav = useNavigate()
  const loading = r.loading && !s

  const series = (s?.revenue_series ?? []).map((x) => ({ month: x.month, Billed: num(x.billed), Collected: num(x.collected) }))
  const donut = STATUS_ORDER.map((k) => ({ key: k, name: k[0].toUpperCase() + k.slice(1), value: s?.status_counts?.[k] ?? 0 })).filter(
    (d) => d.value > 0,
  )
  const totalSubs = donut.reduce((a, b) => a + b.value, 0)
  const collectionRate = s && num(s.billed) > 0 ? Math.round((num(s.collected) / num(s.billed)) * 100) : null

  return (
    <>
      <PageHeader
        title="Dashboard"
        sub="Recurring revenue, collections and what needs attention."
        actions={
          <div className="row wrap" role="group" aria-label="Date range">
            {PRESETS.map((p) => {
              const from = addDaysISO(todayISO(), -p.days)
              const on = range.from === from && range.to === todayISO()
              return (
                <Button key={p.label} size="sm" variant={on ? 'primary' : 'default'} aria-pressed={on} onClick={() => setRange({ from, to: todayISO() })}>
                  {p.label}
                </Button>
              )
            })}
            <Input type="date" aria-label="From date" className="input-sm" style={{ width: 145 }} value={range.from} onChange={(e) => e.target.value && setRange({ ...range, from: e.target.value })} />
            <span className="muted">to</span>
            <Input type="date" aria-label="To date" className="input-sm" style={{ width: 145 }} value={range.to} onChange={(e) => e.target.value && setRange({ ...range, to: e.target.value })} />
          </div>
        }
      />
      <ErrorBanner error={r.error} onRetry={r.reload} />

      <div className="kpis">
        <KpiCard loading={loading} label="Active subscriptions" value={s?.active_subscriptions ?? 0} foot={s ? `${s.churned_last_30} churned in 30 days` : undefined} />
        <KpiCard loading={loading} label="MRR" value={money(s?.mrr)} foot={s ? `ARPU ${money(s.arpu)}` : undefined} tone="accent" />
        <KpiCard loading={loading} label="Billed" value={money(s?.billed)} foot="In selected range" />
        <KpiCard
          loading={loading}
          label="Collected"
          value={money(s?.collected)}
          foot={collectionRate != null ? `${collectionRate}% of billed` : 'In selected range'}
          tone="success"
        />
        <KpiCard loading={loading} label="Outstanding" value={money(s?.outstanding)} foot="Confirmed, unpaid" tone="warning" />
        <KpiCard
          loading={loading}
          label="Overdue"
          value={money(s?.overdue_amount)}
          foot={s ? `${s.overdue_count} invoice${s.overdue_count === 1 ? '' : 's'} past due` : undefined}
          tone="danger"
        />
      </div>

      <div className="dash-grid">
        <Card
          title="Billed vs collected"
          actions={
            <div className="legend" aria-hidden="true">
              <span>
                <i style={{ background: 'var(--chart-1)' }} />
                Billed
              </span>
              <span>
                <i style={{ background: 'var(--chart-2)' }} />
                Collected (dashed)
              </span>
            </div>
          }
        >
          {loading ? (
            <Skeleton h={260} />
          ) : series.length === 0 ? (
            <EmptyState icon={<Icon.dashboard />} title="No revenue in this range" body="Invoices billed in the selected dates show up here." />
          ) : (
            <div style={{ height: 260 }} role="img" aria-label={`Monthly billed and collected amounts, ${series.length} months`}>
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={series} margin={{ top: 8, right: 8, left: 0, bottom: 0 }}>
                  <defs>
                    <linearGradient id="gBilled" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#714B67" stopOpacity={0.28} />
                      <stop offset="100%" stopColor="#714B67" stopOpacity={0.02} />
                    </linearGradient>
                    <linearGradient id="gColl" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#017E84" stopOpacity={0.18} />
                      <stop offset="100%" stopColor="#017E84" stopOpacity={0.01} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid stroke="#ece9ef" vertical={false} />
                  <XAxis dataKey="month" tickFormatter={monthLabel} tick={{ fontSize: 12, fill: '#6b6472' }} axisLine={false} tickLine={false} />
                  <YAxis tickFormatter={(v) => moneyCompact(v)} tick={{ fontSize: 12, fill: '#6b6472' }} axisLine={false} tickLine={false} width={64} />
                  <Tooltip content={<ChartTooltip />} cursor={{ stroke: '#cfcad4' }} />
                  <Area type="monotone" dataKey="Billed" stroke="#714B67" strokeWidth={2} fill="url(#gBilled)" activeDot={{ r: 5, strokeWidth: 2, stroke: '#fff' }} animationDuration={280} />
                  <Area
                    type="monotone"
                    dataKey="Collected"
                    stroke="#017E84"
                    strokeWidth={2}
                    strokeDasharray="6 4"
                    fill="url(#gColl)"
                    activeDot={{ r: 5, strokeWidth: 2, stroke: '#fff' }}
                    animationDuration={280}
                  />
                </AreaChart>
              </ResponsiveContainer>
            </div>
          )}
        </Card>

        <Card title="Subscriptions by status">
          {loading ? (
            <Skeleton h={260} />
          ) : totalSubs === 0 ? (
            <EmptyState icon={<Icon.loop />} title="No subscriptions yet" action={<Link className="btn btn-primary" to="/subscriptions/new">New subscription</Link>} />
          ) : (
            <div className="row" style={{ alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
              <div style={{ width: 160, height: 160, position: 'relative' }} role="img" aria-label={`${totalSubs} subscriptions by status`}>
                <ResponsiveContainer width="100%" height="100%">
                  <PieChart>
                    <Pie data={donut} dataKey="value" nameKey="name" innerRadius={52} outerRadius={76} paddingAngle={2} stroke="#fff" strokeWidth={2} animationDuration={280}>
                      {donut.map((d) => (
                        <Cell key={d.key} fill={STATUS_COLORS[d.key]} />
                      ))}
                    </Pie>
                    <Tooltip formatter={(v: number, n: string) => [v, n]} />
                  </PieChart>
                </ResponsiveContainer>
                <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', pointerEvents: 'none', textAlign: 'center' }}>
                  <div>
                    <div style={{ fontSize: 'var(--fs-xl)', fontWeight: 700 }}>{totalSubs}</div>
                    <div className="muted" style={{ fontSize: 'var(--fs-xs)' }}>total</div>
                  </div>
                </div>
              </div>
              <ul className="list-plain" style={{ flex: 1, minWidth: 140 }}>
                {donut.map((d) => (
                  <li key={d.key} style={{ padding: '5px 0' }}>
                    <Link to={`/subscriptions?status=${d.key}`} className="row" style={{ flex: 1, color: 'var(--text)', textDecoration: 'none' }}>
                      <i style={{ width: 10, height: 10, borderRadius: 3, background: STATUS_COLORS[d.key], display: 'inline-block' }} />
                      {d.name}
                      <span className="spacer" />
                      <strong className="num">{d.value}</strong>
                    </Link>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </Card>
      </div>

      <div className="dash-grid">
        <Card title="Renewals and forecast">
          {loading ? (
            <Skeleton h={120} />
          ) : (
            <div className="stack">
              <div>
                <div className="section-title">Renewals due</div>
                <div className="horizon">
                  {(['d30', 'd60', 'd90'] as const).map((k) => (
                    <div className="horizon-cell" key={k}>
                      <div className="h-label">Next {k.slice(1)} days</div>
                      <div className="h-value">{s?.renewals?.[k] ?? 0}</div>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <div className="section-title">Forecast billing</div>
                <div className="horizon">
                  {(['d30', 'd60', 'd90'] as const).map((k) => (
                    <div className="horizon-cell" key={k}>
                      <div className="h-label">Next {k.slice(1)} days</div>
                      <div className="h-value">{moneyCompact(s?.forecast?.[k])}</div>
                      <div className="muted" style={{ fontSize: 'var(--fs-xs)' }}>{money(s?.forecast?.[k])}</div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}
        </Card>

        <Card title="Customers at risk">
          {loading ? (
            <Skeleton h={120} />
          ) : !s?.at_risk?.length ? (
            <EmptyState icon={<Icon.check />} title="No customers at risk" body="Nobody has overdue invoices." />
          ) : (
            <ul className="list-plain">
              {s.at_risk.slice(0, 6).map((c) => (
                <li key={c.customer_id}>
                  <div style={{ minWidth: 0 }}>
                    <div style={{ fontWeight: 600 }}>{c.customer_name}</div>
                    <div className="muted" style={{ fontSize: 'var(--fs-xs)' }}>
                      {c.overdue_count} overdue invoice{c.overdue_count === 1 ? '' : 's'}
                    </div>
                  </div>
                  <span className="spacer" />
                  <strong className="num" style={{ color: 'var(--danger)' }}>
                    {money(c.overdue_amount)}
                  </strong>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>

      <Card title="Overdue invoices" pad={false} actions={<Link to="/invoices?overdue=true" className="btn btn-sm">View all</Link>}>
        <Table<Invoice>
          rows={s?.top_overdue ?? (loading ? null : [])}
          loading={loading}
          rowKey={(i) => i.id}
          onRowClick={(i) => nav(`/invoices/${i.id}`)}
          columns={[
            { key: 'n', header: 'Number', render: (i) => <strong className="mono">{i.number}</strong> },
            { key: 'c', header: 'Customer', render: (i) => i.customer_name },
            { key: 'd', header: 'Due', render: (i) => date(i.due_date) },
            { key: 'b', header: 'Balance', align: 'right', render: (i) => money(i.balance) },
            { key: 's', header: 'Status', render: (i) => <InvoicePill inv={i} /> },
          ]}
          empty={<EmptyState icon={<Icon.check />} title="Nothing overdue" body="All posted invoices are within their due dates." />}
        />
      </Card>
    </>
  )
}
