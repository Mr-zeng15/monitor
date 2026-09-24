// ★ 云端图表数据「形状容错」归一化（2026-09-21）
//
// 背景：机器人（Dify 工作流）后面挂了一层 LLM，同一个问题多次提问，回覆 JSON 的形状会漂移。
//   已观察到的形态（HAR/Console 实证）：
//     ① 标准 echarts option：{ title:{text}, xAxis:{data:[...]}, series:[{name,data:[...]}] }
//     ② 原始行表（LLM 把数据表原样回吐，附一段 message）：
//          { data: [ {fab:'2A', week:'WK202633', count_value:8}, ... ], message: '…' }
//     ③ 包装层：{ option:{…} } / { data:{ xAxis, series } } / { result:{ chart:{…} } } / 裸数组 [ {…} ]
//     ④ 宽表：{ rows:[ {week:'WK202633', '2A':8, '2B':3} ] } —— 厂别挂在「列名」上
//     ⑤ series 写成 map：{ series: { '2A':[8,5], '2B':[3,7] } }
//     ⑥ xAxis 写成字符串：'WK202633,WK202634'，或 series[].data 里混着字符串数字
//
// 认识：图表真正必需的只有「x 轴标签」+「每厂一条数值折线」两样，其余（title/unit/message/多余列）
//   都是附加值。所以这里的目标不是「猜得很全」，而是**只要这两样在，就一定能出图**。
//
// 归一化后的统一契约（cloudAbl / cloudDppm 共用）：
//   { title, unit, xAxis: string[], series: [{ name, data: (number|null)[] }], wow: {label,byFab}|null, shape }
// 真的一套都没命中（没有可用轴 / 没有任何数值）才返回 null → 调用方沿用静态示例（不撒谎）。

// —— 列语义关键词表（比较前先归一化 key：转小写 + 去空格/下划线/括号等）——
const FAB_KEYS = ['fab', 'fabno', 'fabname', 'factory', 'factoryname', 'workshop', 'shop', 'area', 'areaname',
  'dept', 'line', '车间', '厂别', '厂', '车间别', '厂区', '产线']
const WEEK_KEYS = ['week', 'weeklabel', 'weekname', 'weekno', 'wk', 'wkno', 'wkid', 'yearweek', 'weekid',
  'xaxis', 'x', 'label', 'labels', 'category', 'categories', 'period', 'date', 'month',
  '周别', '周次', '周', '日期', '月份', '时间', '周期']
const VALUE_KEYS = ['countvalue', 'cntvalue', 'count', 'cnt', 'value', 'numbers', 'number', 'num',
  'qty', 'quantity', 'total', 'amount', 'sum', 'result',
  '报警数', '不良数', '数量', '数值', '值', '次数', '件数']
// 可以「钻进去」找内容的包装键（LLM 爱包一层）
const CONTAINER_KEYS = ['option', 'options', 'echarts', 'chart', 'chartoption', 'config',
  'data', 'dataset', 'result', 'results', 'output', 'outputs', 'payload', 'body',
  'answer', 'json', 'content', 'rows', 'records', 'list', 'items', 'table', 'values']
// 「环比列」的各种写法（末列不是周别，是差值 → 必须剥离，否则会把折线图 y 轴拉爆）
const WOW_RE = /^(wow|w\/w|环比|较上周|变化|变化幅度|差值|增减)$/i

/* ── 基础工具 ─────────────────────────────────────────── */
function isObj(v) { return v !== null && typeof v === 'object' && !Array.isArray(v) }

function normKey(k) {
  return String(k === null || k === undefined ? '' : k)
    .toLowerCase()
    .replace(/[\s_\-./\\()[\]{}（）【】:：,，]/g, '')
}

/** 宽松取数：数字 / '1,234' / '12%' / '8.0' → number；'—' / '-' / 'N/A' / '' → null */
export function toNum(v) {
  if (typeof v === 'number') return isFinite(v) ? v : null
  if (typeof v === 'boolean') return v ? 1 : 0
  if (v === null || v === undefined) return null
  const s = String(v).trim().replace(/,/g, '').replace(/%$/, '').replace(/[次件个]$/, '').trim()
  if (!s || s === '-' || s === '--' || s === '—' || /^(n\/?a|null|nan|none)$/i.test(s)) return null
  const n = Number(s)
  return isNaN(n) ? null : n
}

function numLike(v) {
  if (typeof v === 'number') return isFinite(v)
  const s = String(v === null || v === undefined ? '' : v).trim()
  return !!s && toNum(s) !== null
}

function toLabel(v) { return String(v === null || v === undefined ? '' : v).trim() }

function digitsOf(s) { const m = String(s).match(/\d+/g); return m ? Number(m.join('')) : NaN }

/** '2A' / 'FAB2A' / '2a车间' / '2A FAB' → '2A'（LLM 输出厂名写法漂移，统一回来） */
function coerceFab(name, fabList) {
  const s = toLabel(name).toUpperCase()
  if (!s) return ''
  if (fabList && fabList.length) {
    for (const f of fabList) {
      const u = String(f).toUpperCase()
      if (s === u || s.replace(/[^0-9A-Z]/g, '') === u) return f
    }
  }
  const m = s.match(/(?:^|[^0-9])2\s*([A-D])(?:[^0-9A-Z]|$)/) || s.match(/^2([A-D])$/)
  if (m) return '2' + m[1]
  return ''
}

/* ── 候选节点收集：把包装层逐层剥开 ───────────────────── */
function collectCandidates(root, maxDepth = 6) {
  const out = []
  const seen = new Set()
  ;(function walk(node, depth) {
    if (node === null || node === undefined || depth > maxDepth) return
    if (Array.isArray(node)) {
      if (seen.has(node)) return
      seen.add(node)
      out.push(node)
      // 数组元素里可能才是 echarts option（如 [{option:{…}}]）
      for (let i = 0; i < Math.min(node.length, 30); i++) {
        if (isObj(node[i])) walk(node[i], depth + 1)
      }
      return
    }
    if (!isObj(node) || seen.has(node)) return
    seen.add(node)
    out.push(node)
    for (const k of CONTAINER_KEYS) {
      if (k in node) walk(node[k], depth + 1)
    }
  })(root, 0)
  return out
}

/* ── 从对象里读 x 轴 ─────────────────────────────────── */
function axisFrom(node) {
  const cand = [node.xAxis, node.xaxis, node.x, node.categories, node.category,
    node.labels, node.xLabels, node.xlabels, node.weeks, node.periods]
  for (const c of cand) {
    if (Array.isArray(c) && c.length) return c.map(toLabel)
    if (isObj(c)) {
      if (Array.isArray(c.data) && c.data.length) return c.data.map(toLabel)
      if (Array.isArray(c.categories) && c.categories.length) return c.categories.map(toLabel)
    }
    if (typeof c === 'string' && c.trim()) {
      const parts = c.split(/[,，|;；\s]+/).map(s => s.trim()).filter(Boolean)
      if (parts.length >= 2) return parts
    }
  }
  return []
}

/* ── 从对象里读 series（echarts 形态 / map 形态）──────── */
function seriesFrom(node, fabList) {
  const list = []
  const raw = node.series || node.lines || node.datasets || node.items
  const legend = (node.legend && Array.isArray(node.legend.data)) ? node.legend.data.map(toLabel) : []
  if (Array.isArray(raw)) {
    raw.forEach((s, i) => {
      if (Array.isArray(s)) {                       // series: [[8,5,13], [3,7,4]]
        list.push({ name: coerceFab(legend[i], fabList) || toLabel(legend[i]) || '', data: s.map(toNum) })
        return
      }
      if (!isObj(s)) return
      const name = s.name ?? s.fab ?? s.label ?? s.title ?? legend[i] ?? ''
      const data = s.data ?? s.values ?? s.value ?? s.count ?? s.count_value ?? s.y ?? []
      list.push({ name: coerceFab(name, fabList) || toLabel(name), data: (Array.isArray(data) ? data : [data]).map(toNum) })
    })
    return list
  }
  if (isObj(raw)) {                               // series: { '2A':[..], '2B':[..] }
    for (const k of Object.keys(raw)) {
      const v = raw[k]
      if (!Array.isArray(v)) continue
      list.push({ name: coerceFab(k, fabList) || toLabel(k), data: v.map(toNum) })
    }
    return list
  }
  // yAxis 里塞数值（单厂形态）：{ yAxis: { data: [...] } }
  const yc = [node.yAxis, node.yaxis, node.y]
  for (const c of yc) {
    if (isObj(c) && Array.isArray(c.data) && c.data.length && c.data.some(numLike)) {
      list.push({ name: coerceFab(node.name || node.fab || node.label, fabList), data: c.data.map(toNum) })
      break
    }
  }
  return list
}

/* ── 从行表里读数据（长表 / 宽表 / 矩阵 / 单列）───────── */
function matchKey(keys, candidates) {
  const nk = keys.map(k => [k, normKey(k)])
  for (const c of candidates) { const hit = nk.find(([, n]) => n === c); if (hit) return hit[0] }
  for (const c of candidates) { const hit = nk.find(([, n]) => n.startsWith(c)); if (hit) return hit[0] }
  for (const c of candidates) { const hit = nk.find(([, n]) => n.includes(c)); if (hit) return hit[0] }
  return ''
}

function guessNumericKey(sample, keys, exclude) {
  for (const k of keys) {
    if (exclude.includes(k)) continue
    const vals = sample.map(r => r[k]).filter(v => v !== null && v !== undefined && v !== '')
    if (vals.length && vals.filter(numLike).length / vals.length >= 0.6) return k
  }
  return ''
}

function pivotRows(rows, columns, opts) {
  // 矩阵形态：{ columns:[...], rows:[[...],[...]] } → 先转成行对象
  if (columns && columns.length && rows.length && Array.isArray(rows[0])) {
    rows = rows.map(arr => {
      const o = {}
      columns.forEach((c, i) => { o[toLabel(c) || ('c' + i)] = arr[i] })
      return o
    })
  }
  const objs = rows.filter(isObj)
  if (!objs.length) return null
  const sample = objs.slice(0, 30)

  const keys = []
  for (const r of sample) for (const k of Object.keys(r)) if (!keys.includes(k)) keys.push(k)
  if (!keys.length) return null

  const fabKey = matchKey(keys, FAB_KEYS)
  const weekKey = matchKey(keys, WEEK_KEYS)
  // 宽表：厂别写在列名上（'2A' / '2B' …）
  const fabCols = keys.filter(k => k !== weekKey && k !== fabKey && !!coerceFab(k, opts.fabList))
  const valueKey = matchKey(keys, VALUE_KEYS) || guessNumericKey(sample, keys, [fabKey, weekKey].filter(Boolean))

  // 统一先取 x 轴：有周别列就用它（保留首次出现顺序 —— 周别本来就有序，不重排）；
  // 没有周别列时先用内部占位符分组，最后统一换成界面上好看的 W1..Wn。
  const idOf = (r, i) => (weekKey ? toLabel(r[weekKey]) : '#' + i)
  const ids = []
  objs.forEach((r, i) => { const l = idOf(r, i); if (l !== '' && !ids.includes(l)) ids.push(l) })

  let series = []
  let shape = ''

  if (valueKey && fabKey) {
    // ── 长表：一行一个 (厂, 周, 值) ──
    shape = 'rows-long'
    const byFab = new Map()
    objs.forEach((r, i) => {
      const fab = coerceFab(r[fabKey], opts.fabList) || toLabel(r[fabKey]) || opts.defaultName
      if (!byFab.has(fab)) byFab.set(fab, new Map())
      byFab.get(fab).set(idOf(r, i), toNum(r[valueKey]))
    })
    series = [...byFab.entries()].map(([name, m]) => ({ name, data: ids.map(l => (m.has(l) ? m.get(l) : null)) }))
  } else if (fabCols.length) {
    // ── 宽表：一行一个周，各厂各占一列 ──
    shape = 'rows-wide'
    series = fabCols.map(col => {
      const m = new Map()
      objs.forEach((r, i) => m.set(idOf(r, i), toNum(r[col])))
      return { name: coerceFab(col, opts.fabList) || toLabel(col), data: ids.map(l => (m.has(l) ? m.get(l) : null)) }
    })
  } else {
    // ── 单列：只有一串数值（如单厂 DPPM）──
    const k = valueKey || guessNumericKey(sample, keys, [fabKey, weekKey].filter(Boolean))
    if (!k) return null
    shape = 'rows-single'
    const m = new Map()
    objs.forEach((r, i) => m.set(idOf(r, i), toNum(r[k])))
    series = [{ name: toLabel(opts.defaultName), data: ids.map(l => (m.has(l) ? m.get(l) : null)) }]
  }

  const xAxis = weekKey ? ids : ids.map((_, i) => 'W' + (i + 1))
  if (!xAxis.length) return null
  return { xAxis, series, shape }
}

/* ── 环比列剥离：末列是 WoW / 环比 时拆出来，不画进折线 ── */
export function splitWow(xAxis, series) {
  const last = toLabel(xAxis[xAxis.length - 1])
  if (!WOW_RE.test(last) || xAxis.length < 2) return { xAxis, series, wow: null }
  const byFab = {}
  series.forEach(s => { if (s.data.length >= xAxis.length) byFab[s.name] = s.data[s.data.length - 1] })
  return {
    xAxis: xAxis.slice(0, -1),
    series: series.map(s => ({ name: s.name, data: s.data.slice(0, xAxis.length - 1) })),
    wow: { label: last, byFab }
  }
}

/**
 * 把任意形状的云端 JSON 归一化成图表契约。
 * @param {*} raw 后端 data.data（或整包 data）
 * @param {{fabList?:string[], defaultName?:string}} opts
 *        fabList：给定时会把 series 名强制归一化到该集合，且「一条都没匹配上」视为失败
 * @returns {{title,unit,xAxis,series,wow,shape}|null}
 */
export function normalizeChart(raw, opts = {}) {
  const o = { fabList: opts.fabList || null, defaultName: opts.defaultName || '' }
  if (raw === null || raw === undefined) return null

  const candidates = collectCandidates(raw, 6)
  let axis = []
  let series = []
  let node = null
  let shape = ''

  // ① 先找 echarts option 形态（xAxis + series 同处一个对象）
  for (const c of candidates) {
    if (!isObj(c)) continue
    const a = axisFrom(c)
    const s = seriesFrom(c, o.fabList)
    if (a.length && s.length) { node = c; axis = a; series = s; shape = 'echarts'; break }
  }
  // ② 再找行表形态（含矩阵 / 长表 / 宽表 / 单列）
  if (!shape) {
    for (const c of candidates) {
      if (Array.isArray(c)) {
        // 单纯的基础类型数组（['WK1','WK2']）不足以做图表，跳过
        if (!c.length || !isObj(c[0])) continue
        const p = pivotRows(c, null, o)
        if (p && p.series.length) { axis = p.xAxis; series = p.series; shape = p.shape; node = null; break }
      } else if (isObj(c) && Array.isArray(c.rows)) {
        const p = pivotRows(c.rows, c.columns || c.header || c.headers, o)
        if (p && p.series.length) { axis = p.xAxis; series = p.series; shape = p.shape; node = c; break }
      }
    }
  }
  // ③ 最后兜底：只有 series、x 轴要自己编号
  if (!shape) {
    for (const c of candidates) {
      if (!isObj(c)) continue
      const s = seriesFrom(c, o.fabList)
      if (s.length && s.some(x => x.data.some(v => v !== null))) { node = c; series = s; shape = 'series-only'; break }
    }
  }
  if (!shape) return null

  // series 名归一化（LLM 写 '2a'/'FAB2A'/'2A车间' 都收回来）
  series = series
    .map(s => ({ name: coerceFab(s.name, o.fabList) || toLabel(s.name), data: (s.data || []).map(toNum) }))
    .filter(s => s.data.length)

  // 轴与折线长度对齐：轴更长（更可信）→ 折线补 null 留空档；轴更短 → 轴按数据补 W 编号
  const axisLen = axis.length
  const maxLen = series.reduce((n, s) => Math.max(n, s.data.length), 0)
  if (!maxLen) return null
  const n = axisLen >= maxLen ? axisLen : maxLen
  if (axisLen !== n) {
    axis = (axisLen > n)
      ? axis.slice(-n)
      : Array.from({ length: n }, (_, i) => axis[i] || ('W' + (i + 1)))
  }
  series = series.map(s => ({
    name: s.name,
    data: s.data.length === n ? s.data : Array.from({ length: n }, (_, i) => (i < s.data.length ? s.data[i] : null))
  }))

  // ★ fabList 给定（ABL 场景）时要求「至少一条折线能对上厂名」，否则宁可不亮也不半亮
  if (o.fabList && o.fabList.length && !series.some(s => o.fabList.includes(s.name))) return null

  // title / unit
  let title = ''
  if (node) {
    const t = node.title
    title = isObj(t) ? toLabel(t.text) : toLabel(t)
    if (!title) title = toLabel(node.name || node.chartTitle || node.chart_title)
  }
  let unit = ''
  if (node) {
    unit = toLabel(node.unit || node.unitName || node.unit_name)
    if (!unit) {
      const yName = isObj(node.yAxis || node.yaxis) ? toLabel((node.yAxis || node.yaxis).name) : ''
      // ★ 2026-09-22：echarts 里 yAxis.name 是「轴的名字」，**不等于单位**。
      //   DPPM 2B 的真实回覆就是 {"yAxis":{"name":"DPPM"}} —— 把它当单位会让界面
      //   显示成「3851.09DPPM」。故仅当轴名既不是图表标题、也不等于任何折线名时，
      //   才把它当单位（ABL 的 "次数" 仍然成立）。
      if (yName && yName !== title && !series.some(s => s.name === yName)) unit = yName
    }
  }

  const sp = splitWow(axis, series)
  return { title, unit, xAxis: sp.xAxis, series: sp.series, wow: sp.wow, shape }
}

/** 诊断用：一句话描述归一化结果（不参与业务，只打 Console） */
export function describeShape(raw, out) {
  if (!out) return '未识别出可用图表（缺 x 轴或数值）'
  return `${out.shape} · 轴 ${out.xAxis.length} 点 · 折线 ${out.series.length} 条 [${out.series.map(s => s.name).join('/')}]`
}
