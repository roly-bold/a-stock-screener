import { useEffect, useMemo, useState } from 'react'
import { getScanHistory } from '../api/client'

function formatScope(scope) {
  if (!scope) return '全部板块 / 全部行业'
  return `${scope.market_board || '全部板块'} / ${scope.industry || '全部行业'}`
}

function formatLog(log) {
  if (log.type === 'error') return log.message || '扫描出错'
  if (log.type === 'cancelled') return '扫描已停止'
  if (log.type === 'complete') return '扫描完成'
  if (log.phase) {
    const pct = log.percent ?? 0
    const current = log.current ?? 0
    const total = log.total ?? 0
    const suffix = log.pending ? `，剩余 ${log.pending} 个任务等待返回` : ''
    return `${log.phase}: ${current}/${total} (${pct}%)${suffix}`
  }
  return log.message || log.type
}

export default function ScanHistoryPanel() {
  const [runs, setRuns] = useState([])
  const [expandedRunId, setExpandedRunId] = useState('')

  useEffect(() => {
    let mounted = true
    const load = async () => {
      try {
        const res = await getScanHistory()
        if (!mounted) return
        const nextRuns = res.runs || []
        setRuns(nextRuns)
        if (!expandedRunId && nextRuns.length) {
          setExpandedRunId(nextRuns[0].run_id)
        }
      } catch {}
    }
    load()
    const timer = setInterval(load, 10000)
    return () => {
      mounted = false
      clearInterval(timer)
    }
  }, [expandedRunId])

  const visibleRuns = useMemo(() => runs.slice(0, 8), [runs])

  return (
    <section className="history-panel">
      <div className="history-header">
        <div>
          <h3>扫描历史 / 日志</h3>
          <p>最近 8 次扫描都会保留阶段日志，后面再卡住时能直接看到停在哪。</p>
        </div>
      </div>
      {!visibleRuns.length ? (
        <div className="empty-state history-empty">暂无扫描历史</div>
      ) : (
        <div className="history-list">
          {visibleRuns.map((run) => {
            const expanded = expandedRunId === run.run_id
            const latestLog = run.logs?.[run.logs.length - 1]
            return (
              <article key={run.run_id} className="history-card">
                <button className="history-summary" onClick={() => setExpandedRunId(expanded ? '' : run.run_id)}>
                  <div className="history-main">
                    <div className={`history-status status-${run.status}`}>{run.status}</div>
                    <div className="history-meta">
                      <strong>{formatScope(run.scope)}</strong>
                      <span>{run.started_at} {run.finished_at ? `→ ${run.finished_at}` : ''}</span>
                    </div>
                  </div>
                  <div className="history-side">
                    <span>{run.signals_count || 0} 条信号</span>
                    <span>{expanded ? '收起' : '展开'}</span>
                  </div>
                </button>
                <div className="history-preview">
                  <span>最近日志</span>
                  <span>{latestLog ? `${latestLog.timestamp} · ${formatLog(latestLog)}` : '暂无日志'}</span>
                </div>
                {run.error && <div className="history-error">{run.error}</div>}
                {expanded && (
                  <div className="history-logs">
                    {(run.logs || []).slice(-20).map((log, index) => (
                      <div key={`${run.run_id}-${index}`} className="history-log-row">
                        <span>{log.timestamp}</span>
                        <span>{formatLog(log)}</span>
                      </div>
                    ))}
                  </div>
                )}
              </article>
            )
          })}
        </div>
      )}
    </section>
  )
}
