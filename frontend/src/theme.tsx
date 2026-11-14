import { App as AntApp, ConfigProvider, theme } from 'antd'
import uzUZ from 'antd/locale/uz_UZ'
import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'

type Mode = 'light' | 'dark'
const ThemeCtx = createContext<{ mode: Mode; toggle: () => void }>({ mode: 'light', toggle: () => {} })
export const useThemeMode = () => useContext(ThemeCtx)

const KEY = 'pcrm_theme'

function initialMode(): Mode {
  try {
    const saved = localStorage.getItem(KEY)
    if (saved === 'light' || saved === 'dark') return saved
  } catch {
    /* localStorage yopiq bo'lishi mumkin */
  }
  return window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
}

export function ThemeProvider({ children }: { children: ReactNode }) {
  const [mode, setMode] = useState<Mode>(initialMode)
  useEffect(() => {
    document.documentElement.dataset.theme = mode
    try {
      localStorage.setItem(KEY, mode)
    } catch {
      /* e'tiborsiz */
    }
  }, [mode])

  const dark = mode === 'dark'
  return (
    <ThemeCtx.Provider value={{ mode, toggle: () => setMode(dark ? 'light' : 'dark') }}>
      <ConfigProvider
        locale={uzUZ}
        theme={{
          algorithm: dark ? theme.darkAlgorithm : theme.defaultAlgorithm,
          token: {
            colorPrimary: '#4F46E5',
            colorSuccess: '#16A34A',
            colorWarning: '#F59E0B',
            colorError: '#DC2626',
            borderRadius: 10,
            fontFamily: "'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
            colorBgLayout: dark ? '#0B0F19' : '#F5F7FB',
            colorBgContainer: dark ? '#111827' : '#FFFFFF',
            colorBorderSecondary: dark ? '#1F2937' : '#EEF0F4',
          },
          components: {
            Layout: { siderBg: dark ? '#0F1422' : '#FFFFFF', headerBg: dark ? '#111827' : '#FFFFFF', headerHeight: 64 },
            Menu: {
              itemBg: 'transparent',
              itemBorderRadius: 8,
              itemSelectedBg: dark ? 'rgba(99,102,241,0.18)' : '#EEF2FF',
              itemSelectedColor: dark ? '#A5B4FC' : '#4F46E5',
            },
            Card: { paddingLG: 20 },
            Table: { headerBg: dark ? '#0F1422' : '#F8FAFC', headerColor: dark ? '#9CA3AF' : '#64748B' },
          },
        }}
      >
        <AntApp>{children}</AntApp>
      </ConfigProvider>
    </ThemeCtx.Provider>
  )
}
