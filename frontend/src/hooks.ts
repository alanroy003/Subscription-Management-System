import { useCallback, useEffect, useRef, useState } from 'react'
import { api, type Query } from './api'
import { errorMessage } from './components/toast'

export function useDebounced<T>(value: T, ms = 300): T {
  const [v, setV] = useState(value)
  useEffect(() => {
    const t = window.setTimeout(() => setV(value), ms)
    return () => window.clearTimeout(t)
  }, [value, ms])
  return v
}

/** Runs an async loader whenever deps change; exposes reload. Ignores stale responses. */
export function useAsync<T>(fn: () => Promise<T>, deps: unknown[]) {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [loading, setLoading] = useState(true)
  const seq = useRef(0)
  const fnRef = useRef(fn)
  fnRef.current = fn

  const load = useCallback(async () => {
    const my = ++seq.current
    setLoading(true)
    setError(null)
    try {
      const d = await fnRef.current()
      if (my === seq.current) setData(d)
    } catch (e) {
      if (my === seq.current) setError(errorMessage(e))
    } finally {
      if (my === seq.current) setLoading(false)
    }
  }, [])

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps)

  return { data, setData, error, loading, reload: load }
}

/** Paginated list with page state; resets to page 1 when query changes. */
export function useList<T>(path: string, query: Query = {}) {
  const [page, setPage] = useState(1)
  const key = JSON.stringify(query)
  const prevKey = useRef(key)
  if (prevKey.current !== key) {
    prevKey.current = key
    if (page !== 1) setPage(1)
  }
  const res = useAsync(() => api.list<T>(path, { ...query, page }), [path, key, page])
  return {
    rows: res.data?.results ?? null,
    count: res.data?.count ?? 0,
    loading: res.loading,
    error: res.error,
    reload: res.reload,
    page,
    setPage,
  }
}

/** Cached lookup lists for pickers (products, plans, customers...). */
const lookupCache = new Map<string, Promise<unknown[]>>()
export function useLookup<T>(path: string, enabled = true) {
  const [items, setItems] = useState<T[]>([])
  useEffect(() => {
    if (!enabled) return
    let p = lookupCache.get(path) as Promise<T[]> | undefined
    if (!p) {
      p = api.all<T>(path)
      lookupCache.set(path, p as Promise<unknown[]>)
      p.catch(() => lookupCache.delete(path))
    }
    let alive = true
    p.then((x) => alive && setItems(x)).catch(() => {})
    return () => {
      alive = false
    }
  }, [path, enabled])
  return items
}
export function invalidateLookup(path?: string) {
  if (path) lookupCache.delete(path)
  else lookupCache.clear()
}
