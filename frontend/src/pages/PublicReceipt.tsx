import { CheckCircleFilled, CloseCircleFilled } from '@ant-design/icons'
import { useQuery } from '@tanstack/react-query'
import { Card, Result, Skeleton } from 'antd'
import axios from 'axios'
import { useParams } from 'react-router-dom'
import { fmtDateTime } from '../utils'

type R = { valid: boolean; cancelled: boolean; center_name: string; receipt_no: string; amount_display: string; paid_at: string; student: string }

/** Chekdagi QR-kod ochadigan ochiq sahifa: chek haqiqiymi? */
export default function PublicReceipt() {
  const { token } = useParams()
  const { data, isLoading, isError } = useQuery({
    queryKey: ['public-receipt', token],
    queryFn: async () => (await axios.get<R>(`/api/public/receipt/${token}/`)).data,
    retry: false,
  })
  return (
    <div className="login-wrap">
      <Card style={{ width: '100%', maxWidth: 420 }}>
        {isLoading ? <Skeleton active /> : isError || !data ? (
          <Result status="error" title="Chek topilmadi" subTitle="Bu chek tizimda yo'q — u soxta bo'lishi mumkin." />
        ) : (
          <Result
            icon={data.valid ? <CheckCircleFilled style={{ color: '#16A34A' }} /> : <CloseCircleFilled style={{ color: '#DC2626' }} />}
            title={data.valid ? 'Chek haqiqiy' : 'Chek bekor qilingan'}
            subTitle={data.center_name}
            extra={
              <div style={{ textAlign: 'left', display: 'grid', gap: 6 }}>
                <div>Chek №: <b>{data.receipt_no}</b></div>
                <div>Summa: <b>{data.amount_display}</b></div>
                <div>Sana: {fmtDateTime(data.paid_at)}</div>
                <div>O'quvchi: {data.student}</div>
              </div>
            }
          />
        )}
      </Card>
    </div>
  )
}
