import { PrinterOutlined } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Button, Modal, Skeleton } from 'antd'
import { QRCodeSVG } from 'qrcode.react'
import { api } from '../api'
import type { Payment } from '../types'
import { fmtDateTime, money } from '../utils'

type Receipt = Payment & { center_name: string; groups: string[]; method_display: string; balance: number }

export default function ReceiptModal({ paymentId, onClose }: { paymentId: number | null; onClose: () => void }) {
  const { data } = useQuery({
    queryKey: ['receipt', paymentId],
    queryFn: async () => (await api.get<Receipt>(`/payments/${paymentId}/receipt/`)).data,
    enabled: !!paymentId,
  })
  const verifyUrl = data ? `${window.location.origin}/r/${data.receipt_token}` : ''

  return (
    <Modal
      open={!!paymentId}
      onCancel={onClose}
      title="Chek"
      width={400}
      footer={[
        <Button key="c" onClick={onClose}>Yopish</Button>,
        <Button key="p" type="primary" icon={<PrinterOutlined />} onClick={() => window.print()} disabled={!data}>
          Chop etish
        </Button>,
      ]}
    >
      {!data ? (
        <Skeleton active />
      ) : (
        <div className="receipt">
          <h3>{data.center_name}</h3>
          <div className="center">TO'LOV CHEKI</div>
          <hr />
          <div className="row"><span>Chek №</span><b>{data.receipt_no}</b></div>
          <div className="row"><span>Sana</span><span>{fmtDateTime(data.paid_at)}</span></div>
          <div className="row"><span>O'quvchi</span><span style={{ textAlign: 'right' }}>{data.student_name}</span></div>
          {data.groups.length > 0 && (
            <div className="row"><span>Guruh</span><span style={{ textAlign: 'right' }}>{data.groups.join(', ')}</span></div>
          )}
          <div className="row"><span>Usul</span><span>{data.method_display}</span></div>
          <hr />
          <div className="row total"><span>JAMI</span><span>{money(data.amount)}</span></div>
          <div className="row">
            <span>{data.balance < 0 ? 'Qolgan qarz' : 'Balans'}</span>
            <span>{money(Math.abs(data.balance))}</span>
          </div>
          {data.cancelled_at && <div className="center" style={{ fontWeight: 700, marginTop: 6 }}>*** BEKOR QILINGAN ***</div>}
          <hr />
          <div className="row"><span>Qabul qildi</span><span>{data.received_by_name}</span></div>
          <div className="center" style={{ marginTop: 8 }}>
            <QRCodeSVG value={verifyUrl} size={96} />
            <div style={{ fontSize: 10, marginTop: 4 }}>Chekni tekshirish uchun skanerlang</div>
          </div>
          <div className="center" style={{ marginTop: 6 }}>Rahmat!</div>
        </div>
      )}
    </Modal>
  )
}
