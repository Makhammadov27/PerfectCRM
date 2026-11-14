import { useMutation, useQueryClient } from '@tanstack/react-query'
import { App, Form, Input, InputNumber, Modal, Segmented } from 'antd'
import { useEffect, useState } from 'react'
import { api, errorText } from '../api'
import type { Payment } from '../types'
import { StudentSelect, useStudents } from './common'
import ReceiptModal from './ReceiptModal'

export default function PaymentModal({
  open, onClose, studentId,
}: { open: boolean; onClose: () => void; studentId?: number }) {
  const [form] = Form.useForm()
  const { message } = App.useApp()
  const qc = useQueryClient()
  const [receiptId, setReceiptId] = useState<number | null>(null)
  const { data: students = [] } = useStudents()
  const selected = Form.useWatch('student', form)

  const debtOf = (id?: number) => {
    const st = students.find((s) => s.id === id)
    return st && st.balance < 0 ? -st.balance : undefined
  }

  useEffect(() => {
    if (open) form.setFieldsValue({ student: studentId, amount: debtOf(studentId), method: 'cash', note: '' })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, studentId, form])

  // Boshqa o'quvchi tanlansa — uning qarz summasini qo'yamiz
  useEffect(() => {
    if (open && selected && selected !== studentId) form.setFieldValue('amount', debtOf(selected))
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selected])

  const m = useMutation({
    mutationFn: async (v: object) => (await api.post<Payment>('/payments/', v)).data,
    onSuccess: (p) => {
      message.success("To'lov qabul qilindi")
      qc.invalidateQueries()
      onClose()
      setReceiptId(p.id)
    },
    onError: (e) => message.error(errorText(e)),
  })

  return (
    <>
      <Modal
        title="To'lov qabul qilish"
        open={open}
        onCancel={onClose}
        onOk={() => form.submit()}
        okText="Qabul qilish va chek"
        confirmLoading={m.isPending}
        destroyOnHidden
      >
        <Form form={form} layout="vertical" onFinish={(v) => m.mutate(v)} requiredMark={false}>
          <Form.Item name="student" label="O'quvchi" rules={[{ required: true, message: "O'quvchini tanlang" }]}>
            <StudentSelect disabled={!!studentId} />
          </Form.Item>
          <Form.Item name="amount" label="Summa" rules={[{ required: true, message: 'Summani kiriting' }]}>
            <InputNumber<number>
              style={{ width: '100%' }}
              min={1}
              step={25000}
              size="large"
              addonAfter="so'm"
              formatter={(v) => `${v ?? ''}`.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')}
              parser={(v) => Number((v ?? '').replace(/\s/g, ''))}
            />
          </Form.Item>
          <Form.Item name="method" label="To'lov usuli">
            <Segmented block options={[{ label: 'Naqd', value: 'cash' }, { label: 'Karta', value: 'card' }, { label: "O'tkazma", value: 'transfer' }]} />
          </Form.Item>
          <Form.Item name="note" label="Izoh">
            <Input placeholder="Ixtiyoriy" />
          </Form.Item>
        </Form>
      </Modal>
      <ReceiptModal paymentId={receiptId} onClose={() => setReceiptId(null)} />
    </>
  )
}
