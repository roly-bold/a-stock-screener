import { useEffect, useState } from 'react'
import { getScanUniverse } from '../api/client'

const STORAGE_KEY = 'scan_scope'
const DEFAULT_SCOPE = {
  market_board: '全部板块',
  industry: '全部行业',
}

function loadSavedScope() {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    return saved ? { ...DEFAULT_SCOPE, ...JSON.parse(saved) } : { ...DEFAULT_SCOPE }
  } catch {
    return { ...DEFAULT_SCOPE }
  }
}

export default function ScanScopeSelector({ value, onChange }) {
  const [open, setOpen] = useState(false)
  const [options, setOptions] = useState({ market_boards: [], industries: [], total_count: 0 })
  const [loading, setLoading] = useState(false)

  const scope = value || loadSavedScope()

  useEffect(() => {
    let cancelled = false
    setLoading(true)
    getScanUniverse(scope.market_board === '全部板块' ? '' : scope.market_board)
      .then((res) => {
        if (!cancelled) setOptions(res)
      })
      .catch(() => {
        if (!cancelled) setOptions({ market_boards: [], industries: [], total_count: 0 })
      })
      .finally(() => {
        if (!cancelled) setLoading(false)
      })
    return () => { cancelled = true }
  }, [scope.market_board])

  const updateScope = (patch) => {
    const next = { ...scope, ...patch }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next))
    onChange?.(next)
  }

  return (
    <div className="scope-panel">
      <button className="btn btn-sm strategy-toggle" onClick={() => setOpen(!open)}>
        扫描范围 {open ? '▲' : '▼'}
      </button>
      {open && (
        <div className="strategy-grid">
          <div className="param-group">
            <label>市场板块</label>
            <select
              value={scope.market_board}
              onChange={(e) => updateScope({ market_board: e.target.value, industry: '全部行业' })}
            >
              <option value="全部板块">全部板块</option>
              {options.market_boards.map((item) => (
                <option key={item.name} value={item.name}>{item.name} ({item.count})</option>
              ))}
            </select>
          </div>
          <div className="param-group">
            <label>行业板块</label>
            <select
              value={scope.industry}
              onChange={(e) => updateScope({ industry: e.target.value })}
            >
              <option value="全部行业">全部行业</option>
              {options.industries.map((item) => (
                <option key={item.name} value={item.name}>{item.name} ({item.count})</option>
              ))}
            </select>
          </div>
          <div className="scope-summary">
            <span>当前范围</span>
            <strong>{loading ? '加载中...' : `${options.total_count || 0} 只股票`}</strong>
          </div>
        </div>
      )}
    </div>
  )
}

export { DEFAULT_SCOPE, loadSavedScope }
