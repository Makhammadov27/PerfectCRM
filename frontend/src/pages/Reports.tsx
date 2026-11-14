import { FileExcelOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Button, Card, Col, List, Progress, Row, Table, theme } from 'antd'
import { useState } from 'react'
import { Bar, BarChart, CartesianGrid, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api, download } from '../api'
import { MonthPicker, PageHead, monthParam, thisMonth } from '../components/common'
import { monthLabel } from '../utils'

type AttRow = {
  group_id: number
  group_name: string
  teacher_name: string
  lessons: number
  present: number
  late: number
  absent: number
  excused: number
  rate: number
}

const EXPORTS = [
  { kind: 'payments', title: "To'lovlar", desc: "Oy davomidagi barcha to'lovlar, cheklar bilan" },
  { kind: 'invoices', title: 'Oylik hisoblar', desc: "Har bir o'quvchi: hisoblangan, to'langan, qarz" },
  { kind: 'debtors', title: 'Qarzdorlar', desc: "Hozirgi qarzdorlar ro'yxati, ota-ona telefoni bilan" },
  { kind: 'attendance', title: 'Davomat', desc: "Guruh, sana va o'quvchi bo'yicha" },
  { kind: 'salaries', title: 'Maoshlar', desc: "O'qituvchilarga to'langan maoshlar" },
]

export default function Reports() {
  const { token } = theme.useToken()
  const [month, setMonth] = useState(thisMonth())
  const { data = [], isLoading } = useQuery({
    queryKey: ['att-report', monthParam(month)],
    queryFn: async () => (await api.get<AttRow[]>('/reports/attendance/', { params: { month: monthParam(month) } })).data,
  })

  return (
    <>
      <PageHead title="Hisobotlar" sub={monthLabel(month)} extra={<MonthPicker value={month} onChange={setMonth} />} />
      <Row gutter={[16, 16]}>
        <Col xs={24} xl={15}>
          <Card title="Guruhlar bo'yicha davomat" variant="borderless">
            {data.length > 0 && (
              <ResponsiveContainer width="100%" height={Math.max(160, data.length * 44)}>
                <BarChart data={data} layout="vertical" margin={{ left: 20, right: 20 }}>
                  <CartesianGrid horizontal={false} stroke={token.colorBorderSecondary} />
                  <XAxis type="number" domain={[0, 100]} unit="%" tick={{ fontSize: 12, fill: token.colorTextSecondary }} />
                  <YAxis type="category" dataKey="group_name" width={130} tick={{ fontSize: 12, fill: token.colorText }} />
                  <Tooltip formatter={(v: number) => [`${v}%`, 'Davomat']}
                    contentStyle={{ borderRadius: 10, border: 'none', background: token.colorBgElevated }} />
                  <Bar dataKey="rate" fill={token.colorPrimary} radius={[0, 6, 6, 0]} barSize={20} />
                </BarChart>
              </ResponsiveContainer>
            )}
            <Table<AttRow>
              rowKey="group_id" loading={isLoading} dataSource={data} size="small" pagination={false}
              scroll={{ x: 640 }} style={{ marginTop: 12 }}
              columns={[
                { title: 'Guruh', dataIndex: 'group_name' },
                { title: "O'qituvchi", dataIndex: 'teacher_name' },
                { title: 'Darslar', dataIndex: 'lessons', align: 'center' },
                { title: 'Keldi', dataIndex: 'present', align: 'center' },
                { title: 'Kechikdi', dataIndex: 'late', align: 'center' },
                { title: 'Kelmadi', dataIndex: 'absent', align: 'center' },
                { title: 'Sababli', dataIndex: 'excused', align: 'center' },
                { title: '%', dataIndex: 'rate', width: 120, render: (v) => <Progress percent={v} size="small" /> },
              ]}
            />
          </Card>
        </Col>
        <Col xs={24} xl={9}>
          <Card title="Excel'ga yuklab olish" variant="borderless">
            <List
              dataSource={EXPORTS}
              renderItem={(e) => (
                <List.Item
                  actions={[
                    <Button key="d" icon={<FileExcelOutlined />}
                      onClick={() => download(`/reports/export/${e.kind}/?month=${monthParam(month)}`, `${e.kind}-${monthParam(month)}.xlsx`)}>
                      Yuklab olish
                    </Button>,
                  ]}
                >
                  <List.Item.Meta title={e.title} description={e.desc} />
                </List.Item>
              )}
            />
          </Card>
        </Col>
      </Row>
    </>
  )
}
