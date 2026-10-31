import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'
import { Navigate, useLocation } from 'react-router-dom'
import { api, onUnauthorized, tokenStore } from './api'
import type { Role, User } from './types'
import { invalidateLookup } from './hooks'

interface AuthState {
  user: User | null
  ready: boolean
  login: (email: string, password: string) => Promise<User>
  signup: (name: string, email: string, password: string) => Promise<User>
  logout: () => Promise<void>
  refresh: () => Promise<void>
  isAdmin: boolean
  isStaff: boolean // admin or staff
}

const Ctx = createContext<AuthState | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null)
  const [ready, setReady] = useState(false)

  const clear = useCallback(() => {
    tokenStore.clear()
    invalidateLookup()
    setUser(null)
  }, [])

  const refresh = useCallback(async () => {
    if (!tokenStore.get()) {
      setUser(null)
      return
    }
    try {
      setUser(await api.get<User>('/auth/me'))
    } catch {
      clear()
    }
  }, [clear])

  useEffect(() => {
    onUnauthorized(() => {
      invalidateLookup()
      setUser(null)
    })
    refresh().finally(() => setReady(true))
  }, [refresh])

  const login = useCallback(async (email: string, password: string) => {
    const r = await api.create<{ token: string; user: User }>('/auth/login', { email, password })
    tokenStore.set(r.token)
    invalidateLookup()
    setUser(r.user)
    return r.user
  }, [])

  const signup = useCallback(async (name: string, email: string, password: string) => {
    const r = await api.create<{ token: string; user: User }>('/auth/signup', { name, email, password })
    tokenStore.set(r.token)
    invalidateLookup()
    setUser(r.user)
    return r.user
  }, [])

  const logout = useCallback(async () => {
    try {
      await api.action('/auth/logout')
    } catch {
      /* token may already be invalid */
    }
    clear()
  }, [clear])

  const value = useMemo<AuthState>(
    () => ({
      user,
      ready,
      login,
      signup,
      logout,
      refresh,
      isAdmin: user?.role === 'admin',
      isStaff: user?.role === 'admin' || user?.role === 'staff',
    }),
    [user, ready, login, signup, logout, refresh],
  )
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>
}

export function useAuth(): AuthState {
  const c = useContext(Ctx)
  if (!c) throw new Error('useAuth outside AuthProvider')
  return c
}

export function homeFor(role: Role | undefined) {
  return role === 'customer' ? '/portal' : '/dashboard'
}

export function RequireRole({ roles, children }: { roles: Role[]; children: ReactNode }) {
  const { user, ready } = useAuth()
  const loc = useLocation()
  if (!ready) return null
  if (!user) return <Navigate to="/login" replace state={{ from: loc.pathname + loc.search }} />
  if (!roles.includes(user.role)) return <Navigate to={homeFor(user.role)} replace />
  return <>{children}</>
}
