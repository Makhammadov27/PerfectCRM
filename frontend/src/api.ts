import axios, { AxiosError } from 'axios'

const ACCESS = 'pcrm_access'
const REFRESH = 'pcrm_refresh'

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS)
  },
  get refresh() {
    return localStorage.getItem(REFRESH)
  },
  set(access: string, refresh?: string) {
    localStorage.setItem(ACCESS, access)
    if (refresh) localStorage.setItem(REFRESH, refresh)
  },
  clear() {
    localStorage.removeItem(ACCESS)
    localStorage.removeItem(REFRESH)
  },
}

export const api = axios.create({ baseURL: '/api' })

api.interceptors.request.use((cfg) => {
  if (tokens.access) cfg.headers.Authorization = `Bearer ${tokens.access}`
  return cfg
})

let refreshing: Promise<string | null> | null = null

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as (typeof error.config & { _retry?: boolean }) | undefined
    if (error.response?.status === 401 && original && !original._retry && tokens.refresh) {
      original._retry = true
      refreshing ??= axios
        .post('/api/auth/refresh/', { refresh: tokens.refresh })
        .then((r) => {
          tokens.set(r.data.access)
          return r.data.access as string
        })
        .catch(() => {
          tokens.clear()
          window.location.href = '/login'
          return null
        })
        .finally(() => {
          refreshing = null
        })
      const token = await refreshing
      if (token) {
        original.headers = original.headers ?? {}
        original.headers.Authorization = `Bearer ${token}`
        return api(original)
      }
    }
    return Promise.reject(error)
  },
)

/** Server xatosini o'qiladigan matnga aylantiradi. */
export function errorText(e: unknown): string {
  const err = e as AxiosError<Record<string, unknown>>
  const data = err?.response?.data
  if (!data) return err?.message || 'Xatolik yuz berdi'
  if (typeof data === 'string') return 'Server xatosi'
  const flat = (v: unknown): string =>
    Array.isArray(v) ? v.map(flat).join('; ') : typeof v === 'object' && v ? Object.values(v).map(flat).join('; ') : String(v)
  if ('detail' in data) return flat(data.detail)
  return Object.entries(data)
    .map(([k, v]) => (k === 'non_field_errors' ? flat(v) : `${k}: ${flat(v)}`))
    .join('\n')
}

/** Excel faylni yuklab olish (token bilan). */
export async function download(url: string, filename: string) {
  const r = await api.get(url, { responseType: 'blob' })
  const href = URL.createObjectURL(r.data)
  const a = document.createElement('a')
  a.href = href
  a.download = filename
  a.click()
  URL.revokeObjectURL(href)
}

export type Paged<T> = { count: number; results: T[] }
