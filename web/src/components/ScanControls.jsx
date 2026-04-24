import { useState, useEffect, useCallback, useRef } from 'react'
import { startScan, scanState, stopScan as apiStopScan } from '../api/client'
import ScanScopeSelector, { loadSavedScope } from './ScanScopeSelector'
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
  const [error, setError] = useState('')
  const [params, setParams] = useState(loadSavedParams)
  const [scope, setScope] = useState(loadSavedScope)
  const esRef = useRef(null)
  const pollRef = useRef(null)

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

  const changeScope = useCallback((nextScope) => {
    setScope(nextScope)
  }, [])

  const stopScan = useCallback(() => {
    setRunning(false)
    setProgress(null)
    if (esRef.current) { esRef.current.close(); esRef.current = null }
    if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null }
  }, [])

  const startPolling = useCallback(() => {
    if (pollRef.current) return
    pollRef.current = setInterval(async () => {
      try {
        const res = await scanState()
        if (res.status === 'running') {
          if (res.progress) setProgress(res.progress)
          setError('')
          return
        }
        if (res.status === 'complete') {
          stopScan()
          setError('')
          onComplete()
          return
        }
        if (res.status === 'error') {
          stopScan()
          setError(res.error || '扫描出错')
          return
        }
        if (res.status === 'idle') {
          stopScan()
          onComplete()
          setError('扫描已结束，已刷新最新结果')
        }
      } catch {}
    }, 5000)
  }, [onComplete, stopScan])

  const connectSSE = useCallback(() => {
    if (esRef.current) esRef.current.close()
    const es = new EventSource('/api/scan/status')
    esRef.current = es
    es.onmessage = (e) => {
      const data = JSON.parse(e.data)
      if (data.type === 'progress') {
        setProgress(data)
        setError('')
      } else if (data.type === 'complete') {
        stopScan()
        onComplete()
      } else if (data.type === 'error') {
        stopScan()
        setError(data.message || '扫描出错')
      } else if (data.type === 'cancelled') {
        stopScan()
        setError('扫描已停止')
      } else if (data.type === 'watchlist_alerts') {
        if (data.alerts?.length && Notification.permission === 'granted') {
          for (const a of data.alerts) {
            new Notification('止损提醒', { body: `${a.name}(${a.code}) 已触发止损信号！` })
          }
        }
      }
    }
    es.onerror = () => {
      if (esRef.current === es) {
        es.close()
        esRef.current = null
      }
      setError(prev => prev || '实时连接中断，正在切换到轮询状态...')
      startPolling()
    }
  }, [onComplete, startPolling, stopScan])

  const start = useCallback(async () => {
    setError('')
    try {
      connectSSE()
      await new Promise(r => setTimeout(r, 200))
      const res = await startScan({ strategy: params, scope })
      if (res.status === 'started' || res.status === 'already_running') {
        setRunning(true)
        startPolling()
      }
    } catch (e) {
      setError('启动扫描失败')
      if (esRef.current) esRef.current.close()
    }
  }, [connectSSE, startPolling, params, scope])

  const handleStop = useCallback(async () => {
    try { await apiStopScan() } catch {}
    stopScan()
  }, [stopScan])

  useEffect(() => {
    scanState().then(res => {
      if (res.status === 'running') {
        setRunning(true)
        connectSSE()
        startPolling()
      } else if (res.status === 'complete') {
        onComplete()
      }
    })
  }, [connectSSE, onComplete, startPolling])

  useEffect(() => () => {
    if (esRef.current) esRef.current.close()
    if (pollRef.current) clearInterval(pollRef.current)
  }, [])

  const pct = progress ? progress.percent : 0
  const phaseLabel = progress?.phase ? `阶段: ${progress.phase}` : ''

  return (
    <>
      <div className="scan-bar">
        <button className="btn btn-primary" disabled={running} onClick={start}>
          {running ? '扫描中...' : '开始扫描'}
        </button>
        {running && (
          <button className="btn btn-danger" onClick={handleStop}>
            停止扫描
          </button>
        )}
        {running && progress && (
          <>
            <div className="progress-bar">
              <div className="progress-fill" style={{ width: `${pct}%` }} />
            </div>
            <span className="progress-text">{progress.current}/{progress.total} ({pct}%)</span>
            {phaseLabel && <span className="progress-text">{phaseLabel}</span>}
          </>
        )}
      </div>
      {error && <p className="error-msg">{error}</p>}
      <ScanScopeSelector value={scope} onChange={changeScope} />
      <StrategyParams params={params} onChange={changeParam} onReset={resetParams} />
      <ScheduleSettings />
    </>
  )
}
