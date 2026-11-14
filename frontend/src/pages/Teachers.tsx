import { PlusOutlined } from '@ant-design/icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Alert, App, Button, Card, Form, Input, Modal, Switch, Table, Tag } from 'antd'
import { useEffect, useState } from 'react'
import { api, errorText } from '../api'
import { PageHead, useTeachers } from '../components/common'
import type { Teacher } from '../types'
import { phone } from '../utils'

export default function Teachers() {
  const { data = [], isLoading } = useTeachers()
  const [edit, setEdit] = useState<Teacher | null | undefined>(undefined)
  const [form] = Form.useForm()
  const { message } = App.useApp()
  const qc = useQueryClient()

  useEffect(() => {
    if (edit === undefined) return
    form.resetFields()
    form.setFieldsValue(edit ?? { is_active: true })
  }, [edit, form])

  const m = useMutation({
    mutationFn: async (v: object) => (edit ? api.patch(`/teachers/${edit.id}/`, v) : api.post('/teachers/', v)),
    onSuccess: () => {
      message.success('Saqlandi')
      qc.invalidateQueries({ queryKey: ['teachers'] })
      setEdit(undefined)
    },
    onError: (e) => message.error(errorText(e)),
  })

  return (
    <>
      <PageHead title="O'qituvchilar" sub={`${data.length} ta`}
        extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => setEdit(null)}>Yangi o'qituvchi</Button>} />
      <Card variant="borderless">
        <Table<Teacher>
          rowKey="id" loading={isLoading} dataSource={data} pagination={false} scroll={{ x: 600 }}
          onRow={(r) => ({ onClick: () => setEdit(r), style: { cursor: 'pointer' } })}
          columns={[
            { title: 'F.I.Sh.', dataIndex: 'full_name', render: (v) => <b>{v}</b> },
            { title: 'Telefon', dataIndex: 'phone', render: phone },
            { title: 'Guruhlar', dataIndex: 'groups_count', align: 'center' },
            {
              title: 'Telegram bot',
              dataIndex: 'telegram_linked',
              render: (v) => (v ? <Tag color="blue">Ulangan</Tag> : <Tag>Ulanmagan</Tag>),
            },
            { title: 'Holat', dataIndex: 'is_active', render: (v) => (v ? <Tag color="green">Faol</Tag> : <Tag>Faol emas</Tag>) },
          ]}
        />
      </Card>
      <Modal title={edit ? "O'qituvchini tahrirlash" : "Yangi o'qituvchi"} open={edit !== undefined}
        onCancel={() => setEdit(undefined)} onOk={() => form.submit()} confirmLoading={m.isPending}>
        <Alert type="info" showIcon style={{ marginBottom: 16 }}
          message="O'qituvchi davomatni Telegram bot orqali oladi: botga /start bosib, shu telefon raqamini yuborishi kifoya." />
        <Form form={form} layout="vertical" onFinish={m.mutate} requiredMark={false}>
          <Form.Item name="full_name" label="F.I.Sh." rules={[{ required: true }]}>
            <Input />
          </Form.Item>
          <Form.Item name="phone" label="Telefon (Telegramdagi raqam)" rules={[{ required: true }]}>
            <Input placeholder="+998901234567" />
          </Form.Item>
          <Form.Item name="is_active" label="Faol" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>
    </>
  )
}
