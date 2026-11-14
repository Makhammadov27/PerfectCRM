import { ClockCircleOutlined, PlusOutlined, TeamOutlined, UserOutlined } from '@ant-design/icons'
import { Button, Card, Col, Empty, Input, Row, Segmented, Skeleton, Tag, theme } from 'antd'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { PageHead, useGroups } from '../components/common'
import GroupForm from '../components/GroupForm'
import { money, scheduleText } from '../utils'

const COLORS = ['#4F46E5', '#0891B2', '#16A34A', '#D97706', '#DB2777', '#7C3AED', '#059669', '#DC2626']

export default function Groups() {
  const nav = useNavigate()
  const { token } = theme.useToken()
  const [status, setStatus] = useState('active')
  const [search, setSearch] = useState('')
  const [formOpen, setFormOpen] = useState(false)
  const { data = [], isLoading } = useGroups(status)
  const list = data.filter((g) => `${g.name} ${g.subject} ${g.teacher_name}`.toLowerCase().includes(search.toLowerCase()))

  return (
    <>
      <PageHead
        title="Guruhlar"
        sub={`${list.length} ta guruh`}
        extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => setFormOpen(true)}>Yangi guruh</Button>}
      />
      <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap' }}>
        <Input.Search allowClear placeholder="Qidirish" style={{ width: 260 }} onChange={(e) => setSearch(e.target.value)} />
        <Segmented value={status} onChange={(v) => setStatus(v as string)}
          options={[{ label: 'Faol', value: 'active' }, { label: 'Tugagan', value: 'finished' }]} />
      </div>
      {isLoading ? (
        <Skeleton active />
      ) : list.length === 0 ? (
        <Card variant="borderless"><Empty description="Guruh yo'q" /></Card>
      ) : (
        <Row gutter={[16, 16]}>
          {list.map((g) => {
            const color = COLORS[g.id % COLORS.length]
            return (
              <Col key={g.id} xs={24} md={12} xl={8}>
                <Card hoverable variant="borderless" onClick={() => nav(`/groups/${g.id}`)}
                  style={{ borderTop: `4px solid ${color}`, height: '100%' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 8 }}>
                    <div>
                      <div style={{ fontSize: 17, fontWeight: 700 }}>{g.name}</div>
                      <div style={{ color: token.colorTextSecondary }}>{g.subject}</div>
                    </div>
                    <Tag color={color} style={{ height: 'fit-content' }}>{g.room_name}</Tag>
                  </div>
                  <div style={{ marginTop: 16, display: 'grid', gap: 6, color: token.colorTextSecondary }}>
                    <span><UserOutlined /> {g.teacher_name}</span>
                    <span><ClockCircleOutlined /> {scheduleText(g.schedule)}</span>
                    <span><TeamOutlined /> {g.students_count} o'quvchi</span>
                  </div>
                  <div style={{ marginTop: 14, fontWeight: 600 }}>
                    {money(g.monthly_price)} <span style={{ fontWeight: 400, color: token.colorTextSecondary }}>/ oy</span>
                  </div>
                </Card>
              </Col>
            )
          })}
        </Row>
      )}
      <GroupForm open={formOpen} onClose={() => setFormOpen(false)} onSaved={(g) => nav(`/groups/${g.id}`)} />
    </>
  )
}
