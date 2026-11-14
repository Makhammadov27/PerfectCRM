import { PlusOutlined, SearchOutlined } from '@ant-design/icons'
import { Button, Card, Input, Segmented, Select, Space, Table, Tag } from 'antd'
import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Balance, PageHead, useGroups, useStudents } from '../components/common'
import StudentForm from '../components/StudentForm'
import type { Student } from '../types'
import { fmtDate, phone } from '../utils'

export default function Students() {
  const nav = useNavigate()
  const [search, setSearch] = useState('')
  const [status, setStatus] = useState('active')
  const [group, setGroup] = useState<number>()
  const [onlyDebtors, setOnlyDebtors] = useState(false)
  const [formOpen, setFormOpen] = useState(false)
  const { data: groups = [] } = useGroups()

  const params: Record<string, string> = {}
  if (search) params.search = search
  if (status !== 'all') params.status = status
  if (group) params.group = String(group)
  if (onlyDebtors) params.debtors = '1'
  const { data = [], isLoading } = useStudents(params)

  return (
    <>
      <PageHead
        title="O'quvchilar"
        sub={`${data.length} ta`}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={() => setFormOpen(true)}>
            Yangi o'quvchi
          </Button>
        }
      />
      <Card variant="borderless">
        <Space wrap style={{ marginBottom: 16 }}>
          <Input
            allowClear
            prefix={<SearchOutlined />}
            placeholder="Ism yoki telefon"
            style={{ width: 240 }}
            onChange={(e) => setSearch(e.target.value)}
          />
          <Segmented
            value={status}
            onChange={(v) => setStatus(v as string)}
            options={[{ label: "O'qiyapti", value: 'active' }, { label: 'Ketgan', value: 'left' }, { label: 'Hammasi', value: 'all' }]}
          />
          <Select
            allowClear
            placeholder="Guruh"
            style={{ width: 200 }}
            value={group}
            onChange={setGroup}
            options={groups.map((g) => ({ value: g.id, label: g.name }))}
          />
          <Segmented
            value={onlyDebtors ? 'd' : 'a'}
            onChange={(v) => setOnlyDebtors(v === 'd')}
            options={[{ label: 'Barchasi', value: 'a' }, { label: 'Qarzdorlar', value: 'd' }]}
          />
        </Space>
        <Table<Student>
          rowKey="id"
          loading={isLoading}
          dataSource={data}
          scroll={{ x: 800 }}
          pagination={{ pageSize: 20, showSizeChanger: false }}
          onRow={(r) => ({ onClick: () => nav(`/students/${r.id}`), style: { cursor: 'pointer' } })}
          columns={[
            { title: 'F.I.Sh.', dataIndex: 'full_name', render: (v) => <b>{v}</b> },
            {
              title: 'Guruhlar',
              dataIndex: 'groups',
              render: (gs: Student['groups']) => gs.map((g) => <Tag key={g.id}>{g.name}</Tag>),
            },
            {
              title: 'Ota-ona',
              dataIndex: 'parents',
              render: (ps: Student['parents']) =>
                ps.map((p) => (
                  <div key={p.id}>
                    {phone(p.phone)} {p.telegram_linked && <Tag color="blue" bordered={false}>Telegram</Tag>}
                  </div>
                )),
            },
            { title: 'Balans', dataIndex: 'balance', align: 'right', sorter: (a, b) => a.balance - b.balance, render: (v) => <Balance value={v} /> },
            { title: "Qo'shilgan", dataIndex: 'created_at', render: fmtDate, responsive: ['lg'] },
          ]}
        />
      </Card>
      <StudentForm open={formOpen} onClose={() => setFormOpen(false)} onSaved={(s) => nav(`/students/${s.id}`)} />
    </>
  )
}
