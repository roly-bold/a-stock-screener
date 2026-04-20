import { useState, useEffect } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { stockHistory, stockSignals } from '../api/client'
import KlineChart from './KlineChart'

export default function CompareView() {
  const [searchParams] = useSearchParams()
  const codes = searchParams.get('codes')?.split(',').filter(Boolean) || []
  const [charts, setCharts] = useState([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    if (!codes.length) { setLoading(false); return }
    Promise.all(codes.map(async code => {
      const [h, s] = await Promise.all([stockHistory(code), stockSignals(code)])
      return { code, name: h.name || s.name || '', history: h.data || [], signals: s.signals || [] }
    })).then(setCharts).finally(() => setLoading(false))
  }, [searchParams])

  if (loading) return <div className="empty-state">加载中...</div>
  if (!codes.length) return <div className="empty-state">未选择对比股票</div>

  return (
    <>
      <Link to="/" className="back-link">← 返回列表</Link>
      <h2 style={{ marginBottom: 16 }}>多股对比 ({codes.length}只)</h2>
      <div className="compare-grid">
        {charts.map(c => (
          <div key={c.code} className="compare-card">
            <div className="compare-card-header">{c.name} ({c.code})</div>
            <KlineChart history={c.history} signals={c.signals} height={320} compact />
          </div>
        ))}
      </div>
    </>
  )
}
