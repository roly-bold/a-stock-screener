import { useState, useEffect } from 'react'
import { useParams, useLocation, Link } from 'react-router-dom'
import { stockHistory, stockSignals } from '../api/client'
import KlineChart from './KlineChart'
import SignalCard from './SignalCard'

export default function StockDetail() {
  const { code } = useParams()
  const location = useLocation()
  const strategy = location.state?.strategy || {}
  const [history, setHistory] = useState([])
  const [signals, setSignals] = useState([])
  const [name, setName] = useState('')
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')

  useEffect(() => {
    setLoading(true)
    setError('')
    Promise.all([stockHistory(code), stockSignals(code, 120, strategy)])
      .then(([h, s]) => {
        setHistory(h.data || [])
        setSignals(s.signals || [])
        setName(h.name || s.name || '')
      })
      .catch(() => setError('加载数据失败'))
      .finally(() => setLoading(false))
  }, [code])

  return (
    <>
      <Link to="/" className="back-link">← 返回列表</Link>
      <div className="stock-header">
        <h2>{code}</h2>
        <span className="name">{name}</span>
      </div>
      {loading && <div className="empty-state">加载中...</div>}
      {error && <p className="error-msg">{error}</p>}
      {!loading && !error && (
        <>
          {signals.length > 0 && <SignalCard signal={signals[0]} />}
          <KlineChart history={history} signals={signals} />
        </>
      )}
    </>
  )
}
