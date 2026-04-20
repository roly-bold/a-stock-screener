export default function SignalCard({ signal }) {
  const items = [
    { label: '起爆日', value: signal.breakout_date },
    { label: '买入日', value: signal.entry_date },
    { label: '买入价', value: signal.entry_price?.toFixed(2) },
    { label: '最新价', value: signal.latest_close?.toFixed(2) },
    { label: '浮盈', value: `${signal.pnl_pct >= 0 ? '+' : ''}${signal.pnl_pct?.toFixed(2)}%`, cls: signal.pnl_pct >= 0 ? 'up' : 'down' },
    { label: '突破位', value: signal.pivot_high?.toFixed(2) },
    { label: '支撑位', value: signal.support_price?.toFixed(2) },
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
