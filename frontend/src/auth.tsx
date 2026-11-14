import { useQuery, useQueryClient } from '@tanstack/react-query'
import { createContext, useContext, useState, type ReactNode } from 'react'
import { api, tokens } from './api'
import type { Me } from './types'

type Auth = { me: Me | null; loading: boolean; login: (phone: string, password: string) => Promise<void>; logout: () => void }
const AuthCtx = createContext<Auth>(null!)
export const useAuth = () => useContext(AuthCtx)

export function AuthProvider({ children }: { children: ReactNode }) {
  const qc = useQueryClient()
  const [hasToken, setHasToken] = useState(() => !!tokens.access)
  const { data, isLoading } = useQuery({
    queryKey: ['me'],
    queryFn: async () => (await api.get<Me>('/auth/me/')).data,
    enabled: hasToken,
    retry: false,
  })

  const login = async (phone: string, password: string) => {
    const r = await api.post('/auth/login/', { phone, password })
    tokens.set(r.data.access, r.data.refresh)
    const me = (await api.get<Me>('/auth/me/')).data
    qc.setQueryData(['me'], me)
    setHasToken(true)
  }
  const logout = () => {
    tokens.clear()
    qc.clear()
    window.location.href = '/login'
  }

  return (
    <AuthCtx.Provider value={{ me: data ?? null, loading: hasToken && isLoading, login, logout }}>
      {children}
    </AuthCtx.Provider>
  )
}
