import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Alert, App, Button, Col, DatePicker, Drawer, Form, Input, InputNumber, Row, Select, Space, TimePicker } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { useEffect } from 'react'
import { api, errorText } from '../api'
import type { Group } from '../types'
import { WEEKDAYS } from '../utils'
import { useRooms, useTeachers } from './common'

const money = {
  style: { width: '100%' },
  formatter: (v: number | string | undefined) => `${v ?? ''}`.replace(/\B(?=(\d{3})+(?!\d))/g, ' '),
  parser: (v: string | undefined) => Number((v ?? '').replace(/\s/g, '')),
}

type SlotForm = { weekday: number; time: [Dayjs, Dayjs] }

export default function GroupForm({
  open, onClose, group, onSaved,
}: { open: boolean; onClose: () => void; group?: Group | null; onSaved?: (g: Group) => void }) {
  const [form] = Form.useForm()
  const { message } = App.useApp()
  const qc = useQueryClient()
  const { data: teachers = [] } = useTeachers()
  const { data: rooms = [] } = useRooms()

  useEffect(() => {
    if (!open) return
    form.resetFields()
    if (group) {
      form.setFieldsValue({
        ...group,
        start_date: dayjs(group.start_date),
        end_date: group.end_date ? dayjs(group.end_date) : null,
        schedule: group.schedule.map((s) => ({
          weekday: s.weekday,
          time: [dayjs(s.start_time, 'HH:mm:ss'), dayjs(s.end_time, 'HH:mm:ss')],
        })),
      })
    } else {
      const t: [Dayjs, Dayjs] = [dayjs('14:00', 'HH:mm'), dayjs('15:30', 'HH:mm')]
      form.setFieldsValue({
        monthly_price: 300000, lesson_price: 25000, start_date: dayjs(), status: 'active',
        schedule: [0, 2, 4].map((weekday) => ({ weekday, time: t })),
      })
    }
  }, [open, group, form])

  const m = useMutation({
    mutationFn: async (v: Record<string, unknown>) => {
      const body = {
        ...v,
        start_date: (v.start_date as Dayjs).format('YYYY-MM-DD'),
        end_date: v.end_date ? (v.end_date as Dayjs).format('YYYY-MM-DD') : null,
        schedule: (v.schedule as SlotForm[]).map((s) => ({
          weekday: s.weekday, start_time: s.time[0].format('HH:mm'), end_time: s.time[1].format('HH:mm'),
        })),
      }
      return group
        ? (await api.put<Group>(`/groups/${group.id}/`, body)).data
        : (await api.post<Group>('/groups/', body)).data
    },
    onSuccess: (g) => {
      message.success('Guruh saqlandi')
      qc.invalidateQueries({ queryKey: ['groups'] })
      qc.invalidateQueries({ queryKey: ['group', g.id] })
      qc.invalidateQueries({ queryKey: ['lessons'] })
      onSaved?.(g)
      onClose()
    },
    onError: (e) => message.error({ content: errorText(e), duration: 6 }),
  })

  return (
    <Drawer
      title={group ? 'Guruhni tahrirlash' : 'Yangi guruh'}
      open={open}
      onClose={onClose}
      width={560}
      extra={<Button type="primary" onClick={() => form.submit()} loading={m.isPending}>Saqlash</Button>}
    >
      <Form form={form} layout="vertical" onFinish={m.mutate} requiredMark={false}>
        <Row gutter={12}>
          <Col span={12}>
            <Form.Item name="name" label="Guruh nomi" rules={[{ required: true }]}>
              <Input placeholder="Ingliz tili A1-1" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="subject" label="Fan / kurs" rules={[{ required: true }]}>
              <Input placeholder="Ingliz tili" />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="teacher" label="O'qituvchi" rules={[{ required: true }]}>
              <Select showSearch optionFilterProp="label"
                options={teachers.filter((t) => t.is_active).map((t) => ({ value: t.id, label: t.full_name }))} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="room" label="Xona" rules={[{ required: true }]}>
              <Select options={rooms.map((r) => ({ value: r.id, label: r.name }))} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="monthly_price" label="Oylik narx" rules={[{ required: true }]}>
              <InputNumber<number> min={0} step={10000} addonAfter="so'm" {...money} />
            </Form.Item>
          </Col>
          <Col span={12}>
            <Form.Item name="lesson_price" label="Bitta dars narxi" rules={[{ required: true }]}
              tooltip="Oy o'rtasida qo'shilgan/ketgan o'quvchi uchun ishlatiladi">
              <InputNumber<number> min={0} step={5000} addonAfter="so'm" {...money} />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="start_date" label="Boshlanish" rules={[{ required: true }]}>
              <DatePicker style={{ width: '100%' }} format="DD.MM.YYYY" />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="end_date" label="Tugash">
              <DatePicker style={{ width: '100%' }} format="DD.MM.YYYY" />
            </Form.Item>
          </Col>
          <Col span={8}>
            <Form.Item name="status" label="Holat">
              <Select options={[{ value: 'active', label: 'Faol' }, { value: 'finished', label: 'Tugagan' }]} />
            </Form.Item>
          </Col>
        </Row>

        <div style={{ fontWeight: 600, marginBottom: 12 }}>Dars jadvali</div>
        <Form.List name="schedule">
          {(fields, { add, remove }) => (
            <>
              {fields.map(({ key, name }) => (
                <Space key={key} align="start" style={{ display: 'flex' }}>
                  <Form.Item name={[name, 'weekday']} rules={[{ required: true, message: 'Kun' }]}>
                    <Select style={{ width: 150 }} options={WEEKDAYS.map((d, i) => ({ value: i, label: d }))} />
                  </Form.Item>
                  <Form.Item name={[name, 'time']} rules={[{ required: true, message: 'Vaqt' }]}>
                    <TimePicker.RangePicker format="HH:mm" minuteStep={5} needConfirm={false} />
                  </Form.Item>
                  <Button type="text" danger icon={<MinusCircleOutlined />} onClick={() => remove(name)} />
                </Space>
              ))}
              <Button type="dashed" block icon={<PlusOutlined />}
                onClick={() => add({ weekday: undefined, time: [dayjs('14:00', 'HH:mm'), dayjs('15:30', 'HH:mm')] })}>
                Kun qo'shish
              </Button>
            </>
          )}
        </Form.List>
        <Alert style={{ marginTop: 16 }} type="info" showIcon
          message="Xona yoki o'qituvchi shu vaqtda band bo'lsa, tizim saqlashga ruxsat bermaydi." />
      </Form>
    </Drawer>
  )
}
