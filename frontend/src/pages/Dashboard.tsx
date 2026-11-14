import {
  AppstoreOutlined, CheckCircleOutlined, DollarOutlined, RiseOutlined, UserOutlined, WarningOutlined,
} from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Button, Card, Col, Empty, List, Progress, Row, Skeleton, Tag, theme } from 'antd'
import dayjs from 'dayjs'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Area, AreaChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { MonthPicker, PageHead, StatCard, monthParam, thisMonth } from '../components/common'
import PaymentModal from '../components/PaymentModal'
import { fmtTime, money, moneyShort, monthLabel } from '../utils'

type Dash = {
  students_active: number
  groups_active: number
  teachers_active: number
  income: number
  refunds: number
  salaries: number
  net: number
  expected: number
  collected: number
  total_debt: number
  overdue_debt: number
  debtors_count: number
  attendance_rate: number | null
  income_by_day: { date: string; amount: number }[]
  income_by_method: { method: string; label: string; amount: number }[]
  today_lessons: {
    id: number
    group_name: string
    teacher_name: string
    room_name: string
    start_time: string
    end_time: string
    attendance_taken: boolean
    kind: string
  }[]
}

export default function Dashboard() {
  const [month, setMonth] = useState(thisMonth())
  const [payOpen, setPayOpen] = useState(false)
  const nav = useNavigate()
  const { token } = theme.useToken()
  const { data, isLoading } = useQuery({
    queryKey: ['dashboard', monthParam(month)],
    queryFn: async () => (await api.get<Dash>('/reports/dashboard/', { params: { month: monthParam(month) } })).data,
  })

  const collectedPct = data?.expected ? Math.round((data.collected * 100) / data.expected) : 0

  return (
    <>
      <PageHead
        title="Bosh sahifa"
        sub={monthLabel(month)}
        extra={
          <>
            <MonthPicker value={month} onChange={setMonth} />
            <Button type="primary" icon={<DollarOutlined />} onClick={() => setPayOpen(true)}>
              To'lov qabul qilish
            </Button>
          </>
        }
      />
      {isLoading || !data ? (
        <Skeleton active paragraph={{ rows: 10 }} />
      ) : (
        <>
          <Row gutter={[16, 16]}>
            <Col xs={24} sm={12} xl={6}>
              <StatCard icon={<RiseOutlined />} color="#4F46E5" label="Oy tushumi" value={money(data.income)}
                hint={`Sof: ${money(data.net)}`} />
            </Col>
            <Col xs={24} sm={12} xl={6}>
              <StatCard icon={<WarningOutlined />} color="#DC2626" label="Umumiy qarz" value={money(data.total_debt)}
                hint={`${data.debtors_count} ta o'quvchining muddati o'tgan`} />
            </Col>
            <Col xs={24} sm={12} xl={6}>
              <StatCard icon={<UserOutlined />} color="#0891B2" label="Faol o'quvchilar" value={data.students_active}
                hint={`${data.groups_active} guruh · ${data.teachers_active} o'qituvchi`} />
            </Col>
            <Col xs={24} sm={12} xl={6}>
              <StatCard icon={<CheckCircleOutlined />} color="#16A34A" label="Davomat"
                value={data.attendance_rate === null ? '—' : `${data.attendance_rate}%`} hint="Kelganlar ulushi" />
            </Col>
          </Row>

          <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
            <Col xs={24} xl={16}>
              <Card title="Kunlik tushum" variant="borderless">
                <ResponsiveContainer width="100%" height={280}>
                  <AreaChart data={data.income_by_day} margin={{ left: 0, right: 8, top: 8 }}>
                    <defs>
                      <linearGradient id="inc" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor={token.colorPrimary} stopOpacity={0.3} />
                        <stop offset="100%" stopColor={token.colorPrimary} stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid vertical={false} stroke={token.colorBorderSecondary} />
                    <XAxis dataKey="date" tickFormatter={(d) => dayjs(d).format('D')} tick={{ fontSize: 12, fill: token.colorTextSecondary }}
                      axisLine={false} tickLine={false} />
                    <YAxis tickFormatter={moneyShort} tick={{ fontSize: 12, fill: token.colorTextSecondary }} axisLine={false}
                      tickLine={false} width={56} />
                    <Tooltip
                      formatter={(v: number) => [money(v), 'Tushum']}
                      labelFormatter={(d) => dayjs(d).format('DD.MM.YYYY')}
                      contentStyle={{ borderRadius: 10, border: 'none', background: token.colorBgElevated, boxShadow: token.boxShadow }}
                    />
                    <Area type="monotone" dataKey="amount" stroke={token.colorPrimary} strokeWidth={2} fill="url(#inc)" />
                  </AreaChart>
                </ResponsiveContainer>
              </Card>
            </Col>
            <Col xs={24} xl={8}>
              <Card title="Oy rejasi" variant="borderless" style={{ height: '100%' }}>
                <div style={{ textAlign: 'center', marginBottom: 16 }}>
                  <Progress type="dashboard" percent={collectedPct} size={150} strokeColor={token.colorPrimary} />
                </div>
                <Row justify="space-between" style={{ marginBottom: 8 }}>
                  <span style={{ color: token.colorTextSecondary }}>Hisoblangan</span>
                  <b>{money(data.expected)}</b>
                </Row>
                <Row justify="space-between" style={{ marginBottom: 16 }}>
                  <span style={{ color: token.colorTextSecondary }}>Yig'ilgan</span>
                  <b>{money(data.collected)}</b>
                </Row>
                {data.income_by_method.map((m) => (
                  <Row key={m.method} justify="space-between" style={{ marginBottom: 6 }}>
                    <Tag>{m.label}</Tag>
                    <span>{money(m.amount)}</span>
                  </Row>
                ))}
              </Card>
            </Col>
          </Row>

          <Card
            title="Bugungi darslar"
            variant="borderless"
            style={{ marginTop: 16 }}
            extra={<Button type="link" onClick={() => nav('/schedule')}>Jadval</Button>}
          >
            {data.today_lessons.length === 0 ? (
              <Empty description="Bugun dars yo'q" />
            ) : (
              <List
                dataSource={data.today_lessons}
                renderItem={(l) => (
                  <List.Item
                    extra={
                      l.attendance_taken ? <Tag color="green">Davomat olindi</Tag> : <Tag color="default">Kutilmoqda</Tag>
                    }
                  >
                    <List.Item.Meta
                      avatar={
                        <div className="stat-icon" style={{ background: `${token.colorPrimary}14`, color: token.colorPrimary, width: 40, height: 40 }}>
                          <AppstoreOutlined />
                        </div>
                      }
                      title={
                        <>
                          {fmtTime(l.start_time)}–{fmtTime(l.end_time)} · {l.group_name}{' '}
                          {l.kind === 'makeup' && <Tag color="orange">Qo'shimcha</Tag>}
                        </>
                      }
                      description={`${l.teacher_name} · ${l.room_name}`}
                    />
                  </List.Item>
                )}
              />
            )}
          </Card>
        </>
      )}
      <PaymentModal open={payOpen} onClose={() => setPayOpen(false)} />
    </>
  )
}
