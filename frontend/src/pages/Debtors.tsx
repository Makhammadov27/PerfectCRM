import { DollarOutlined, FileExcelOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Button, Card, Col, Row, Table, Tag } from 'antd'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, download } from '../api'
import { PageHead, StatCard } from '../components/common'
import PaymentModal from '../components/PaymentModal'
import type { Debtor } from '../types'
import { fmtDate, money, phone } from '../utils'

export default function Debtors() {
  const nav = useNavigate()
  const [payFor, setPayFor] = useState<number>()
  const { data = [], isLoading } = useQuery({
    queryKey: ['debtors'],
    queryFn: async () => (await api.get<Debtor[]>('/reports/debtors/')).data,
  })
  const total = data.reduce((a, r) => a + r.debt, 0)
  const overdue = data.reduce((a, r) => a + r.overdue_debt, 0)

  return (
    <>
      <PageHead
        title="Qarzdorlar"
        sub="To'lanmagan oylik hisoblar bo'yicha"
        extra={<Button icon={<FileExcelOutlined />} onClick={() => download('/reports/export/debtors/', 'qarzdorlar.xlsx')}>Excel</Button>}
      />
      <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
        <Col xs={24} md={8}><StatCard icon="Σ" color="#DC2626" label="Jami qarz" value={money(total)} /></Col>
        <Col xs={24} md={8}><StatCard icon="!" color="#D97706" label="Muddati o'tgan" value={money(overdue)} /></Col>
        <Col xs={24} md={8}><StatCard icon="#" color="#4F46E5" label="O'quvchilar" value={data.length} /></Col>
      </Row>
      <Card variant="borderless">
        <Table<Debtor>
          rowKey="student_id" loading={isLoading} dataSource={data} scroll={{ x: 900 }} pagination={{ pageSize: 30 }}
          columns={[
            { title: "O'quvchi", dataIndex: 'student_name', render: (v, r) => <a onClick={() => nav(`/students/${r.student_id}`)}><b>{v}</b></a> },
            { title: 'Guruhlar', dataIndex: 'groups', render: (gs: string[]) => gs.map((g) => <Tag key={g}>{g}</Tag>) },
            { title: 'Ota-ona', dataIndex: 'parent_phones', render: (ps: string[]) => ps.map((p) => <div key={p}>{phone(p)}</div>) },
            { title: 'Qarz', dataIndex: 'debt', align: 'right', sorter: (a, b) => a.debt - b.debt, render: (v) => <b>{money(v)}</b> },
            { title: 'Muddat', dataIndex: 'oldest_due', render: fmtDate },
            {
              title: 'Kechikish', dataIndex: 'days_overdue', sorter: (a, b) => a.days_overdue - b.days_overdue,
              render: (d: number) => d > 0 ? <Tag color={d > 10 ? 'red' : 'orange'}>{d} kun</Tag> : <Tag>Muddat kelmagan</Tag>,
            },
            { title: '', render: (_, r) => <Button size="small" type="primary" ghost icon={<DollarOutlined />} onClick={() => setPayFor(r.student_id)}>To'lov</Button> },
          ]}
        />
      </Card>
      <PaymentModal open={!!payFor} onClose={() => setPayFor(undefined)} studentId={payFor} />
    </>
  )
}
