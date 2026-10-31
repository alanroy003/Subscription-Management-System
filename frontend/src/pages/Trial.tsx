import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api } from '../api'
import { Icon } from '../components/icons'
import { useToast } from '../components/toast'
import { Button, Field, Modal, Select } from '../components/ui'
import { date, money, periodUnit } from '../format'
import { useAsync } from '../hooks'
import type { Subscription } from '../types'

export interface TrialInfo {
  offered: boolean
  plan: { id: number; name: string; days: number } | null
  eligible: boolean
  current: {
    id: number
    number: string
    status: string
    expiry_date: string | null
    days_left: number | null
    converted_to: string | null
    converted_to_id: number | null
  } | null
  paid_plans: { id: number; name: string; price: string; billing_period: string }[]
}

/** Pick a paid plan and turn a free trial into a paid subscription that starts when the trial ends. */
export function ConvertTrialModal({
  subscriptionId,
  open,
  onClose,
  portal,
}: {
  subscriptionId: number
  open: boolean
  onClose: () => void
  portal?: boolean
}) {
  const toast = useToast()
  const nav = useNavigate()
  const info = useAsync(() => (open ? api.get<TrialInfo>('/trial') : Promise.resolve(null)), [open])
  const [planId, setPlanId] = useState('')
  const [busy, setBusy] = useState(false)
  const plans = info.data?.paid_plans ?? []

  const convert = async () => {
    if (!planId) return toast.error('Choose the plan to continue on.')
    setBusy(true)
    try {
      const paid = await api.action<Subscription>(`/subscriptions/${subscriptionId}/convert`, { plan: Number(planId) })
      toast.success(`Converted: ${paid.number} starts ${date(paid.start_date)}`)
      onClose()
      nav(`${portal ? '/portal' : ''}/subscriptions/${paid.id}`)
    } catch (e) {
      toast.error(e)
    } finally {
      setBusy(false)
    }
  }

  return (
    <Modal
      open={open}
      onClose={onClose}
      title="Convert to a paid plan"
      footer={
        <>
          <Button onClick={onClose}>Cancel</Button>
          <Button variant="primary" loading={busy} onClick={convert}>
            Convert
          </Button>
        </>
      }
    >
      <p className="muted">
        The paid subscription keeps the same products and starts the day the free trial ends, so there is no gap.
      </p>
      <Field label="Paid plan" required>
        {(id) => (
          <Select
            id={id}
            value={planId}
            placeholder={info.loading ? 'Loading plans…' : 'Choose a plan'}
            onChange={(e) => setPlanId(e.target.value)}
            options={plans.map((p) => ({
              value: p.id,
              label: `${p.name} · ${money(p.price)} / ${periodUnit[p.billing_period] ?? p.billing_period}`,
            }))}
          />
        )}
      </Field>
    </Modal>
  )
}

/** Portal banner: offer the free trial, or show how long the current one has left. */
export function TrialBanner({ onChanged }: { onChanged: () => void }) {
  const toast = useToast()
  const info = useAsync(() => api.get<TrialInfo>('/trial'), [])
  const [busy, setBusy] = useState(false)
  const [converting, setConverting] = useState(false)
  const t = info.data
  if (!t || !t.offered) return null

  const start = async () => {
    setBusy(true)
    try {
      await api.action('/trial/start')
      toast.success('Your free trial has started')
      info.reload()
      onChanged()
    } catch (e) {
      toast.error(e)
    } finally {
      setBusy(false)
    }
  }

  if (t.eligible && t.plan)
    return (
      <div className="alert alert-info row wrap" style={{ justifyContent: 'space-between', gap: 12, marginBottom: 16 }}>
        <span>
          <strong>Start your free {t.plan.days}-day trial.</strong> No payment needed, and it ends on its own.
        </span>
        <Button variant="primary" icon={<Icon.play />} loading={busy} onClick={start}>
          Start free trial
        </Button>
      </div>
    )

  const c = t.current
  if (!c || c.converted_to || c.status !== 'active') return null
  return (
    <div className="alert alert-info row wrap" style={{ justifyContent: 'space-between', gap: 12, marginBottom: 16 }}>
      <span>
        <strong>Free trial: {c.days_left === 0 ? 'ends today' : `${c.days_left} day${c.days_left === 1 ? '' : 's'} left`}</strong>
        {c.expiry_date ? ` (until ${date(c.expiry_date)})` : ''}. Choose a plan to keep going without a break.
      </span>
      <Button variant="primary" onClick={() => setConverting(true)}>
        Choose a plan
      </Button>
      <ConvertTrialModal subscriptionId={c.id} open={converting} onClose={() => setConverting(false)} portal />
    </div>
  )
}
