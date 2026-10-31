import { Fragment } from 'react'
import { Icon } from '../components/icons'
import { Button, Field, Input, Select, Textarea } from '../components/ui'
import { money, num, periodLabel } from '../format'
import { useLookup } from '../hooks'
import type { Customer, PaymentTerm, Plan, Product, SubAction, SubLine, SubStatus, Variant } from '../types'
import { ProductVariantPicker } from './Catalog'

export const DEFAULT_TERMS: PaymentTerm[] = [
  { days: 0, label: 'Immediate' },
  { days: 15, label: 'Net 15' },
  { days: 30, label: 'Net 30' },
  { days: 45, label: 'Net 45' },
]

export function usePaymentTerms() {
  const t = useLookup<PaymentTerm>('/payment-terms')
  return t.length ? t : DEFAULT_TERMS
}

export const actionMeta: Record<
  SubAction,
  { label: string; portalLabel?: string; variant: 'primary' | 'accent' | 'default' | 'danger'; confirm?: string }
> = {
  send_quotation: { label: 'Send quotation', variant: 'primary' },
  confirm: { label: 'Confirm', portalLabel: 'Accept quotation', variant: 'primary' },
  activate: { label: 'Activate', variant: 'accent' },
  pause: { label: 'Pause', variant: 'default', confirm: 'Paused subscriptions are not billed until resumed.' },
  resume: { label: 'Resume', variant: 'accent' },
  close: {
    label: 'Close',
    variant: 'danger',
    confirm: 'Closing ends the subscription. No further invoices will be created.',
  },
  renew: { label: 'Renew', variant: 'default', confirm: 'Renewing creates a new subscription for the next term.' },
}

/* Lifecycle stepper: draft → quotation → confirmed → active → closed, paused branches off active. */
const MAIN: SubStatus[] = ['draft', 'quotation', 'confirmed', 'active', 'closed']
export function Lifecycle({ status }: { status: SubStatus }) {
  const effective = status === 'paused' ? 'active' : status
  const idx = MAIN.indexOf(effective)
  return (
    <div className="lifecycle" aria-label={`Lifecycle: currently ${status}`}>
      {MAIN.map((s, i) => {
        const state = i < idx ? 'done' : i === idx ? 'current' : ''
        const isPausedHere = status === 'paused' && s === 'active'
        return (
          <Fragment key={s}>
            {i > 0 && <div className={`lc-bar ${i <= idx ? 'done' : ''}`} />}
            <div
              className={`lc-step ${state} ${isPausedHere ? 'alt' : ''}`}
              aria-current={state === 'current' ? 'step' : undefined}
            >
              <span className="lc-dot" />
              {isPausedHere ? 'Paused' : s[0].toUpperCase() + s.slice(1)}
            </div>
          </Fragment>
        )
      })}
    </div>
  )
}

export function variantPrice(p?: Product, v?: Variant): string {
  if (!p) return '0.00'
  if (v?.price) return v.price
  return (num(p.sales_price) + num(v?.price_extra)).toFixed(2)
}

export function LinesEditor({
  lines,
  onChange,
  readOnly,
  error,
}: {
  lines: SubLine[]
  onChange: (l: SubLine[]) => void
  readOnly?: boolean
  error?: string
}) {
  const products = useLookup<Product>('/products')
  const upd = (i: number, patch: Partial<SubLine>) => onChange(lines.map((l, j) => (j === i ? { ...l, ...patch } : l)))
  const total = lines.reduce((s, l) => s + num(l.quantity) * num(l.unit_price), 0)
  return (
    <div>
      {error && (
        <div className="alert alert-error" style={{ margin: '0 0 12px' }}>
          {error}
        </div>
      )}
      <div className="table-wrap">
        <table className="table lines-editor">
          <thead>
            <tr>
              <th>Product</th>
              <th>Description</th>
              <th className="th-right">Qty</th>
              <th className="th-right">Unit price</th>
              <th className="th-right">Subtotal</th>
              {!readOnly && <th style={{ width: 40 }} />}
            </tr>
          </thead>
          <tbody>
            {lines.length === 0 && (
              <tr>
                <td colSpan={6} className="muted" style={{ textAlign: 'center', padding: 24 }}>
                  No lines yet.{!readOnly && ' Add a product to price this subscription.'}
                </td>
              </tr>
            )}
            {lines.map((l, i) =>
              readOnly ? (
                <tr key={l.id ?? i}>
                  <td>
                    <strong>{l.product_name}</strong>
                    {l.variant_label && <div className="muted">{l.variant_label}</div>}
                  </td>
                  <td>{l.description || '—'}</td>
                  <td className="right num">{num(l.quantity)}</td>
                  <td className="right num">{money(l.unit_price)}</td>
                  <td className="right num">{money(l.subtotal ?? num(l.quantity) * num(l.unit_price))}</td>
                </tr>
              ) : (
                <tr key={l.id ?? `n${i}`}>
                  <td style={{ minWidth: 200 }}>
                    <ProductVariantPicker
                      products={products}
                      product={l.product}
                      variant={l.variant}
                      onChange={(product, variant, p, v) =>
                        upd(i, {
                          product,
                          variant,
                          unit_price: variantPrice(p, v),
                          tax_group: p?.tax_group ?? null,
                          product_name: p?.name,
                          description: p ? `${p.name}${v ? ` (${v.attribute}: ${v.value})` : ''}` : '',
                        })
                      }
                    />
                  </td>
                  <td style={{ minWidth: 160 }}>
                    <Input aria-label="Description" value={l.description} onChange={(e) => upd(i, { description: e.target.value })} />
                  </td>
                  <td className="right">
                    <Input
                      aria-label="Quantity"
                      className="qty"
                      type="number"
                      min="1"
                      value={l.quantity}
                      onChange={(e) => upd(i, { quantity: e.target.value })}
                    />
                  </td>
                  <td className="right">
                    <Input
                      aria-label="Unit price"
                      className="price"
                      type="number"
                      step="0.01"
                      min="0"
                      value={l.unit_price}
                      onChange={(e) => upd(i, { unit_price: e.target.value })}
                    />
                  </td>
                  <td className="right num" style={{ verticalAlign: 'middle' }}>
                    {money(num(l.quantity) * num(l.unit_price))}
                  </td>
                  <td>
                    <Button
                      size="sm"
                      variant="ghost"
                      iconOnly
                      icon={<Icon.trash />}
                      aria-label="Remove line"
                      onClick={() => onChange(lines.filter((_, j) => j !== i))}
                    />
                  </td>
                </tr>
              ),
            )}
          </tbody>
          {lines.length > 0 && (
            <tfoot>
              <tr>
                <td colSpan={4} className="right">
                  Recurring subtotal (before tax)
                </td>
                <td className="right num">{money(total)}</td>
                {!readOnly && <td />}
              </tr>
            </tfoot>
          )}
        </table>
      </div>
      {!readOnly && (
        <div style={{ padding: '12px 16px' }}>
          <Button
            size="sm"
            icon={<Icon.plus />}
            onClick={() =>
              onChange([
                ...lines,
                { product: null, variant: null, description: '', quantity: 1, unit_price: '0.00', tax_group: null },
              ])
            }
          >
            Add line
          </Button>
        </div>
      )}
    </div>
  )
}

export interface SubHeaderDraft {
  customer: number | null
  plan: number | null
  start_date: string | null
  expiry_date: string | null
  payment_term_days: number
  notes: string
}

export function SubHeaderForm({
  d,
  set,
  errors,
}: {
  d: SubHeaderDraft
  set: (patch: Partial<SubHeaderDraft>) => void
  errors: Record<string, string[]>
}) {
  const customers = useLookup<Customer>('/customers')
  const plans = useLookup<Plan>('/plans')
  const terms = usePaymentTerms()
  return (
    <div className="grid-2">
      <Field label="Customer" required error={errors.customer}>
        {(id) => (
          <Select
            id={id}
            options={customers.map((c) => ({ value: c.id, label: `${c.name}${c.email ? ` · ${c.email}` : ''}` }))}
            placeholder="Choose customer…"
            value={d.customer ?? ''}
            onChange={(e) => set({ customer: e.target.value ? Number(e.target.value) : null })}
          />
        )}
      </Field>
      <Field label="Plan" required error={errors.plan}>
        {(id) => (
          <Select
            id={id}
            options={plans
              .filter((p) => p.is_available !== false || p.id === d.plan)
              .map((p) => ({ value: p.id, label: `${p.name} · ${periodLabel[p.billing_period]} · ${money(p.price)}` }))}
            placeholder="Choose plan…"
            value={d.plan ?? ''}
            onChange={(e) => set({ plan: e.target.value ? Number(e.target.value) : null })}
          />
        )}
      </Field>
      <Field label="Start date" error={errors.start_date}>
        {(id) => <Input id={id} type="date" value={d.start_date ?? ''} onChange={(e) => set({ start_date: e.target.value || null })} />}
      </Field>
      <Field label="Expiry date" hint="Leave empty for no end date." error={errors.expiry_date}>
        {(id) => (
          <Input id={id} type="date" value={d.expiry_date ?? ''} onChange={(e) => set({ expiry_date: e.target.value || null })} />
        )}
      </Field>
      <Field label="Payment terms" error={errors.payment_term_days}>
        {(id) => (
          <Select
            id={id}
            options={terms.map((t) => ({ value: t.days, label: t.label }))}
            value={d.payment_term_days}
            onChange={(e) => set({ payment_term_days: Number(e.target.value) })}
          />
        )}
      </Field>
      <Field label="Notes" className="span-2" error={errors.notes}>
        {(id) => <Textarea id={id} rows={2} value={d.notes} onChange={(e) => set({ notes: e.target.value })} />}
      </Field>
    </div>
  )
}

export function linesPayload(lines: SubLine[]) {
  return lines.map((l) => ({
    ...(l.id ? { id: l.id } : {}),
    product: l.product,
    variant: l.variant,
    description: l.description,
    quantity: l.quantity,
    unit_price: l.unit_price,
    tax_group: l.tax_group,
  }))
}

export function linesError(lines: SubLine[]): string | undefined {
  if (lines.some((l) => !l.product)) return 'Each line needs a product.'
  if (lines.some((l) => num(l.quantity) <= 0)) return 'Quantities must be greater than zero.'
  return undefined
}
