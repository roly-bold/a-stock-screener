import { useState, useRef, useEffect } from 'react'
import { searchStock } from '../api/client'

export default function SearchInput({ onSelect }) {
  const [q, setQ] = useState('')
  const [results, setResults] = useState([])
  const [open, setOpen] = useState(false)
  const timer = useRef(null)
  const wrapRef = useRef(null)

  useEffect(() => {
    const handler = (e) => {
      if (wrapRef.current && !wrapRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handler)
    return () => document.removeEventListener('mousedown', handler)
  }, [])

  function onChange(val) {
    setQ(val)
    if (timer.current) clearTimeout(timer.current)
    if (!val.trim()) { setResults([]); setOpen(false); return }
    timer.current = setTimeout(async () => {
      try {
        const data = await searchStock(val.trim())
        setResults(data.results || [])
        setOpen(true)
      } catch { setResults([]) }
    }, 300)
  }

  function pick(item) {
    setQ('')
    setResults([])
    setOpen(false)
    onSelect(item.code)
  }

  return (
    <div className="search-wrap" ref={wrapRef}>
      <input
        placeholder="搜索股票代码/名称"
        value={q}
        onChange={(e) => onChange(e.target.value)}
        onFocus={() => results.length && setOpen(true)}
      />
      {open && results.length > 0 && (
        <div className="search-dropdown">
          {results.map((r) => (
            <div key={r.code} className="search-item" onClick={() => pick(r)}>
              {r.name}<span className="code">{r.code}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
