import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api, ApiError, downloadFile } from '../api'
import { useAuth } from '../auth'
import { BrandMark, Icon } from '../components/icons'
import { useToast } from '../components/toast'
import {
  Button,
  Card,
  ConfirmDialog,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  PageHeader,
  SearchInput,
  Select,
  Skeleton,
  StatusPill,
  Table,
  Textarea,
  Toggle,
} from '../components/ui'
import { date, dateTime, money, num, titleCase, todayISO } from '../format'
import { useAsync, useDebounced, useList } from '../hooks'
import type { Invoice, InvStatus, Payment, PayMethod } from '../types'

const TABS: { key: '' | InvStatus; label: string }[] = [
  { key: '', label: 'All' },
  { key: 'draft', label: 'Draft' },
  { key: 'confirmed', label: 'Confirmed' },
  { key: 'paid', label: 'Paid' },
  { key: 'cancelled', label: 'Cancelled' },
]

export const METHODS: { value: PayMethod; label: string }[] = [
  { value: 'bank_transfer', label: 'Bank transfer' },
  { value: 'upi', label: 'UPI' },
  { value: 'card', label: 'Card' },
  { value: 'cash', label: 'Cash' },
  { value: 'cheque', label: 'Cheque' },
]
const methodLabel = (m: string) => METHODS.find((x) => x.value === m)?.label ?? titleCase(m)

export function InvoicePill({ inv }: { inv: Pick<Invoice, 'status' | 'is_overdue'> }) {
  return inv.is_overdue ? <StatusPill status="overdue" /> : <StatusPill status={inv.status} kind="invoice" />
}

export function InvoicesPage({ portal = false }: { portal?: boolean }) {
  const [sp, setSp] = useSearchParams()
  const status = (sp.get('status') ?? '') as '' | InvStatus
  const overdue = sp.get('overdue') === 'true'
  const [search, setSearch] = useState('')
  const [dateFrom, setDateFrom] = useState('')
  const [dateTo, setDateTo] = useState('')
  const q = useDebounced(search)
  const list = useList<Invoice>('/invoices', { status, overdue, search: q, date_from: dateFrom, date_to: dateTo })
  const nav = useNavigate()
  const toast = useToast()
  const [selected, setSelected] = useState<Set<number>>(new Set())
  const [bulkBusy, setBulkBusy] = useState(false)
  const base = portal ? '/portal/invoices' : '/invoices'

  useEffect(() => setSelected(new Set()), [status, overdue, q, list.page])

  const setParam = (k: string, v: string | null) => {
    const n = new URLSearchParams(sp)
    if (v) n.set(k, v)
    else n.delete(k)
    setSp(n, { replace: true })
  }

  const bulkConfirm = async () => {
    setBulkBusy(true)
    try {
      await api.action('/invoices/bulk-confirm', { ids: [...selected] })
      toast.success(`${selected.size} invoice${selected.size === 1 ? '' : 's'} confirmed`)
      setSelected(new Set())
      list.reload()
    } catch (e) {
      toast.error(e)
    } finally {
      setBulkBusy(false)
    }
  }

  return (
    <>
      <PageHeader
        title={portal ? 'My invoices' : 'Invoices'}
        sub={portal ? 'Download, print or check what is due.' : 'Billed periods, payments and balances.'}
      />
      <div className="tabs" role="tablist" aria-label="Filter by status">
        {TABS.map((t) => (
          <button key={t.key} role="tab" className="tab" aria-selected={status === t.key} onClick={() => setParam('status', t.key)}>
            {t.label}
          </button>
        ))}
      </div>
      <ErrorBanner error={list.error} onRetry={list.reload} />
      <Card pad={false}>
        <div className="toolbar" style={{ padding: '12px 16px 0', marginBottom: 12 }}>
          <SearchInput value={search} onChange={setSearch} placeholder="Search number or customer" />
          <Toggle checked={overdue} onChange={(v) => setParam('overdue', v ? 'true' : null)} label="Overdue only" />
          {!portal && (
            <>
              <label className="row muted" style={{ gap: 6 }}>
                From
                <Input type="date" className="input-sm" style={{ width: 150 }} value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} />
              </label>
              <label className="row muted" style={{ gap: 6 }}>
                To
                <Input type="date" className="input-sm" style={{ width: 150 }} value={dateTo} onChange={(e) => setDateTo(e.target.value)} />
              </label>
            </>
          )}
          <div className="spacer" />
          {!portal && selected.size > 0 && (
            <Button variant="primary" size="sm" icon={<Icon.check />} loading={bulkBusy} onClick={bulkConfirm}>
              Confirm {selected.size} draft{selected.size === 1 ? '' : 's'}
            </Button>
          )}
        </div>
        <Table<Invoice>
          rows={list.rows}
          loading={list.loading && !list.rows}
          rowKey={(r) => r.id}
          onRowClick={(r) => nav(`${base}/${r.id}`)}
          page={list.page}
          count={list.count}
          onPage={list.setPage}
          selectable={
            portal
              ? undefined
              : { selected, onChange: setSelected, canSelect: (r) => r.status === 'draft', id: (r) => r.id }
          }
          columns={[
            { key: 'n', header: 'Number', render: (r) => <strong className="mono">{r.number || 'Draft'}</strong> },
            ...(portal ? [] : [{ key: 'c', header: 'Customer', render: (r: Invoice) => r.customer_name }]),
            { key: 's', header: 'Subscription', render: (r) => <span className="mono">{r.subscription_number || '—'}</span> },
            { key: 'd', header: 'Date', render: (r) => date(r.invoice_date) },
            { key: 'due', header: 'Due', render: (r) => date(r.due_date) },
            { key: 't', header: 'Total', align: 'right', render: (r) => money(r.total) },
            { key: 'b', header: 'Balance', align: 'right', render: (r) => (num(r.balance) > 0 ? money(r.balance) : '—') },
            { key: 'st', header: 'Status', render: (r) => <InvoicePill inv={r} /> },
          ]}
          empty={
            <EmptyState
              icon={<Icon.invoice />}
              title={overdue ? 'Nothing overdue' : 'No invoices found'}
              body={overdue ? 'Every posted invoice is within its due date.' : portal ? 'Invoices appear here once billed.' : 'Run billing to create invoices for active subscriptions.'}
              action={!portal && !overdue && <Link className="btn btn-primary" to="/billing">Open billing</Link>}
            />
          }
        />
      </Card>
    </>
  )
}

/* ---------------- Detail ---------------- */
export function InvoiceDetailPage({ portal = false }: { portal?: boolean }) {
  const { id } = useParams()
  const { isStaff } = useAuth()
  const toast = useToast()
  const inv = useAsync(() => api.get<Invoice>(`/invoices/${id}`), [id])
  const [busy, setBusy] = useState<string | null>(null)
  const [confirmCancel, setConfirmCancel] = useState(false)
  const base = portal ? '/portal/invoices' : '/invoices'
  const canAct = !portal && isStaff

  const act = async (action: 'confirm' | 'cancel' | 'send') => {
    setBusy(action)
    try {
      const r = await api.action<Invoice | null>(`/invoices/${id}/${action}`)
      toast.success({ confirm: 'Invoice confirmed', cancel: 'Invoice cancelled', send: 'Invoice sent to customer' }[action])
      if (r && typeof r === 'object' && 'id' in r) inv.setData(r)
      else inv.reload()
      setConfirmCancel(false)
    } catch (e) {
      toast.error(e)
    } finally {
      setBusy(null)
    }
  }

  const downloadPdf = async () => {
    if (!inv.data) return
    setBusy('pdf')
    try {
      await downloadFile(`/invoices/${id}/pdf`, `${inv.data.number}.pdf`)
    } catch (e) {
      toast.error(e)
    } finally {
      setBusy(null)
    }
  }

  if (inv.error)
    return (
      <>
        <PageHeader title="Invoice" crumbs={[{ label: portal ? 'My invoices' : 'Invoices', to: base }]} />
        <ErrorBanner error={inv.error} onRetry={inv.reload} />
      </>
    )
  const i = inv.data
  if (!i)
    return (
      <div className="stack">
        <Skeleton w={240} h={28} />
        <Skeleton h={300} />
      </div>
    )

  const printUrl = `${portal ? '/portal' : ''}/invoices/${i.id}/print`
  return (
    <>
      <PageHeader
        crumbs={[{ label: portal ? 'My invoices' : 'Invoices', to: base }]}
        title={
          <div className="title-row">
            <h1 className="mono">{i.number || 'Draft invoice'}</h1>
            <InvoicePill inv={i} />
          </div>
        }
        sub={
          <>
            {i.customer_name}
            {i.subscription_number && (
              <>
                {' · '}
                <Link to={`${portal ? '/portal' : ''}/subscriptions/${i.subscription}`} className="mono">
                  {i.subscription_number}
                </Link>
              </>
            )}
          </>
        }
        actions={
          <>
            {canAct && i.status === 'draft' && (
              <Button variant="primary" icon={<Icon.check />} loading={busy === 'confirm'} disabled={!!busy} onClick={() => act('confirm')}>
                Confirm
              </Button>
            )}
            {canAct && (i.status === 'confirmed' || i.status === 'paid') && (
              <Button icon={<Icon.send />} loading={busy === 'send'} disabled={!!busy} onClick={() => act('send')}>
                {i.sent_at ? 'Send again' : 'Send by email'}
              </Button>
            )}
            {(i.status !== 'draft' || canAct) && (
              <Button icon={<Icon.file />} loading={busy === 'pdf'} disabled={!!busy} onClick={downloadPdf}>
                Download PDF
              </Button>
            )}
            {i.status !== 'draft' && (
              <Link to={printUrl} className="btn" target="_blank" rel="noopener">
                <Icon.printer />
                Print
              </Link>
            )}
            {canAct && (i.status === 'draft' || i.status === 'confirmed') && i.payments.length === 0 && (
              <Button variant="danger" disabled={!!busy} onClick={() => setConfirmCancel(true)}>
                Cancel invoice
              </Button>
            )}
          </>
        }
      />

      <div className="detail-grid">
        <div className="stack">
          <Card pad={false}>
            <div className="card-body">
              <dl className="dl" style={{ gridTemplateColumns: '120px 1fr 120px 1fr' }}>
                <dt>Invoice date</dt>
                <dd>{date(i.invoice_date)}</dd>
                <dt>Due date</dt>
                <dd style={{ color: i.is_overdue ? 'var(--danger)' : undefined }}>{date(i.due_date)}</dd>
                <dt>Period</dt>
                <dd>{i.period_start ? `${date(i.period_start)} – ${date(i.period_end)}` : '—'}</dd>
                <dt>Sent</dt>
                <dd>{i.sent_at ? dateTime(i.sent_at) : 'Not sent'}</dd>
              </dl>
            </div>
            <InvoiceLinesTable inv={i} />
            <InvoiceTotals inv={i} />
          </Card>
          <Card title="Payments" pad={false}>
            <Table<Payment>
              compact
              rows={i.payments ?? []}
              rowKey={(p) => p.id}
              columns={[
                { key: 'd', header: 'Date', render: (p) => date(p.date) },
                { key: 'm', header: 'Method', render: (p) => methodLabel(p.method) },
                { key: 'n', header: 'Note', render: (p) => p.note || '—' },
                { key: 'a', header: 'Amount', align: 'right', render: (p) => money(p.amount) },
              ]}
              empty={<EmptyState icon={<Icon.card />} title="No payments yet" body={i.status === 'confirmed' ? 'Record a payment when the customer pays.' : undefined} />}
            />
          </Card>
        </div>
        <div className="stack">
          <Card title="Bill to">
            <CustomerBlock inv={i} />
          </Card>
          {canAct && i.status === 'confirmed' && num(i.balance) > 0 && <PaymentForm inv={i} onDone={inv.reload} />}
          {i.status === 'draft' && canAct && (
            <div className="alert alert-info">Draft invoices can be edited by the billing run. Confirm to post it and accept payments.</div>
          )}
        </div>
      </div>

      <ConfirmDialog
        open={confirmCancel}
        title={`Cancel ${i.number || 'this draft'}?`}
        body="Cancelled invoices cannot be paid or reopened. Any discount usage is released."
        confirmLabel="Cancel invoice"
        danger
        onConfirm={() => act('cancel')}
        onClose={() => setConfirmCancel(false)}
      />
    </>
  )
}

function CustomerBlock({ inv }: { inv: Invoice }) {
  const c = inv.customer_snapshot
  return (
    <div style={{ lineHeight: 1.6 }}>
      <strong>{c?.name || inv.customer_name}</strong>
      {c?.email && <div>{c.email}</div>}
      {c?.address && <div style={{ whiteSpace: 'pre-wrap' }}>{c.address}</div>}
      {c?.state && <div>{c.state}</div>}
      {c?.gstin && (
        <div>
          GSTIN <span className="mono">{c.gstin}</span>
        </div>
      )}
    </div>
  )
}

function InvoiceLinesTable({ inv }: { inv: Invoice }) {
  return (
    <div className="table-wrap">
      <table className="table">
        <thead>
          <tr>
            <th>Description</th>
            <th className="th-right">Qty</th>
            <th className="th-right">Unit price</th>
            <th className="th-right">Discount</th>
            <th className="th-right">Tax</th>
            <th className="th-right">Total</th>
          </tr>
        </thead>
        <tbody>
          {inv.lines.map((l, idx) => (
            <tr key={idx}>
              <td>{l.description}</td>
              <td className="right num">{num(l.quantity)}</td>
              <td className="right num">{money(l.unit_price)}</td>
              <td className="right num">
                {num(l.discount_amount) > 0 ? (
                  <>
                    −{money(l.discount_amount)}
                    {l.discount_name && <div className="muted" style={{ fontSize: 'var(--fs-xs)' }}>{l.discount_name}</div>}
                  </>
                ) : (
                  '—'
                )}
              </td>
              <td className="right num">
                {l.taxes?.length
                  ? l.taxes.map((t, k) => (
                      <div key={k} style={{ fontSize: 'var(--fs-xs)' }}>
                        <span className="muted">
                          {t.name} {num(t.rate)}%
                        </span>{' '}
                        {money(t.amount)}
                      </div>
                    ))
                  : num(l.tax_amount) > 0
                    ? money(l.tax_amount)
                    : '—'}
              </td>
              <td className="right num strong">{money(l.total)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function taxBreakdown(inv: Invoice) {
  const m = new Map<string, number>()
  for (const l of inv.lines) for (const t of l.taxes ?? []) {
    const k = `${t.name} (${num(t.rate)}%)`
    m.set(k, (m.get(k) ?? 0) + num(t.amount))
  }
  return [...m.entries()]
}

function InvoiceTotals({ inv }: { inv: Invoice }) {
  const taxes = taxBreakdown(inv)
  return (
    <div className="totals">
      <span className="muted">Subtotal</span>
      <span className="num right">{money(inv.subtotal)}</span>
      {num(inv.discount_total) > 0 && (
        <>
          <span className="muted">Discount</span>
          <span className="num right">−{money(inv.discount_total)}</span>
        </>
      )}
      {taxes.length
        ? taxes.map(([k, v]) => (
            <span key={k} style={{ display: 'contents' }}>
              <span className="muted">{k}</span>
              <span className="num right">{money(v)}</span>
            </span>
          ))
        : (
          <>
            <span className="muted">Tax</span>
            <span className="num right">{money(inv.tax_total)}</span>
          </>
        )}
      <span className="grand">Total</span>
      <span className="grand num right">{money(inv.total)}</span>
      {num(inv.amount_paid) > 0 && (
        <>
          <span className="muted">Paid</span>
          <span className="num right">−{money(inv.amount_paid)}</span>
        </>
      )}
      <span style={{ fontWeight: 600 }}>Balance due</span>
      <span className="num right" style={{ fontWeight: 700, color: num(inv.balance) > 0 ? 'var(--brand)' : 'var(--success)' }}>
        {money(inv.balance)}
      </span>
    </div>
  )
}

function PaymentForm({ inv, onDone }: { inv: Invoice; onDone: () => void }) {
  const toast = useToast()
  const [method, setMethod] = useState<PayMethod>('bank_transfer')
  const [amount, setAmount] = useState(num(inv.balance).toFixed(2))
  const [d, setD] = useState(todayISO())
  const [note, setNote] = useState('')
  const [busy, setBusy] = useState(false)
  const [errors, setErrors] = useState<Record<string, string[]>>({})
  useEffect(() => setAmount(num(inv.balance).toFixed(2)), [inv.balance])

  const over = num(amount) > num(inv.balance)
  const submit = async () => {
    if (num(amount) <= 0 || over) {
      setErrors({ amount: [over ? `Cannot exceed the balance of ${money(inv.balance)}.` : 'Enter an amount above zero.'] })
      return
    }
    setBusy(true)
    setErrors({})
    try {
      await api.create('/payments', { invoice: inv.id, method, amount, date: d, note })
      toast.success(`Payment of ${money(amount)} recorded`)
      setNote('')
      onDone()
    } catch (e) {
      if (e instanceof ApiError) setErrors(e.fields)
      toast.error(e)
    } finally {
      setBusy(false)
    }
  }
  return (
    <Card title="Record payment">
      <form
        className="stack"
        onSubmit={(e) => {
          e.preventDefault()
          submit()
        }}
      >
        <Field label="Method" error={errors.method}>
          {(id) => <Select id={id} options={METHODS} value={method} onChange={(e) => setMethod(e.target.value as PayMethod)} />}
        </Field>
        <Field label="Amount (₹)" required error={errors.amount} hint={`Balance ${money(inv.balance)}`}>
          {(id, desc) => (
            <Input
              id={id}
              type="number"
              step="0.01"
              min="0.01"
              max={num(inv.balance)}
              aria-describedby={desc}
              aria-invalid={over || undefined}
              value={amount}
              onChange={(e) => setAmount(e.target.value)}
            />
          )}
        </Field>
        <Field label="Date" error={errors.date}>
          {(id) => <Input id={id} type="date" value={d} onChange={(e) => setD(e.target.value)} />}
        </Field>
        <Field label="Note" error={errors.note}>
          {(id) => <Textarea id={id} rows={2} value={note} onChange={(e) => setNote(e.target.value)} placeholder="UTR or cheque number" />}
        </Field>
        <Button type="submit" variant="accent" loading={busy}>
          Record payment
        </Button>
      </form>
    </Card>
  )
}

/* ---------------- Print ---------------- */
export function InvoicePrintPage() {
  const { id } = useParams()
  const inv = useAsync(() => api.get<Invoice>(`/invoices/${id}`), [id])
  useEffect(() => {
    if (!inv.data) return
    document.title = `Invoice ${inv.data.number ?? inv.data.id}`
    const t = window.setTimeout(() => window.print(), 400)
    return () => window.clearTimeout(t)
  }, [inv.data])

  if (inv.error) return <div className="print-page"><ErrorBanner error={inv.error} onRetry={inv.reload} /></div>
  const i = inv.data
  if (!i)
    return (
      <div className="print-page">
        <Skeleton h={400} />
      </div>
    )
  return (
    <>
      <div className="print-toolbar no-print">
        <Button variant="primary" icon={<Icon.printer />} onClick={() => window.print()}>
          Print or save as PDF
        </Button>
        <Button onClick={() => window.close()}>Close</Button>
      </div>
      <article className="print-page">
        <div className="print-head">
          <div>
            <div className="row" style={{ gap: 10, marginBottom: 8 }}>
              <BrandMark />
              <strong style={{ fontSize: '1.125rem' }}>Brightloop</strong>
            </div>
            <div className="muted">{i.company?.name ?? 'Subscription billing'}</div>
            {i.company && (
              <div className="muted" style={{ fontSize: 'var(--fs-sm)' }}>
                {i.company.address}
                <br />
                GSTIN {i.company.gstin}
              </div>
            )}
          </div>
          <div style={{ textAlign: 'right' }}>
            <h1>TAX INVOICE</h1>
            <div className="mono" style={{ fontSize: '1rem', fontWeight: 600 }}>
              {i.number || 'DRAFT'}
            </div>
            <div style={{ marginTop: 6 }}>
              <InvoicePill inv={i} />
            </div>
          </div>
        </div>
        <div className="print-cols">
          <div>
            <h4>Bill to</h4>
            <CustomerBlock inv={i} />
          </div>
          <div>
            <dl className="dl" style={{ gridTemplateColumns: '120px 1fr' }}>
              <dt>Invoice date</dt>
              <dd>{date(i.invoice_date)}</dd>
              <dt>Due date</dt>
              <dd>{date(i.due_date)}</dd>
              {i.period_start && (
                <>
                  <dt>Service period</dt>
                  <dd>
                    {date(i.period_start)} – {date(i.period_end)}
                  </dd>
                </>
              )}
              {i.subscription_number && (
                <>
                  <dt>Subscription</dt>
                  <dd className="mono">{i.subscription_number}</dd>
                </>
              )}
            </dl>
          </div>
        </div>
        <div className="card" style={{ boxShadow: 'none' }}>
          <InvoiceLinesTable inv={i} />
        </div>
        <InvoiceTotals inv={i} />
        {i.payments?.length > 0 && (
          <div style={{ marginTop: 16 }}>
            <h4 className="section-title">Payments received</h4>
            {i.payments.map((p) => (
              <div key={p.id} className="row" style={{ fontSize: 'var(--fs-sm)' }}>
                {date(p.date)} · {methodLabel(p.method)}
                <div className="spacer" />
                <span className="num">{money(p.amount)}</span>
              </div>
            ))}
          </div>
        )}
        <div className="print-foot">
          Amounts in {i.currency || 'INR'}. Prices exclude tax; tax is computed per line. Thank you for your business.
        </div>
      </article>
    </>
  )
}

/* ---------------- Payments ---------------- */
export function PaymentsPage() {
  const [search, setSearch] = useState('')
  const q = useDebounced(search)
  const list = useList<Payment>('/payments', { search: q })
  const nav = useNavigate()
  const total = (list.rows ?? []).reduce((s, p) => s + num(p.amount), 0)
  return (
    <>
      <PageHeader title="Payments" sub="Money received against posted invoices." />
      <ErrorBanner error={list.error} onRetry={list.reload} />
      <Card pad={false}>
        <div className="toolbar" style={{ padding: '12px 16px 0', marginBottom: 12 }}>
          <SearchInput value={search} onChange={setSearch} placeholder="Search invoice or customer" />
          <div className="spacer" />
          {list.rows && list.rows.length > 0 && <span className="muted">This page: {money(total)}</span>}
        </div>
        <Table<Payment>
          rows={list.rows}
          loading={list.loading && !list.rows}
          rowKey={(r) => r.id}
          onRowClick={(r) => nav(`/invoices/${r.invoice}`)}
          page={list.page}
          count={list.count}
          onPage={list.setPage}
          columns={[
            { key: 'd', header: 'Date', render: (r) => date(r.date) },
            { key: 'i', header: 'Invoice', render: (r) => <span className="mono">{r.invoice_number ?? `#${r.invoice}`}</span> },
            { key: 'c', header: 'Customer', render: (r) => r.customer_name ?? '—' },
            { key: 'm', header: 'Method', render: (r) => methodLabel(r.method) },
            { key: 'n', header: 'Note', render: (r) => r.note || '—' },
            { key: 'a', header: 'Amount', align: 'right', render: (r) => <strong>{money(r.amount)}</strong> },
          ]}
          empty={<EmptyState icon={<Icon.card />} title="No payments recorded" body="Record payments from a posted invoice." />}
        />
      </Card>
    </>
  )
}
