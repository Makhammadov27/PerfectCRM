import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Alert, App, DatePicker, Form, Input, InputNumber, Modal, Select } from 'antd'
import dayjs from 'dayjs'
import { useEffect } from 'react'
import { api, errorText } from '../api'
import type { Enrollment, Payment } from '../types'
import { money } from '../utils'
import { StudentSelect, useGroups } from './common'

const moneyInput = {
  style: { width: '100%' },
  formatter: (v: number | string | undefined) => `${v ?? ''}`.replace(/\B(?=(\d{3})+(?!\d))/g, ' '),
  parser: (v: string | undefined) => Number((v ?? '').replace(/\s/g, '')),
}

function DiscountFields() {
  const type = Form.useWatch('discount_type')
  return (
    <>
      <Form.Item name="discount_type" label="Chegirma" initialValue="none">
        <Select options={[{ value: 'none', label: "Yo'q" }, { value: 'percent', label: 'Foiz (%)' }, { value: 'fixed', label: "Qat'iy summa (oyiga)" }]} />
      </Form.Item>
      {type && type !== 'none' && (
        <>
          <Form.Item name="discount_value" label={type === 'percent' ? 'Foiz' : 'Summa'} rules={[{ required: true }]}>
            <InputNumber<number> min={0} max={type === 'percent' ? 100 : undefined} {...moneyInput} />
          </Form.Item>
          <Form.Item name="discount_reason" label="Sababi">
            <Input placeholder="Masalan: aka-uka" />
          </Form.Item>
        </>
      )}
    </>
  )
}

/** O'quvchini guruhga qo'shish. groupId yoki studentId oldindan berilishi mumkin. */
export function EnrollModal({
  open, onClose, studentId, groupId,
}: { open: boolean; onClose: () => void; studentId?: number; groupId?: number }) {
  const [form] = Form.useForm()
  const { message } = App.useApp()
  const qc = useQueryClient()
  const { data: groups = [] } = useGroups()

  useEffect(() => {
    if (open) form.setFieldsValue({ student: studentId, group: groupId, joined_at: dayjs(), discount_type: 'none' })
  }, [open, studentId, groupId, form])

  const m = useMutation({
    mutationFn: async (v: Record<string, unknown>) =>
      api.post(`/groups/${v.group}/enroll/`, { ...v, joined_at: (v.joined_at as dayjs.Dayjs).format('YYYY-MM-DD') }),
    onSuccess: () => {
      message.success("Guruhga qo'shildi, hisob yaratildi")
      qc.invalidateQueries()
      onClose()
    },
    onError: (e) => message.error(errorText(e)),
  })

  const groupId_ = Form.useWatch('group', form)
  const selectedGroup = groups.find((g) => g.id === groupId_)

  return (
    <Modal title="Guruhga qo'shish" open={open} onCancel={onClose} onOk={() => form.submit()} confirmLoading={m.isPending} okText="Qo'shish">
      <Form form={form} layout="vertical" onFinish={m.mutate} requiredMark={false}>
        <Form.Item name="student" label="O'quvchi" rules={[{ required: true }]}>
          <StudentSelect disabled={!!studentId} />
        </Form.Item>
        <Form.Item name="group" label="Guruh" rules={[{ required: true, message: 'Guruhni tanlang' }]}>
          <Select disabled={!!groupId} showSearch optionFilterProp="label"
            options={groups.map((g) => ({ value: g.id, label: `${g.name} — ${g.teacher_name}` }))} />
        </Form.Item>
        <Form.Item name="joined_at" label="Qo'shilgan sana" rules={[{ required: true }]}
          extra="Oy o'rtasida qo'shilsa: qolgan darslar × dars narxi hisoblanadi">
          <DatePicker style={{ width: '100%' }} format="DD.MM.YYYY" />
        </Form.Item>
        {selectedGroup && (
          <Alert type="info" showIcon style={{ marginBottom: 16 }}
            message={`Oylik: ${money(selectedGroup.monthly_price)} · Bitta dars: ${money(selectedGroup.lesson_price)}`} />
        )}
        <DiscountFields />
      </Form>
    </Modal>
  )
}

export function DiscountModal({ enrollment, onClose }: { enrollment: Enrollment | null; onClose: () => void }) {
  const [form] = Form.useForm()
  const { message } = App.useApp()
  const qc = useQueryClient()
  useEffect(() => {
    if (enrollment) form.setFieldsValue(enrollment)
  }, [enrollment, form])
  const m = useMutation({
    mutationFn: async (v: object) => api.post(`/enrollments/${enrollment!.id}/discount/`, v),
    onSuccess: () => {
      message.success('Chegirma saqlandi. Joriy oy hisobi qayta hisoblandi')
      qc.invalidateQueries()
      onClose()
    },
    onError: (e) => message.error(errorText(e)),
  })
  return (
    <Modal title={`Chegirma — ${enrollment?.group_name ?? ''}`} open={!!enrollment} onCancel={onClose} onOk={() => form.submit()}
      confirmLoading={m.isPending}>
      <Form form={form} layout="vertical" onFinish={m.mutate}>
        <DiscountFields />
      </Form>
    </Modal>
  )
}

export function LeaveModal({ enrollment, onClose }: { enrollment: Enrollment | null; onClose: () => void }) {
  const [form] = Form.useForm()
  const { message, modal } = App.useApp()
  const qc = useQueryClient()
  useEffect(() => {
    if (enrollment) form.setFieldsValue({ left_at: dayjs() })
  }, [enrollment, form])
  const m = useMutation({
    mutationFn: async (v: { left_at: dayjs.Dayjs }) =>
      (await api.post<{ refundable: number }>(`/enrollments/${enrollment!.id}/leave/`, { left_at: v.left_at.format('YYYY-MM-DD') })).data,
    onSuccess: (r) => {
      qc.invalidateQueries()
      const studentId = enrollment!.student
      onClose()
      if (r.refundable > 0) {
        modal.info({
          title: 'Guruhdan chiqarildi',
          content: `O'quvchiga qaytarish mumkin bo'lgan summa: ${money(r.refundable)}. Pulni berganingizdan keyin "Pul qaytarish" tugmasi orqali qayd eting.`,
        })
      } else message.success('Guruhdan chiqarildi')
      void studentId
    },
    onError: (e) => message.error(errorText(e)),
  })
  return (
    <Modal title={`Guruhdan chiqarish — ${enrollment?.group_name ?? ''}`} open={!!enrollment} onCancel={onClose}
      onOk={() => form.submit()} okText="Chiqarish" okButtonProps={{ danger: true }} confirmLoading={m.isPending}>
      <Form form={form} layout="vertical" onFinish={m.mutate}>
        <Form.Item name="left_at" label="Oxirgi dars sanasi" rules={[{ required: true }]}
          extra="Shu kungacha bo'lgan darslar uchun pul olinadi, ortiqchasi qaytariladi">
          <DatePicker style={{ width: '100%' }} format="DD.MM.YYYY" />
        </Form.Item>
      </Form>
    </Modal>
  )
}

export function RefundModal({
  open, onClose, studentId, max,
}: { open: boolean; onClose: () => void; studentId: number; max: number }) {
  const [form] = Form.useForm()
  const { message } = App.useApp()
  const qc = useQueryClient()
  useEffect(() => {
    if (open) form.setFieldsValue({ amount: max > 0 ? max : undefined, reason: '' })
  }, [open, max, form])
  const m = useMutation({
    mutationFn: async (v: object) => api.post('/refunds/', { ...v, student: studentId }),
    onSuccess: () => {
      message.success('Qaytarish qayd etildi')
      qc.invalidateQueries()
      onClose()
    },
    onError: (e) => message.error(errorText(e)),
  })
  return (
    <Modal title="Pul qaytarish" open={open} onCancel={onClose} onOk={() => form.submit()} confirmLoading={m.isPending}>
      <Alert type="info" showIcon style={{ marginBottom: 16 }} message={`Qaytarish mumkin: ${money(Math.max(0, max))}`} />
      <Form form={form} layout="vertical" onFinish={m.mutate} requiredMark={false}>
        <Form.Item name="amount" label="Summa" rules={[{ required: true }]}>
          <InputNumber<number> min={1} max={max} addonAfter="so'm" {...moneyInput} />
        </Form.Item>
        <Form.Item name="reason" label="Sabab" rules={[{ required: true, message: 'Sababni yozing' }]}>
          <Input placeholder="Masalan: guruhdan ketdi" />
        </Form.Item>
      </Form>
    </Modal>
  )
}

export function CancelPaymentModal({ payment, onClose }: { payment: Payment | null; onClose: () => void }) {
  const [form] = Form.useForm()
  const { message } = App.useApp()
  const qc = useQueryClient()
  const m = useMutation({
    mutationFn: async (v: object) => api.post(`/payments/${payment!.id}/cancel/`, v),
    onSuccess: () => {
      message.success("To'lov bekor qilindi")
      qc.invalidateQueries()
      form.resetFields()
      onClose()
    },
    onError: (e) => message.error(errorText(e)),
  })
  return (
    <Modal title={`To'lovni bekor qilish — chek ${payment?.receipt_no ?? ''}`} open={!!payment} onCancel={onClose}
      onOk={() => form.submit()} okText="Bekor qilish" okButtonProps={{ danger: true }} confirmLoading={m.isPending}>
      <Alert type="warning" showIcon style={{ marginBottom: 16 }}
        message={`${payment?.student_name}: ${money(payment?.amount)}. To'lov o'chirilmaydi — "bekor qilingan" deb belgilanadi va qarz qayta hisoblanadi.`} />
      <Form form={form} layout="vertical" onFinish={m.mutate}>
        <Form.Item name="reason" label="Sabab" rules={[{ required: true, message: 'Sababni yozing' }]}>
          <Input.TextArea rows={2} placeholder="Masalan: summa xato kiritildi" />
        </Form.Item>
      </Form>
    </Modal>
  )
}
