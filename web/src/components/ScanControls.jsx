import { useState, useEffect, useCallback } from 'react'
import { startScan, scanState } from '../api/client'
import StrategyParams, { DEFAULTS } from './StrategyParams'
import ScheduleSettings from './ScheduleSettings'

const STORAGE_KEY = 'strategy_params'

function loadSavedParams() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved ? { ...DEFAULTS, ...JSON.parse(saved) } : { ...DEFAULTS }
  } catch {
    return { ...DEFAULTS }
  }
}

export default function ScanControls({ onComplete, onParamsChange }) {
  const [running, setRunning] = useState(false)
  const [progress, setProgress] = useState(null)
  const [params, setParams] = useState(loadSavedParams)

  const saveParams = useCallback((newParams) => {
    setParams(newParams)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(newParams))
    onParamsChange?.(newParams)
  }, [onParamsChange])

  const changeParam = useCallback((key, value) => {
    saveParams({ ...params, [key]: value })
  }, [params, saveParams])

  const resetParams = useCallback(() => {
    saveParams({ ...DEFAULTS })
  }, [saveParams])

  useEffect(() => {
    onParamsChange?.(params)
  }, [])

  const connectSSE = useCallback(() => {
    const es = new EventSource('/api/scan/status')
    es.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.type === 'progress') {
        setProgress(data)
      } else if (data.type === 'complete') {
        setRunning(false)
        setProgress(null)
        es.close()
        onComplete()
      } else if (data.type === 'error') {
        setRunning(false)
        setProgress(null)
        es.close()
      } else if (data.type === 'watchlist_alerts') {
        if (data.alerts?.length && Notification.permission === 'granted') {
          for (const a of data.alerts) {
            new Notification('止损提醒', { body: `${a.name}(${a.code}) 已触发止损信号！` })
          }
        }
      }
    }
    es.onerror = () => { es.close(); setRunning(false); setProgress(null) }
    return es
  }, [onComplete])

  const start = useCallback(async () => {
    try {
      const res = await startScan({ strategy: params })
      if (res.status === 'started') {
        setRunning(true)
        connectSSE()
      } else if (res.status === 'already_running') {
        setRunning(true)
        connectSSE()
      }
    } catch {}
  }, [connectSSE, params])

  useEffect(() => {
    scanState().then(res => {
      if (res.status === 'running') {
        setRunning(true)
        const es = connectSSE()
        return () => es.close()
      }
    })
  }, [connectSSE])

  const pct = progress ? progress.percent : 0

  return (
    <>
      <div className="scan-bar">
        <button className="btn btn-primary" disabled={running} onClick={start}>
          {running ? '扫描中...' : '开始扫描'}
        </button>
        {running && progress && (
          <>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${pct}%` }} />
            </div>
            <span className="progress-text">{progress.current}/{progress.total} ({pct}%)</span>
          </>
        )}
      </div>
      <StrategyParams params={params} onChange={changeParam} onReset={resetParams} />
      <ScheduleSettings />
    </>
  )
}
