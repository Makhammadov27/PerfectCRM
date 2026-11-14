import dayjs from 'dayjs'

export const money = (n: number | null | undefined) =>
  `${Math.round(n ?? 0)
    .toString()
    .replace(/\B(?=(\d{3})+(?!\d))/g, ' ')} so'm`

export const moneyShort = (n: number) =>
  n >= 1_000_000 ? `${(n / 1_000_000).toFixed(n % 1_000_000 ? 1 : 0)} mln` : n >= 1000 ? `${Math.round(n / 1000)} ming` : String(n)

export const fmtDate = (d?: string | null) => (d ? dayjs(d).format('DD.MM.YYYY') : '—')
export const fmtDateTime = (d?: string | null) => (d ? dayjs(d).format('DD.MM.YYYY HH:mm') : '—')
export const fmtTime = (t?: string | null) => (t ? t.slice(0, 5) : '')

export const phone = (p?: string | null) => {
  const d = (p || '').replace(/\D/g, '')
  if (d.length !== 12) return p || '—'
  return `+${d.slice(0, 3)} ${d.slice(3, 5)} ${d.slice(5, 8)} ${d.slice(8, 10)} ${d.slice(10)}`
}

export const MONTHS = ['Yanvar', 'Fevral', 'Mart', 'Aprel', 'May', 'Iyun', 'Iyul', 'Avgust', 'Sentabr', 'Oktabr', 'Noyabr', 'Dekabr']
export const monthLabel = (d: string | dayjs.Dayjs) => {
  const x = dayjs(d)
  return `${MONTHS[x.month()]} ${x.year()}`
}

export const WEEKDAYS = ['Dushanba', 'Seshanba', 'Chorshanba', 'Payshanba', 'Juma', 'Shanba', 'Yakshanba']
export const WEEKDAYS_SHORT = ['Du', 'Se', 'Chor', 'Pay', 'Ju', 'Sha', 'Yak']

export const METHOD: Record<string, string> = { cash: 'Naqd', card: 'Karta', transfer: "O'tkazma" }

export const ATTENDANCE: Record<string, { label: string; color: string; icon: string }> = {
  present: { label: 'Keldi', color: 'green', icon: '✅' },
  absent: { label: 'Kelmadi', color: 'red', icon: '❌' },
  late: { label: 'Kechikdi', color: 'orange', icon: '⏰' },
  excused: { label: 'Sababli', color: 'gold', icon: '🟡' },
}

export const INVOICE_STATUS: Record<string, { label: string; color: string }> = {
  open: { label: "To'lanmagan", color: 'red' },
  partial: { label: 'Qisman', color: 'orange' },
  paid: { label: "To'langan", color: 'green' },
  void: { label: 'Bekor', color: 'default' },
}

export const scheduleText = (slots: { weekday: number; start_time: string; end_time: string }[]) => {
  if (!slots.length) return '—'
  const days = slots.map((s) => WEEKDAYS_SHORT[s.weekday]).join('/')
  const times = [...new Set(slots.map((s) => `${fmtTime(s.start_time)}–${fmtTime(s.end_time)}`))]
  return `${days} ${times.join(', ')}`
}
