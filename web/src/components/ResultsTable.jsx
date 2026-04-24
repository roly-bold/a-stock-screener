import { useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { addToWatchlist } from '../api/client'
import { formatPct, getSignalDecision, getSignalMetrics } from '../utils/signalDecision'

const VIEW_ALL = 'all'
const VIEW_SHORTLIST = 'shortlist'

function buildDecoratedSignals(signals) {
  return signals.map((signal) => {
    const metrics = getSignalMetrics(signal)
    const decision = getSignalDecision(signal)
    return { ...signal, ...metrics, decision }
  })
}

function compareValues(a, b, dir) {
  let va = a
  let vb = b
  if (typeof va === 'string') {
    va = va || ''
    vb = vb || ''
  }
  if (va == null && vb == null) return 0
  if (va == null) return 1
  if (vb == null) return -1
  if (va < vb) return dir === 'asc' ? -1 : 1
  if (va > vb) return dir === 'asc' ? 1 : -1
  return 0
}

export default function ResultsTable({ signals, strategyParams }) {
  const navigate = useNavigate()
  const [viewMode, setViewMode] = useState(VIEW_SHORTLIST)
  const [sortKey, setSortKey] = useState('entry_date')
  const [sortDir, setSortDir] = useState('desc')
  const [selected, setSelected] = useState(new Set())

  const decoratedSignals = useMemo(() => buildDecoratedSignals(signals), [signals])
  const shortlistSignals = useMemo(
    () => decoratedSignals.filter((signal) => signal.decision.label === '可关注'),
    [decoratedSignals],
  )

  const sorted = useMemo(() => {
    const source = viewMode === VIEW_SHORTLIST ? shortlistSignals : decoratedSignals
    const arr = [...source]
    arr.sort((a, b) => {
      let result = compareValues(a[sortKey], b[sortKey], sortDir)
      if (result !== 0) return result

      if (viewMode === VIEW_SHORTLIST) {
        result = compareValues(a.distanceToEntryPct, b.distanceToEntryPct, 'asc')
        if (result !== 0) return result
        result = compareValues(a.stopLossRiskPct, b.stopLossRiskPct, 'asc')
        if (result !== 0) return result
      }

      return compareValues(a.code, b.code, 'asc')
    })
    return arr
  }, [decoratedSignals, shortlistSignals, sortKey, sortDir, viewMode])

  const visibleSelected = useMemo(
    () => sorted.filter((signal) => selected.has(signal.code)),
    [selected, sorted],
  )

  function toggleSort(key) {
    if (sortKey === key) {
      setSortDir((dir) => (dir === 'asc' ? 'desc' : 'asc'))
      return
    }
    setSortKey(key)
    setSortDir(key === 'distanceToEntryPct' || key === 'stopLossRiskPct' ? 'asc' : 'desc')
  }

  function switchView(mode) {
    setViewMode(mode)
    if (mode === VIEW_SHORTLIST) {
      setSortKey('entry_date')
      setSortDir('desc')
    }
  }

  function SortTh({ k, children }) {
    const arrow = sortKey === k ? (sortDir === 'asc' ? '▲' : '▼') : ''
    return <th onClick={() => toggleSort(k)}>{children}<span className="sort-arrow">{arrow}</span></th>
  }

  function toggleSelect(code, e) {
    e.stopPropagation()
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(code)) next.delete(code)
      else next.add(code)
      return next
    })
  }

  function compareSelected() {
    const codes = visibleSelected.map((signal) => signal.code)
    navigate(`/compare?codes=${codes.join(',')}`)
  }

  async function handleWatch(signal, e) {
    e.stopPropagation()
    try {
      await addToWatchlist({
        code: signal.code,
        name: signal.name,
        entry_price: signal.entry_price,
        entry_date: signal.entry_date,
      })
    } catch {}
  }

  if (!signals.length) {
    return <div className="empty-state">暂无扫描结果，点击上方按钮开始扫描</div>
  }

  return (
    <>
      <div className="results-hint">
        <span>先看</span>
        <strong>判断</strong>
        <span>、</span>
        <strong>买入日</strong>
        <span>、</span>
        <strong>距买点%</strong>
        <span>、</span>
        <strong>预估止损%</strong>
        <span>；默认的交易清单只保留 `可关注`，更适合直接做候选池。</span>
      </div>

      <div className="results-toolbar">
        <div className="view-switch">
          <button
            className={`btn btn-sm ${viewMode === VIEW_SHORTLIST ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => switchView(VIEW_SHORTLIST)}
          >
            交易清单 ({shortlistSignals.length})
          </button>
          <button
            className={`btn btn-sm ${viewMode === VIEW_ALL ? 'btn-primary' : 'btn-ghost'}`}
            onClick={() => switchView(VIEW_ALL)}
          >
            全部结果 ({decoratedSignals.length})
          </button>
        </div>
        <div className="results-toolbar-text">
          {viewMode === VIEW_SHORTLIST
            ? '默认按买入日优先，买点越新越靠前；同一天内更接近买点、止损更短的排前面。'
            : '切回全部结果后，可以继续复盘已过买点和已止损信号。'}
        </div>
      </div>

      {!sorted.length ? (
        <div className="empty-state shortlist-empty">
          当前没有 `可关注` 候选，说明这批结果更偏历史复盘。
          <div style={{ marginTop: 12 }}>
            <button className="btn btn-sm btn-ghost" onClick={() => switchView(VIEW_ALL)}>查看全部结果</button>
          </div>
        </div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th className="th-check"></th>
                <SortTh k="code">代码</SortTh>
                <SortTh k="name">名称</SortTh>
                <th>判断</th>
                <SortTh k="breakout_date">起爆日</SortTh>
                <SortTh k="entry_date">买入日</SortTh>
                <SortTh k="entry_price">买入价</SortTh>
                <SortTh k="latest_close">最新价</SortTh>
                <SortTh k="pnl_pct">浮盈%</SortTh>
                <SortTh k="distanceToEntryPct">距买点%</SortTh>
                <SortTh k="distanceToSupportPct">距支撑%</SortTh>
                <SortTh k="stopLossRiskPct">预估止损%</SortTh>
                <SortTh k="pivot_high">突破位</SortTh>
                <SortTh k="support_price">支撑位</SortTh>
                <SortTh k="winner_rate">获利盘%</SortTh>
                <SortTh k="broker_count">券商</SortTh>
                <SortTh k="exit_triggered">止损</SortTh>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((signal) => (
                <tr
                  key={`${signal.code}-${signal.entry_date}-${signal.breakout_date}`}
                  onClick={() => navigate(`/stock/${signal.code}`, { state: { strategy: strategyParams } })}
                  style={{ cursor: 'pointer' }}
                >
                  <td onClick={(e) => e.stopPropagation()}>
                    <input
                      type="checkbox"
                      checked={selected.has(signal.code)}
                      onChange={(e) => toggleSelect(signal.code, e)}
                    />
                  </td>
                  <td>{signal.code}</td>
                  <td>{signal.name}</td>
                  <td>
                    <span className={`decision-badge decision-${signal.decision.tone}`} title={signal.decision.reason}>
                      {signal.decision.label}
                    </span>
                  </td>
                  <td>{signal.breakout_date}</td>
                  <td>{signal.entry_date}</td>
                  <td>{signal.entry_price?.toFixed(2)}</td>
                  <td>{signal.latest_close?.toFixed(2)}</td>
                  <td className={signal.pnl_pct >= 0 ? 'up' : 'down'}>
                    {signal.pnl_pct >= 0 ? '+' : ''}{signal.pnl_pct?.toFixed(2)}%
                  </td>
                  <td className={signal.distanceToEntryPct >= 0 ? 'up' : 'down'}>{formatPct(signal.distanceToEntryPct)}</td>
                  <td className={signal.distanceToSupportPct >= 0 ? 'up' : 'down'}>{formatPct(signal.distanceToSupportPct)}</td>
                  <td className={signal.stopLossRiskPct != null && signal.stopLossRiskPct <= 8 ? 'up' : 'down'}>
                    {formatPct(signal.stopLossRiskPct)}
                  </td>
                  <td>{signal.pivot_high?.toFixed(2)}</td>
                  <td>{signal.support_price?.toFixed(2)}</td>
                  <td className={signal.winner_rate > 50 ? 'up' : 'down'}>{signal.winner_rate?.toFixed(1)}</td>
                  <td>{signal.broker_count > 0 ? <span className="broker-badge" title={signal.brokers?.join('、')}>{signal.broker_count}家</span> : ''}</td>
                  <td>{signal.exit_triggered ? '✓' : ''}</td>
                  <td><button className="btn btn-sm btn-watch" onClick={(e) => handleWatch(signal, e)}>监控</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {visibleSelected.length > 0 && (
        <div className="select-bar">
          <span>已选 {visibleSelected.length} 只</span>
          <button className="btn btn-sm btn-primary" onClick={compareSelected} disabled={visibleSelected.length < 2}>
            对比
          </button>
        </div>
      )}
    </>
  )
}
