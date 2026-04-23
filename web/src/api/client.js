const BASE = '/api'

export async function fetchJSON(path, options = {}) {
  const res = await fetch(`${BASE}${path}`, options)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export function scanResults() {
  return fetchJSON('/scan/results')
}

export function startScan(params = {}) {
  return fetchJSON('/scan/start', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(params),
  })
}

export function getStrategyParams() {
  return fetchJSON('/scan/params')
}

export function scanState() {
  return fetchJSON('/scan/state')
}

export function stopScan() {
  return fetchJSON('/scan/stop', { method: 'POST' })
}

export function stockHistory(code, days = 120) {
  return fetchJSON(`/stock/${code}/history?days=${days}`)
}

export function stockSignals(code, days = 120, strategy = {}) {
  const params = new URLSearchParams({ days })
  for (const [k, v] of Object.entries(strategy)) {
    if (v !== undefined && v !== null) params.set(k, v)
  }
  return fetchJSON(`/stock/${code}/signals?${params}`)
}

export function searchStock(q) {
  return fetchJSON(`/stock/search?q=${encodeURIComponent(q)}`)
}

export function getSchedule() {
  return fetchJSON('/scan/schedule')
}

export function updateSchedule(config) {
  return fetchJSON('/scan/schedule', {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(config),
  })
}

export function getWatchlist() {
  return fetchJSON('/watchlist')
}

export function addToWatchlist(item) {
  return fetchJSON('/watchlist', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(item),
  })
}

export function removeFromWatchlist(code) {
  return fetchJSON(`/watchlist/${code}`, { method: 'DELETE' })
}

export function refreshWatchlist() {
  return fetchJSON('/watchlist/refresh', { method: 'POST' })
}

export function getWatchlistAlerts() {
  return fetchJSON('/watchlist/alerts')
}
