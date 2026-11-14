import { FileExcelOutlined, PlusOutlined } from '@ant-design/icons'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { App, Button, Card, DatePicker, Form, Input, InputNumber, Modal, Popconfirm, Select, Table, Tag } from 'antd'
import dayjs, { type Dayjs } from 'dayjs'
import { useEffect, useState } from 'react'
import { api, download, errorText } from '../api'
import { MonthPicker, PageHead, monthParam, thisMonth, useTeachers } from '../components/common'
import type { Salary } from '../types'
import { fmtDate, money, monthLabel } from '../utils'

export default function Salaries() {
  const [month, setMonth] = useState(thisMonth())
  const [edit, setEdit] = useState<Salary | null | undefined>(undefined)
  const [form] = Form.useForm()
  const { message } = App.useApp()
  const qc = useQueryClient()
  const { data: teachers = [] } = useTeachers()
  const { data = [], isLoading } = useQuery({
    queryKey: ['salaries', monthParam(month)],
    queryFn: async () => (await api.get<Salary[]>('/salaries/', { params: { month: monthParam(month) } })).data,
  })

  useEffect(() => {
    if (edit === undefined) return
    form.resetFields()
    form.setFieldsValue(edit
      ? { ...edit, period: dayjs(edit.period), paid_at: edit.paid_at ? dayjs(edit.paid_at) : null }
      : { period: month, paid_at: dayjs() })
  }, [edit, form, month])

  const save = useMutation({
    mutationFn: async (v: { period: Dayjs; paid_at: Dayjs | null }) => {
      const body = { ...v, period: v.period.format('YYYY-MM-01'), paid_at: v.paid_at ? v.paid_at.format('YYYY-MM-DD') : null }
      return edit ? api.put(`/salaries/${edit.id}/`, body) : api.post('/salaries/', body)
    },
    onSuccess: () => {
      message.success('Saqlandi')
      qc.invalidateQueries({ queryKey: ['salaries'] })
      qc.invalidateQueries({ queryKey: ['dashboard'] })
      setEdit(undefined)
    },
    onError: (e) => message.error(errorText(e)),
  })
  const del = useMutation({
    mutationFn: async (id: number) => api.delete(`/salaries/${id}/`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['salaries'] }),
  })
  const total = data.reduce((a, s) => a + s.amount, 0)

  return (
    <>
      <PageHead
        title="O'qituvchilar maoshi"
        sub={`${monthLabel(month)} · jami ${money(total)}`}
        extra={
          <>
            <MonthPicker value={month} onChange={setMonth} />
            <Button icon={<FileExcelOutlined />} onClick={() => download(`/reports/export/salaries/?month=${monthParam(month)}`, `maoshlar-${monthParam(month)}.xlsx`)}>Excel</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setEdit(null)}>Maosh kiritish</Button>
          </>
        }
      />
      <Card variant="borderless">
        <Table<Salary>
          rowKey="id" loading={isLoading} dataSource={data} pagination={false}
          columns={[
            { title: "O'qituvchi", dataIndex: 'teacher_name', render: (v, r) => <a onClick={() => setEdit(r)}><b>{v}</b></a> },
            { title: 'Summa', dataIndex: 'amount', align: 'right', render: money },
            { title: 'Holat', dataIndex: 'paid_at', render: (v) => (v ? <Tag color="green">To'landi {fmtDate(v)}</Tag> : <Tag color="orange">To'lanmagan</Tag>) },
            { title: 'Izoh', dataIndex: 'note' },
            {
              title: '', width: 60,
              render: (_, r) => (
                <Popconfirm title="O'chirasizmi?" onConfirm={() => del.mutate(r.id)} okText="Ha" cancelText="Yo'q">
                  <Button type="text" danger size="small">O'chirish</Button>
                </Popconfirm>
              ),
            },
          ]}
        />
      </Card>
      <Modal title={edit ? 'Maoshni tahrirlash' : 'Maosh kiritish'} open={edit !== undefined} onCancel={() => setEdit(undefined)}
        onOk={() => form.submit()} confirmLoading={save.isPending}>
        <Form form={form} layout="vertical" onFinish={save.mutate} requiredMark={false}>
          <Form.Item name="teacher" label="O'qituvchi" rules={[{ required: true }]}>
            <Select showSearch optionFilterProp="label" options={teachers.map((t) => ({ value: t.id, label: t.full_name }))} />
          </Form.Item>
          <Form.Item name="period" label="Qaysi oy uchun" rules={[{ required: true }]}>
            <DatePicker picker="month" format="MMMM YYYY" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="amount" label="Summa" rules={[{ required: true }]}>
            <InputNumber<number> min={0} style={{ width: '100%' }} addonAfter="so'm"
              formatter={(v) => `${v ?? ''}`.replace(/\B(?=(\d{3})+(?!\d))/g, ' ')}
              parser={(v) => Number((v ?? '').replace(/\s/g, ''))} />
          </Form.Item>
          <Form.Item name="paid_at" label="To'langan sana" extra="Bo'sh qoldirilsa — 'to'lanmagan'">
            <DatePicker format="DD.MM.YYYY" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="note" label="Izoh"><Input /></Form.Item>
        </Form>
      </Modal>
    </>
  )
}
