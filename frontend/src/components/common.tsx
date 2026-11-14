import { Card, DatePicker, Select, Tag, theme } from 'antd'
import { useQuery } from '@tanstack/react-query'
import dayjs, { type Dayjs } from 'dayjs'
import type { ReactNode } from 'react'
import { api } from '../api'
import type { Group, Room, Student, Teacher } from '../types'
import { money } from '../utils'

export function PageHead({ title, sub, extra }: { title: ReactNode; sub?: ReactNode; extra?: ReactNode }) {
  return (
    <div className="page-head">
      <div>
        <h1>{title}</h1>
        {sub && <div className="sub">{sub}</div>}
      </div>
      {extra && <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>{extra}</div>}
    </div>
  )
}

export function StatCard({
  icon, label, value, hint, color,
}: { icon: ReactNode; label: string; value: ReactNode; hint?: ReactNode; color: string }) {
  return (
    <Card className="stat-card" variant="borderless" style={{ height: '100%' }}>
      <div className="stat-icon" style={{ background: `${color}1A`, color }}>
        {icon}
      </div>
      <div style={{ minWidth: 0 }}>
        <div className="stat-label">{label}</div>
        <div className="stat-value">{value}</div>
        {hint && <div className="stat-hint">{hint}</div>}
      </div>
    </Card>
  )
}

export function Balance({ value }: { value: number }) {
  const { token } = theme.useToken()
  if (value < 0) return <span style={{ color: token.colorError, fontWeight: 600 }}>−{money(-value)}</span>
  if (value > 0) return <span style={{ color: token.colorSuccess, fontWeight: 600 }}>+{money(value)}</span>
  return <Tag color="green">Qarz yo'q</Tag>
}

export function MonthPicker({ value, onChange }: { value: Dayjs; onChange: (v: Dayjs) => void }) {
  return (
    <DatePicker
      picker="month"
      value={value}
      allowClear={false}
      format="MMMM YYYY"
      onChange={(v) => v && onChange(v.startOf('month'))}
    />
  )
}

export const monthParam = (d: Dayjs) => d.format('YYYY-MM')
export const thisMonth = () => dayjs().startOf('month')

export function useTeachers() {
  return useQuery({ queryKey: ['teachers'], queryFn: async () => (await api.get<Teacher[]>('/teachers/')).data })
}
export function useRooms() {
  return useQuery({ queryKey: ['rooms'], queryFn: async () => (await api.get<Room[]>('/rooms/')).data })
}
export function useGroups(status = 'active') {
  return useQuery({
    queryKey: ['groups', status],
    queryFn: async () => (await api.get<Group[]>('/groups/', { params: { status } })).data,
  })
}
export function useStudents(params: Record<string, string> = {}) {
  return useQuery({
    queryKey: ['students', params],
    queryFn: async () => (await api.get<Student[]>('/students/', { params })).data,
  })
}

export function StudentSelect({ value, onChange, disabled }: { value?: number; onChange?: (v: number) => void; disabled?: boolean }) {
  const { data = [], isLoading } = useStudents()
  return (
    <Select
      showSearch
      value={value}
      onChange={onChange}
      disabled={disabled}
      loading={isLoading}
      placeholder="O'quvchini tanlang"
      optionFilterProp="label"
      options={data.map((s) => ({
        value: s.id,
        label: `${s.full_name}${s.balance < 0 ? ` (qarz ${money(-s.balance)})` : ''}`,
      }))}
    />
  )
}
