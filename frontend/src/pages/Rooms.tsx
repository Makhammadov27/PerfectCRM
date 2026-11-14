import { DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { App, Button, Card, Form, Input, InputNumber, Modal, Popconfirm, Table } from 'antd'
import { useEffect, useState } from 'react'
import { api, errorText } from '../api'
import { PageHead, useRooms } from '../components/common'
import type { Room } from '../types'

export default function Rooms() {
  const { data = [], isLoading } = useRooms()
  const [edit, setEdit] = useState<Room | null | undefined>(undefined)
  const [form] = Form.useForm()
  const { message } = App.useApp()
  const qc = useQueryClient()

  useEffect(() => {
    if (edit === undefined) return
    form.resetFields()
    form.setFieldsValue(edit ?? { capacity: 15 })
  }, [edit, form])

  const save = useMutation({
    mutationFn: async (v: object) => (edit ? api.put(`/rooms/${edit.id}/`, v) : api.post('/rooms/', v)),
    onSuccess: () => {
      message.success('Saqlandi')
      qc.invalidateQueries({ queryKey: ['rooms'] })
      setEdit(undefined)
    },
    onError: (e) => message.error(errorText(e)),
  })
  const del = useMutation({
    mutationFn: async (id: number) => api.delete(`/rooms/${id}/`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['rooms'] }),
    onError: (e) => message.error(errorText(e)),
  })

  return (
    <>
      <PageHead title="Xonalar" extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => setEdit(null)}>Yangi xona</Button>} />
      <Card variant="borderless" style={{ maxWidth: 640 }}>
        <Table<Room>
          rowKey="id" loading={isLoading} dataSource={data} pagination={false}
          columns={[
            { title: 'Nomi', dataIndex: 'name', render: (v, r) => <a onClick={() => setEdit(r)}><b>{v}</b></a> },
            { title: "Sig'imi", dataIndex: 'capacity', render: (v) => `${v} kishi` },
            {
              title: '', width: 60,
              render: (_, r) => (
                <Popconfirm title="Xonani o'chirasizmi?" onConfirm={() => del.mutate(r.id)} okText="Ha" cancelText="Yo'q">
                  <Button type="text" danger icon={<DeleteOutlined />} />
                </Popconfirm>
              ),
            },
          ]}
        />
      </Card>
      <Modal title={edit ? 'Xonani tahrirlash' : 'Yangi xona'} open={edit !== undefined} onCancel={() => setEdit(undefined)}
        onOk={() => form.submit()} confirmLoading={save.isPending}>
        <Form form={form} layout="vertical" onFinish={save.mutate} requiredMark={false}>
          <Form.Item name="name" label="Nomi" rules={[{ required: true }]}><Input placeholder="101-xona" /></Form.Item>
          <Form.Item name="capacity" label="Sig'imi"><InputNumber min={1} style={{ width: '100%' }} /></Form.Item>
        </Form>
      </Modal>
    </>
  )
}
