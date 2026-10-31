import { useState, type FormEvent, type ReactNode } from 'react'
import { Link, Navigate, useLocation, useNavigate, useSearchParams } from 'react-router-dom'
import { api, ApiError } from '../../api'
import { homeFor, useAuth } from '../../auth'
import { BrandMark } from '../../components/icons'
import { errorMessage, useToast } from '../../components/toast'
import { Button, Field, Input } from '../../components/ui'

function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="auth">
      <div className="auth-art" aria-hidden="true">
        <div className="brand">
          <BrandMark />
          Brightloop
        </div>
        <svg className="loop-art" viewBox="0 0 200 200">
          <circle cx="100" cy="100" r="70" fill="none" stroke="rgba(255,255,255,.18)" strokeWidth="18" />
          <circle
            cx="100"
            cy="100"
            r="70"
            fill="none"
            stroke="#2BC4CA"
            strokeWidth="18"
            strokeDasharray="300 440"
            strokeLinecap="round"
            transform="rotate(-90 100 100)"
          />
          <circle cx="100" cy="30" r="12" fill="#fff" />
        </svg>
        <h2>Recurring revenue, on a steady loop.</h2>
        <p>Quotes, subscriptions, invoices and payments in one place, billed on time, every period.</p>
      </div>
      <div className="auth-form-wrap">
        <div className="auth-form">{children}</div>
      </div>
    </div>
  )
}

export const passwordRules = [
  { key: 'len', label: 'More than 8 characters', test: (p: string) => p.length > 8 },
  { key: 'up', label: 'An uppercase letter', test: (p: string) => /[A-Z]/.test(p) },
  { key: 'low', label: 'A lowercase letter', test: (p: string) => /[a-z]/.test(p) },
  { key: 'sp', label: 'A special character', test: (p: string) => /[^A-Za-z0-9]/.test(p) },
]
export const passwordOk = (p: string) => passwordRules.every((r) => r.test(p))

export function PasswordChecklist({ value, id }: { value: string; id?: string }) {
  return (
    <ul className="checklist" id={id} aria-label="Password requirements">
      {passwordRules.map((r) => {
        const ok = r.test(value)
        return (
          <li key={r.key} className={ok ? 'ok' : ''}>
            {r.label}
            <span className="sr-only">{ok ? ' (met)' : ' (not met)'}</span>
          </li>
        )
      })}
    </ul>
  )
}

export function LoginPage() {
  const { login, user, ready } = useAuth()
  const nav = useNavigate()
  const loc = useLocation() as { state?: { from?: string } }
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)

  if (ready && user) return <Navigate to={homeFor(user.role)} replace />

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    setErr(null)
    try {
      const u = await login(email.trim(), password)
      const from = loc.state?.from
      nav(from && from !== '/login' ? from : homeFor(u.role), { replace: true })
    } catch (e2) {
      setErr(e2 instanceof ApiError && e2.status === 400 ? 'Email or password is incorrect.' : errorMessage(e2))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout>
      <h1>Sign in</h1>
      <p className="sub">Use the email and password for your Brightloop account.</p>
      <form className="stack" onSubmit={submit} noValidate>
        {err && (
          <div className="alert alert-error" role="alert">
            {err}
          </div>
        )}
        <Field label="Email">
          {(id) => (
            <Input id={id} type="email" autoComplete="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          )}
        </Field>
        <Field label="Password">
          {(id) => (
            <Input
              id={id}
              type="password"
              autoComplete="current-password"
              required
              value={password}
              onChange={(e) => setPassword(e.target.value)}
            />
          )}
        </Field>
        <Button type="submit" variant="primary" loading={busy} disabled={!email || !password}>
          Sign in
        </Button>
      </form>
      <div className="auth-links">
        <Link to="/forgot-password">Forgot password?</Link>
        <Link to="/signup">Create an account</Link>
      </div>
    </AuthLayout>
  )
}

export function SignupPage() {
  const { signup, user, ready } = useAuth()
  const nav = useNavigate()
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [err, setErr] = useState<string | null>(null)
  const [fields, setFields] = useState<Record<string, string[]>>({})
  const [busy, setBusy] = useState(false)

  if (ready && user) return <Navigate to={homeFor(user.role)} replace />
  const mismatch = confirm.length > 0 && confirm !== password
  const valid = name.trim() && /\S+@\S+\.\S+/.test(email) && passwordOk(password) && confirm === password

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!valid) return
    setBusy(true)
    setErr(null)
    setFields({})
    try {
      const u = await signup(name.trim(), email.trim(), password)
      nav(homeFor(u.role), { replace: true })
    } catch (e2) {
      if (e2 instanceof ApiError) setFields(e2.fields)
      setErr(errorMessage(e2))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout>
      <h1>Create your account</h1>
      <p className="sub">Manage your subscriptions and invoices online.</p>
      <form className="stack" onSubmit={submit} noValidate>
        {err && (
          <div className="alert alert-error" role="alert">
            {err}
          </div>
        )}
        <Field label="Full name" required error={fields.name}>
          {(id) => <Input id={id} autoComplete="name" value={name} onChange={(e) => setName(e.target.value)} />}
        </Field>
        <Field label="Email" required error={fields.email}>
          {(id) => (
            <Input id={id} type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
          )}
        </Field>
        <Field label="Password" required error={fields.password}>
          {(id) => (
            <>
              <Input
                id={id}
                type="password"
                autoComplete="new-password"
                aria-describedby={`${id}-rules`}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
              <PasswordChecklist value={password} id={`${id}-rules`} />
            </>
          )}
        </Field>
        <Field label="Confirm password" required error={mismatch ? 'Passwords do not match.' : undefined}>
          {(id, d) => (
            <Input
              id={id}
              type="password"
              autoComplete="new-password"
              aria-describedby={d}
              aria-invalid={mismatch || undefined}
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
            />
          )}
        </Field>
        <Button type="submit" variant="primary" loading={busy} disabled={!valid}>
          Create account
        </Button>
      </form>
      <div className="auth-links">
        <span className="muted">Already have an account?</span>
        <Link to="/login">Sign in</Link>
      </div>
    </AuthLayout>
  )
}

export function ForgotPasswordPage() {
  const [email, setEmail] = useState('')
  const [sent, setSent] = useState(false)
  const [busy, setBusy] = useState(false)
  const toast = useToast()
  const submit = async (e: FormEvent) => {
    e.preventDefault()
    setBusy(true)
    try {
      await api.action('/auth/password-reset', { email: email.trim() })
      setSent(true)
    } catch (e2) {
      toast.error(e2)
    } finally {
      setBusy(false)
    }
  }
  return (
    <AuthLayout>
      <h1>Reset your password</h1>
      <p className="sub">Enter your account email and we will send a reset link.</p>
      {sent ? (
        <div className="alert alert-info" role="status">
          If an account exists for <strong>{email}</strong>, a reset link is on its way. Check your inbox.
        </div>
      ) : (
        <form className="stack" onSubmit={submit}>
          <Field label="Email">
            {(id) => (
              <Input id={id} type="email" required autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} />
            )}
          </Field>
          <Button type="submit" variant="primary" loading={busy} disabled={!email}>
            Send reset link
          </Button>
        </form>
      )}
      <div className="auth-links">
        <Link to="/login">Back to sign in</Link>
      </div>
    </AuthLayout>
  )
}

export function ResetPasswordPage() {
  const [sp] = useSearchParams()
  const uid = sp.get('uid') ?? ''
  const token = sp.get('token') ?? ''
  const [password, setPassword] = useState('')
  const [confirm, setConfirm] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const toast = useToast()
  const nav = useNavigate()
  const valid = passwordOk(password) && password === confirm

  const submit = async (e: FormEvent) => {
    e.preventDefault()
    if (!valid) return
    setBusy(true)
    setErr(null)
    try {
      await api.action('/auth/password-reset/confirm', { uid, token, password })
      toast.success('Password updated. Sign in with your new password.')
      nav('/login', { replace: true })
    } catch (e2) {
      setErr(errorMessage(e2))
    } finally {
      setBusy(false)
    }
  }

  return (
    <AuthLayout>
      <h1>Choose a new password</h1>
      <p className="sub">Your new password replaces the old one immediately.</p>
      {!uid || !token ? (
        <div className="alert alert-error" role="alert">
          This reset link is incomplete. Request a new one from <Link to="/forgot-password">Forgot password</Link>.
        </div>
      ) : (
        <form className="stack" onSubmit={submit} noValidate>
          {err && (
            <div className="alert alert-error" role="alert">
              {err}
            </div>
          )}
          <Field label="New password" required>
            {(id) => (
              <>
                <Input
                  id={id}
                  type="password"
                  autoComplete="new-password"
                  aria-describedby={`${id}-rules`}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                />
                <PasswordChecklist value={password} id={`${id}-rules`} />
              </>
            )}
          </Field>
          <Field
            label="Confirm new password"
            required
            error={confirm && confirm !== password ? 'Passwords do not match.' : undefined}
          >
            {(id) => (
              <Input id={id} type="password" autoComplete="new-password" value={confirm} onChange={(e) => setConfirm(e.target.value)} />
            )}
          </Field>
          <Button type="submit" variant="primary" loading={busy} disabled={!valid}>
            Update password
          </Button>
        </form>
      )}
      <div className="auth-links">
        <Link to="/login">Back to sign in</Link>
      </div>
    </AuthLayout>
  )
}
