export type Role = 'admin' | 'staff' | 'customer'

export interface User {
  id: number
  email: string
  name: string
  role: Role
  customer_id: number | null
}

export interface Page<T> {
  count: number
  next: string | null
  previous: string | null
  results: T[]
}

export type Id = number

export interface Variant {
  id?: Id
  attribute: string
  value: string
  price_extra: string
  price?: string
}

export interface Product {
  id: Id
  name: string
  type: 'service' | 'software' | 'goods'
  sales_price: string
  cost_price: string
  notes: string
  tax_group: Id | null
  tax_group_name?: string
  is_active: boolean
  variants: Variant[]
}

export type BillingPeriod = 'daily' | 'weekly' | 'monthly' | 'yearly'

export interface Plan {
  id: Id
  name: string
  product: Id | null
  product_name?: string
  price: string
  billing_period: BillingPeriod
  min_quantity: number
  available_from: string | null
  available_to: string | null
  auto_close: boolean
  closable: boolean
  pausable: boolean
  renewable: boolean
  is_trial?: boolean
  trial_days?: number
  is_available?: boolean
}

export interface TaxGroup {
  id: Id
  name: string
  rate: string
  mode: 'gst' | 'simple'
  is_active: boolean
}

export interface Discount {
  id: Id
  name: string
  kind: 'fixed' | 'percent'
  value: string
  min_amount: string | null
  min_quantity: number | null
  start_date: string | null
  end_date: string | null
  usage_limit: number | null
  used_count?: number
  scope: 'all' | 'products'
  products: Id[]
  is_active: boolean
}

export interface TemplateLine {
  id?: Id
  product: Id | null
  product_name?: string
  variant: Id | null
  quantity: number | string
}

export interface QuotationTemplate {
  id: Id
  name: string
  plan: Id | null
  plan_name?: string
  validity_days: number
  notes: string
  lines: TemplateLine[]
}

export interface PaymentTerm {
  days: number
  label: string
}

export interface Customer {
  id: Id
  name: string
  email: string
  phone: string
  address: string
  state: string
  gstin: string
  has_login?: boolean
}

export type SubStatus = 'draft' | 'quotation' | 'confirmed' | 'active' | 'paused' | 'closed'
export type SubAction = 'send_quotation' | 'confirm' | 'activate' | 'pause' | 'resume' | 'close' | 'renew' | 'convert'

export interface SubLine {
  id?: Id
  product: Id | null
  product_name?: string
  variant: Id | null
  variant_label?: string
  description: string
  quantity: number | string
  unit_price: string
  tax_group: Id | null
  subtotal?: string
}

export interface SubEvent {
  at: string
  from_status: string | null
  to_status: string
  user_name: string | null
  note: string | null
}

export interface Subscription {
  id: Id
  number: string
  customer: Id
  customer_name: string
  plan: Id
  plan_name: string
  billing_period: BillingPeriod
  status: SubStatus
  start_date: string | null
  expiry_date: string | null
  next_invoice_date: string | null
  payment_term_days: number
  quotation_valid_until: string | null
  notes: string
  lines: SubLine[]
  subtotal: string
  recurring_total: string
  available_actions: SubAction[]
  is_trial?: boolean
  converted_to?: Id | null
  converted_to_number?: string | null
  events: SubEvent[]
  created_at: string
}

export type InvStatus = 'draft' | 'confirmed' | 'paid' | 'cancelled'

export interface InvoiceTax {
  name: string
  rate: string
  amount: string
}

export interface InvoiceLine {
  description: string
  quantity: string | number
  unit_price: string
  subtotal: string
  discount_name: string | null
  discount_amount: string
  taxes: InvoiceTax[]
  tax_amount: string
  total: string
}

export type PayMethod = 'cash' | 'bank_transfer' | 'upi' | 'card' | 'cheque'

export interface Payment {
  id: Id
  invoice: Id
  invoice_number?: string
  customer_name?: string
  method: PayMethod
  amount: string
  date: string
  note: string
  created_at?: string
}

export interface Invoice {
  id: Id
  number: string | null
  subscription: Id | null
  subscription_number: string | null
  customer: Id
  customer_name: string
  customer_snapshot: { name: string; email: string; address: string; state: string; gstin: string } | null
  company?: { name: string; address: string; state: string; gstin: string }
  period_start: string | null
  period_end: string | null
  invoice_date: string
  due_date: string
  status: InvStatus
  currency: string
  subtotal: string
  discount_total: string
  tax_total: string
  total: string
  amount_paid: string
  balance: string
  is_overdue: boolean
  lines: InvoiceLine[]
  payments: Payment[]
  sent_at: string | null
}

export interface BillingItem {
  subscription_number: string
  period_start: string
  total: string
  status: string
  error: string | null
}

export interface BillingRun {
  id: Id | null
  run_date: string
  dry_run: boolean
  created: number
  skipped: number
  failed: number
  items?: BillingItem[]
}

export interface Summary {
  active_subscriptions: number
  status_counts: Record<SubStatus, number>
  billed: string
  collected: string
  outstanding: string
  overdue_amount: string
  overdue_count: number
  mrr: string
  arpu: string
  churned_last_30: number
  churn_rate: string | number
  revenue_series: { month: string; billed: string; collected: string }[]
  renewals: { d30: number; d60: number; d90: number }
  forecast: { d30: string; d60: string; d90: string }
  at_risk: { customer_id: Id; customer_name: string; overdue_count: number; overdue_amount: string }[]
  top_overdue: Invoice[]
}

export interface StaffUser {
  id: Id
  email: string
  name: string
  role: Role
  is_active?: boolean
  date_joined?: string
}
