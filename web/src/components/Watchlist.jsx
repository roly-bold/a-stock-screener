import { useState, useEffect, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { getWatchlist, removeFromWatchlist, refreshWatchlist } from '../api/client'

export default function Watchlist() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [refreshing, setRefreshing] = useState(false)

  const load = useCallback(async () => {
    try {
      const data = await getWatchlist()
      setItems(data.items || [])
    } catch {}
    setLoading(false)
  }, [])

  useEffect(() => { load() }, [load])

  useEffect(() => {
    if (Notification.permission === 'default') {
      Notification.requestPermission()
    }
  }, [])

  async function handleRefresh() {
    setRefreshing(true)
    try {
      const res = await refreshWatchlist()
      if (res.alerts && res.alerts.length > 0) {
        for (const alert of res.alerts) {
          if (Notification.permission === 'granted') {
            new Notification('止损提醒', { body: `${alert.name}(${alert.code}) 已触发止损信号！` })
          }
        }
      }
      await load()
    } catch {}
    setRefreshing(false)
  }

  async function handleRemove(code) {
    try {
      await removeFromWatchlist(code)
      setItems(prev => prev.filter(i => i.code !== code))
    } catch {}
  }

  if (loading) return <div className="empty-state">加载中...</div>

  return (
    <>
      <Link to="/" className="back-link">← 返回列表</Link>
      <div className="scan-bar">
        <h2>监控列表</h2>
        <button className="btn btn-primary btn-sm" onClick={handleRefresh} disabled={refreshing}>
          {refreshing ? '刷新中...' : '刷新数据'}
        </button>
      </div>
      {items.length === 0 ? (
        <div className="empty-state">暂无监控股票，从扫描结果中添加</div>
      ) : (
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>代码</th>
                <th>名称</th>
                <th>买入价</th>
                <th>最新价</th>
                <th>浮盈%</th>
                <th>止损</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {items.map(item => (
                <tr key={item.code}>
                  <td>{item.code}</td>
                  <td>{item.name}</td>
                  <td>{item.entry_price?.toFixed(2)}</td>
                  <td>{item.latest_close?.toFixed(2) || '-'}</td>
                  <td className={item.pnl_pct >= 0 ? 'up' : 'down'}>
                    {item.pnl_pct != null ? `${item.pnl_pct >= 0 ? '+' : ''}${item.pnl_pct.toFixed(2)}%` : '-'}
                  </td>
                  <td>{item.exit_triggered ? <span className="alert-badge">止损</span> : ''}</td>
                  <td><button className="btn btn-sm btn-danger" onClick={() => handleRemove(item.code)}>移除</button></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </>
  )
}
