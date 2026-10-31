import { useEffect, useState, type ReactNode } from 'react'
import { NavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { BrandMark, Icon } from './icons'
import { Button } from './ui'

interface NavItem {
  to: string
  /** Opens outside the app (e.g. the API docs served by the backend). */
  external?: boolean
  label: string
  icon: ReactNode
  adminOnly?: boolean
}
interface NavGroup {
  label: string
  items: NavItem[]
}

const consoleNav: NavGroup[] = [
  {
    label: 'Overview',
    items: [{ to: '/dashboard', label: 'Dashboard', icon: <Icon.dashboard /> }],
  },
  {
    label: 'Sales',
    items: [
      { to: '/subscriptions', label: 'Subscriptions', icon: <Icon.loop /> },
      { to: '/quotation-templates', label: 'Quotation templates', icon: <Icon.template /> },
      { to: '/customers', label: 'Customers', icon: <Icon.users /> },
    ],
  },
  {
    label: 'Billing',
    items: [
      { to: '/invoices', label: 'Invoices', icon: <Icon.invoice /> },
      { to: '/payments', label: 'Payments', icon: <Icon.card /> },
      { to: '/billing', label: 'Billing runs', icon: <Icon.play /> },
    ],
  },
  {
    label: 'Catalog',
    items: [
      { to: '/products', label: 'Products', icon: <Icon.box /> },
      { to: '/plans', label: 'Plans', icon: <Icon.calendar /> },
      { to: '/tax-groups', label: 'Tax groups', icon: <Icon.percent /> },
      { to: '/discounts', label: 'Discounts', icon: <Icon.tag /> },
    ],
  },
  {
    label: 'Settings',
    items: [
      { to: '/users', label: 'Users', icon: <Icon.shield />, adminOnly: true },
      { to: '/api-keys', label: 'API keys', icon: <Icon.loop />, adminOnly: true },
      { to: '/audit-log', label: 'Audit log', icon: <Icon.file />, adminOnly: true },
      { to: '/api/docs', label: 'API docs', icon: <Icon.template />, adminOnly: true, external: true },
    ],
  },
]

const portalNav: NavGroup[] = [
  {
    label: 'My account',
    items: [
      { to: '/portal', label: 'Overview', icon: <Icon.home /> },
      { to: '/portal/subscriptions', label: 'My subscriptions', icon: <Icon.loop /> },
      { to: '/portal/invoices', label: 'My invoices', icon: <Icon.invoice /> },
    ],
  },
]

function initials(name: string) {
  return (
    name
      .split(/\s+/)
      .filter(Boolean)
      .slice(0, 2)
      .map((p) => p[0]?.toUpperCase())
      .join('') || '?'
  )
}

export function Shell() {
  const { user, logout, isAdmin } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const [open, setOpen] = useState(false)
  useEffect(() => setOpen(false), [loc.pathname])

  const groups = (user?.role === 'customer' ? portalNav : consoleNav)
    .map((g) => ({ ...g, items: g.items.filter((i) => !i.adminOnly || isAdmin) }))
    .filter((g) => g.items.length)

  return (
    <div className="shell">
      <div className="topbar-mobile no-print">
        <Button
          variant="ghost"
          iconOnly
          icon={<Icon.menu />}
          aria-label="Open navigation"
          aria-expanded={open}
          onClick={() => setOpen((o) => !o)}
          style={{ color: '#fff' }}
        />
        <BrandMark />
        <strong>Brightloop</strong>
      </div>
      <aside className={`sidebar no-print ${open ? 'open' : ''}`} aria-label="Primary">
        <NavLink to={user?.role === 'customer' ? '/portal' : '/dashboard'} className="brand">
          <BrandMark />
          Brightloop
        </NavLink>
        <nav>
          {groups.map((g) => (
            <div key={g.label}>
              <div className="nav-section">{g.label}</div>
              {g.items.map((i) => (
                i.external ? (
                  <a key={i.to} href={i.to} target="_blank" rel="noreferrer" className="nav-link">
                    {i.icon}
                    {i.label}
                  </a>
                ) : (
                  <NavLink key={i.to} to={i.to} end={i.to === '/portal'} className="nav-link">
                    {i.icon}
                    {i.label}
                  </NavLink>
                )
              ))}
            </div>
          ))}
        </nav>
        <div className="side-foot">
          <div className="who">
            <div className="avatar" aria-hidden="true">
              {initials(user?.name || user?.email || '')}
            </div>
            <div style={{ minWidth: 0 }}>
              <div className="who-name">{user?.name || user?.email}</div>
              <div className="who-role">{user?.role}</div>
            </div>
          </div>
          <button
            className="nav-link side-btn"
            onClick={async () => {
              await logout()
              nav('/login')
            }}
          >
            <Icon.logout />
            Sign out
          </button>
        </div>
      </aside>
      <main className="main" id="main">
        <Outlet />
      </main>
    </div>
  )
}
