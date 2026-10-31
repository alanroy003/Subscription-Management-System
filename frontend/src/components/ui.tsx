import {
  useEffect,
  useId,
  useRef,
  useState,
  type ButtonHTMLAttributes,
  type InputHTMLAttributes,
  type ReactNode,
  type SelectHTMLAttributes,
  type TextareaHTMLAttributes,
} from 'react'
import { Link } from 'react-router-dom'
import { Icon } from './icons'
import { titleCase } from '../format'

/* ---------------- Button ---------------- */
type Variant = 'primary' | 'accent' | 'danger' | 'danger-solid' | 'ghost' | 'default'
interface BtnProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: Variant
  size?: 'sm' | 'md'
  loading?: boolean
  icon?: ReactNode
  iconOnly?: boolean
}
export function Button({
  variant = 'default',
  size = 'md',
  loading,
  icon,
  iconOnly,
  className = '',
  children,
  disabled,
  type = 'button',
  ...rest
}: BtnProps) {
  const cls = [
    'btn',
    variant !== 'default' && `btn-${variant}`,
    size === 'sm' && 'btn-sm',
    iconOnly && 'btn-icon',
    className,
  ]
    .filter(Boolean)
    .join(' ')
  return (
    <button type={type} className={cls} disabled={disabled || loading} aria-busy={loading || undefined} {...rest}>
      {loading ? <span className="spinner" aria-hidden="true" /> : icon}
      {children}
    </button>
  )
}

/* ---------------- Field + inputs ---------------- */
interface FieldProps {
  label?: ReactNode
  hint?: ReactNode
  error?: string | string[]
  required?: boolean
  className?: string
  children: (id: string, describedBy?: string) => ReactNode
}
export function Field({ label, hint, error, required, className = '', children }: FieldProps) {
  const id = useId()
  const err = Array.isArray(error) ? error.join(' ') : error
  const descId = err || hint ? `${id}-desc` : undefined
  return (
    <div className={`field ${className}`}>
      {label && (
        <label htmlFor={id}>
          {label}
          {required && (
            <span className="req" aria-hidden="true">
              *
            </span>
          )}
        </label>
      )}
      {children(id, descId)}
      {err ? (
        <span id={descId} className="field-error">
          {err}
        </span>
      ) : hint ? (
        <span id={descId} className="field-hint">
          {hint}
        </span>
      ) : null}
    </div>
  )
}

export function Input({ className = '', ...p }: InputHTMLAttributes<HTMLInputElement>) {
  return <input className={`input ${className}`} {...p} />
}
export function Textarea({ className = '', ...p }: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  return <textarea className={`textarea ${className}`} {...p} />
}
export interface Option {
  value: string | number
  label: string
}
interface SelectProps extends Omit<SelectHTMLAttributes<HTMLSelectElement>, 'children'> {
  options: Option[]
  placeholder?: string
}
export function Select({ options, placeholder, className = '', ...p }: SelectProps) {
  return (
    <select className={`select ${className}`} {...p}>
      {placeholder !== undefined && <option value="">{placeholder}</option>}
      {options.map((o) => (
        <option key={o.value} value={o.value}>
          {o.label}
        </option>
      ))}
    </select>
  )
}

export function Toggle({
  checked,
  onChange,
  label,
  disabled,
}: {
  checked: boolean
  onChange: (v: boolean) => void
  label: ReactNode
  disabled?: boolean
}) {
  return (
    <label className="toggle">
      <input type="checkbox" checked={checked} disabled={disabled} onChange={(e) => onChange(e.target.checked)} />
      <span className="toggle-track" aria-hidden="true" />
      <span>{label}</span>
    </label>
  )
}

export function SearchInput({
  value,
  onChange,
  placeholder = 'Search',
}: {
  value: string
  onChange: (v: string) => void
  placeholder?: string
}) {
  return (
    <div className="search">
      <Icon.search />
      <input
        className="input"
        type="search"
        value={value}
        placeholder={placeholder}
        aria-label={placeholder}
        onChange={(e) => onChange(e.target.value)}
      />
    </div>
  )
}

/* ---------------- Status pill ---------------- */
export function StatusPill({ status, kind }: { status: string; kind?: 'invoice' | 'sub' }) {
  const key = kind === 'invoice' && status === 'confirmed' ? 'inv-confirmed' : status
  const label = kind === 'invoice' && status === 'confirmed' ? 'Confirmed' : titleCase(status)
  return <span className={`pill pill-${key}`}>{label}</span>
}

/* ---------------- Skeleton / Empty ---------------- */
export function Skeleton({ w = '100%', h = 14, style }: { w?: string | number; h?: number; style?: React.CSSProperties }) {
  return <div className="skel" style={{ width: w, height: h, ...style }} aria-hidden="true" />
}
export function SkeletonRows({ rows = 6, cols = 5 }: { rows?: number; cols?: number }) {
  return (
    <>
      {Array.from({ length: rows }).map((_, r) => (
        <tr key={r} aria-hidden="true">
          {Array.from({ length: cols }).map((__, c) => (
            <td key={c}>
              <Skeleton w={c === 0 ? '70%' : `${40 + ((r * 7 + c * 13) % 45)}%`} />
            </td>
          ))}
        </tr>
      ))}
    </>
  )
}
export function EmptyState({
  title,
  body,
  action,
  icon,
}: {
  title: string
  body?: ReactNode
  action?: ReactNode
  icon?: ReactNode
}) {
  return (
    <div className="empty">
      <div className="empty-icon">{icon ?? <Icon.file />}</div>
      <h3>{title}</h3>
      {body && <p>{body}</p>}
      {action}
    </div>
  )
}

/* ---------------- Page header / Card ---------------- */
export function PageHeader({
  title,
  sub,
  crumbs,
  actions,
}: {
  title: ReactNode
  sub?: ReactNode
  crumbs?: { label: string; to: string }[]
  actions?: ReactNode
}) {
  return (
    <header className="page-header">
      <div>
        {crumbs && (
          <nav className="crumbs" aria-label="Breadcrumb">
            {crumbs.map((c, i) => (
              <span key={c.to}>
                <Link to={c.to}>{c.label}</Link>
                {i < crumbs.length - 1 ? ' / ' : ' /'}
              </span>
            ))}
          </nav>
        )}
        {typeof title === 'string' ? <h1>{title}</h1> : title}
        {sub && <div className="sub">{sub}</div>}
      </div>
      {actions && <div className="page-actions">{actions}</div>}
    </header>
  )
}

export function Card({
  title,
  actions,
  children,
  pad = true,
  className = '',
}: {
  title?: ReactNode
  actions?: ReactNode
  children: ReactNode
  pad?: boolean
  className?: string
}) {
  return (
    <section className={`card ${className}`}>
      {title && (
        <div className="card-head">
          {typeof title === 'string' ? <h2>{title}</h2> : title}
          <div className="spacer" />
          {actions}
        </div>
      )}
      {pad ? <div className="card-body">{children}</div> : children}
    </section>
  )
}

export function KpiCard({
  label,
  value,
  foot,
  tone,
  loading,
}: {
  label: string
  value: ReactNode
  foot?: ReactNode
  tone?: 'accent' | 'danger' | 'warning' | 'success'
  loading?: boolean
}) {
  return (
    <div className={`card kpi ${tone ? `tone-${tone}` : ''}`}>
      <div className="kpi-label">{label}</div>
      {loading ? (
        <Skeleton w="60%" h={28} style={{ marginTop: 6 }} />
      ) : (
        <div className="kpi-value">{value}</div>
      )}
      {foot && <div className="kpi-foot">{foot}</div>}
    </div>
  )
}

/* ---------------- Table ---------------- */
export interface Column<T> {
  key: string
  header: ReactNode
  render: (row: T) => ReactNode
  align?: 'right'
  width?: string | number
}
interface TableProps<T> {
  columns: Column<T>[]
  rows: T[] | null
  loading?: boolean
  rowKey: (r: T) => string | number
  onRowClick?: (r: T) => void
  empty?: ReactNode
  page?: number
  count?: number
  pageSize?: number
  onPage?: (p: number) => void
  selectable?: {
    selected: Set<number>
    onChange: (s: Set<number>) => void
    canSelect: (r: T) => boolean
    id: (r: T) => number
  }
  compact?: boolean
}
export function Table<T>({
  columns,
  rows,
  loading,
  rowKey,
  onRowClick,
  empty,
  page,
  count,
  pageSize = 25,
  onPage,
  selectable,
  compact,
}: TableProps<T>) {
  const totalPages = count != null ? Math.max(1, Math.ceil(count / pageSize)) : 1
  const selRows = selectable && rows ? rows.filter(selectable.canSelect) : []
  const allSel = selectable && selRows.length > 0 && selRows.every((r) => selectable.selected.has(selectable.id(r)))
  const cols = columns.length + (selectable ? 1 : 0)
  return (
    <>
      <div className="table-wrap">
        <table className={`table ${compact ? 'table-compact' : ''}`}>
          <thead>
            <tr>
              {selectable && (
                <th style={{ width: 36 }}>
                  <input
                    type="checkbox"
                    className="check"
                    aria-label="Select all selectable rows"
                    checked={!!allSel}
                    disabled={selRows.length === 0}
                    onChange={(e) => {
                      const s = new Set(selectable.selected)
                      selRows.forEach((r) => (e.target.checked ? s.add(selectable.id(r)) : s.delete(selectable.id(r))))
                      selectable.onChange(s)
                    }}
                  />
                </th>
              )}
              {columns.map((c) => (
                <th key={c.key} className={c.align === 'right' ? 'th-right' : ''} style={{ width: c.width }}>
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {loading || rows === null ? (
              <SkeletonRows cols={cols} />
            ) : rows.length === 0 ? (
              <tr>
                <td colSpan={cols}>{empty ?? <EmptyState title="Nothing here yet" />}</td>
              </tr>
            ) : (
              rows.map((r) => (
                <tr
                  key={rowKey(r)}
                  className={onRowClick ? 'clickable' : ''}
                  tabIndex={onRowClick ? 0 : undefined}
                  onClick={onRowClick ? () => onRowClick(r) : undefined}
                  onKeyDown={
                    onRowClick
                      ? (e) => {
                          if (e.key === 'Enter') onRowClick(r)
                        }
                      : undefined
                  }
                >
                  {selectable && (
                    <td onClick={(e) => e.stopPropagation()}>
                      {selectable.canSelect(r) && (
                        <input
                          type="checkbox"
                          className="check"
                          aria-label="Select row"
                          checked={selectable.selected.has(selectable.id(r))}
                          onChange={(e) => {
                            const s = new Set(selectable.selected)
                            if (e.target.checked) s.add(selectable.id(r))
                            else s.delete(selectable.id(r))
                            selectable.onChange(s)
                          }}
                        />
                      )}
                    </td>
                  )}
                  {columns.map((c) => (
                    <td key={c.key} className={c.align === 'right' ? 'right num' : ''}>
                      {c.render(r)}
                    </td>
                  ))}
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>
      {onPage && page != null && count != null && count > 0 && (
        <div className="pager">
          <span>
            {(page - 1) * pageSize + 1}–{Math.min(page * pageSize, count)} of {count}
          </span>
          <div className="spacer" />
          <Button
            size="sm"
            iconOnly
            icon={<Icon.chevronLeft />}
            aria-label="Previous page"
            disabled={page <= 1}
            onClick={() => onPage(page - 1)}
          />
          <span>
            Page {page} of {totalPages}
          </span>
          <Button
            size="sm"
            iconOnly
            icon={<Icon.chevronRight />}
            aria-label="Next page"
            disabled={page >= totalPages}
            onClick={() => onPage(page + 1)}
          />
        </div>
      )}
    </>
  )
}

/* ---------------- Overlays ---------------- */
function useOverlay(open: boolean, onClose: () => void) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const prev = document.activeElement as HTMLElement | null
    const node = ref.current
    const first = node?.querySelector<HTMLElement>(
      'input:not([disabled]), select, textarea, button:not([disabled]), [tabindex]:not([tabindex="-1"])',
    )
    first?.focus()
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
      if (e.key === 'Tab' && node) {
        const f = Array.from(
          node.querySelectorAll<HTMLElement>(
            'a[href], button:not([disabled]), input:not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])',
          ),
        )
        if (!f.length) return
        const a = f[0]
        const z = f[f.length - 1]
        if (e.shiftKey && document.activeElement === a) {
          e.preventDefault()
          z.focus()
        } else if (!e.shiftKey && document.activeElement === z) {
          e.preventDefault()
          a.focus()
        }
      }
    }
    document.addEventListener('keydown', onKey)
    document.body.style.overflow = 'hidden'
    return () => {
      document.removeEventListener('keydown', onKey)
      document.body.style.overflow = ''
      prev?.focus?.()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])
  return ref
}

interface OverlayProps {
  open: boolean
  onClose: () => void
  title: ReactNode
  children: ReactNode
  footer?: ReactNode
  wide?: boolean
}
export function Modal({ open, onClose, title, children, footer, wide }: OverlayProps) {
  const ref = useOverlay(open, onClose)
  const hid = useId()
  if (!open) return null
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} className={`modal ${wide ? 'wide' : ''}`} role="dialog" aria-modal="true" aria-labelledby={hid}>
        <div className="ov-head">
          <h2 id={hid}>{title}</h2>
          <div className="spacer" />
          <Button variant="ghost" size="sm" iconOnly icon={<Icon.x />} aria-label="Close" onClick={onClose} />
        </div>
        <div className="ov-body">{children}</div>
        {footer && <div className="ov-foot">{footer}</div>}
      </div>
    </div>
  )
}
export function Drawer({ open, onClose, title, children, footer, wide }: OverlayProps) {
  const ref = useOverlay(open, onClose)
  const hid = useId()
  if (!open) return null
  return (
    <div className="overlay" onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div ref={ref} className={`drawer ${wide ? 'wide' : ''}`} role="dialog" aria-modal="true" aria-labelledby={hid}>
        <div className="ov-head">
          <h2 id={hid}>{title}</h2>
          <div className="spacer" />
          <Button variant="ghost" size="sm" iconOnly icon={<Icon.x />} aria-label="Close" onClick={onClose} />
        </div>
        <div className="ov-body">{children}</div>
        {footer && <div className="ov-foot">{footer}</div>}
      </div>
    </div>
  )
}

export function ConfirmDialog({
  open,
  title,
  body,
  confirmLabel = 'Confirm',
  danger,
  onConfirm,
  onClose,
  withNote,
}: {
  open: boolean
  title: string
  body?: ReactNode
  confirmLabel?: string
  danger?: boolean
  onConfirm: (note: string) => Promise<void> | void
  onClose: () => void
  withNote?: boolean
}) {
  const [busy, setBusy] = useState(false)
  const [note, setNote] = useState('')
  useEffect(() => {
    if (open) setNote('')
  }, [open])
  return (
    <Modal
      open={open}
      onClose={() => !busy && onClose()}
      title={title}
      footer={
        <>
          <Button onClick={onClose} disabled={busy}>
            Cancel
          </Button>
          <Button
            variant={danger ? 'danger-solid' : 'primary'}
            loading={busy}
            onClick={async () => {
              setBusy(true)
              try {
                await onConfirm(note)
              } finally {
                setBusy(false)
              }
            }}
          >
            {confirmLabel}
          </Button>
        </>
      }
    >
      <div className="stack">
        {body && <div style={{ color: 'var(--text-2)' }}>{body}</div>}
        {withNote && (
          <Field label="Note (optional)">
            {(id) => <Textarea id={id} value={note} onChange={(e) => setNote(e.target.value)} rows={2} />}
          </Field>
        )}
      </div>
    </Modal>
  )
}

export function ErrorBanner({ error, onRetry }: { error: string | null; onRetry?: () => void }) {
  if (!error) return null
  return (
    <div className="alert alert-error row" role="alert" style={{ marginBottom: 16 }}>
      <span>{error}</span>
      <div className="spacer" />
      {onRetry && (
        <Button size="sm" onClick={onRetry}>
          Retry
        </Button>
      )}
    </div>
  )
}
