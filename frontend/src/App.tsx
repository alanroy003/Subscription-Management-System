import { Link, Navigate, Route, Routes } from 'react-router-dom'
import { homeFor, RequireRole, useAuth } from './auth'
import { Shell } from './components/Shell'
import { EmptyState } from './components/ui'
import { ForgotPasswordPage, LoginPage, ResetPasswordPage, SignupPage } from './pages/auth/AuthPages'
import { BillingPage } from './pages/Billing'
import {
  CustomersPage,
  DiscountsPage,
  PlansPage,
  ProductsPage,
  TaxGroupsPage,
  TemplatesPage,
  UsersPage,
} from './pages/Catalog'
import { DashboardPage } from './pages/Dashboard'
import { InvoiceDetailPage, InvoicePrintPage, InvoicesPage, PaymentsPage } from './pages/Invoices'
import { PortalHomePage } from './pages/portal/PortalHome'
import { NewSubscriptionPage, SubscriptionDetailPage, SubscriptionsPage } from './pages/Subscriptions'

const STAFF = ['admin', 'staff'] as const
const ADMIN = ['admin'] as const
const CUSTOMER = ['customer'] as const

function Home() {
  const { user, ready } = useAuth()
  if (!ready) return null
  return <Navigate to={user ? homeFor(user.role) : '/login'} replace />
}

function NotFound() {
  return (
    <EmptyState
      title="Page not found"
      body="The link may be old, or you may not have access to it."
      action={
        <Link to="/" className="btn btn-primary">
          Go to start
        </Link>
      }
    />
  )
}

export default function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />

      {/* Print views render without the app shell */}
      <Route
        path="/invoices/:id/print"
        element={
          <RequireRole roles={[...STAFF]}>
            <InvoicePrintPage />
          </RequireRole>
        }
      />
      <Route
        path="/portal/invoices/:id/print"
        element={
          <RequireRole roles={[...CUSTOMER]}>
            <InvoicePrintPage />
          </RequireRole>
        }
      />

      <Route
        element={
          <RequireRole roles={[...STAFF]}>
            <Shell />
          </RequireRole>
        }
      >
        <Route path="/dashboard" element={<DashboardPage />} />
        <Route path="/subscriptions" element={<SubscriptionsPage />} />
        <Route path="/subscriptions/new" element={<NewSubscriptionPage />} />
        <Route path="/subscriptions/:id" element={<SubscriptionDetailPage />} />
        <Route path="/quotation-templates" element={<TemplatesPage />} />
        <Route path="/customers" element={<CustomersPage />} />
        <Route path="/products" element={<ProductsPage />} />
        <Route path="/plans" element={<PlansPage />} />
        <Route path="/tax-groups" element={<TaxGroupsPage />} />
        <Route path="/discounts" element={<DiscountsPage />} />
        <Route path="/invoices" element={<InvoicesPage />} />
        <Route path="/invoices/:id" element={<InvoiceDetailPage />} />
        <Route path="/payments" element={<PaymentsPage />} />
        <Route path="/billing" element={<BillingPage />} />
        <Route
          path="/users"
          element={
            <RequireRole roles={[...ADMIN]}>
              <UsersPage />
            </RequireRole>
          }
        />
      </Route>

      <Route
        element={
          <RequireRole roles={[...CUSTOMER]}>
            <Shell />
          </RequireRole>
        }
      >
        <Route path="/portal" element={<PortalHomePage />} />
        <Route path="/portal/subscriptions" element={<SubscriptionsPage portal />} />
        <Route path="/portal/subscriptions/:id" element={<SubscriptionDetailPage portal />} />
        <Route path="/portal/invoices" element={<InvoicesPage portal />} />
        <Route path="/portal/invoices/:id" element={<InvoiceDetailPage portal />} />
      </Route>

      <Route path="/" element={<Home />} />
      <Route path="*" element={<NotFound />} />
    </Routes>
  )
}
