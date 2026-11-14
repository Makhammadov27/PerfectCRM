import { LockOutlined, PhoneOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Form, Input, Typography } from 'antd'
import { useState } from 'react'
import { Navigate, useNavigate } from 'react-router-dom'
import { errorText } from '../api'
import { useAuth } from '../auth'

export default function Login() {
  const { me, login } = useAuth()
  const nav = useNavigate()
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)

  if (me) return <Navigate to="/" replace />

  const submit = async (v: { phone: string; password: string }) => {
    setLoading(true)
    setError('')
    try {
      await login(v.phone.trim(), v.password)
      nav('/')
    } catch (e) {
      const t = errorText(e)
      setError(t.includes('No active account') ? "Telefon raqami yoki parol noto'g'ri" : t)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="login-wrap">
      <Card style={{ width: '100%', maxWidth: 400, boxShadow: '0 20px 50px -20px rgba(79,70,229,.25)' }}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div className="brand-logo" style={{ width: 52, height: 52, fontSize: 24, margin: '0 auto 12px', borderRadius: 14 }}>
            P
          </div>
          <Typography.Title level={3} style={{ margin: 0 }}>
            PerfectCRM
          </Typography.Title>
          <Typography.Text type="secondary">Admin paneliga kirish</Typography.Text>
        </div>
        {error && <Alert type="error" message={error} showIcon style={{ marginBottom: 16 }} />}
        <Form layout="vertical" onFinish={submit} requiredMark={false} size="large">
          <Form.Item name="phone" label="Telefon raqami" rules={[{ required: true, message: 'Telefon raqamini kiriting' }]}>
            <Input prefix={<PhoneOutlined />} placeholder="+998901234567" autoComplete="username" />
          </Form.Item>
          <Form.Item name="password" label="Parol" rules={[{ required: true, message: 'Parolni kiriting' }]}>
            <Input.Password prefix={<LockOutlined />} autoComplete="current-password" />
          </Form.Item>
          <Button type="primary" htmlType="submit" block loading={loading}>
            Kirish
          </Button>
        </Form>
      </Card>
    </div>
  )
}
