import { useState } from 'react'

const PARAMS = [
  { key: 'rise_threshold', label: '涨幅阈值%', min: 5, max: 15, step: 0.5 },
  { key: 'vol_ratio_threshold', label: '量比阈值', min: 1, max: 5, step: 0.1 },
  { key: 'vol_shrink_ratio', label: '缩量比', min: 0.1, max: 0.9, step: 0.05 },
  { key: 'vol_ma_window', label: '量均线窗口', min: 5, max: 60, step: 1 },
  { key: 'cons_min_days', label: '整理最少天数', min: 1, max: 7, step: 1 },
  { key: 'cons_max_days', label: '整理最多天数', min: 5, max: 30, step: 1 },
]

const DEFAULTS = {
  vol_ma_window: 20,
  vol_ratio_threshold: 2.0,
  rise_threshold: 9.5,
  cons_min_days: 3,
  cons_max_days: 15,
  vol_shrink_ratio: 0.5,
}

export default function StrategyParams({ params, onChange, onReset }) {
  const [open, setOpen] = useState(false)

  return (
    <div className="strategy-panel">
      <button className="btn btn-sm strategy-toggle" onClick={() => setOpen(!open)}>
        策略参数 {open ? '▲' : '▼'}
      </button>
      {open && (
        <div className="strategy-grid">
          {PARAMS.map(p => (
            <div key={p.key} className="param-group">
              <label>{p.label}</label>
              <input
                type="number"
                min={p.min}
                max={p.max}
                step={p.step}
                value={params[p.key]}
                onChange={(e) => onChange(p.key, parseFloat(e.target.value) || DEFAULTS[p.key])}
              />
            </div>
          ))}
          <button className="btn btn-sm" onClick={onReset}>重置默认</button>
        </div>
      )}
    </div>
  )
}

export { DEFAULTS }
