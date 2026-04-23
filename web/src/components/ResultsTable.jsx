import { useState, useMemo } from 'react'
import { useNavigate } from 'react-router-dom'
import { addToWatchlist } from '../api/client'

export default function ResultsTable({ signals, strategyParams }) {
  const navigate = useNavigate()
  const [sortKey, setSortKey] = useState('entry_date')
  const [sortDir, setSortDir] = useState('desc')
  const [selected, setSelected] = useState(new Set())

  const sorted = useMemo(() => {
    const arr = [...signals]
    arr.sort((a, b) => {
      let va = a[sortKey], vb = b[sortKey]
      if (typeof va === 'string') { va = va || ''; vb = vb || '' }
      if (va < vb) return sortDir === 'asc' ? -1 : 1
      if (va > vb) return sortDir === 'asc' ? 1 : -1
      return 0
    })
    return arr
  }, [signals, sortKey, sortDir])

  function toggleSort(key) {
    if (sortKey === key) setSortDir(d => d === 'asc' ? 'desc' : 'asc')
    else { setSortKey(key); setSortDir('desc') }
  }

  function SortTh({ k, children }) {
    const arrow = sortKey === k ? (sortDir === 'asc' ? '▲' : '▼') : ''
    return <th onClick={() => toggleSort(k)}>{children}<span className="sort-arrow">{arrow}</span></th>
  }

  function toggleSelect(i, e) {
    e.stopPropagation()
    setSelected(prev => {
      const next = new Set(prev)
      if (next.has(i)) { next.delete(i) } else { next.add(i) }
      return next
    })
  }

  function compareSelected() {
    const codes = [...selected].map(i => sorted[i].code)
    navigate(`/compare?codes=${codes.join(',')}`)
  }

  async function handleWatch(s, e) {
    e.stopPropagation()
    try {
      await addToWatchlist({ code: s.code, name: s.name, entry_price: s.entry_price, entry_date: s.entry_date })
    } catch {}
  }

  if (!signals.length) {
    return <div className="empty-state">暂无扫描结果，点击上方按钮开始扫描</div>
  }

  return (
    <>
      <div className="table-wrap">
        <table>
          <thead>
            <tr>
              <th className="th-check"></th>
              <SortTh k="code">代码</SortTh>
              <SortTh k="name">名称</SortTh>
              <SortTh k="breakout_date">起爆日</SortTh>
              <SortTh k="entry_date">买入日</SortTh>
              <SortTh k="entry_price">买入价</SortTh>
              <SortTh k="latest_close">最新价</SortTh>
              <SortTh k="pnl_pct">浮盈%</SortTh>
              <SortTh k="pivot_high">突破位</SortTh>
              <SortTh k="support_price">支撑位</SortTh>
              <SortTh k="winner_rate">胜率%</SortTh>
              <SortTh k="broker_count">券商</SortTh>
              <SortTh k="exit_triggered">止损</SortTh>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {sorted.map((s, i) => (
              <tr key={i} onClick={() => navigate(`/stock/${s.code}`, { state: { strategy: strategyParams } })} style={{ cursor: 'pointer' }}>
                <td onClick={(e) => e.stopPropagation()}>
                  <input type="checkbox" checked={selected.has(i)} onChange={(e) => toggleSelect(i, e)} />
                </td>
                <td>{s.code}</td>
                <td>{s.name}</td>
                <td>{s.breakout_date}</td>
                <td>{s.entry_date}</td>
                <td>{s.entry_price?.toFixed(2)}</td>
                <td>{s.latest_close?.toFixed(2)}</td>
                <td className={s.pnl_pct >= 0 ? 'up' : 'down'}>
                  {s.pnl_pct >= 0 ? '+' : ''}{s.pnl_pct?.toFixed(2)}%
                </td>
                <td>{s.pivot_high?.toFixed(2)}</td>
                <td>{s.support_price?.toFixed(2)}</td>
                <td className={s.winner_rate > 50 ? 'up' : 'down'}>{s.winner_rate?.toFixed(1)}</td>
                <td>{s.broker_count > 0 ? <span className="broker-badge" title={s.brokers?.join('、')}>{s.broker_count}家</span> : ''}</td>
                <td>{s.exit_triggered ? '✓' : ''}</td>
                <td><button className="btn btn-sm btn-watch" onClick={(e) => handleWatch(s, e)}>监控</button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {selected.size > 0 && (
        <div className="select-bar">
          <span>已选 {selected.size} 只</span>
          <button className="btn btn-sm btn-primary" onClick={compareSelected} disabled={selected.size < 2}>
            对比
          </button>
        </div>
      )}
    </>
  )
}
