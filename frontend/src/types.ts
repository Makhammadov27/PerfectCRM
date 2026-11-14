export type Me = { id: number; phone: string; full_name: string; role: 'admin' | 'teacher' }

export type Teacher = {
  id: number
  phone: string
  full_name: string
  is_active: boolean
  telegram_linked: boolean
  groups_count: number
}

export type Room = { id: number; name: string; capacity: number }

export type Slot = { weekday: number; start_time: string; end_time: string }

export type Group = {
  id: number
  name: string
  subject: string
  teacher: number
  teacher_name: string
  room: number
  room_name: string
  monthly_price: number
  lesson_price: number
  start_date: string
  end_date: string | null
  status: 'active' | 'finished'
  schedule: Slot[]
  students_count: number
}

export type Parent = { id?: number; full_name: string; phone: string; telegram_linked?: boolean }

export type Student = {
  id: number
  full_name: string
  phone: string
  birth_date: string | null
  note: string
  status: 'active' | 'left'
  created_at: string
  parents: Parent[]
  groups: { id: number; name: string; enrollment_id: number }[]
  balance: number
}

export type Enrollment = {
  id: number
  student: number
  student_name: string
  student_phone: string
  group: number
  group_name: string
  joined_at: string
  left_at: string | null
  discount_type: 'none' | 'percent' | 'fixed'
  discount_value: number
  discount_reason: string
  balance?: number
}

export type Lesson = {
  id: number
  group: number
  group_name: string
  teacher_name: string
  room: number
  room_name: string
  date: string
  start_time: string
  end_time: string
  status: 'planned' | 'done' | 'cancelled'
  kind: 'regular' | 'makeup'
  replaces: number | null
  attendance_taken: boolean
}

export type AttendanceStatus = 'present' | 'absent' | 'late' | 'excused'

export type Invoice = {
  id: number
  student_id: number
  student_name: string
  group_name: string
  period: string
  lessons_count: number
  base_amount: number
  discount_amount: number
  amount: number
  paid_amount: number
  debt: number
  due_date: string
  status: 'open' | 'partial' | 'paid' | 'void'
}

export type Payment = {
  id: number
  student: number
  student_name: string
  amount: number
  method: 'cash' | 'card' | 'transfer'
  paid_at: string
  receipt_no: string
  receipt_token: string
  note: string
  received_by_name: string
  cancelled_at: string | null
  cancelled_by_name: string | null
  cancel_reason: string
}

export type Refund = {
  id: number
  student: number
  student_name: string
  amount: number
  paid_at: string
  given_by_name: string
  reason: string
}

export type Salary = {
  id: number
  teacher: number
  teacher_name: string
  period: string
  amount: number
  paid_at: string | null
  note: string
}

export type Debtor = {
  student_id: number
  student_name: string
  phone: string
  parent_phones: string[]
  groups: string[]
  debt: number
  overdue_debt: number
  oldest_due: string
  days_overdue: number
}

export type Notification = {
  id: number
  parent_name: string
  parent_phone: string
  student_name: string | null
  channel: 'telegram' | 'sms'
  kind: string
  text: string
  status: 'pending' | 'sent' | 'failed'
  attempts: number
  error: string
  created_at: string
  sent_at: string | null
}
