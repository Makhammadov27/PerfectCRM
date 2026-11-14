import { Spin } from 'antd'
import { lazy, Suspense, type ReactNode } from 'react'
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'
import { AuthProvider, useAuth } from './auth'
import AppLayout from './layout/AppLayout'
import Login from './pages/Login'

const Dashboard = lazy(() => import('./pages/Dashboard'))
const Students = lazy(() => import('./pages/Students'))
const StudentDetail = lazy(() => import('./pages/StudentDetail'))
const Groups = lazy(() => import('./pages/Groups'))
const GroupDetail = lazy(() => import('./pages/GroupDetail'))
const Schedule = lazy(() => import('./pages/Schedule'))
const Payments = lazy(() => import('./pages/Payments'))
const Debtors = lazy(() => import('./pages/Debtors'))
const Teachers = lazy(() => import('./pages/Teachers'))
const Rooms = lazy(() => import('./pages/Rooms'))
const Salaries = lazy(() => import('./pages/Salaries'))
const Reports = lazy(() => import('./pages/Reports'))
const Settings = lazy(() => import('./pages/Settings'))
const Notifications = lazy(() => import('./pages/Notifications'))
const PublicReceipt = lazy(() => import('./pages/PublicReceipt'))

const Loader = () => (
  <div style={{ display: 'grid', placeItems: 'center', minHeight: '60vh' }}>
    <Spin size="large" />
  </div>
)

function Protected({ children }: { children: ReactNode }) {
  const { me, loading } = useAuth()
  if (loading) return <Loader />
  if (!me) return <Navigate to="/login" replace />
  if (me.role !== 'admin')
    return (
      <div style={{ padding: 40, textAlign: 'center' }}>
        Veb-panel faqat admin uchun. O'qituvchilar davomatni Telegram bot orqali oladi.
      </div>
    )
  return <>{children}</>
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <Suspense fallback={<Loader />}>
          <Routes>
            <Route path="/login" element={<Login />} />
            <Route path="/r/:token" element={<PublicReceipt />} />
            <Route
              element={
                <Protected>
                  <AppLayout />
                </Protected>
              }
            >
              <Route index element={<Dashboard />} />
              <Route path="students" element={<Students />} />
              <Route path="students/:id" element={<StudentDetail />} />
              <Route path="groups" element={<Groups />} />
              <Route path="groups/:id" element={<GroupDetail />} />
              <Route path="schedule" element={<Schedule />} />
              <Route path="payments" element={<Payments />} />
              <Route path="debtors" element={<Debtors />} />
              <Route path="teachers" element={<Teachers />} />
              <Route path="rooms" element={<Rooms />} />
              <Route path="salaries" element={<Salaries />} />
              <Route path="reports" element={<Reports />} />
              <Route path="notifications" element={<Notifications />} />
              <Route path="settings" element={<Settings />} />
              <Route path="*" element={<Navigate to="/" replace />} />
            </Route>
          </Routes>
        </Suspense>
      </AuthProvider>
    </BrowserRouter>
  )
}
