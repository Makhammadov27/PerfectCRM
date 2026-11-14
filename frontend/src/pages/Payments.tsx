import { DollarOutlined, FileExcelOutlined, PrinterOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Button, Card, DatePicker, Input, Select, Space, Table, Tag, theme } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, download, type Paged } from '../api'
import { PageHead } from '../components/common'
import { CancelPaymentModal } from '../components/EnrollmentModals'
import PaymentModal from '../components/PaymentModal'
import ReceiptModal from '../components/ReceiptModal'
import type { Payment } from '../types'
import { METHOD, fmtDateTime, money } from '../utils'

export default function Payments() {
  const nav = useNavigate()
  const { token } = theme.useToken()
  const [range, setRange] = useState<[Dayjs, Dayjs]>([dayjs().startOf('month'), dayjs()])
  const [method, setMethod] = useState<string>()
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [payOpen, setPayOpen] = useState(false)
  const [receipt, setReceipt] = useState<number | null>(null)
  const [cancel, setCancel] = useState<Payment | null>(null)

  const params = {
    page, date_from: range[0].format('YYYY-MM-DD'), date_to: range[1].format('YYYY-MM-DD'),
    ...(method ? { method } : {}), ...(search ? { search } : {}),
  }
  const { data, isLoading } = useQuery({
    queryKey: ['payments', params],
    queryFn: async () => (await api.get<Paged<Payment>>('/payments/', { params })).data,
  })
  const total = (data?.results ?? []).filter((p) => !p.cancelled_at).reduce((a, p) => a + p.amount, 0)

  return (
    <>
      <PageHead
        title="To'lovlar"
        sub={data ? `${data.count} ta to'lov` : undefined}
        extra={
          <>
            <Button icon={<FileExcelOutlined />} onClick={() => download(`/reports/export/payments/?month=${range[0].format('YYYY-MM')}`, `tolovlar-${range[0].format('YYYY-MM')}.xlsx`)}>
              Excel
            </Button>
            <Button type="primary" icon={<DollarOutlined />} onClick={() => setPayOpen(true)}>To'lov qabul qilish</Button>
          </>
        }
      />
      <Card variant="borderless">
        <Space wrap style={{ marginBottom: 16 }}>
          <DatePicker.RangePicker value={range} format="DD.MM.YYYY" allowClear={false}
            onChange={(v) => { if (v?.[0] && v[1]) { setRange([v[0], v[1]]); setPage(1) } }} />
          <Select allowClear placeholder="Usul" style={{ width: 140 }} value={method} onChange={(v) => { setMethod(v); setPage(1) }}
            options={Object.entries(METHOD).map(([value, label]) => ({ value, label }))} />
          <Input.Search allowClear placeholder="O'quvchi yoki chek №" style={{ width: 240 }}
            onSearch={(v) => { setSearch(v); setPage(1) }} />
        </Space>
        <Table<Payment>
          rowKey="id" loading={isLoading} dataSource={data?.results} scroll={{ x: 900 }}
          pagination={{ current: page, pageSize: 50, total: data?.count, onChange: setPage, showSizeChanger: false }}
          summary={() => data?.results.length ? (
            <Table.Summary.Row>
              <Table.Summary.Cell index={0} colSpan={3}><b>Sahifadagi jami (bekor qilinganlarsiz)</b></Table.Summary.Cell>
              <Table.Summary.Cell index={3} align="right"><b style={{ color: token.colorPrimary }}>{money(total)}</b></Table.Summary.Cell>
              <Table.Summary.Cell index={4} colSpan={4} />
            </Table.Summary.Row>
          ) : null}
          columns={[
            { title: 'Chek', dataIndex: 'receipt_no', width: 110 },
            { title: 'Sana', dataIndex: 'paid_at', render: fmtDateTime, width: 150 },
            { title: "O'quvchi", dataIndex: 'student_name', render: (v, r) => <a onClick={() => nav(`/students/${r.student}`)}>{v}</a> },
            { title: 'Summa', dataIndex: 'amount', align: 'right', render: (v, r) => r.cancelled_at ? <s>{money(v)}</s> : <b>{money(v)}</b> },
            { title: 'Usul', dataIndex: 'method', render: (v) => <Tag bordered={false}>{METHOD[v]}</Tag> },
            { title: 'Qabul qildi', dataIndex: 'received_by_name', responsive: ['lg'] },
            { title: 'Holat', render: (_, r) => r.cancelled_at ? <Tag color="red" title={r.cancel_reason}>Bekor qilingan</Tag> : <Tag color="green">Faol</Tag> },
            {
              title: '', width: 110,
              render: (_, r) => (
                <Space>
                  <Button size="small" icon={<PrinterOutlined />} onClick={() => setReceipt(r.id)} />
                  {!r.cancelled_at && <Button size="small" danger onClick={() => setCancel(r)}>Bekor</Button>}
                </Space>
              ),
            },
          ]}
        />
      </Card>
      <PaymentModal open={payOpen} onClose={() => setPayOpen(false)} />
      <ReceiptModal paymentId={receipt} onClose={() => setReceipt(null)} />
      <CancelPaymentModal payment={cancel} onClose={() => setCancel(null)} />
    </>
  )
}
