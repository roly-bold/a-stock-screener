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
  const { distanceToEntryPct, distanceToSupportPct, signalAgeDays } = getSignalMetrics(signal)

  if (signal.exit_triggered) {
    return {
      label: '已触发止损',
      tone: 'danger',
      reason: '按当前策略，这个历史买点已经失效。',
    }
  }

  const nearEntry = distanceToEntryPct != null && distanceToEntryPct >= -3 && distanceToEntryPct <= 8
  const nearSupport = distanceToSupportPct != null && distanceToSupportPct <= 12
  const freshSignal = signalAgeDays != null && signalAgeDays <= 5

  if (freshSignal && nearEntry && nearSupport) {
    return {
      label: '可关注',
      tone: 'good',
      reason: '买点较新，价格离历史买点和支撑位都不远。',
    }
  }

  return {
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
