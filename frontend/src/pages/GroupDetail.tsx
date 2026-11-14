import { ArrowLeftOutlined, EditOutlined, PlusOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Button, Card, Col, Descriptions, Row, Skeleton, Space, Table, Tabs, Tag, theme } from 'antd'
import dayjs from 'dayjs'
import { useState } from 'react'
import { useNavigate, useParams } from 'react-router-dom'
import { api } from '../api'
import { Balance, MonthPicker, thisMonth } from '../components/common'
import { DiscountModal, EnrollModal, LeaveModal } from '../components/EnrollmentModals'
import GroupForm from '../components/GroupForm'
import { AttendanceModal, LessonTag } from '../components/LessonModals'
import type { Enrollment, Group, Lesson } from '../types'
import { WEEKDAYS, fmtDate, fmtTime, money, scheduleText } from '../utils'

export default function GroupDetail() {
  const { id } = useParams()
  const nav = useNavigate()
  const { token } = theme.useToken()
  const [edit, setEdit] = useState(false)
  const [enroll, setEnroll] = useState(false)
  const [leave, setLeave] = useState<Enrollment | null>(null)
  const [discount, setDiscount] = useState<Enrollment | null>(null)
  const [lessonId, setLessonId] = useState<number | null>(null)
  const [month, setMonth] = useState(thisMonth())
  const [showLeft, setShowLeft] = useState(false)

  const { data: g } = useQuery({
    queryKey: ['group', Number(id)],
    queryFn: async () => (await api.get<Group>(`/groups/${id}/`)).data,
  })
  const { data: students = [], isLoading: stLoading } = useQuery({
    queryKey: ['group', Number(id), 'students', showLeft],
    queryFn: async () => (await api.get<Enrollment[]>(`/groups/${id}/students/`, { params: showLeft ? { all: 1 } : {} })).data,
  })
  const { data: lessons = [], isLoading: lLoading } = useQuery({
    queryKey: ['lessons', 'group', Number(id), month.format('YYYY-MM')],
    queryFn: async () =>
      (await api.get<Lesson[]>('/lessons/', {
        params: {
          group: id, include_cancelled: 1,
          date_from: month.format('YYYY-MM-DD'), date_to: month.endOf('month').format('YYYY-MM-DD'),
        },
      })).data,
  })

  if (!g) return <Skeleton active paragraph={{ rows: 10 }} />

  return (
    <>
      <Button type="text" icon={<ArrowLeftOutlined />} onClick={() => nav('/groups')} style={{ marginBottom: 8 }}>
        Guruhlar
      </Button>
      <Card variant="borderless">
        <Row gutter={16} align="middle">
          <Col flex="auto">
            <div style={{ fontSize: 22, fontWeight: 700 }}>
              {g.name} {g.status === 'finished' && <Tag>Tugagan</Tag>}
            </div>
            <div style={{ color: token.colorTextSecondary }}>{g.subject}</div>
          </Col>
          <Col>
            <Space wrap>
              <Button type="primary" icon={<PlusOutlined />} onClick={() => setEnroll(true)}>O'quvchi qo'shish</Button>
              <Button icon={<EditOutlined />} onClick={() => setEdit(true)}>Tahrirlash</Button>
            </Space>
          </Col>
        </Row>
        <Descriptions size="small" column={{ xs: 1, md: 3 }} style={{ marginTop: 16 }}>
          <Descriptions.Item label="O'qituvchi">{g.teacher_name}</Descriptions.Item>
          <Descriptions.Item label="Xona">{g.room_name}</Descriptions.Item>
          <Descriptions.Item label="Jadval">{scheduleText(g.schedule)}</Descriptions.Item>
          <Descriptions.Item label="Oylik narx">{money(g.monthly_price)}</Descriptions.Item>
          <Descriptions.Item label="Dars narxi">{money(g.lesson_price)}</Descriptions.Item>
          <Descriptions.Item label="Boshlangan">{fmtDate(g.start_date)}</Descriptions.Item>
        </Descriptions>
      </Card>

      <Card variant="borderless" style={{ marginTop: 16 }}>
        <Tabs
          items={[
            {
              key: 's',
              label: `O'quvchilar (${g.students_count})`,
              children: (
                <>
                  <Button size="small" style={{ marginBottom: 12 }} onClick={() => setShowLeft(!showLeft)}>
                    {showLeft ? 'Faqat hozirgilar' : "Ketganlarni ham ko'rsatish"}
                  </Button>
                  <Table<Enrollment>
                    rowKey="id" loading={stLoading} dataSource={students} pagination={false} scroll={{ x: 640 }}
                    columns={[
                      { title: 'F.I.Sh.', dataIndex: 'student_name', render: (v, r) => <a onClick={() => nav(`/students/${r.student}`)}>{v}</a> },
                      { title: "Qo'shilgan", dataIndex: 'joined_at', render: fmtDate },
                      {
                        title: 'Chegirma',
                        render: (_, r) => r.discount_type === 'none' ? '—' : r.discount_type === 'percent' ? `${r.discount_value}%` : money(r.discount_value),
                      },
                      { title: 'Balans', dataIndex: 'balance', align: 'right', render: (v) => <Balance value={v ?? 0} /> },
                      {
                        title: '',
                        render: (_, r) => r.left_at ? <Tag>Ketgan {fmtDate(r.left_at)}</Tag> : (
                          <Space>
                            <Button size="small" onClick={() => setDiscount(r)}>Chegirma</Button>
                            <Button size="small" danger onClick={() => setLeave(r)}>Chiqarish</Button>
                          </Space>
                        ),
                      },
                    ]}
                  />
                </>
              ),
            },
            {
              key: 'l',
              label: 'Darslar va davomat',
              children: (
                <>
                  <div style={{ marginBottom: 12 }}><MonthPicker value={month} onChange={setMonth} /></div>
                  <Table<Lesson>
                    rowKey="id" size="small" loading={lLoading} dataSource={lessons} pagination={false}
                    onRow={(r) => ({ onClick: () => setLessonId(r.id), style: { cursor: 'pointer' } })}
                    columns={[
                      { title: 'Sana', dataIndex: 'date', render: (d) => `${fmtDate(d)}, ${WEEKDAYS[(dayjs(d).day() + 6) % 7]}` },
                      { title: 'Vaqt', render: (_, r) => `${fmtTime(r.start_time)}–${fmtTime(r.end_time)}` },
                      { title: 'Xona', dataIndex: 'room_name' },
                      { title: 'Holat', render: (_, r) => <LessonTag l={r} /> },
                    ]}
                  />
                </>
              ),
            },
          ]}
        />
      </Card>

      <GroupForm open={edit} onClose={() => setEdit(false)} group={g} />
      <EnrollModal open={enroll} onClose={() => setEnroll(false)} groupId={g.id} />
      <LeaveModal enrollment={leave} onClose={() => setLeave(null)} />
      <DiscountModal enrollment={discount} onClose={() => setDiscount(null)} />
      <AttendanceModal lessonId={lessonId} onClose={() => setLessonId(null)} />
    </>
  )
}
