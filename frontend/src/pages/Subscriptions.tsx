import { useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../api'
import { useAuth } from '../auth'
import { Icon } from '../components/icons'
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
} from '../components/ui'
import { date, dateTime, money, periodLabel, periodUnit, todayISO, titleCase } from '../format'
import { useAsync, useDebounced, useList, useLookup } from '../hooks'
import type { Customer, Invoice, QuotationTemplate, SubAction, SubLine, Subscription, SubStatus } from '../types'
import {
  actionMeta,
  Lifecycle,
  LinesEditor,
  linesError,
  linesPayload,
  SubHeaderForm,
  usePaymentTerms,
  type SubHeaderDraft,
} from './subscriptionParts'
import { ConvertTrialModal } from './Trial'

const TABS: { key: '' | SubStatus; label: string }[] = [
  { key: '', label: 'All' },
  { key: 'draft', label: 'Draft' },
  { key: 'quotation', label: 'Quotation' },
  { key: 'confirmed', label: 'Confirmed' },
  { key: 'active', label: 'Active' },
  { key: 'paused', label: 'Paused' },
  { key: 'closed', label: 'Closed' },
]

export function SubscriptionsPage({ portal = false }: { portal?: boolean }) {
  const [sp, setSp] = useSearchParams()
  const status = (sp.get('status') ?? '') as '' | SubStatus
  const [search, setSearch] = useState('')
  const q = useDebounced(search)
  const list = useList<Subscription>('/subscriptions', { status, search: q })
  const nav = useNavigate()
  const base = portal ? '/portal/subscriptions' : '/subscriptions'

  return (
    <>
      <PageHeader
        title={portal ? 'My subscriptions' : 'Subscriptions'}
        sub={portal ? 'Your plans, quotations and what renews next.' : 'Quotations and recurring contracts.'}
        actions={
          !portal && (
            <Button variant="primary" icon={<Icon.plus />} onClick={() => nav('/subscriptions/new')}>
              New subscription
            </Button>
          )
        }
      />
      <div className="tabs" role="tablist" aria-label="Filter by status">
        {TABS.map((t) => (
          <button
            key={t.key}
            role="tab"
            className="tab"
            aria-selected={status === t.key}
            onClick={() => {
              const n = new URLSearchParams(sp)
              if (t.key) n.set('status', t.key)
              else n.delete('status')
              setSp(n, { replace: true })
            }}
          >
            {t.label}
          </button>
        ))}
      </div>
      <ErrorBanner error={list.error} onRetry={list.reload} />
      <Card pad={false}>
        <div className="toolbar" style={{ padding: '12px 16px 0', marginBottom: 12 }}>
          <SearchInput value={search} onChange={setSearch} placeholder="Search number, customer or plan" />
          <div className="spacer" />
          {!list.loading && <span className="muted">{list.count} subscriptions</span>}
        </div>
        <Table<Subscription>
          rows={list.rows}
          loading={list.loading && !list.rows}
          rowKey={(r) => r.id}
          onRowClick={(r) => nav(`${base}/${r.id}`)}
          page={list.page}
          count={list.count}
          onPage={list.setPage}
          columns={[
            { key: 'number', header: 'Number', render: (r) => <strong className="mono">{r.number}</strong> },
            ...(portal ? [] : [{ key: 'customer', header: 'Customer', render: (r: Subscription) => r.customer_name }]),
            { key: 'plan', header: 'Plan', render: (r) => r.plan_name },
            { key: 'period', header: 'Billing', render: (r) => periodLabel[r.billing_period] ?? r.billing_period },
            { key: 'start', header: 'Start', render: (r) => date(r.start_date) },
            { key: 'next', header: 'Next invoice', render: (r) => date(r.next_invoice_date) },
            { key: 'total', header: 'Recurring', align: 'right', render: (r) => money(r.recurring_total) },
            { key: 'status', header: 'Status', render: (r) => <StatusPill status={r.status} /> },
          ]}
          empty={
            <EmptyState
              icon={<Icon.loop />}
              title={status ? `No ${status} subscriptions` : 'No subscriptions yet'}
              body={portal ? 'When you receive a quotation it appears here.' : 'Create one from scratch or from a quotation template.'}
              action={
                !portal && (
                  <Button variant="primary" icon={<Icon.plus />} onClick={() => nav('/subscriptions/new')}>
                    New subscription
                  </Button>
                )
              }
            />
          }
        />
      </Card>
    </>
  )
}

/* ---------------- Detail ---------------- */
export function SubscriptionDetailPage({ portal = false }: { portal?: boolean }) {
  const { id } = useParams()
  const { isStaff } = useAuth()
  const toast = useToast()
  const nav = useNavigate()
  const sub = useAsync(() => api.get<Subscription>(`/subscriptions/${id}`), [id])
  const invoices = useAsync(() => api.list<Invoice>('/invoices', { subscription: id, page_size: 50 }), [id])
  const terms = usePaymentTerms()
  const [pending, setPending] = useState<SubAction | null>(null)
  const [busyAction, setBusyAction] = useState<SubAction | null>(null)
  const [converting, setConverting] = useState(false)
  const [head, setHead] = useState<SubHeaderDraft | null>(null)
  const [lines, setLines] = useState<SubLine[]>([])
  const [errors, setErrors] = useState<Record<string, string[]>>({})
  const [saving, setSaving] = useState(false)
  const [dirty, setDirty] = useState(false)

  const s = sub.data
  const editable = !portal && isStaff && !!s && (s.status === 'draft' || s.status === 'quotation')
  const base = portal ? '/portal/subscriptions' : '/subscriptions'

  useEffect(() => {
    if (!s) return
    setHead({
      customer: s.customer,
      plan: s.plan,
      start_date: s.start_date,
      expiry_date: s.expiry_date,
      payment_term_days: s.payment_term_days,
      notes: s.notes ?? '',
    })
    setLines(s.lines.map((l) => ({ ...l })))
    setDirty(false)
    setErrors({})
  }, [s])

  const runAction = async (action: SubAction, note?: string) => {
    if (dirty && editable) {
      toast.info('Save or discard your changes first.')
      return
    }
    setBusyAction(action)
    try {
      const updated = await api.action<Subscription>(`/subscriptions/${id}/transition`, { action, ...(note ? { note } : {}) })
      const label = actionMeta[action]
      toast.success(`${portal && label.portalLabel ? label.portalLabel : label.label}: done`)
      setPending(null)
      if (action === 'renew' && updated && updated.id && String(updated.id) !== String(id)) {
        nav(`${base}/${updated.id}`)
      } else if (updated && updated.id) {
        sub.setData(updated)
      } else {
        sub.reload()
      }
      invoices.reload()
    } catch (e) {
      toast.error(e)
    } finally {
      setBusyAction(null)
    }
  }

  const save = async () => {
    if (!head) return
    const le = linesError(lines)
    if (le) {
      setErrors({ lines: [le] })
      return
    }
    setSaving(true)
    setErrors({})
    try {
      const updated = await api.update<Subscription>('/subscriptions', id!, { ...head, lines: linesPayload(lines) })
      sub.setData(updated)
      toast.success('Subscription saved')
    } catch (e) {
      if (e instanceof ApiError) setErrors(e.fields)
      toast.error(e)
    } finally {
      setSaving(false)
    }
  }

  if (sub.error)
    return (
      <>
        <PageHeader title="Subscription" crumbs={[{ label: portal ? 'My subscriptions' : 'Subscriptions', to: base }]} />
        <ErrorBanner error={sub.error} onRetry={sub.reload} />
      </>
    )
  if (!s || !head)
    return (
      <div className="stack">
        <Skeleton w={240} h={28} />
        <Skeleton h={64} />
        <Skeleton h={240} />
      </div>
    )

  const meta = (a: SubAction) => actionMeta[a] ?? { label: titleCase(a), variant: 'default' as const }
  const actions = s.available_actions ?? []

  return (
    <>
      <PageHeader
        crumbs={[{ label: portal ? 'My subscriptions' : 'Subscriptions', to: base }]}
        title={
          <div className="title-row">
            <h1 className="mono">{s.number}</h1>
            <StatusPill status={s.status} />
          </div>
        }
        sub={
          <>
            {portal ? '' : `${s.customer_name} · `}
            {s.plan_name} · billed {periodUnit[s.billing_period] ? `every ${periodUnit[s.billing_period]}` : s.billing_period}
          </>
        }
        actions={actions.map((a) => {
          const m = meta(a)
          return (
            <Button
              key={a}
              variant={m.variant}
              loading={busyAction === a}
              disabled={!!busyAction}
              onClick={() =>
                a === 'convert' ? setConverting(true) : m.confirm || a === 'close' ? setPending(a) : runAction(a)
              }
            >
              {portal && m.portalLabel ? m.portalLabel : m.label}
            </Button>
          )
        })}
      />

      <Card pad={false} className="fade-in">
        <Lifecycle status={s.status} />
      </Card>

      {s.is_trial && (
        <div className="alert alert-info" style={{ marginTop: 16 }}>
          <strong>Free trial</strong>
          {s.expiry_date ? ` until ${date(s.expiry_date)}` : ''}; its invoices are 0 and settled automatically.
          {s.converted_to && s.converted_to_number && (
            <>
              {' '}Converted to{' '}
              <Link className="mono" to={`${portal ? '/portal' : ''}/subscriptions/${s.converted_to}`}>
                {s.converted_to_number}
              </Link>
              .
            </>
          )}
        </div>
      )}
      <ConvertTrialModal subscriptionId={s.id} open={converting} onClose={() => setConverting(false)} portal={portal} />

      {s.status === 'quotation' && s.quotation_valid_until && (
        <div className="alert alert-info" style={{ marginTop: 16 }}>
          {portal ? 'This quotation is' : 'Quotation'} valid until <strong>{date(s.quotation_valid_until)}</strong>.
          {portal && actions.includes('confirm') && ' Accept it to start your subscription.'}
        </div>
      )}

      <div className="detail-grid" style={{ marginTop: 16 }}>
        <div className="stack">
          <Card
            title="Details"
            actions={
              editable &&
              dirty && (
                <>
                  <Button
                    size="sm"
                    onClick={() => {
                      sub.setData({ ...s })
                    }}
                  >
                    Discard
                  </Button>
                  <Button size="sm" variant="primary" loading={saving} onClick={save}>
                    Save changes
                  </Button>
                </>
              )
            }
          >
            {editable ? (
              <SubHeaderForm
                d={head}
                errors={errors}
                set={(p) => {
                  setHead({ ...head, ...p })
                  setDirty(true)
                }}
              />
            ) : (
              <dl className="dl">
                {!portal && (
                  <>
                    <dt>Customer</dt>
                    <dd>{s.customer_name}</dd>
                  </>
                )}
                <dt>Plan</dt>
                <dd>{s.plan_name}</dd>
                <dt>Start date</dt>
                <dd>{date(s.start_date)}</dd>
                <dt>Expiry date</dt>
                <dd>{s.expiry_date ? date(s.expiry_date) : 'No end date'}</dd>
                <dt>Next invoice</dt>
                <dd>{date(s.next_invoice_date)}</dd>
                <dt>Payment terms</dt>
                <dd>{terms.find((t) => t.days === s.payment_term_days)?.label ?? `${s.payment_term_days} days`}</dd>
                {s.notes && (
                  <>
                    <dt>Notes</dt>
                    <dd style={{ whiteSpace: 'pre-wrap' }}>{s.notes}</dd>
                  </>
                )}
              </dl>
            )}
          </Card>

          <Card
            title="Order lines"
            pad={false}
            actions={
              editable &&
              dirty && (
                <Button size="sm" variant="primary" loading={saving} onClick={save}>
                  Save changes
                </Button>
              )
            }
          >
            <LinesEditor
              lines={lines}
              readOnly={!editable}
              error={errors.lines?.join(' ')}
              onChange={(l) => {
                setLines(l)
                setDirty(true)
              }}
            />
            {!editable && (
              <div className="totals">
                <span className="muted">Subtotal</span>
                <span className="num right">{money(s.subtotal)}</span>
                <span className="grand">Recurring total</span>
                <span className="grand num right">{money(s.recurring_total)}</span>
              </div>
            )}
          </Card>

          <Card title="Invoices" pad={false}>
            <Table<Invoice>
              compact
              rows={invoices.data?.results ?? null}
              loading={invoices.loading && !invoices.data}
              rowKey={(r) => r.id}
              onRowClick={(r) => nav(portal ? `/portal/invoices/${r.id}` : `/invoices/${r.id}`)}
              columns={[
                { key: 'n', header: 'Number', render: (r) => <span className="mono">{r.number || 'Draft'}</span> },
                { key: 'p', header: 'Period', render: (r) => `${date(r.period_start)} – ${date(r.period_end)}` },
                { key: 'd', header: 'Due', render: (r) => date(r.due_date) },
                { key: 't', header: 'Total', align: 'right', render: (r) => money(r.total) },
                {
                  key: 's',
                  header: 'Status',
                  render: (r) => (r.is_overdue ? <StatusPill status="overdue" /> : <StatusPill status={r.status} kind="invoice" />),
                },
              ]}
              empty={<EmptyState icon={<Icon.invoice />} title="No invoices yet" body="Invoices are created at activation and on each billing run." />}
            />
          </Card>
        </div>

        <Card title="History">
          {s.events?.length ? (
            <ol className="timeline">
              {[...s.events].reverse().map((e, i) => (
                <li key={i}>
                  <div className="t-title">
                    {e.from_status ? `${titleCase(e.from_status)} → ${titleCase(e.to_status)}` : `Created as ${titleCase(e.to_status)}`}
                  </div>
                  <div className="t-meta">
                    {dateTime(e.at)}
                    {e.user_name ? ` · ${e.user_name}` : ''}
                  </div>
                  {e.note && <div className="t-note">{e.note}</div>}
                </li>
              ))}
            </ol>
          ) : (
            <p className="muted" style={{ margin: 0 }}>
              Created {dateTime(s.created_at)}. Status changes appear here.
            </p>
          )}
        </Card>
      </div>

      <ConfirmDialog
        open={!!pending}
        title={pending ? `${portal && meta(pending).portalLabel ? meta(pending).portalLabel : meta(pending).label} ${s.number}?` : ''}
        body={pending ? meta(pending).confirm : undefined}
        confirmLabel={pending ? (portal && meta(pending).portalLabel ? meta(pending).portalLabel : meta(pending).label) : 'Confirm'}
        danger={pending === 'close'}
        withNote={!portal}
        onConfirm={(note) => (pending ? runAction(pending, note) : undefined)}
        onClose={() => setPending(null)}
      />
    </>
  )
}

/* ---------------- New ---------------- */
export function NewSubscriptionPage() {
  const [mode, setMode] = useState<'blank' | 'template'>('blank')
  const nav = useNavigate()
  const toast = useToast()
  const [head, setHead] = useState<SubHeaderDraft>({
    customer: null,
    plan: null,
    start_date: todayISO(),
    expiry_date: null,
    payment_term_days: 0,
    notes: '',
  })
  const [lines, setLines] = useState<SubLine[]>([])
  const [errors, setErrors] = useState<Record<string, string[]>>({})
  const [busy, setBusy] = useState(false)
  const templates = useLookup<QuotationTemplate>('/quotation-templates')
  const customers = useLookup<Customer>('/customers')
  const [tpl, setTpl] = useState<{ template: number | null; customer: number | null; start_date: string }>({
    template: null,
    customer: null,
    start_date: todayISO(),
  })

  const createBlank = async () => {
    const e: Record<string, string[]> = {}
    if (!head.customer) e.customer = ['Choose a customer.']
    if (!head.plan) e.plan = ['Choose a plan.']
    const le = linesError(lines)
    if (le) e.lines = [le]
    if (Object.keys(e).length) return setErrors(e)
    setBusy(true)
    setErrors({})
    try {
      const s = await api.create<Subscription>('/subscriptions', { ...head, lines: linesPayload(lines) })
      toast.success(`Subscription ${s.number ?? ''} created`)
      nav(`/subscriptions/${s.id}`)
    } catch (err) {
      if (err instanceof ApiError) setErrors(err.fields)
      toast.error(err)
    } finally {
      setBusy(false)
    }
  }

  const createFromTemplate = async () => {
    const e: Record<string, string[]> = {}
    if (!tpl.template) e.template = ['Choose a template.']
    if (!tpl.customer) e.customer = ['Choose a customer.']
    if (Object.keys(e).length) return setErrors(e)
    setBusy(true)
    setErrors({})
    try {
      const s = await api.action<Subscription>('/subscriptions/from-template', tpl)
      toast.success(`Quotation ${s.number ?? ''} created`)
      nav(`/subscriptions/${s.id}`)
    } catch (err) {
      if (err instanceof ApiError) setErrors(err.fields)
      toast.error(err)
    } finally {
      setBusy(false)
    }
  }

  const chosen = templates.find((t) => t.id === tpl.template)

  return (
    <>
      <PageHeader
        title="New subscription"
        crumbs={[{ label: 'Subscriptions', to: '/subscriptions' }]}
        sub="Starts as a draft. Send it as a quotation or confirm it directly."
      />
      <div className="tabs" role="tablist">
        <button role="tab" className="tab" aria-selected={mode === 'blank'} onClick={() => setMode('blank')}>
          Start blank
        </button>
        <button role="tab" className="tab" aria-selected={mode === 'template'} onClick={() => setMode('template')}>
          From quotation template
        </button>
      </div>

      {mode === 'blank' ? (
        <div className="stack">
          <Card title="Details">
            <SubHeaderForm d={head} set={(p) => setHead({ ...head, ...p })} errors={errors} />
          </Card>
          <Card title="Order lines" pad={false}>
            <LinesEditor lines={lines} onChange={setLines} error={errors.lines?.join(' ')} />
          </Card>
          <div className="row">
            <div className="spacer" />
            <Link to="/subscriptions" className="btn">
              Cancel
            </Link>
            <Button variant="primary" loading={busy} onClick={createBlank}>
              Create draft
            </Button>
          </div>
        </div>
      ) : (
        <Card title="Quotation from template">
          <div className="stack">
            <div className="grid-2">
              <Field label="Template" required error={errors.template}>
                {(id) => (
                  <Select
                    id={id}
                    placeholder="Choose template…"
                    options={templates.map((t) => ({ value: t.id, label: t.name }))}
                    value={tpl.template ?? ''}
                    onChange={(e) => setTpl({ ...tpl, template: e.target.value ? Number(e.target.value) : null })}
                  />
                )}
              </Field>
              <Field label="Customer" required error={errors.customer}>
                {(id) => (
                  <Select
                    id={id}
                    placeholder="Choose customer…"
                    options={customers.map((c) => ({ value: c.id, label: c.name }))}
                    value={tpl.customer ?? ''}
                    onChange={(e) => setTpl({ ...tpl, customer: e.target.value ? Number(e.target.value) : null })}
                  />
                )}
              </Field>
              <Field label="Start date" error={errors.start_date}>
                {(id) => (
                  <Input id={id} type="date" value={tpl.start_date} onChange={(e) => setTpl({ ...tpl, start_date: e.target.value })} />
                )}
              </Field>
            </div>
            {chosen && (
              <div className="alert alert-info">
                <strong>{chosen.name}</strong>: {chosen.plan_name ?? 'plan'} · {chosen.lines.length} line
                {chosen.lines.length === 1 ? '' : 's'} · valid for {chosen.validity_days} days.
                {chosen.lines.length > 0 && (
                  <div style={{ marginTop: 4 }}>
                    {chosen.lines.map((l, i) => (
                      <div key={i}>
                        {l.quantity} × {l.product_name ?? `Product #${l.product}`}
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}
            {templates.length === 0 && (
              <p className="muted" style={{ margin: 0 }}>
                No templates yet. <Link to="/quotation-templates">Create a quotation template</Link> first.
              </p>
            )}
            <div className="row">
              <div className="spacer" />
              <Button variant="primary" loading={busy} onClick={createFromTemplate}>
                Create quotation
              </Button>
            </div>
          </div>
        </Card>
      )}
    </>
  )
}
