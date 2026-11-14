import {
  AppstoreOutlined, BankOutlined, BarChartOutlined, BellOutlined, CalendarOutlined, DashboardOutlined,
  DollarOutlined, LogoutOutlined, MenuOutlined, MoonOutlined, SettingOutlined, SunOutlined, TeamOutlined,
  UserOutlined, WalletOutlined, WarningOutlined,
} from '@ant-design/icons'
import { Avatar, Button, Drawer, Dropdown, Grid, Layout, Menu, theme } from 'antd'
import { useState } from 'react'
import { Outlet, useLocation, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth'
import { useThemeMode } from '../theme'

const { Sider, Header, Content } = Layout

const items = [
  { key: '/', icon: <DashboardOutlined />, label: 'Bosh sahifa' },
  { key: '/students', icon: <UserOutlined />, label: "O'quvchilar" },
  { key: '/groups', icon: <AppstoreOutlined />, label: 'Guruhlar' },
  { key: '/schedule', icon: <CalendarOutlined />, label: 'Jadval va davomat' },
  { type: 'divider' as const },
  { key: '/payments', icon: <DollarOutlined />, label: "To'lovlar" },
  { key: '/debtors', icon: <WarningOutlined />, label: 'Qarzdorlar' },
  { key: '/salaries', icon: <WalletOutlined />, label: 'Maoshlar' },
  { key: '/reports', icon: <BarChartOutlined />, label: 'Hisobotlar' },
  { type: 'divider' as const },
  { key: '/teachers', icon: <TeamOutlined />, label: "O'qituvchilar" },
  { key: '/rooms', icon: <BankOutlined />, label: 'Xonalar' },
  { key: '/notifications', icon: <BellOutlined />, label: 'Xabarlar' },
  { key: '/settings', icon: <SettingOutlined />, label: 'Sozlamalar' },
]

export default function AppLayout() {
  const nav = useNavigate()
  const loc = useLocation()
  const { me, logout } = useAuth()
  const { mode, toggle } = useThemeMode()
  const screens = Grid.useBreakpoint()
  const [open, setOpen] = useState(false)
  const { token } = theme.useToken()
  const mobile = !screens.lg

  const selected = '/' + (loc.pathname.split('/')[1] || '')
  const menu = (
    <>
      <div className="brand">
        <div className="brand-logo">P</div>
        PerfectCRM
      </div>
      <Menu
        mode="inline"
        selectedKeys={[selected]}
        items={items}
        style={{ border: 'none', padding: '0 10px' }}
        onClick={({ key }) => {
          nav(key)
          setOpen(false)
        }}
      />
    </>
  )

  return (
    <Layout style={{ minHeight: '100vh' }}>
      {mobile ? (
        <Drawer open={open} onClose={() => setOpen(false)} placement="left" width={260} styles={{ body: { padding: 0 } }}>
          {menu}
        </Drawer>
      ) : (
        <Sider
          width={248}
          style={{ position: 'sticky', top: 0, height: '100vh', overflow: 'auto', borderRight: `1px solid ${token.colorBorderSecondary}` }}
        >
          {menu}
        </Sider>
      )}
      <Layout>
        <Header
          style={{
            position: 'sticky', top: 0, zIndex: 10, display: 'flex', alignItems: 'center', gap: 8,
            padding: mobile ? '0 12px' : '0 28px', borderBottom: `1px solid ${token.colorBorderSecondary}`,
          }}
        >
          {mobile && <Button type="text" icon={<MenuOutlined />} onClick={() => setOpen(true)} />}
          <div style={{ flex: 1 }} />
          <Button
            type="text"
            shape="circle"
            icon={mode === 'dark' ? <SunOutlined /> : <MoonOutlined />}
            onClick={toggle}
            title="Rejimni almashtirish"
          />
          <Dropdown
            menu={{ items: [{ key: 'logout', icon: <LogoutOutlined />, label: 'Chiqish', onClick: logout }] }}
            trigger={['click']}
          >
            <Button type="text" style={{ height: 44, display: 'flex', alignItems: 'center', gap: 8 }}>
              <Avatar style={{ background: token.colorPrimary }}>{me?.full_name?.[0] ?? 'A'}</Avatar>
              {!mobile && <span style={{ fontWeight: 500 }}>{me?.full_name}</span>}
            </Button>
          </Dropdown>
        </Header>
        <Content style={{ padding: mobile ? 16 : 28, maxWidth: 1440, width: '100%', margin: '0 auto' }}>
          <Outlet />
        </Content>
      </Layout>
    </Layout>
  )
}
