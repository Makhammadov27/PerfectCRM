import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Alert, App, Button, DatePicker, Form, Modal, Radio, Select, Skeleton, Space, Table, Tag, TimePicker } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { useEffect, useState } from 'react'
import { api, errorText } from '../api'
import type { AttendanceStatus, Lesson } from '../types'
import { ATTENDANCE, fmtDate, fmtTime } from '../utils'
import { useRooms } from './common'

type Row = { student: number; student_name: string; status: AttendanceStatus | null; marked_by: string | null }

/** Admin: darsning davomatini ko'rish va o'zgartirish, darsni bekor qilish. */
export function AttendanceModal({ lessonId, onClose }: { lessonId: number | null; onClose: () => void }) {
  const { message } = App.useApp()
  const qc = useQueryClient()
  const [draft, setDraft] = useState<Record<number, AttendanceStatus>>({})
  const [cancelOpen, setCancelOpen] = useState(false)

  const { data } = useQuery({
    queryKey: ['attendance', lessonId],
    queryFn: async () => (await api.get<{ lesson: Lesson; rows: Row[] }>(`/lessons/${lessonId}/attendance/`)).data,
    enabled: !!lessonId,
  })
  useEffect(() => {
    if (data) setDraft(Object.fromEntries(data.rows.map((r) => [r.student, r.status ?? 'present'])))
  }, [data])

  const save = useMutation({
    mutationFn: async () =>
      api.post(`/lessons/${lessonId}/attendance/`, {
        items: Object.entries(draft).map(([student, status]) => ({ student: Number(student), status })),
      }),
    onSuccess: () => {
      message.success('Davomat saqlandi')
      qc.invalidateQueries({ queryKey: ['attendance'] })
      qc.invalidateQueries({ queryKey: ['lessons'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      onClose()
    },
    onError: (e) => message.error(errorText(e)),
  })

  const l = data?.lesson
  const taken = data?.rows.some((r) => r.status)
  return (
    <>
      <Modal
        open={!!lessonId}
        onCancel={onClose}
        width={620}
        title={l ? `${l.group_name} — ${fmtDate(l.date)} ${fmtTime(l.start_time)}` : 'Davomat'}
        footer={
          l?.status === 'cancelled' ? null : (
            <Space>
              {!taken && <Button danger onClick={() => setCancelOpen(true)}>Darsni bekor qilish</Button>}
              <Button onClick={onClose}>Yopish</Button>
              <Button type="primary" loading={save.isPending} onClick={() => save.mutate()} disabled={!data?.rows.length}>
                Saqlash
              </Button>
            </Space>
          )
        }
      >
        {!data ? (
          <Skeleton active />
        ) : (
          <>
            {l?.status === 'cancelled' && <Alert type="warning" showIcon message="Bu dars bekor qilingan" style={{ marginBottom: 12 }} />}
            {taken ? (
              <Alert type="info" showIcon style={{ marginBottom: 12 }}
                message={`Davomatni ${data.rows.find((r) => r.marked_by)?.marked_by ?? "o'qituvchi"} olgan. Admin sifatida o'zgartirishingiz mumkin — o'zgarish audit logga yoziladi.`} />
            ) : (
              <Alert type="info" showIcon style={{ marginBottom: 12 }}
                message="Davomat hali olinmagan. O'qituvchi Telegram bot orqali oladi yoki shu yerda belgilashingiz mumkin." />
            )}
            <Table<Row>
              rowKey="student" size="small" pagination={false} dataSource={data.rows}
              locale={{ emptyText: "Guruhda o'quvchi yo'q" }}
              columns={[
                { title: "O'quvchi", dataIndex: 'student_name' },
                {
                  title: 'Holat',
                  render: (_, r) => (
                    <Radio.Group
                      size="small" optionType="button" buttonStyle="solid"
                      value={draft[r.student]}
                      disabled={l?.status === 'cancelled'}
                      onChange={(e) => setDraft({ ...draft, [r.student]: e.target.value })}
                      options={Object.entries(ATTENDANCE).map(([value, a]) => ({ value, label: a.label }))}
                    />
                  ),
                },
              ]}
            />
          </>
        )}
      </Modal>
      {l && <CancelLessonModal lesson={cancelOpen ? l : null} onClose={() => setCancelOpen(false)} onDone={onClose} />}
    </>
  )
}

function CancelLessonModal({ lesson, onClose, onDone }: { lesson: Lesson | null; onClose: () => void; onDone: () => void }) {
  const [form] = Form.useForm()
  const { message } = App.useApp()
  const qc = useQueryClient()
  const { data: rooms = [] } = useRooms()
  useEffect(() => {
    if (lesson)
      form.setFieldsValue({
        makeup_date: dayjs(lesson.date).add(1, 'day'),
        time: [dayjs(lesson.start_time, 'HH:mm:ss'), dayjs(lesson.end_time, 'HH:mm:ss')],
        room: lesson.room,
      })
  }, [lesson, form])
  const m = useMutation({
    mutationFn: async (v: { makeup_date: Dayjs; time: [Dayjs, Dayjs]; room: number }) =>
      api.post(`/lessons/${lesson!.id}/cancel/`, {
        makeup_date: v.makeup_date.format('YYYY-MM-DD'),
        start_time: v.time[0].format('HH:mm'),
        end_time: v.time[1].format('HH:mm'),
        room: v.room,
      }),
    onSuccess: () => {
      message.success("Dars bekor qilindi, qo'shimcha dars qo'yildi")
      qc.invalidateQueries({ queryKey: ['lessons'] })
      onClose()
      onDone()
    },
    onError: (e) => message.error({ content: errorText(e), duration: 6 }),
  })
  return (
    <Modal title="Darsni bekor qilish" open={!!lesson} onCancel={onClose} onOk={() => form.submit()}
      okText="Bekor qilish va ko'chirish" okButtonProps={{ danger: true }} confirmLoading={m.isPending}>
      <Alert type="info" showIcon style={{ marginBottom: 16 }}
        message="Oylik to'lov o'zgarmaydi — dars boshqa kunga ko'chiriladi (qo'shimcha dars)." />
      <Form form={form} layout="vertical" onFinish={m.mutate}>
        <Form.Item name="makeup_date" label="Qo'shimcha dars sanasi" rules={[{ required: true }]}>
          <DatePicker style={{ width: '100%' }} format="DD.MM.YYYY" />
        </Form.Item>
        <Form.Item name="time" label="Vaqti" rules={[{ required: true }]}>
          <TimePicker.RangePicker format="HH:mm" minuteStep={5} style={{ width: '100%' }} needConfirm={false} />
        </Form.Item>
        <Form.Item name="room" label="Xona">
          <Select options={rooms.map((r) => ({ value: r.id, label: r.name }))} />
        </Form.Item>
      </Form>
    </Modal>
  )
}

export function LessonTag({ l }: { l: Lesson }) {
  if (l.status === 'cancelled') return <Tag>Bekor</Tag>
  if (l.attendance_taken) return <Tag color="green">Davomat olindi</Tag>
  if (l.kind === 'makeup') return <Tag color="orange">Qo'shimcha</Tag>
  return <Tag>Rejada</Tag>
}
