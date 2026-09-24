import fs from 'node:fs'
const D = 'D:/产量监控系统/backend/static/frontend/assets/'
const files = fs.readdirSync(D).filter(f => f.endsWith('.css'))
let tot = { s1: 0, s2: 0, well: 0, field: 0, line: 0 }
const per = []
for (const f of files) {
  const c = fs.readFileSync(D + f, 'utf8')
  const g = s => (c.match(new RegExp('var\\(--' + s + '\\)', 'g')) || []).length
  const o = { f, s1: g('surface-1'), s2: g('surface-2'), well: g('well'), field: g('field'), line: g('line-[12]') }
  for (const k of ['s1', 's2', 'well', 'field', 'line']) tot[k] += o[k]
  if (o.s1 + o.s2 + o.well + o.field + o.line) per.push(o)
}
for (const o of per) console.log('[OK]', o.f.padEnd(38), `surface-1=${o.s1} surface-2=${o.s2} well=${o.well} field=${o.field} line=${o.line}`)
console.log('--- 合计:', JSON.stringify(tot))

// 断言：白天块里不允许再出现纯白底
let bad = []
for (const f of files) {
  const c = fs.readFileSync(D + f, 'utf8')
  // 粗略：每个 [data-theme=light] 之后到块尾，查找 background:#fff
  const idx = c.indexOf('[data-theme=light]')
  if (idx < 0) continue
  const seg = c.slice(idx)
  const m = seg.match(/background(?:-color)?:\s*#(?:fff|ffffff|f2f7fc|f4f8fc|f7fafd)\b/gi)
  if (m) bad.push(f + ' -> ' + m.length + ' 处 ' + [...new Set(m)].join(','))
}
console.log(bad.length ? '[WARN] 白天块残留白底:\n' + bad.join('\n') : '[OK] 白天块内已无纯白底')
