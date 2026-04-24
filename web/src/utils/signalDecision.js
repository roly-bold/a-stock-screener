function parseDate(value) {
  if (!value) return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

function pctDistance(current, base) {
  if (current == null || base == null || base === 0) return null
  return ((current - base) / base) * 100
}

function daysBetween(fromValue, toValue) {
  const from = parseDate(fromValue)
  const to = parseDate(toValue)
  if (!from || !to) return null
  return Math.round((to - from) / (1000 * 60 * 60 * 24))
}

const DECISION_RULES = {
  shortlist: {
    maxSignalAgeDays: 8,
    minDistanceToEntryPct: -5,
    maxDistanceToEntryPct: 12,
    maxDistanceToSupportPct: 15,
  },
  watchlist: {
    maxSignalAgeDays: 15,
    minDistanceToEntryPct: -8,
    maxDistanceToEntryPct: 18,
    maxDistanceToSupportPct: 20,
  },
}

function matchesWindow(metrics, rule) {
  const { distanceToEntryPct, distanceToSupportPct, signalAgeDays } = metrics
  return (
    signalAgeDays != null &&
    signalAgeDays <= rule.maxSignalAgeDays &&
    distanceToEntryPct != null &&
    distanceToEntryPct >= rule.minDistanceToEntryPct &&
    distanceToEntryPct <= rule.maxDistanceToEntryPct &&
    distanceToSupportPct != null &&
    distanceToSupportPct <= rule.maxDistanceToSupportPct
  )
}

export function getSignalMetrics(signal) {
  const distanceToEntryPct = pctDistance(signal.latest_close, signal.entry_price)
  const distanceToSupportPct = pctDistance(signal.latest_close, signal.support_price)
  const stopLossRiskPct = signal.latest_close && signal.support_price
    ? ((signal.latest_close - signal.support_price) / signal.latest_close) * 100
    : null
  const signalAgeDays = daysBetween(signal.entry_date, signal.latest_date)

  return {
    distanceToEntryPct,
    distanceToSupportPct,
    stopLossRiskPct,
    signalAgeDays,
  }
}

export function getSignalDecision(signal) {
  const metrics = getSignalMetrics(signal)

  if (signal.exit_triggered) {
    return {
      bucket: 'stopped',
      label: '已触发止损',
      tone: 'danger',
      reason: '按当前策略，这个历史买点已经失效。',
    }
  }

  if (matchesWindow(metrics, DECISION_RULES.shortlist)) {
    return {
      bucket: 'shortlist',
      label: '可关注',
      tone: 'good',
      reason: '信号仍较新，价格还在买点附近，距离支撑位也不算远。',
    }
  }

  if (matchesWindow(metrics, DECISION_RULES.watchlist)) {
    return {
      bucket: 'watchlist',
      label: '观察池',
      tone: 'info',
      reason: '结构还在，但价格或时效已经开始偏离，适合等回踩或重新转强。',
    }
  }

  return {
    bucket: 'stale',
    label: '已过买点',
    tone: 'warn',
    reason: '信号已偏旧，或者当前价格距离历史买点/支撑位过远。',
  }
}

export function formatPct(value, digits = 2) {
  if (value == null || Number.isNaN(value)) return '-'
  const fixed = value.toFixed(digits)
  return `${value >= 0 ? '+' : ''}${fixed}%`
}
