import type { Page } from './types'

const TOKEN_KEY = 'brightloop.token'

export const tokenStore = {
  get: (): string | null => {
    try {
      return localStorage.getItem(TOKEN_KEY)
    } catch {
      return null
    }
  },
  set: (t: string) => {
    try {
      localStorage.setItem(TOKEN_KEY, t)
    } catch {
      /* ignore */
    }
  },
  clear: () => {
    try {
      localStorage.removeItem(TOKEN_KEY)
    } catch {
      /* ignore */
    }
  },
}

/** Called on any 401 response; the auth provider installs a handler. */
let unauthorizedHandler: () => void = () => {}
export function onUnauthorized(fn: () => void) {
  unauthorizedHandler = fn
}

export class ApiError extends Error {
  status: number
  fields: Record<string, string[]>
  constructor(status: number, message: string, fields: Record<string, string[]> = {}) {
    super(message)
    this.status = status
    this.fields = fields
  }
}

function humanField(k: string) {
  if (k === 'non_field_errors') return ''
  return k.replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase()) + ': '
}

function flatten(v: unknown): string[] {
  if (v == null) return []
  if (typeof v === 'string') return [v]
  if (Array.isArray(v)) return v.flatMap(flatten)
  if (typeof v === 'object') return Object.values(v as Record<string, unknown>).flatMap(flatten)
  return [String(v)]
}

function parseError(status: number, body: unknown): ApiError {
  if (body && typeof body === 'object' && !Array.isArray(body)) {
    const obj = body as Record<string, unknown>
    if (typeof obj.detail === 'string') return new ApiError(status, obj.detail)
    const fields: Record<string, string[]> = {}
    const parts: string[] = []
    for (const [k, v] of Object.entries(obj)) {
      const msgs = flatten(v)
      fields[k] = msgs
      if (msgs.length) parts.push(humanField(k) + msgs.join(' '))
    }
    if (parts.length) return new ApiError(status, parts.join(' · '), fields)
  }
  if (Array.isArray(body)) return new ApiError(status, flatten(body).join(' '))
  if (typeof body === 'string' && body.trim() && body.length < 300) return new ApiError(status, body)
  const generic: Record<number, string> = {
    400: 'The request was rejected. Check the fields and try again.',
    403: 'You do not have permission to do that.',
    404: 'Not found.',
    500: 'The server hit an error. Try again in a moment.',
  }
  return new ApiError(status, generic[status] ?? `Request failed (${status}).`)
}

export type Query = Record<string, string | number | boolean | null | undefined>

export function qs(q?: Query): string {
  if (!q) return ''
  const p = new URLSearchParams()
  for (const [k, v] of Object.entries(q)) {
    if (v === undefined || v === null || v === '' || v === false) continue
    p.set(k, String(v))
  }
  const s = p.toString()
  return s ? `?${s}` : ''
}

/** Set VITE_API_TRAILING_SLASH=true if the backend router expects `/path/`. */
const TRAILING_SLASH = import.meta.env.VITE_API_TRAILING_SLASH === 'true'

function url(path: string) {
  const clean = path.startsWith('/') ? path : `/${path}`
  let full = clean.startsWith('/api/') ? clean : `/api${clean}`
  if (TRAILING_SLASH) {
    const [p, q] = full.split('?')
    full = (p.endsWith('/') ? p : `${p}/`) + (q ? `?${q}` : '')
  }
  return full
}

export async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' }
  const token = tokenStore.get()
  if (token) headers.Authorization = `Token ${token}`
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  let res: Response
  try {
    res = await fetch(url(path), {
      method,
      headers,
      body: body !== undefined ? JSON.stringify(body) : undefined,
    })
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Check that the backend is running.')
  }
  const text = await res.text()
  let data: unknown = null
  if (text) {
    try {
      data = JSON.parse(text)
    } catch {
      data = text
    }
  }
  if (res.status === 401) {
    if (token) {
      tokenStore.clear()
      unauthorizedHandler()
    }
    throw parseError(401, data ?? { detail: 'Your session has ended. Sign in again.' })
  }
  if (!res.ok) throw parseError(res.status, data)
  return data as T
}

/** Downloads a file (e.g. an invoice PDF) with the signed-in user's token and saves it under `filename`. */
export async function downloadFile(path: string, filename: string): Promise<void> {
  const headers: Record<string, string> = { Accept: 'application/pdf, application/json' }
  const token = tokenStore.get()
  if (token) headers.Authorization = `Token ${token}`
  let res: Response
  try {
    res = await fetch(url(path), { headers })
  } catch {
    throw new ApiError(0, 'Cannot reach the server. Check that the backend is running.')
  }
  if (!res.ok) {
    let data: unknown = null
    try {
      data = await res.json()
    } catch {
      data = null
    }
    throw parseError(res.status, data ?? { detail: 'The file could not be downloaded.' })
  }
  const href = URL.createObjectURL(await res.blob())
  const a = document.createElement('a')
  a.href = href
  a.download = filename
  document.body.appendChild(a)
  a.click()
  a.remove()
  window.setTimeout(() => URL.revokeObjectURL(href), 1000)
}

/** Normalises list responses: accepts paginated objects or bare arrays. */
function toPage<T>(data: Page<T> | T[]): Page<T> {
  if (Array.isArray(data)) return { count: data.length, next: null, previous: null, results: data }
  return data
}

export const api = {
  get: <T>(path: string, q?: Query) => request<T>('GET', path + qs(q)),
  list: async <T>(path: string, q?: Query) => toPage(await request<Page<T> | T[]>('GET', path + qs(q))),
  /** Fetches up to 200 items, for pickers. */
  all: async <T>(path: string, q?: Query) =>
    toPage(await request<Page<T> | T[]>('GET', path + qs({ page_size: 200, ...q }))).results,
  create: <T>(path: string, body: unknown) => request<T>('POST', path, body),
  update: <T>(path: string, id: number | string, body: unknown) => request<T>('PATCH', `${path}/${id}`, body),
  remove: (path: string, id: number | string) => request<void>('DELETE', `${path}/${id}`),
  action: <T>(path: string, body: unknown = {}) => request<T>('POST', path, body),
}
