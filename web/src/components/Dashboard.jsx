import { useState, useEffect, useCallback } from 'react'
import { scanResults } from '../api/client'
import ScanControls from './ScanControls'
import ScanHistoryPanel from './ScanHistoryPanel'
import ResultsTable from './ResultsTable'

export default function Dashboard() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState('')
  const [strategyParams, setStrategyParams] = useState(null)

  const loadResults = useCallback(async () => {
    setLoading(true)
    setError('')
    try {
      const res = await scanResults()
      setData(res)
    } catch (e) {
      setError('加载失败，请检查后端服务')
    }
    setLoading(false)
  }, [])

  const onComplete = useCallback(() => { loadResults() }, [loadResults])

  useEffect(() => { loadResults() }, [loadResults])

  const signals = data?.signals || []
  const timestamp = data?.timestamp || ''

  return (
    <>
      <ScanControls onComplete={onComplete} onParamsChange={setStrategyParams} />
      <ScanHistoryPanel />
      {error && <p className="error-msg">{error}</p>}
      {loading && !data ? (
        <div className="empty-state">加载中...</div>
      ) : (
        <>
          {timestamp && <p style={{ fontSize: 13, color: 'var(--text-dim)', marginBottom: 12 }}>
            上次扫描: {timestamp} | 共 {signals.length} 条信号
          </p>}
          <ResultsTable signals={signals} strategyParams={strategyParams} />
        </>
      )}
    </>
  )
}
