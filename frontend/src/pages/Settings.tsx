import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, App, Button, Card, Col, Form, Input, InputNumber, Row, Skeleton } from 'antd'
import { useEffect } from 'react'
import { api, errorText } from '../api'
import { PageHead } from '../components/common'

const TEMPLATES: { key: string; label: string; vars: string }[] = [
  { key: 'tpl_absent', label: 'Darsga kelmadi', vars: '{center} {student} {date} {group}' },
  { key: 'tpl_late', label: 'Darsga kechikdi', vars: '{center} {student} {date} {group}' },
  { key: 'tpl_payment_soon', label: "To'lov eslatmasi (muddatdan oldin)", vars: '{center} {student} {month} {amount} {due}' },
  { key: 'tpl_payment_due', label: "To'lov muddati bugun", vars: '{center} {student} {month} {due} {debt}' },
  { key: 'tpl_payment_overdue', label: "To'lov kechikdi", vars: '{center} {student} {month} {debt}' },
  { key: 'tpl_payment_received', label: "To'lov qabul qilindi", vars: '{center} {student} {amount} {receipt} {balance}' },
]

const NUMBERS: { key: string; label: string; suffix: string }[] = [
  { key: 'payment_due_day', label: "Har oy to'lov muddati", suffix: '-kun' },
  { key: 'first_invoice_due_days', label: "Yangi o'quvchi uchun muddat", suffix: 'kun' },
  { key: 'reminder_days_before', label: 'Eslatma muddatdan oldin', suffix: 'kun' },
  { key: 'overdue_repeat_days', label: 'Kechikkanda har', suffix: 'kunda' },
  { key: 'attendance_open_before_min', label: 'Davomat ochiladi (darsdan oldin)', suffix: 'daqiqa' },
  { key: 'attendance_close_after_min', label: 'Davomat yopiladi (darsdan keyin)', suffix: 'daqiqa' },
]

export default function Settings() {
  const [form] = Form.useForm()
  const { message } = App.useApp()
  const qc = useQueryClient()
  const { data } = useQuery({ queryKey: ['settings'], queryFn: async () => (await api.get<Record<string, string>>('/settings/')).data })
  const { data: eskiz } = useQuery({
    queryKey: ['eskiz'],
    queryFn: async () => (await api.get<{ balance?: number; error?: string }>('/notifications/eskiz_balance/')).data,
    retry: false,
  })
  useEffect(() => {
    if (data) form.setFieldsValue(data)
  }, [data, form])

  const save = useMutation({
    mutationFn: async (v: object) => api.post('/settings/', v),
    onSuccess: () => {
      message.success('Sozlamalar saqlandi')
      qc.invalidateQueries({ queryKey: ['settings'] })
    },
    onError: (e) => message.error(errorText(e)),
  })

  if (!data) return <Skeleton active />
  return (
    <>
      <PageHead title="Sozlamalar" extra={<Button type="primary" onClick={() => form.submit()} loading={save.isPending}>Saqlash</Button>} />
      <Form form={form} layout="vertical" onFinish={save.mutate}>
        <Row gutter={[16, 16]}>
          <Col xs={24} xl={10}>
            <Card title="Umumiy" variant="borderless">
              <Form.Item name="center_name" label="Markaz nomi" extra="Xabarlar va chekda ko'rinadi">
                <Input />
              </Form.Item>
              <Row gutter={12}>
                {NUMBERS.map((n) => (
                  <Col span={12} key={n.key}>
                    <Form.Item name={n.key} label={n.label}>
                      <InputNumber min={0} style={{ width: '100%' }} addonAfter={n.suffix} stringMode />
                    </Form.Item>
                  </Col>
                ))}
              </Row>
            </Card>
            <Card title="SMS (Eskiz.uz)" variant="borderless" style={{ marginTop: 16 }}>
              {eskiz?.balance !== undefined ? (
                <Alert type="success" showIcon message={`Ulangan. Balans: ${eskiz.balance.toLocaleString('ru-RU')} so'm`} />
              ) : (
                <Alert type="warning" showIcon message={eskiz?.error ? `Ulanmadi: ${eskiz.error}` : 'Tekshirilmoqda...'} />
              )}
            </Card>
          </Col>
          <Col xs={24} xl={14}>
            <Card title="Xabar shablonlari" variant="borderless">
              <Alert type="warning" showIcon style={{ marginBottom: 16 }}
                message="Eskiz.uz faqat tasdiqlangan SMS matnlarini yuboradi. Shablonni o'zgartirsangiz, Eskiz kabinetida yangi matnni moderatsiyaga yuboring." />
              {TEMPLATES.map((t) => (
                <Form.Item key={t.key} name={t.key} label={t.label} extra={`O'zgaruvchilar: ${t.vars}`}>
                  <Input.TextArea autoSize={{ minRows: 2 }} />
                </Form.Item>
              ))}
            </Card>
          </Col>
        </Row>
      </Form>
    </>
  )
}
