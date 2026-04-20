import ReactECharts from 'echarts-for-react'

export default function KlineChart({ history, signals, height = 520, compact = false }) {
  if (!history?.length) return null

  const dates = history.map(b => b.date)
  const ohlc = history.map(b => [b.open, b.close, b.low, b.high])
  const volumes = history.map(b => b.volume)
  const pctChanges = history.map(b => b.pct_change)

  const markPoints = []
  const markLines = []
  const markAreas = []

  signals.forEach(sig => {
    const breakoutIdx = dates.indexOf(sig.breakout_date)
    const entryIdx = dates.indexOf(sig.entry_date)
    const consStartIdx = breakoutIdx + 1
    const consEndIdx = dates.indexOf(sig.consolidation_end)

    if (breakoutIdx >= 0) {
      markPoints.push({
        name: '起爆',
        coord: [sig.breakout_date, history[breakoutIdx].high],
        symbol: 'triangle',
        symbolSize: 12,
        itemStyle: { color: '#ef4444' },
        label: { show: true, formatter: '起爆', position: 'top', color: '#ef4444', fontSize: 11 }
      })
    }

    if (entryIdx >= 0) {
      markPoints.push({
        name: '买入',
        coord: [sig.entry_date, history[entryIdx].low],
        symbol: 'triangle',
        symbolSize: 12,
        symbolRotate: 180,
        symbolOffset: [0, '50%'],
        itemStyle: { color: '#eab308' },
        label: { show: true, formatter: '买入', position: 'bottom', color: '#eab308', fontSize: 11 }
      })
    }

    if (sig.pivot_high > 0) {
      markLines.push({
        name: '突破位',
        yAxis: sig.pivot_high,
        lineStyle: { color: '#ef4444', type: 'dashed', width: 1 },
        label: { formatter: '突破 {c}', color: '#ef4444', fontSize: 11 }
      })
    }

    if (sig.support_price > 0) {
      markLines.push({
        name: '支撑位',
        yAxis: sig.support_price,
        lineStyle: { color: '#22c55e', type: 'dashed', width: 1 },
        label: { formatter: '支撑 {c}', color: '#22c55e', fontSize: 11 }
      })
    }

    if (consStartIdx >= 0 && consEndIdx >= 0 && consEndIdx >= consStartIdx) {
      markAreas.push({
        name: '整理区间',
        coord: [
          [dates[consStartIdx], sig.pivot_high],
          [dates[consEndIdx], sig.support_price]
        ],
        itemStyle: { color: 'rgba(234, 179, 8, 0.08)' }
      })
    }
  })

  const ma5 = calcMA(history, 5)
  const ma20 = calcMA(history, 20)

  const option = {
    animation: false,
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'cross' },
      backgroundColor: 'rgba(13,17,23,0.9)',
      borderColor: '#30363d',
      textStyle: { color: '#e6edf3', fontSize: 12 },
    },
    axisPointer: { link: [{ xAxisIndex: 'all' }] },
    grid: [
      { left: '8%', right: '4%', top: compact ? '8%' : '5%', height: compact ? '55%' : '60%' },
      { left: '8%', right: '4%', top: compact ? '70%' : '72%', height: compact ? '18%' : '20%' },
    ],
    xAxis: [
      { type: 'category', data: dates, boundaryGap: true, axisLine: { lineStyle: { color: '#30363d' } }, axisLabel: { color: '#8b949e', fontSize: 11 }, splitLine: { show: false } },
      { type: 'category', gridIndex: 1, data: dates, boundaryGap: true, axisLine: { lineStyle: { color: '#30363d' } }, axisLabel: { color: '#8b949e', fontSize: 11 }, splitLine: { show: false } },
    ],
    yAxis: [
      { scale: true, splitLine: { lineStyle: { color: '#30363d' } }, axisLabel: { color: '#8b949e', fontSize: 11 } },
      { scale: true, gridIndex: 1, splitNumber: 2, splitLine: { lineStyle: { color: '#30363d' } }, axisLabel: { color: '#8b949e', fontSize: 11 } },
    ],
    dataZoom: [
      { type: 'inside', xAxisIndex: [0, 1], start: 60, end: 100 },
      { show: true, xAxisIndex: [0, 1], type: 'slider', bottom: '2%', start: 60, end: 100, borderColor: '#30363d', fillerColor: 'rgba(88,166,255,0.15)', textStyle: { color: '#8b949e' } },
    ],
    series: [
      {
        name: 'K线',
        type: 'candlestick',
        data: ohlc,
        itemStyle: {
          color: '#ef4444',
          color0: '#22c55e',
          borderColor: '#ef4444',
          borderColor0: '#22c55e',
        },
        markPoint: { data: markPoints, animation: false },
        markLine: { data: markLines, animation: false, symbol: 'none' },
        markArea: { data: markAreas, animation: false },
      },
      {
        name: 'MA5',
        type: 'line',
        data: ma5,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1, color: '#eab308' },
      },
      {
        name: 'MA20',
        type: 'line',
        data: ma20,
        smooth: true,
        showSymbol: false,
        lineStyle: { width: 1, color: '#58a6ff' },
      },
      {
        name: '成交量',
        type: 'bar',
        xAxisIndex: 1,
        yAxisIndex: 1,
        data: volumes.map((v, i) => ({
          value: v,
          itemStyle: { color: pctChanges[i] >= 0 ? 'rgba(239,68,68,0.6)' : 'rgba(34,197,94,0.6)' }
        })),
      },
    ],
  }

  return <ReactECharts option={option} style={{ height: 520 }} notMerge={true} />
}

function calcMA(history, n) {
  const result = []
  for (let i = 0; i < history.length; i++) {
    if (i < n - 1) { result.push(null); continue }
    let sum = 0
    for (let j = 0; j < n; j++) sum += history[i - j].close
    result.push(+(sum / n).toFixed(2))
  }
  return result
}
