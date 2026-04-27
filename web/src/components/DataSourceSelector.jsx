import { useState, useEffect, useCallback } from 'react'
import { getDataSource, setDataSource } from '../api/client'

const LABELS = {
  tushare: 'Tushare',
  ifind: 'iFinD (同花顺)',
}

export default function DataSourceSelector({ onChange }) {
  const [current, setCurrent] = useState(null)
  const [options, setOptions] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState('')

  useEffect(() => {
    getDataSource().then(res => {
      setCurrent(res.current)
      setOptions(res.options || ['tushare', 'ifind'])
      setError('')
    }).catch(() => {
      setCurrent('tushare')
      setOptions(['tushare', 'ifind'])
    })
  }, [])

  const handleChange = useCallback(async (e) => {
    const next = e.target.value
    setLoading(true)
    setError('')
    try {
      await setDataSource(next)
      setCurrent(next)
      onChange?.(next)
    } catch (err) {
      setError('切换失败')
    } finally {
      setLoading(false)
    }
  }, [onChange])

  if (!current) return null

  return (
    <div className="datasource-selector">
      <label>数据源:</label>
      <select value={current} onChange={handleChange} disabled={loading}>
        {options.map(opt => (
          <option key={opt} value={opt}>
            {LABELS[opt] || opt}
          </option>
        ))}
      </select>
      {loading && <span className="ds-hint">切换中...</span>}
      {error && <span className="ds-error">{error}</span>}
    </div>
  )
}
