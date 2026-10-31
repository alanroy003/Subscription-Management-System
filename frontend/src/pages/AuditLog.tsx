import { useState } from 'react'
import { Card, EmptyState, ErrorBanner, Input, Modal, PageHeader, Select, Table } from '../components/ui'
import { Icon } from '../components/icons'
import { dateTime } from '../format'
import { useDebounced, useList } from '../hooks'

interface AuditEvent {
  id: number
  at: string
  action: string
  actor_label: string
  via: 'web' | 'api_key' | 'system'
  api_key_prefix: string
  object_type: string
  object_ref: string
  changes: Record<string, unknown>
  ip: string | null
}

const AREAS = [
  { value: '', label: 'All activity' },
  { value: 'auth.', label: 'Sign-ins and passwords' },
  { value: 'user.', label: 'Users' },
  { value: 'api_key.', label: 'API keys' },
  { value: 'invoice.', label: 'Invoices' },
  { value: 'payment.', label: 'Payments' },
  { value: 'subscription.', label: 'Subscriptions' },
  { value: 'billing.', label: 'Billing runs' },
  { value: 'discount.', label: 'Discounts' },
  { value: 'taxgroup.', label: 'Tax groups' },
  { value: 'product.', label: 'Products' },
  { value: 'plan.', label: 'Plans' },
  { value: 'customer.', label: 'Customers' },
  { value: 'integrity.', label: 'Data checks' },
]

const VIA_LABEL: Record<AuditEvent['via'], string> = { web: 'Web', api_key: 'API key', system: 'System' } // pragma: allowlist secret (display labels)

function actionLabel(action: string): string {
  const [area, verb = ''] = action.split('.')
  return `${area.replace('_', ' ')} ${verb.replace(/_/g, ' ')}`.trim()
}

/** Admin-only, read-only view of the append-only audit log. */
export function AuditLogPage() {
  const [area, setArea] = useState('')
  const [search, setSearch] = useState('')
  const [from, setFrom] = useState('')
  const [to, setTo] = useState('')
  const [open, setOpen] = useState<AuditEvent | null>(null)
  const q = useDebounced(search, 300)
  const list = useList<AuditEvent>('/audit-events', { action: area, search: q, date_from: from, date_to: to })

  return (
    <>
      <PageHeader title="Audit log" sub="Every sensitive action, who did it and from where. Entries can never be edited or deleted." />
      <Card>
        <div className="row" style={{ gap: 12, flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 200px' }}>
            <Select aria-label="Area" value={area} onChange={(e) => setArea(e.target.value)} options={AREAS} />
          </div>
          <div style={{ flex: '2 1 240px' }}>
            <Input aria-label="Search" placeholder="Search reference, email or action" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <Input aria-label="From date" type="date" value={from} onChange={(e) => setFrom(e.target.value)} />
          <Input aria-label="To date" type="date" value={to} onChange={(e) => setTo(e.target.value)} />
        </div>
      </Card>
      <div style={{ height: 16 }} />
      <ErrorBanner error={list.error} onRetry={list.reload} />
      <Card pad={false}>
        <Table<AuditEvent>
          rows={list.rows}
          loading={list.loading && !list.rows}
          rowKey={(e) => e.id}
          page={list.page}
          count={list.count}
          onPage={list.setPage}
          onRowClick={setOpen}
          columns={[
            { key: 'at', header: 'When', render: (e) => dateTime(e.at) },
            { key: 'action', header: 'Action', render: (e) => <strong style={{ textTransform: 'capitalize' }}>{actionLabel(e.action)}</strong> },
            { key: 'ref', header: 'Reference', render: (e) => <span className="mono">{e.object_ref || '—'}</span> },
            { key: 'who', header: 'By', render: (e) => e.actor_label || <span className="muted">System</span> },
            {
              key: 'via',
              header: 'Via',
              render: (e) => (e.via === 'api_key' ? `API key bl_${e.api_key_prefix}` : VIA_LABEL[e.via]),
            },
            { key: 'ip', header: 'IP', render: (e) => <span className="muted">{e.ip ?? '—'}</span> },
          ]}
          empty={<EmptyState icon={<Icon.shield />} title="Nothing logged yet" body="Sensitive actions appear here as they happen." />}
        />
      </Card>
      <Modal open={!!open} onClose={() => setOpen(null)} title={open ? actionLabel(open.action) : ''}>
        {open && (
          <>
            <p className="muted">
              {dateTime(open.at)} · {open.actor_label || 'System'} · {VIA_LABEL[open.via]}
              {open.ip ? ` · ${open.ip}` : ''}
            </p>
            <p>
              <strong>{open.object_type || 'event'}</strong> <span className="mono">{open.object_ref}</span>
            </p>
            <pre className="mono" style={{ whiteSpace: 'pre-wrap', fontSize: 'var(--fs-sm)', maxHeight: 360, overflow: 'auto' }}>
              {JSON.stringify(open.changes, null, 2)}
            </pre>
          </>
        )}
      </Modal>
    </>
  )
}
