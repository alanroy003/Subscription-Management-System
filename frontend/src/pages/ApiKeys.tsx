import { useState } from 'react'
import { api } from '../api'
import { Icon } from '../components/icons'
import { useToast } from '../components/toast'
import { Button, Card, EmptyState, ErrorBanner, Field, Input, PageHeader, Table } from '../components/ui'
import { date } from '../format'
import { useAsync } from '../hooks'

interface ApiKey {
  id: number
  name: string
  prefix: string
  scopes: string[]
  created_at: string
  last_used_at: string | null
  revoked_at: string | null
}

/** Admin-only: issue, list and revoke public API keys. The full key is shown once, right after creation. */
export function ApiKeysPage() {
  const toast = useToast()
  const keys = useAsync(() => api.list<ApiKey>('/api-keys', { page_size: 100 }), [])
  const [name, setName] = useState('')
  const [write, setWrite] = useState(false)
  const [busy, setBusy] = useState(false)
  const [fresh, setFresh] = useState<string | null>(null)

  const create = async () => {
    if (!name.trim()) return toast.error('Give the key a name, for example the system that will use it.')
    setBusy(true)
    try {
      const r = await api.action<ApiKey & { key: string }>('/api-keys', { name, scopes: write ? ['read', 'write'] : ['read'] })
      setFresh(r.key)
      setName('')
      keys.reload()
      toast.success('API key created')
    } catch (e) {
      toast.error(e)
    } finally {
      setBusy(false)
    }
  }

  const revoke = async (k: ApiKey) => {
    try {
      await api.action(`/api-keys/${k.id}/revoke`)
      toast.success(`Key ${k.name} revoked`)
      keys.reload()
    } catch (e) {
      toast.error(e)
    }
  }

  return (
    <>
      <PageHeader
        title="API keys"
        sub={
          <>
            Let other systems use the API with an <code>X-API-Key</code> header. See the{' '}
            <a href="/api/docs" target="_blank" rel="noreferrer">
              API documentation
            </a>
            .
          </>
        }
      />
      <Card title="New key">
        <div className="row" style={{ gap: 12, alignItems: 'flex-end', flexWrap: 'wrap' }}>
          <div style={{ flex: '1 1 260px' }}>
            <Field label="Name" required>
              {(id) => <Input id={id} value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. ERP sync" />}
            </Field>
          </div>
          <label className="row" style={{ gap: 8, paddingBottom: 10 }}>
            <input type="checkbox" checked={write} onChange={(e) => setWrite(e.target.checked)} />
            Allow writes (create and change data)
          </label>
          <Button variant="primary" icon={<Icon.plus />} loading={busy} onClick={create}>
            Create key
          </Button>
        </div>
        {fresh && (
          <div className="alert alert-info" style={{ marginTop: 16 }}>
            <strong>Copy this key now. It will not be shown again.</strong>
            <div className="row" style={{ gap: 8, marginTop: 8 }}>
              <code style={{ wordBreak: 'break-all' }}>{fresh}</code>
              <Button size="sm" onClick={() => navigator.clipboard?.writeText(fresh).then(() => toast.success('Copied'))}>
                Copy
              </Button>
            </div>
          </div>
        )}
      </Card>
      <div style={{ height: 16 }} />
      <Card title="Keys" pad={false}>
        <ErrorBanner error={keys.error} onRetry={keys.reload} />
        <Table<ApiKey>
          rows={keys.data?.results ?? null}
          loading={keys.loading}
          rowKey={(k) => k.id}
          empty={<EmptyState title="No API keys yet" body="Create one to connect another system." />}
          columns={[
            { key: 'name', header: 'Name', render: (k) => <strong>{k.name}</strong> },
            { key: 'prefix', header: 'Key', render: (k) => <code>bl_{k.prefix}_…</code> },
            { key: 'scopes', header: 'Scopes', render: (k) => k.scopes.join(', ') },
            { key: 'created', header: 'Created', render: (k) => date(k.created_at) },
            { key: 'used', header: 'Last used', render: (k) => (k.last_used_at ? date(k.last_used_at) : 'Never') },
            {
              key: 'status',
              header: 'Status',
              render: (k) =>
                k.revoked_at ? <span className="pill pill-closed">Revoked</span> : <span className="pill pill-active">Active</span>,
            },
            {
              key: 'actions',
              header: '',
              align: 'right',
              render: (k) =>
                !k.revoked_at && (
                  <Button size="sm" variant="danger" onClick={() => revoke(k)}>
                    Revoke
                  </Button>
                ),
            },
          ]}
        />
      </Card>
    </>
  )
}
