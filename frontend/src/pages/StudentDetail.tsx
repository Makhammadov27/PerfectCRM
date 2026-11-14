import {
  ArrowLeftOutlined, DollarOutlined, EditOutlined, MoreOutlined, PlusOutlined, PrinterOutlined, RollbackOutlined,
} from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Button, Card, Col, Descriptions, Dropdown, Empty, Row, Skeleton, Space, Table, Tabs, Tag, theme } from 'antd'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { Balance } from '../components/common'
import { CancelPaymentModal, DiscountModal, EnrollModal, LeaveModal, RefundModal } from '../components/EnrollmentModals'
import PaymentModal from '../components/PaymentModal'
import ReceiptModal from '../components/ReceiptModal'
import StudentForm from '../components/StudentForm'
import type { AttendanceStatus, Enrollment, Invoice, Payment, Refund, Student } from '../types'
import { ATTENDANCE, INVOICE_STATUS, METHOD, fmtDate, fmtDateTime, money, monthLabel, phone } from '../utils'

type Details = {
  student: Student
  enrollments: Enrollment[]
  invoices: Invoice[]
  payments: Payment[]
  refunds: Refund[]
  attendance: { id: number; date: string; group_name: string; status: AttendanceStatus }[]
}

export default function StudentDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const { token } = theme.useToken()
  const [edit, setEdit] = useState(false)
  const [pay, setPay] = useState(false)
  const [enroll, setEnroll] = useState(false)
  const [refund, setRefund] = useState(false)
  const [leave, setLeave] = useState<Enrollment | null>(null)
  const [discount, setDiscount] = useState<Enrollment | null>(null)
  const [receipt, setReceipt] = useState<number | null>(null)
  const [cancelPay, setCancelPay] = useState<Payment | null>(null)

  const { data, isLoading } = useQuery({
    queryKey: ['student', Number(id)],
    queryFn: async () => (await api.get<Details>(`/students/${id}/details/`)).data,
  })
  if (isLoading || !data) return <Skeleton active paragraph={{ rows: 12 }} />
  const s = data.student
  const attStats = data.attendance.reduce<Record<string, number>>((a, r) => ({ ...a, [r.status]: (a[r.status] || 0) + 1 }), {})
  const attRate = data.attendance.length
    ? Math.round((((attStats.present || 0) + (attStats.late || 0)) * 100) / data.attendance.length)
    : null

  return (
    <>
      <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => nav(-1)} style={{ marginBottom: 8 }}>
        Orqaga
      </Button>
      <Card variant="borderless">
        <Row gutter={[24, 16]} align="middle">
          <Col flex="auto">
            <Space align="center" size={16}>
              <div className="stat-icon" style={{ background: `${token.colorPrimary}1A`, color: token.colorPrimary, width: 56, height: 56, fontSize: 22, fontWeight: 700 }}>
                {s.full_name[0]}
              </div>
              <div>
                <div style={{ fontSize: 22, fontWeight: 700 }}>
                  {s.full_name} {s.status === 'left' && <Tag>Ketgan</Tag>}
                </div>
                <div style={{ color: token.colorTextSecondary }}>
                  {s.groups.map((g) => g.name).join(', ') || "Guruhga qo'shilmagan"}
                </div>
              </div>
            </Space>
          </Col>
          <Col>
            <div style={{ color: token.colorTextSecondary, fontSize: 13 }}>Balans</div>
            <div style={{ fontSize: 20 }}>
              <Balance value={s.balance} />
            </div>
          </Col>
          <Col>
            <Space wrap>
              <Button type="primary" icon={<DollarOutlined />} onClick={() => setPay(true)}>To'lov</Button>
              <Button icon={<PlusOutlined />} onClick={() => setEnroll(true)}>Guruhga qo'shish</Button>
              <Button icon={<EditOutlined />} onClick={() => setEdit(true)}>Tahrirlash</Button>
              {s.balance > 0 && <Button icon={<RollbackOutlined />} onClick={() => setRefund(true)}>Pul qaytarish</Button>}
            </Space>
          </Col>
        </Row>
        <Descriptions size="small" column={{ xs: 1, md: 3 }} style={{ marginTop: 20 }}>
          <Descriptions.Item label="Davomat">{attRate === null ? '—' : `${attRate}% (oxirgi ${data.attendance.length} dars)`}</Descriptions.Item>
          {s.parents.map((p) => (
            <Descriptions.Item key={p.id} label={p.full_name}>
              {phone(p.phone)}&nbsp;
              {p.telegram_linked ? <Tag color="blue" bordered={false}>Telegram</Tag> : <Tag bordered={false}>SMS</Tag>}
            </Descriptions.Item>
          ))}
          {s.note && <Descriptions.Item label="Izoh">{s.note}</Descriptions.Item>}
        </Descriptions>
      </Card>

      <Card variant="borderless" style={{ marginTop: 16 }}>
        <Tabs
          items={[
            {
              key: 'groups',
              label: `Guruhlar (${data.enrollments.length})`,
              children: (
                <Table<Enrollment>
                  rowKey="id" dataSource={data.enrollments} pagination={false} scroll={{ x: 600 }}
                  columns={[
                    { title: 'Guruh', dataIndex: 'group_name', render: (v, r) => <a onClick={() => nav(`/groups/${r.group}`)}>{v}</a> },
                    { title: "Qo'shilgan", dataIndex: 'joined_at', render: fmtDate },
                    { title: 'Chiqqan', dataIndex: 'left_at', render: (v) => (v ? fmtDate(v) : <Tag color="green">O'qiyapti</Tag>) },
                    {
                      title: 'Chegirma',
                      render: (_, r) => r.discount_type === 'none' ? '—'
                        : r.discount_type === 'percent' ? `${r.discount_value}%` : money(r.discount_value),
                    },
                    {
                      title: '', width: 50,
                      render: (_, r) => !r.left_at && (
                        <Dropdown trigger={['click']} menu={{
                          items: [
                            { key: 'd', label: 'Chegirma', onClick: () => setDiscount(r) },
                            { key: 'l', label: 'Guruhdan chiqarish', danger: true, onClick: () => setLeave(r) },
                          ],
                        }}>
                          <Button type="text" icon={<MoreOutlined />} />
                        </Dropdown>
                      ),
                    },
                  ]}
                />
              ),
            },
            {
              key: 'invoices',
              label: 'Oylik hisoblar',
              children: (
                <Table<Invoice>
                  rowKey="id" dataSource={data.invoices} pagination={false} scroll={{ x: 700 }}
                  columns={[
                    { title: 'Oy', dataIndex: 'period', render: monthLabel },
                    { title: 'Guruh', dataIndex: 'group_name' },
                    { title: 'Darslar', dataIndex: 'lessons_count', align: 'center' },
                    { title: 'Summa', dataIndex: 'amount', align: 'right', render: (v, r) => (
                      <>
                        {money(v)}
                        {r.discount_amount > 0 && <div style={{ fontSize: 12, color: token.colorTextSecondary }}>chegirma {money(r.discount_amount)}</div>}
                      </>
                    ) },
                    { title: "To'langan", dataIndex: 'paid_amount', align: 'right', render: money },
                    { title: 'Muddat', dataIndex: 'due_date', render: fmtDate },
                    { title: 'Holat', dataIndex: 'status', render: (v) => <Tag color={INVOICE_STATUS[v].color}>{INVOICE_STATUS[v].label}</Tag> },
                  ]}
                />
              ),
            },
            {
              key: 'payments',
              label: `To'lovlar (${data.payments.length})`,
              children: (
                <Table<Payment>
                  rowKey="id" dataSource={data.payments} pagination={false} scroll={{ x: 700 }}
                  rowClassName={(r) => (r.cancelled_at ? 'ant-table-row-disabled' : '')}
                  columns={[
                    { title: 'Chek', dataIndex: 'receipt_no' },
                    { title: 'Sana', dataIndex: 'paid_at', render: fmtDateTime },
                    { title: 'Summa', dataIndex: 'amount', align: 'right', render: (v, r) => r.cancelled_at ? <s>{money(v)}</s> : <b>{money(v)}</b> },
                    { title: 'Usul', dataIndex: 'method', render: (v) => METHOD[v] },
                    { title: 'Holat', render: (_, r) => r.cancelled_at ? <Tag color="red" title={r.cancel_reason}>Bekor: {r.cancel_reason}</Tag> : <Tag color="green">Faol</Tag> },
                    {
                      title: '', width: 90,
                      render: (_, r) => (
                        <Space>
                          <Button size="small" icon={<PrinterOutlined />} onClick={() => setReceipt(r.id)} />
                          {!r.cancelled_at && <Button size="small" danger onClick={() => setCancelPay(r)}>Bekor</Button>}
                        </Space>
                      ),
                    },
                  ]}
                />
              ),
            },
            {
              key: 'attendance',
              label: 'Davomat',
              children: data.attendance.length ? (
                <Table
                  rowKey="id" dataSource={data.attendance} pagination={{ pageSize: 20 }} size="small"
                  columns={[
                    { title: 'Sana', dataIndex: 'date', render: fmtDate },
                    { title: 'Guruh', dataIndex: 'group_name' },
                    { title: 'Holat', dataIndex: 'status', render: (v: AttendanceStatus) => <Tag color={ATTENDANCE[v].color}>{ATTENDANCE[v].label}</Tag> },
                  ]}
                />
              ) : <Empty description="Davomat yo'q" />,
            },
            ...(data.refunds.length ? [{
              key: 'refunds',
              label: 'Qaytarilgan pullar',
              children: (
                <Table<Refund>
                  rowKey="id" dataSource={data.refunds} pagination={false}
                  columns={[
                    { title: 'Sana', dataIndex: 'paid_at', render: fmtDateTime },
                    { title: 'Summa', dataIndex: 'amount', render: money },
                    { title: 'Sabab', dataIndex: 'reason' },
                    { title: 'Berdi', dataIndex: 'given_by_name' },
                  ]}
                />
              ),
            }] : []),
          ]}
        />
      </Card>

      <StudentForm open={edit} onClose={() => setEdit(false)} student={s} />
      <PaymentModal open={pay} onClose={() => setPay(false)} studentId={s.id} />
      <EnrollModal open={enroll} onClose={() => setEnroll(false)} studentId={s.id} />
      <LeaveModal enrollment={leave} onClose={() => setLeave(null)} />
      <DiscountModal enrollment={discount} onClose={() => setDiscount(null)} />
      <RefundModal open={refund} onClose={() => setRefund(false)} studentId={s.id} max={s.balance} />
      <ReceiptModal paymentId={receipt} onClose={() => setReceipt(null)} />
      <CancelPaymentModal payment={cancelPay} onClose={() => setCancelPay(null)} />
    </>
  )
}
