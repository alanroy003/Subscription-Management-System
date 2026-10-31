const inr = new Intl.NumberFormat('en-IN', { style: 'currency', currency: 'INR' })
const inrCompact = new Intl.NumberFormat('en-IN', {
  style: 'currency',
  currency: 'INR',
  notation: 'compact',
  maximumFractionDigits: 1,
})

export function num(v: string | number | null | undefined): number {
  if (v === null || v === undefined || v === '') return 0
  const n = typeof v === 'number' ? v : parseFloat(v)
  return Number.isFinite(n) ? n : 0
}

export function money(v: string | number | null | undefined): string {
  return inr.format(num(v))
}

export function moneyCompact(v: string | number | null | undefined): string {
  return inrCompact.format(num(v))
}

function parseDate(v: string): Date {
  // Plain dates ("2026-10-31") parse as local, not UTC.
  return /^\d{4}-\d{2}-\d{2}$/.test(v) ? new Date(`${v}T00:00:00`) : new Date(v)
}

const dFmt = new Intl.DateTimeFormat('en-IN', { day: 'numeric', month: 'short', year: 'numeric' })
const dtFmt = new Intl.DateTimeFormat('en-IN', {
  day: 'numeric',
  month: 'short',
  year: 'numeric',
  hour: 'numeric',
  minute: '2-digit',
})

export function date(v: string | null | undefined): string {
  if (!v) return '—'
  const d = parseDate(v)
  return Number.isNaN(d.getTime()) ? v : dFmt.format(d)
}

export function dateTime(v: string | null | undefined): string {
  if (!v) return '—'
  const d = parseDate(v)
  return Number.isNaN(d.getTime()) ? v : dtFmt.format(d)
}

export function monthLabel(v: string): string {
  const d = parseDate(`${v}-01`)
  return Number.isNaN(d.getTime()) ? v : d.toLocaleDateString('en-IN', { month: 'short', year: '2-digit' })
}

export function todayISO(): string {
  const d = new Date()
  const off = d.getTimezoneOffset()
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 10)
}

export function addDaysISO(iso: string, days: number): string {
  const d = parseDate(iso)
  d.setDate(d.getDate() + days)
  const off = d.getTimezoneOffset()
  return new Date(d.getTime() - off * 60000).toISOString().slice(0, 10)
}

export function titleCase(s: string | null | undefined): string {
  if (!s) return ''
  return s.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase())
}

export const periodLabel: Record<string, string> = {
  daily: 'Daily',
  weekly: 'Weekly',
  monthly: 'Monthly',
  yearly: 'Yearly',
}

export const periodUnit: Record<string, string> = {
  daily: 'day',
  weekly: 'week',
  monthly: 'month',
  yearly: 'year',
}
