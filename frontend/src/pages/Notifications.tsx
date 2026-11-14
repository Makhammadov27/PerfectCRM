import { useQuery } from '@tanstack/react-query'
import { Card, Segmented, Space, Table, Tag } from 'antd'
import { useState } from 'react'
import { api, type Paged } from '../api'
import { PageHead } from '../components/common'
import type { Notification } from '../types'
import { fmtDateTime, phone } from '../utils'

const KIND: Record<string, string> = {
  absent: 'Kelmadi', late: 'Kechikdi', payment_soon: 'Eslatma', payment_due: 'Muddat bugun',
  payment_overdue: 'Kechikkan to\'lov', payment_received: "To'lov qabul qilindi", other: 'Boshqa',
}
const STATUS: Record<string, { label: string; color: string }> = {
  pending: { label: 'Navbatda', color: 'default' },
  sent: { label: 'Yuborildi', color: 'green' },
  failed: { label: 'Xato', color: 'red' },
}

export default function Notifications() {
  const [status, setStatus] = useState('')
  const [channel, setChannel] = useState('')
  const [page, setPage] = useState(1)
  const params = { page, ...(status ? { status } : {}), ...(channel ? { channel } : {}) }
  const { data, isLoading } = useQuery({
    queryKey: ['notifications', params],
    queryFn: async () => (await api.get<Paged<Notification>>('/notifications/', { params })).data,
    refetchInterval: 15000,
  })

  return (
    <>
      <PageHead title="Xabarlar" sub="Ota-onalarga yuborilgan Telegram va SMS xabarlar" />
      <Card variant="borderless">
        <Space wrap style={{ marginBottom: 16 }}>
          <Segmented value={status} onChange={(v) => { setStatus(v as string); setPage(1) }}
            options={[{ label: 'Hammasi', value: '' }, { label: 'Yuborildi', value: 'sent' }, { label: 'Navbatda', value: 'pending' }, { label: 'Xato', value: 'failed' }]} />
          <Segmented value={channel} onChange={(v) => { setChannel(v as string); setPage(1) }}
            options={[{ label: 'Barcha kanal', value: '' }, { label: 'Telegram', value: 'telegram' }, { label: 'SMS', value: 'sms' }]} />
        </Space>
        <Table<Notification>
          rowKey="id" loading={isLoading} dataSource={data?.results} scroll={{ x: 900 }}
          pagination={{ current: page, pageSize: 50, total: data?.count, onChange: setPage, showSizeChanger: false }}
          expandable={{ expandedRowRender: (r) => <div style={{ whiteSpace: 'pre-wrap' }}>{r.text}{r.error && <div style={{ color: 'red', marginTop: 8 }}>{r.error}</div>}</div> }}
          columns={[
            { title: 'Vaqt', dataIndex: 'created_at', render: fmtDateTime, width: 150 },
            { title: 'Kimga', render: (_, r) => <>{r.parent_name}<div style={{ fontSize: 12, opacity: 0.7 }}>{phone(r.parent_phone)}</div></> },
            { title: "O'quvchi", dataIndex: 'student_name' },
            { title: 'Turi', dataIndex: 'kind', render: (v) => KIND[v] ?? v },
            { title: 'Kanal', dataIndex: 'channel', render: (v) => <Tag color={v === 'telegram' ? 'blue' : 'purple'}>{v === 'telegram' ? 'Telegram' : 'SMS'}</Tag> },
            { title: 'Holat', dataIndex: 'status', render: (v) => <Tag color={STATUS[v].color}>{STATUS[v].label}</Tag> },
          ]}
        />
      </Card>
    </>
  )
}
