import { LeftOutlined, RightOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Button, Card, Select, Space, Spin, theme } from 'antd'
import dayjs from 'dayjs'
import { useState } from 'react'
import { api } from '../api'
import { PageHead, useRooms, useTeachers } from '../components/common'
import { AttendanceModal } from '../components/LessonModals'
import type { Lesson } from '../types'
import { WEEKDAYS, fmtTime } from '../utils'

const mondayOf = (d: dayjs.Dayjs) => d.subtract((d.day() + 6) % 7, 'day').startOf('day')

export default function Schedule() {
  const { token } = theme.useToken()
  const [week, setWeek] = useState(mondayOf(dayjs()))
  const [room, setRoom] = useState<number>()
  const [teacher, setTeacher] = useState<string>()
  const [lessonId, setLessonId] = useState<number | null>(null)
  const { data: rooms = [] } = useRooms()
  const { data: teachers = [] } = useTeachers()

  const end = week.add(6, 'day')
  const { data = [], isLoading } = useQuery({
    queryKey: ['lessons', 'week', week.format('YYYY-MM-DD')],
    queryFn: async () =>
      (await api.get<Lesson[]>('/lessons/', {
        params: { date_from: week.format('YYYY-MM-DD'), date_to: end.format('YYYY-MM-DD'), include_cancelled: 1 },
      })).data,
  })
  const lessons = data.filter((l) => (!room || l.room === room) && (!teacher || l.teacher_name === teacher))
  const today = dayjs().format('YYYY-MM-DD')

  return (
    <>
      <PageHead
        title="Jadval va davomat"
        sub={`${week.format('DD.MM')} – ${end.format('DD.MM.YYYY')}`}
        extra={
          <Space wrap>
            <Select allowClear placeholder="Xona" style={{ width: 140 }} value={room} onChange={setRoom}
              options={rooms.map((r) => ({ value: r.id, label: r.name }))} />
            <Select allowClear placeholder="O'qituvchi" style={{ width: 180 }} value={teacher} onChange={setTeacher}
              options={teachers.map((t) => ({ value: t.full_name, label: t.full_name }))} />
            <Space.Compact>
              <Button icon={<LeftOutlined />} onClick={() => setWeek(week.subtract(7, 'day'))} />
              <Button onClick={() => setWeek(mondayOf(dayjs()))}>Bu hafta</Button>
              <Button icon={<RightOutlined />} onClick={() => setWeek(week.add(7, 'day'))} />
            </Space.Compact>
          </Space>
        }
      />
      <Card variant="borderless">
        <Spin spinning={isLoading}>
          <div className="week-grid">
            {WEEKDAYS.map((name, i) => {
              const day = week.add(i, 'day')
              const key = day.format('YYYY-MM-DD')
              const items = lessons.filter((l) => l.date === key)
              return (
                <div key={key}>
                  <div className="week-col-head" style={key === today ? { color: token.colorPrimary } : undefined}>
                    {name}
                    <span className="d">{day.format('DD.MM')}</span>
                  </div>
                  {items.map((l) => (
                    <div
                      key={l.id}
                      className={`lesson-chip ${l.status === 'cancelled' ? 'cancelled' : l.attendance_taken ? 'done' : l.kind === 'makeup' ? 'makeup' : ''}`}
                      onClick={() => setLessonId(l.id)}
                    >
                      <div className="t">{fmtTime(l.start_time)}–{fmtTime(l.end_time)} · {l.room_name}</div>
                      <div className="n">{l.group_name}</div>
                      <div className="t">{l.teacher_name}</div>
                    </div>
                  ))}
                  {!items.length && <div style={{ color: token.colorTextQuaternary, fontSize: 12, padding: 4 }}>—</div>}
                </div>
              )
            })}
          </div>
          <Space size={16} wrap style={{ marginTop: 16, fontSize: 12, color: token.colorTextSecondary }}>
            <span><span className="lesson-chip" style={{ padding: '0 8px', margin: 0 }}>&nbsp;</span> Rejada</span>
            <span><span className="lesson-chip done" style={{ padding: '0 8px', margin: 0 }}>&nbsp;</span> Davomat olindi</span>
            <span><span className="lesson-chip makeup" style={{ padding: '0 8px', margin: 0 }}>&nbsp;</span> Qo'shimcha dars</span>
            <span><span className="lesson-chip cancelled" style={{ padding: '0 8px', margin: 0 }}>&nbsp;</span> Bekor qilingan</span>
          </Space>
        </Spin>
      </Card>
      <AttendanceModal lessonId={lessonId} onClose={() => setLessonId(null)} />
    </>
  )
}
