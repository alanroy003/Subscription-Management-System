/* eslint-disable @typescript-eslint/no-explicit-any */
import { useAuth } from '../auth'
import { CrudPage, type Draft } from '../components/Crud'
import { Icon } from '../components/icons'
import { Button, Input, Select, StatusPill, type Option } from '../components/ui'
import { date, money, num, periodLabel, titleCase } from '../format'
import { useLookup } from '../hooks'
import type { Customer, Discount, Plan, Product, QuotationTemplate, StaffUser, TaxGroup, TemplateLine, Variant } from '../types'

const yesNo = (b: boolean) => (b ? <span className="badge badge-accent">Yes</span> : <span className="badge">No</span>)
const activeBadge = (b: boolean) =>
  b ? <span className="pill pill-active">Active</span> : <span className="pill pill-closed">Archived</span>

/* ---------------- Customers ---------------- */
export function CustomersPage() {
  const { isStaff } = useAuth()
  return (
    <CrudPage<Customer>
      title="Customers"
      singular="Customer"
      sub="People and companies you bill."
      path="/customers"
      icon={<Icon.users />}
      canWrite={isStaff}
      searchPlaceholder="Search by name or email"
      emptyBody="Add a customer, or they can sign up from the portal."
      invalidates={['/customers']}
      columns={[
        { key: 'name', header: 'Name', render: (r) => <strong>{r.name}</strong> },
        { key: 'email', header: 'Email', render: (r) => r.email || '—' },
        { key: 'phone', header: 'Phone', render: (r) => r.phone || '—' },
        { key: 'state', header: 'State', render: (r) => r.state || '—' },
        { key: 'gstin', header: 'GSTIN', render: (r) => (r.gstin ? <span className="mono">{r.gstin}</span> : '—') },
        { key: 'login', header: 'Portal', render: (r) => yesNo(!!r.has_login) },
      ]}
      defaults={{ name: '', email: '', phone: '', address: '', state: '', gstin: '' }}
      fields={[
        { name: 'name', label: 'Name', required: true, span: 2 },
        { name: 'email', label: 'Email', type: 'email', required: true },
        { name: 'phone', label: 'Phone' },
        { name: 'address', label: 'Address', type: 'textarea' },
        { name: 'state', label: 'State', hint: 'Used to choose CGST+SGST or IGST.' },
        { name: 'gstin', label: 'GSTIN', placeholder: '27ABCDE1234F1Z5' },
      ]}
    />
  )
}

/* ---------------- Tax groups ---------------- */
export function TaxGroupsPage() {
  const { isAdmin } = useAuth()
  return (
    <CrudPage<TaxGroup>
      title="Tax groups"
      singular="Tax group"
      sub="GST splits into CGST and SGST within the company state, IGST otherwise."
      path="/tax-groups"
      icon={<Icon.percent />}
      canWrite={isAdmin}
      invalidates={['/tax-groups']}
      columns={[
        { key: 'name', header: 'Name', render: (r) => <strong>{r.name}</strong> },
        { key: 'rate', header: 'Rate', align: 'right', render: (r) => `${num(r.rate)}%` },
        { key: 'mode', header: 'Mode', render: (r) => (r.mode === 'gst' ? 'GST (split)' : 'Simple') },
        { key: 'active', header: 'Status', render: (r) => activeBadge(r.is_active) },
      ]}
      defaults={{ name: '', rate: '18.00', mode: 'gst', is_active: true }}
      fields={[
        { name: 'name', label: 'Name', required: true, span: 2, placeholder: 'GST 18%' },
        { name: 'rate', label: 'Rate (%)', type: 'money', required: true },
        {
          name: 'mode',
          label: 'Mode',
          type: 'select',
          required: true,
          options: [
            { value: 'gst', label: 'GST (CGST+SGST / IGST)' },
            { value: 'simple', label: 'Simple' },
          ],
        },
        { name: 'is_active', label: 'Active', type: 'toggle' },
      ]}
    />
  )
}

/* ---------------- Products ---------------- */
function VariantsEditor({
  draft,
  setDraft,
  readOnly,
}: {
  draft: Draft
  setDraft: (d: Draft) => void
  readOnly: boolean
}) {
  const variants: Variant[] = draft.variants ?? []
  const upd = (i: number, patch: Partial<Variant>) =>
    setDraft({ ...draft, variants: variants.map((v, j) => (j === i ? { ...v, ...patch } : v)) })
  return (
    <div>
      <div className="row" style={{ marginBottom: 8 }}>
        <div className="section-title" style={{ margin: 0 }}>
          Variants
        </div>
        <div className="spacer" />
        {!readOnly && (
          <Button
            size="sm"
            icon={<Icon.plus />}
            onClick={() => setDraft({ ...draft, variants: [...variants, { attribute: '', value: '', price_extra: '0.00' }] })}
          >
            Add variant
          </Button>
        )}
      </div>
      {variants.length === 0 ? (
        <p className="muted" style={{ margin: 0 }}>
          No variants. Add one for options such as edition or brand, each with an extra price.
        </p>
      ) : (
        <div className="card" style={{ overflow: 'hidden' }}>
          <table className="table table-compact lines-editor">
            <thead>
              <tr>
                <th>Attribute</th>
                <th>Value</th>
                <th className="th-right">Extra price</th>
                <th className="th-right">Price</th>
                {!readOnly && <th />}
              </tr>
            </thead>
            <tbody>
              {variants.map((v, i) => (
                <tr key={v.id ?? `n${i}`}>
                  <td>
                    <Input
                      aria-label="Attribute"
                      placeholder="Brand"
                      value={v.attribute}
                      disabled={readOnly}
                      onChange={(e) => upd(i, { attribute: e.target.value })}
                    />
                  </td>
                  <td>
                    <Input
                      aria-label="Value"
                      placeholder="Odoo"
                      value={v.value}
                      disabled={readOnly}
                      onChange={(e) => upd(i, { value: e.target.value })}
                    />
                  </td>
                  <td>
                    <Input
                      aria-label="Extra price"
                      type="number"
                      step="0.01"
                      className="price"
                      value={v.price_extra}
                      disabled={readOnly}
                      onChange={(e) => upd(i, { price_extra: e.target.value })}
                    />
                  </td>
                  <td className="right num" style={{ verticalAlign: 'middle' }}>
                    {money(num(draft.sales_price) + num(v.price_extra))}
                  </td>
                  {!readOnly && (
                    <td>
                      <Button
                        size="sm"
                        variant="ghost"
                        iconOnly
                        icon={<Icon.trash />}
                        aria-label="Remove variant"
                        onClick={() => setDraft({ ...draft, variants: variants.filter((_, j) => j !== i) })}
                      />
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export function ProductsPage() {
  const { isAdmin, isStaff } = useAuth()
  const taxes = useLookup<TaxGroup>('/tax-groups', isStaff)
  return (
    <CrudPage<Product>
      title="Products"
      singular="Product"
      sub="What you sell on subscription, with optional variants."
      path="/products"
      icon={<Icon.box />}
      canWrite={isAdmin}
      wide
      invalidates={['/products']}
      columns={[
        { key: 'name', header: 'Name', render: (r) => <strong>{r.name}</strong> },
        { key: 'type', header: 'Type', render: (r) => titleCase(r.type) },
        { key: 'price', header: 'Sales price', align: 'right', render: (r) => money(r.sales_price) },
        { key: 'cost', header: 'Cost', align: 'right', render: (r) => money(r.cost_price) },
        { key: 'tax', header: 'Tax', render: (r) => r.tax_group_name || '—' },
        { key: 'var', header: 'Variants', align: 'right', render: (r) => r.variants?.length ?? 0 },
        { key: 'active', header: 'Status', render: (r) => activeBadge(r.is_active) },
      ]}
      defaults={{
        name: '',
        type: 'service',
        sales_price: '',
        cost_price: '0.00',
        notes: '',
        tax_group: null,
        is_active: true,
        variants: [],
      }}
      fields={[
        { name: 'name', label: 'Name', required: true, span: 2 },
        {
          name: 'type',
          label: 'Type',
          type: 'select',
          required: true,
          options: [
            { value: 'service', label: 'Service' },
            { value: 'software', label: 'Software' },
            { value: 'goods', label: 'Goods' },
          ],
        },
        {
          name: 'tax_group',
          label: 'Tax group',
          type: 'select',
          placeholder: 'No tax',
          options: taxes.map((t) => ({ value: t.id, label: t.name })),
        },
        { name: 'sales_price', label: 'Sales price (₹)', type: 'money', required: true },
        { name: 'cost_price', label: 'Cost price (₹)', type: 'money' },
        { name: 'notes', label: 'Notes', type: 'textarea' },
        { name: 'is_active', label: 'Active', type: 'toggle' },
      ]}
      toPayload={(d) => ({
        ...d,
        variants: (d.variants ?? []).map((v: Variant) => ({
          ...(v.id ? { id: v.id } : {}),
          attribute: v.attribute,
          value: v.value,
          price_extra: v.price_extra || '0',
        })),
      })}
      extra={(d, setD, _e, ro) => <VariantsEditor draft={d} setDraft={setD} readOnly={ro} />}
    />
  )
}

/* ---------------- Plans ---------------- */
export function PlansPage() {
  const { isAdmin, isStaff } = useAuth()
  const products = useLookup<Product>('/products', isStaff)
  return (
    <CrudPage<Plan>
      title="Plans"
      singular="Plan"
      sub="Billing period, price and what customers may do with their subscription."
      path="/plans"
      icon={<Icon.calendar />}
      canWrite={isAdmin}
      invalidates={['/plans']}
      columns={[
        { key: 'name', header: 'Name', render: (r) => <strong>{r.name}</strong> },
        { key: 'product', header: 'Product', render: (r) => r.product_name || '—' },
        { key: 'period', header: 'Period', render: (r) => periodLabel[r.billing_period] },
        { key: 'price', header: 'Price', align: 'right', render: (r) => money(r.price) },
        { key: 'minq', header: 'Min qty', align: 'right', render: (r) => r.min_quantity },
        {
          key: 'window',
          header: 'Available',
          render: (r) =>
            r.available_from || r.available_to ? `${date(r.available_from)} – ${date(r.available_to)}` : 'Always',
        },
        {
          key: 'opts',
          header: 'Options',
          render: (r) => (
            <span className="row wrap" style={{ gap: 4 }}>
              {r.auto_close && <span className="badge">Auto-close</span>}
              {r.closable && <span className="badge">Closable</span>}
              {r.pausable && <span className="badge">Pausable</span>}
              {r.renewable && <span className="badge">Renewable</span>}
              {r.is_trial && <span className="badge">Free trial · {r.trial_days} days</span>}
            </span>
          ),
        },
        {
          key: 'avail',
          header: 'Status',
          render: (r) =>
            r.is_available === false ? <span className="pill pill-closed">Unavailable</span> : <span className="pill pill-active">Available</span>,
        },
      ]}
      defaults={{
        name: '',
        product: null,
        price: '',
        billing_period: 'monthly',
        min_quantity: 1,
        available_from: null,
        available_to: null,
        auto_close: false,
        closable: true,
        pausable: true,
        renewable: true,
        is_trial: false,
        trial_days: 30,
      }}
      fields={[
        { name: 'name', label: 'Name', required: true, span: 2, placeholder: 'Monthly Standard' },
        {
          name: 'product',
          label: 'Product',
          type: 'select',
          placeholder: 'Any product',
          options: products.map((p) => ({ value: p.id, label: p.name })),
        },
        {
          name: 'billing_period',
          label: 'Billing period',
          type: 'select',
          required: true,
          options: Object.entries(periodLabel).map(([value, label]) => ({ value, label })),
        },
        { name: 'price', label: 'Price (₹)', type: 'money', required: true },
        { name: 'min_quantity', label: 'Minimum quantity', type: 'number', required: true },
        { name: 'available_from', label: 'Available from', type: 'date' },
        { name: 'available_to', label: 'Available to', type: 'date' },
        { name: 'auto_close', label: 'Close automatically at expiry', type: 'toggle' },
        { name: 'closable', label: 'Customer can close', type: 'toggle' },
        { name: 'pausable', label: 'Customer can pause', type: 'toggle' },
        { name: 'renewable', label: 'Customer can renew', type: 'toggle' },
        { name: 'is_trial', label: 'Free trial plan (price 0, one per customer)', type: 'toggle' },
        { name: 'trial_days', label: 'Trial length (days)', type: 'number' },
      ]}
      validate={(d): Record<string, string[]> =>
        d.available_from && d.available_to && d.available_to < d.available_from
          ? { available_to: ['Must be on or after the start date.'] }
          : {}
      }
    />
  )
}

/* ---------------- Discounts ---------------- */
export function DiscountsPage() {
  const { isAdmin, isStaff } = useAuth()
  const products = useLookup<Product>('/products', isStaff)
  const pname = (id: number) => products.find((p) => p.id === id)?.name ?? `#${id}`
  return (
    <CrudPage<Discount>
      title="Discounts"
      singular="Discount"
      sub="The best eligible discount applies per invoice line, before tax."
      path="/discounts"
      icon={<Icon.tag />}
      canWrite={isAdmin}
      columns={[
        { key: 'name', header: 'Name', render: (r) => <strong>{r.name}</strong> },
        {
          key: 'value',
          header: 'Value',
          align: 'right',
          render: (r) => (r.kind === 'percent' ? `${num(r.value)}%` : money(r.value)),
        },
        {
          key: 'cond',
          header: 'Conditions',
          render: (r) =>
            [
              num(r.min_amount) > 0 && `Subtotal ≥ ${money(r.min_amount)}`,
              (r.min_quantity ?? 0) > 1 && `Qty ≥ ${r.min_quantity}`,
            ]
              .filter(Boolean)
              .join(' · ') || 'None',
        },
        {
          key: 'dates',
          header: 'Valid',
          render: (r) => (r.start_date || r.end_date ? `${date(r.start_date)} – ${date(r.end_date)}` : 'Always'),
        },
        {
          key: 'usage',
          header: 'Used',
          align: 'right',
          render: (r) => `${r.used_count ?? 0}${r.usage_limit != null ? ` / ${r.usage_limit}` : ''}`,
        },
        {
          key: 'scope',
          header: 'Applies to',
          render: (r) => (r.scope === 'all' ? 'All products' : r.products.map(pname).join(', ') || 'No products'),
        },
        { key: 'active', header: 'Status', render: (r) => activeBadge(r.is_active) },
      ]}
      defaults={{
        name: '',
        kind: 'percent',
        value: '',
        min_amount: null,
        min_quantity: null,
        start_date: null,
        end_date: null,
        usage_limit: null,
        scope: 'all',
        products: [],
        is_active: true,
      }}
      fields={[
        { name: 'name', label: 'Name', required: true, span: 2 },
        {
          name: 'kind',
          label: 'Type',
          type: 'select',
          required: true,
          options: [
            { value: 'percent', label: 'Percentage' },
            { value: 'fixed', label: 'Fixed amount' },
          ],
        },
        { name: 'value', label: 'Value', type: 'money', required: true, hint: 'Percent (0–100) or rupees.' },
        { name: 'min_amount', label: 'Minimum invoice subtotal (₹)', type: 'money' },
        { name: 'min_quantity', label: 'Minimum line quantity', type: 'number' },
        { name: 'start_date', label: 'Start date', type: 'date' },
        { name: 'end_date', label: 'End date', type: 'date' },
        { name: 'usage_limit', label: 'Usage limit', type: 'number', hint: 'Leave empty for unlimited.' },
        {
          name: 'scope',
          label: 'Applies to',
          type: 'select',
          required: true,
          options: [
            { value: 'all', label: 'All products' },
            { value: 'products', label: 'Selected products' },
          ],
        },
        {
          name: 'products',
          label: 'Products',
          type: 'multiselect',
          options: products.map((p) => ({ value: p.id, label: p.name })),
          when: (d) => d.scope === 'products',
        },
        { name: 'is_active', label: 'Active', type: 'toggle' },
      ]}
      validate={(d): Record<string, string[]> => {
        const e: Record<string, string[]> = {}
        if (d.kind === 'percent' && num(d.value) > 100) e.value = ['A percentage cannot exceed 100.']
        if (d.start_date && d.end_date && d.end_date < d.start_date) e.end_date = ['Must be on or after the start date.']
        if (d.scope === 'products' && !(d.products ?? []).length) e.products = ['Choose at least one product.']
        return e
      }}
      toPayload={(d) => ({ ...d, products: d.scope === 'products' ? d.products : [] })}
    />
  )
}

/* ---------------- Quotation templates ---------------- */
export function ProductVariantPicker({
  products,
  product,
  variant,
  onChange,
  disabled,
}: {
  products: Product[]
  product: number | null
  variant: number | null
  onChange: (product: number | null, variant: number | null, p?: Product, v?: Variant) => void
  disabled?: boolean
}) {
  const p = products.find((x) => x.id === product)
  const vopts: Option[] = (p?.variants ?? []).map((v) => ({
    value: v.id!,
    label: `${v.attribute}: ${v.value}${num(v.price_extra) ? ` (+${money(v.price_extra)})` : ''}`,
  }))
  return (
    <div className="stack" style={{ gap: 6 }}>
      <Select
        aria-label="Product"
        disabled={disabled}
        options={products.map((x) => ({ value: x.id, label: x.name }))}
        placeholder="Choose product…"
        value={product ?? ''}
        onChange={(e) => {
          const np = products.find((x) => String(x.id) === e.target.value)
          onChange(np?.id ?? null, null, np)
        }}
      />
      {vopts.length > 0 && (
        <Select
          aria-label="Variant"
          disabled={disabled}
          options={vopts}
          placeholder="No variant"
          value={variant ?? ''}
          onChange={(e) => {
            const nv = p?.variants.find((x) => String(x.id) === e.target.value)
            onChange(product, nv?.id ?? null, p, nv)
          }}
        />
      )}
    </div>
  )
}

function TemplateLinesEditor({
  draft,
  setDraft,
  readOnly,
  products,
}: {
  draft: Draft
  setDraft: (d: Draft) => void
  readOnly: boolean
  products: Product[]
}) {
  const lines: TemplateLine[] = draft.lines ?? []
  const upd = (i: number, patch: Partial<TemplateLine>) =>
    setDraft({ ...draft, lines: lines.map((l, j) => (j === i ? { ...l, ...patch } : l)) })
  return (
    <div>
      <div className="row" style={{ marginBottom: 8 }}>
        <div className="section-title" style={{ margin: 0 }}>
          Lines
        </div>
        <div className="spacer" />
        {!readOnly && (
          <Button
            size="sm"
            icon={<Icon.plus />}
            onClick={() => setDraft({ ...draft, lines: [...lines, { product: null, variant: null, quantity: 1 }] })}
          >
            Add line
          </Button>
        )}
      </div>
      {lines.length === 0 ? (
        <p className="muted" style={{ margin: 0 }}>
          Add the products this quotation should include.
        </p>
      ) : (
        <div className="card">
          <table className="table table-compact lines-editor">
            <thead>
              <tr>
                <th>Product / variant</th>
                <th className="th-right">Quantity</th>
                {!readOnly && <th />}
              </tr>
            </thead>
            <tbody>
              {lines.map((l, i) => (
                <tr key={l.id ?? `n${i}`}>
                  <td>
                    <ProductVariantPicker
                      products={products}
                      product={l.product}
                      variant={l.variant}
                      disabled={readOnly}
                      onChange={(product, variant) => upd(i, { product, variant })}
                    />
                  </td>
                  <td className="right">
                    <Input
                      aria-label="Quantity"
                      type="number"
                      min="1"
                      className="qty"
                      value={l.quantity}
                      disabled={readOnly}
                      onChange={(e) => upd(i, { quantity: e.target.value })}
                    />
                  </td>
                  {!readOnly && (
                    <td>
                      <Button
                        size="sm"
                        variant="ghost"
                        iconOnly
                        icon={<Icon.trash />}
                        aria-label="Remove line"
                        onClick={() => setDraft({ ...draft, lines: lines.filter((_, j) => j !== i) })}
                      />
                    </td>
                  )}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

export function TemplatesPage() {
  const { isStaff } = useAuth()
  const plans = useLookup<Plan>('/plans', isStaff)
  const products = useLookup<Product>('/products', isStaff)
  return (
    <CrudPage<QuotationTemplate>
      title="Quotation templates"
      singular="Template"
      sub="Reusable starting points for new quotations."
      path="/quotation-templates"
      icon={<Icon.template />}
      canWrite={isStaff}
      wide
      invalidates={['/quotation-templates']}
      columns={[
        { key: 'name', header: 'Name', render: (r) => <strong>{r.name}</strong> },
        { key: 'plan', header: 'Plan', render: (r) => r.plan_name || '—' },
        { key: 'valid', header: 'Valid for', align: 'right', render: (r) => `${r.validity_days} days` },
        { key: 'lines', header: 'Lines', align: 'right', render: (r) => r.lines?.length ?? 0 },
      ]}
      defaults={{ name: '', plan: null, validity_days: 30, notes: '', lines: [] }}
      fields={[
        { name: 'name', label: 'Name', required: true, span: 2 },
        {
          name: 'plan',
          label: 'Plan',
          type: 'select',
          required: true,
          options: plans.map((p) => ({ value: p.id, label: `${p.name} · ${periodLabel[p.billing_period]}` })),
        },
        { name: 'validity_days', label: 'Quotation valid for (days)', type: 'number', required: true },
        { name: 'notes', label: 'Notes', type: 'textarea' },
      ]}
      validate={(d): Record<string, string[]> => {
        const lines: TemplateLine[] = d.lines ?? []
        if (lines.some((l) => !l.product)) return { lines: ['Each line needs a product.'] }
        return {}
      }}
      toPayload={(d) => ({
        name: d.name,
        plan: d.plan,
        validity_days: d.validity_days,
        notes: d.notes,
        lines: (d.lines ?? []).map((l: TemplateLine) => ({
          ...(l.id ? { id: l.id } : {}),
          product: l.product,
          variant: l.variant,
          quantity: l.quantity,
        })),
      })}
      extra={(d, setD, errs, ro) => (
        <>
          {errs.lines && <div className="alert alert-error">{errs.lines.join(' ')}</div>}
          <TemplateLinesEditor draft={d} setDraft={setD} readOnly={ro} products={products} />
        </>
      )}
    />
  )
}

/* ---------------- Users (admin) ---------------- */
export function UsersPage() {
  return (
    <CrudPage<StaffUser>
      title="Users"
      singular="User"
      sub="Staff and admins who can sign in to the console."
      path="/users"
      icon={<Icon.shield />}
      canWrite
      canDelete={false}
      searchPlaceholder="Search users"
      columns={[
        { key: 'name', header: 'Name', render: (r) => <strong>{r.name || '—'}</strong> },
        { key: 'email', header: 'Email', render: (r) => r.email },
        { key: 'role', header: 'Role', render: (r) => <StatusPill status={r.role} /> },
        {
          key: 'active',
          header: 'Status',
          render: (r) => (r.is_active === false ? <span className="pill pill-closed">Inactive</span> : <span className="pill pill-active">Active</span>),
        },
        { key: 'joined', header: 'Joined', render: (r) => date(r.date_joined) },
      ]}
      defaults={{ name: '', email: '', password: '', role: 'staff' }}
      fields={[
        { name: 'name', label: 'Name', required: true, span: 2 },
        { name: 'email', label: 'Email', type: 'email', required: true },
        {
          name: 'role',
          label: 'Role',
          type: 'select',
          required: true,
          options: [
            { value: 'staff', label: 'Staff' },
            { value: 'admin', label: 'Admin' },
          ],
        },
        {
          name: 'password',
          label: 'Initial password',
          type: 'password',
          required: true,
          createOnly: true,
          span: 2,
          hint: 'More than 8 characters with upper, lower and a special character.',
        },
      ]}
      validate={(d): Record<string, string[]> => {
        if (d.id == null) {
          const p: string = d.password ?? ''
          if (!(p.length > 8 && /[A-Z]/.test(p) && /[a-z]/.test(p) && /[^A-Za-z0-9]/.test(p)))
            return { password: ['Use more than 8 characters with upper, lower and a special character.'] }
        }
        return {}
      }}
      toPayload={(d) => {
        const out: any = { name: d.name, email: d.email, role: d.role }
        if (d.id == null) out.password = d.password
        return out
      }}
    />
  )
}
