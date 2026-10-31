/* eslint-disable @typescript-eslint/no-explicit-any */
import { useState, type ReactNode } from 'react'
import { api, ApiError } from '../api'
import { useDebounced, useList, invalidateLookup } from '../hooks'
import { Icon } from './icons'
import { useToast } from './toast'
import {
  Button,
  Card,
  ConfirmDialog,
  Drawer,
  EmptyState,
  ErrorBanner,
  Field,
  Input,
  PageHeader,
  SearchInput,
  Select,
  Table,
  Textarea,
  Toggle,
  type Column,
  type Option,
} from './ui'

export type Draft = Record<string, any>
export type FieldErrors = Record<string, string[]>

export interface FieldDef {
  name: string
  label: string
  type?: 'text' | 'email' | 'number' | 'money' | 'date' | 'textarea' | 'select' | 'toggle' | 'multiselect' | 'password'
  options?: Option[]
  placeholder?: string
  required?: boolean
  hint?: string
  span?: 2
  /** Hide the field when this returns false. */
  when?: (d: Draft) => boolean
  createOnly?: boolean
}

/** Renders one form field bound to a draft object. */
export function FormField({
  f,
  draft,
  set,
  errors,
  disabled,
}: {
  f: FieldDef
  draft: Draft
  set: (name: string, v: any) => void
  errors: FieldErrors
  disabled?: boolean
}) {
  const v = draft[f.name]
  const err = errors[f.name]
  const cls = f.span === 2 || f.type === 'textarea' || f.type === 'multiselect' ? 'span-2' : ''
  if (f.type === 'toggle') {
    return (
      <div className={`field ${cls}`} style={{ justifyContent: 'flex-end' }}>
        <Toggle checked={!!v} onChange={(x) => set(f.name, x)} label={f.label} disabled={disabled} />
        {err && <span className="field-error">{err.join(' ')}</span>}
      </div>
    )
  }
  return (
    <Field label={f.label} hint={f.hint} error={err} required={f.required} className={cls}>
      {(id, desc) => {
        const common = {
          id,
          'aria-describedby': desc,
          'aria-invalid': err ? true : undefined,
          disabled,
          required: f.required,
        }
        switch (f.type) {
          case 'textarea':
            return <Textarea {...common} rows={3} value={v ?? ''} onChange={(e) => set(f.name, e.target.value)} />
          case 'select':
            return (
              <Select
                {...common}
                options={f.options ?? []}
                placeholder={f.placeholder ?? 'Select…'}
                value={v ?? ''}
                onChange={(e) => {
                  const raw = e.target.value
                  const opt = f.options?.find((o) => String(o.value) === raw)
                  set(f.name, raw === '' ? null : opt ? opt.value : raw)
                }}
              />
            )
          case 'multiselect': {
            const sel: any[] = Array.isArray(v) ? v : []
            return (
              <div className="row wrap" style={{ gap: 6 }} id={id} role="group" aria-label={f.label}>
                {(f.options ?? []).map((o) => {
                  const on = sel.includes(o.value)
                  return (
                    <Button
                      key={o.value}
                      size="sm"
                      variant={on ? 'primary' : 'default'}
                      aria-pressed={on}
                      disabled={disabled}
                      onClick={() => set(f.name, on ? sel.filter((x) => x !== o.value) : [...sel, o.value])}
                    >
                      {o.label}
                    </Button>
                  )
                })}
                {!f.options?.length && <span className="muted">No options available.</span>}
              </div>
            )
          }
          case 'number':
          case 'money':
            return (
              <Input
                {...common}
                type="number"
                inputMode="decimal"
                step={f.type === 'money' ? '0.01' : '1'}
                min="0"
                placeholder={f.placeholder}
                value={v ?? ''}
                onChange={(e) => set(f.name, e.target.value === '' ? null : e.target.value)}
              />
            )
          case 'date':
            return (
              <Input
                {...common}
                type="date"
                value={v ?? ''}
                onChange={(e) => set(f.name, e.target.value || null)}
              />
            )
          default:
            return (
              <Input
                {...common}
                type={f.type ?? 'text'}
                placeholder={f.placeholder}
                value={v ?? ''}
                onChange={(e) => set(f.name, e.target.value)}
              />
            )
        }
      }}
    </Field>
  )
}

export interface CrudProps<T extends { id: number }> {
  title: string
  sub?: string
  singular: string
  path: string
  columns: Column<T>[]
  fields: FieldDef[]
  defaults: Draft
  canWrite: boolean
  canDelete?: boolean
  searchPlaceholder?: string
  /** Extra nested editor (variants, lines). */
  extra?: (draft: Draft, setDraft: (d: Draft) => void, errors: FieldErrors, readOnly: boolean) => ReactNode
  toPayload?: (d: Draft) => Draft
  validate?: (d: Draft) => FieldErrors
  wide?: boolean
  emptyBody?: string
  icon?: ReactNode
  /** Lookup cache keys to invalidate after writes. */
  invalidates?: string[]
}

export function CrudPage<T extends { id: number }>(p: CrudProps<T>) {
  const toast = useToast()
  const [search, setSearch] = useState('')
  const q = useDebounced(search)
  const list = useList<T>(p.path, { search: q })
  const [draft, setDraft] = useState<Draft | null>(null)
  const [errors, setErrors] = useState<FieldErrors>({})
  const [saving, setSaving] = useState(false)
  const [confirmDel, setConfirmDel] = useState(false)

  const editing = draft && draft.id != null
  const readOnly = !p.canWrite

  const open = (row?: T) => {
    setErrors({})
    setDraft(row ? structuredClone(row as Draft) : structuredClone(p.defaults))
  }
  const set = (name: string, v: any) => setDraft((d) => (d ? { ...d, [name]: v } : d))

  const save = async () => {
    if (!draft) return
    const localErr = p.validate?.(draft) ?? {}
    for (const f of p.fields) {
      if (f.required && (f.when?.(draft) ?? true) && (draft[f.name] === '' || draft[f.name] == null))
        localErr[f.name] = ['This field is required.']
    }
    if (Object.keys(localErr).length) {
      setErrors(localErr)
      return
    }
    setSaving(true)
    setErrors({})
    try {
      const body = p.toPayload ? p.toPayload(draft) : draft
      if (editing) await api.update(p.path, draft.id, body)
      else await api.create(p.path, body)
      toast.success(`${p.singular} ${editing ? 'saved' : 'created'}`)
      p.invalidates?.forEach(invalidateLookup)
      invalidateLookup(p.path)
      setDraft(null)
      list.reload()
    } catch (e) {
      if (e instanceof ApiError && Object.keys(e.fields).length) setErrors(e.fields)
      toast.error(e)
    } finally {
      setSaving(false)
    }
  }

  const del = async () => {
    if (!draft?.id) return
    try {
      await api.remove(p.path, draft.id)
      toast.success(`${p.singular} deleted`)
      p.invalidates?.forEach(invalidateLookup)
      invalidateLookup(p.path)
      setConfirmDel(false)
      setDraft(null)
      list.reload()
    } catch (e) {
      toast.error(e)
    }
  }

  return (
    <>
      <PageHeader
        title={p.title}
        sub={p.sub}
        actions={
          p.canWrite && (
            <Button variant="primary" icon={<Icon.plus />} onClick={() => open()}>
              New {p.singular.toLowerCase()}
            </Button>
          )
        }
      />
      {readOnly && (
        <div className="alert alert-info" style={{ marginBottom: 16 }}>
          View only. An admin can change {p.title.toLowerCase()}.
        </div>
      )}
      <ErrorBanner error={list.error} onRetry={list.reload} />
      <Card pad={false}>
        <div className="toolbar" style={{ padding: '12px 16px 0', marginBottom: 12 }}>
          <SearchInput value={search} onChange={setSearch} placeholder={p.searchPlaceholder ?? `Search ${p.title.toLowerCase()}`} />
        </div>
        <Table<T>
          columns={p.columns}
          rows={list.rows}
          loading={list.loading && !list.rows}
          rowKey={(r) => r.id}
          onRowClick={(r) => open(r)}
          page={list.page}
          count={list.count}
          onPage={list.setPage}
          empty={
            <EmptyState
              icon={p.icon}
              title={q ? `No ${p.title.toLowerCase()} match "${q}"` : `No ${p.title.toLowerCase()} yet`}
              body={q ? 'Try a different search.' : p.emptyBody}
              action={
                p.canWrite && !q ? (
                  <Button variant="primary" icon={<Icon.plus />} onClick={() => open()}>
                    New {p.singular.toLowerCase()}
                  </Button>
                ) : undefined
              }
            />
          }
        />
      </Card>

      <Drawer
        open={!!draft}
        onClose={() => !saving && setDraft(null)}
        wide={p.wide}
        title={readOnly ? p.singular : editing ? `Edit ${p.singular.toLowerCase()}` : `New ${p.singular.toLowerCase()}`}
        footer={
          readOnly ? (
            <Button onClick={() => setDraft(null)}>Close</Button>
          ) : (
            <>
              {editing && p.canDelete !== false && (
                <Button variant="danger" icon={<Icon.trash />} onClick={() => setConfirmDel(true)}>
                  Delete
                </Button>
              )}
              <div className="spacer" />
              <Button onClick={() => setDraft(null)} disabled={saving}>
                Cancel
              </Button>
              <Button variant="primary" loading={saving} onClick={save}>
                {editing ? 'Save changes' : `Create ${p.singular.toLowerCase()}`}
              </Button>
            </>
          )
        }
      >
        {draft && (
          <form
            onSubmit={(e) => {
              e.preventDefault()
              if (!readOnly) save()
            }}
            className="stack"
          >
            {errors.non_field_errors && <div className="alert alert-error">{errors.non_field_errors.join(' ')}</div>}
            <div className="grid-2">
              {p.fields
                .filter((f) => (f.when?.(draft) ?? true) && !(f.createOnly && editing))
                .map((f) => (
                  <FormField key={f.name} f={f} draft={draft} set={set} errors={errors} disabled={readOnly} />
                ))}
            </div>
            {p.extra?.(draft, (d) => setDraft(d), errors, readOnly)}
            <button type="submit" hidden />
          </form>
        )}
      </Drawer>

      <ConfirmDialog
        open={confirmDel}
        title={`Delete this ${p.singular.toLowerCase()}?`}
        body="This removes it permanently. Records that already reference it may block the delete."
        confirmLabel="Delete"
        danger
        onConfirm={del}
        onClose={() => setConfirmDel(false)}
      />
    </>
  )
}
