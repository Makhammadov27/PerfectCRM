import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { App, Button, Drawer, Form, Input, Space } from 'antd'
import { useEffect } from 'react'
import { api, errorText } from '../api'
import type { Student } from '../types'

const phoneRule = {
  pattern: /^\+?[\d\s\-()]{9,18}$/,
  message: 'Masalan: +998 90 123 45 67',
}

export default function StudentForm({
  open, onClose, student, onSaved,
}: { open: boolean; onClose: () => void; student?: Student | null; onSaved?: (s: Student) => void }) {
  const [form] = Form.useForm()
  const { message } = App.useApp()
  const qc = useQueryClient()

  useEffect(() => {
    if (!open) return
    form.resetFields()
    if (student) form.setFieldsValue(student)
    else form.setFieldsValue({ parents: [{ full_name: '', phone: '' }] })
  }, [open, student, form])

  const m = useMutation({
    mutationFn: async (body: Record<string, unknown>) => {
      return student
        ? (await api.patch<Student>(`/students/${student.id}/`, body)).data
        : (await api.post<Student>('/students/', body)).data
    },
    onSuccess: (s) => {
      message.success('Saqlandi')
      qc.invalidateQueries({ queryKey: ['students'] })
      qc.invalidateQueries({ queryKey: ['student', s.id] })
      onSaved?.(s)
      onClose()
    },
    onError: (e) => message.error(errorText(e)),
  })

  return (
    <Drawer
      title={student ? "O'quvchini tahrirlash" : "Yangi o'quvchi"}
      open={open}
      onClose={onClose}
      width={480}
      extra={
        <Button type="primary" onClick={() => form.submit()} loading={m.isPending}>
          Saqlash
        </Button>
      }
    >
      <Form form={form} layout="vertical" onFinish={m.mutate} requiredMark={false}>
        <Form.Item name="full_name" label="F.I.Sh." rules={[{ required: true, message: 'Ismni kiriting' }]}>
          <Input placeholder="Aliyev Vali" />
        </Form.Item>
        <Form.Item name="note" label="Izoh">
          <Input.TextArea rows={2} />
        </Form.Item>

        <div style={{ fontWeight: 600, margin: '8px 0 12px' }}>Ota-onalar (xabarlar shu raqamlarga boradi)</div>
        <Form.List name="parents">
          {(fields, { add, remove }) => (
            <>
              {fields.map(({ key, name }) => (
                <Space key={key} align="start" style={{ display: 'flex' }}>
                  <Form.Item name={[name, 'id']} hidden>
                    <Input />
                  </Form.Item>
                  <Form.Item name={[name, 'full_name']} rules={[{ required: true, message: 'Ism' }]}>
                    <Input placeholder="Ismi (Onasi)" />
                  </Form.Item>
                  <Form.Item name={[name, 'phone']} rules={[{ required: true, message: 'Telefon' }, phoneRule]}>
                    <Input placeholder="+998 90 123 45 67" />
                  </Form.Item>
                  <Button type="text" danger icon={<MinusCircleOutlined />} onClick={() => remove(name)} />
                </Space>
              ))}
              <Button type="dashed" block icon={<PlusOutlined />} onClick={() => add({ full_name: '', phone: '' })}>
                Ota-ona qo'shish
              </Button>
            </>
          )}
        </Form.List>
      </Form>
    </Drawer>
  )
}
