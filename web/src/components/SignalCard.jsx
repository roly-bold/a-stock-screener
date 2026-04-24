import { formatPct, getSignalDecision, getSignalMetrics } from '../utils/signalDecision'

function pctClass(value) {
  if (value == null) return ''
  return value >= 0 ? 'up' : 'down'
}

export default function SignalCard({ signal }) {
  const decision = getSignalDecision(signal)
  const metrics = getSignalMetrics(signal)
  const items = [
    { label: '当前判断', value: decision.label, cls: decision.tone === 'good' ? 'up' : decision.tone === 'danger' ? 'down' : '' },
    { label: '起爆日', value: signal.breakout_date },
    { label: '买入日', value: signal.entry_date },
    { label: '买入价', value: signal.entry_price?.toFixed(2) },
    { label: '最新价', value: signal.latest_close?.toFixed(2) },
    { label: '浮盈', value: `${signal.pnl_pct >= 0 ? '+' : ''}${signal.pnl_pct?.toFixed(2)}%`, cls: signal.pnl_pct >= 0 ? 'up' : 'down' },
    { label: '距买点', value: formatPct(metrics.distanceToEntryPct), cls: pctClass(metrics.distanceToEntryPct) },
    { label: '距支撑', value: formatPct(metrics.distanceToSupportPct), cls: pctClass(metrics.distanceToSupportPct) },
    { label: '突破位', value: signal.pivot_high?.toFixed(2) },
    { label: '支撑位', value: signal.support_price?.toFixed(2) },
    { label: '获利盘%', value: `${signal.winner_rate?.toFixed(1)}%`, cls: signal.winner_rate > 50 ? 'up' : 'down' },
    { label: '加权成本', value: signal.weight_avg_cost?.toFixed(2) },
    { label: '券商推荐', value: signal.broker_count > 0 ? `${signal.broker_count}家` : '-' },
    { label: '起爆量', value: fmtVol(signal.breakout_vol) },
    { label: '买入量', value: fmtVol(signal.entry_vol) },
  ]

  return (
    <div className="signal-cards">
      {items.map(it => (
        <div key={it.label} className="signal-card">
          <div className="label">{it.label}</div>
          <div className={`value ${it.cls || ''}`}>{it.value}</div>
        </div>
      ))}
    </div>
  )
}

function fmtVol(v) {
  if (!v) return '-'
  if (v >= 10000) return (v / 10000).toFixed(1) + '万'
  return v.toLocaleString()
}
