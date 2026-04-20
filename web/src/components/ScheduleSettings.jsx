import { useState, useEffect } from 'react'
import { getSchedule, updateSchedule } from '../api/client'

export default function ScheduleSettings() {
  const [open, setOpen] = useState(false)
  const [config, setConfig] = useState({ enabled: false, hour: 15, minute: 30 })
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    getSchedule().then(setConfig).catch(() => {})
  }, [])

  async function save(newConfig) {
    setSaving(true)
    try {
      const res = await updateSchedule(newConfig)
      setConfig(res)
    } catch {}
    setSaving(false)
  }

  function toggleEnabled() {
    save({ ...config, enabled: !config.enabled })
  }

  function changeTime(field, value) {
    save({ ...config, [field]: parseInt(value) || 0 })
  }

  return (
    <div className="schedule-panel">
      <button className="btn btn-sm strategy-toggle" onClick={() => setOpen(!open)}>
        定时扫描 {open ? '▲' : '▼'}
      </button>
      {open && (
        <div className="schedule-grid">
          <label className="toggle-row">
            <span>启用</span>
            <input type="checkbox" checked={config.enabled} onChange={toggleEnabled} disabled={saving} />
          </label>
          <div className="time-row">
            <span>扫描时间</span>
            <input type="number" min={0} max={23} value={config.hour}
              onChange={(e) => changeTime('hour', e.target.value)} disabled={saving || !config.enabled} />
            <span>:</span>
            <input type="number" min={0} max={59} value={config.minute}
              onChange={(e) => changeTime('minute', e.target.value)} disabled={saving || !config.enabled} />
          </div>
          {config.enabled && <p className="schedule-hint">将在每日 {String(config.hour).padStart(2,'0')}:{String(config.minute).padStart(2,'0')} 自动扫描</p>}
        </div>
      )}
    </div>
  )
}
