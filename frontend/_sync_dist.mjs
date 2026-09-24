// 同步 frontend/dist -> backend/static/frontend
// 约定：先清空目标目录再递归拷贝（不用 fs.cpSync，避免残留旧 hash 资源）
import fs from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const here = path.dirname(fileURLToPath(import.meta.url))
const SRC = path.join(here, 'dist')
const DST = path.join(here, '..', 'backend', 'static', 'frontend')

function rimraf(p) {
  if (fs.existsSync(p)) fs.rmSync(p, { recursive: true, force: true })
}
function copyDir(src, dst) {
  fs.mkdirSync(dst, { recursive: true })
  for (const ent of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, ent.name)
    const d = path.join(dst, ent.name)
    if (ent.isDirectory()) copyDir(s, d)
    else fs.copyFileSync(s, d)
  }
}

if (!fs.existsSync(SRC)) { console.error('[ERR] dist not found:', SRC); process.exit(1) }
rimraf(DST)
copyDir(SRC, DST)

// ---- 校验 ----
const srcAssets = fs.readdirSync(path.join(SRC, 'assets'))
const dstAssets = fs.readdirSync(path.join(DST, 'assets'))
const problems = []
if (srcAssets.length !== dstAssets.length) {
  problems.push(`assets count mismatch: src=${srcAssets.length} dst=${dstAssets.length}`)
}
for (const f of srcAssets) {
  if (!dstAssets.includes(f)) problems.push(`missing in dst: ${f}`)
}
const idx = fs.readFileSync(path.join(DST, 'index.html'), 'utf8')
if (idx.includes('localhost:8000')) problems.push('index.html contains localhost:8000')
if (!idx.includes('qc-theme')) problems.push('index.html missing theme bootstrap script')

// 新 CSS 必须带白天覆盖块
const cssFile = dstAssets.find(f => f.startsWith('index-') && f.endsWith('.css'))
const css = fs.readFileSync(path.join(DST, 'assets', cssFile), 'utf8')
// 压缩后注释会被剥离 → 断言「令牌是否定义 + 语义规则是否存在」，**不锁死具体色值**。
// （2026-09-24 白天调色板三次改版后已脱钩色值：--surface-* 这一族只在 [data-theme=light] 里定义，
//   因此「存在」即等价于「白天块在」，调色再调也不会误报。）
if (!css.includes('--bg-root:#')) problems.push('light palette (--bg-root) missing')
if (!css.includes('--surface-1:')) problems.push('surface-1 token missing')
if (!css.includes('--surface-2:')) problems.push('surface-2 token missing')
if (!css.includes('--well:')) problems.push('well token missing')
if (!css.includes('--field:')) problems.push('field token missing')
if (!css.includes('--line-1:')) problems.push('line-1 token missing')
if (!css.includes('.ts-input')) problems.push('light search-bar rule missing')
if (!css.includes('td.el-table__cell')) problems.push('light el-table td rule missing')
const lightHits = (css.match(/\[data-theme=light\]/g) || []).length
const surfaceUse = (css.match(/var\(--surface-[12]\)/g) || []).length

console.log('[SYNC] assets src=%d dst=%d', srcAssets.length, dstAssets.length)
console.log('[SYNC] main css =', cssFile, '| [data-theme=light] occurrences =', lightHits, '| var(--surface-*) 引用 =', surfaceUse)
console.log('[SYNC] index.html theme bootstrap =', idx.includes('qc-theme'))
console.log(problems.length ? '[FAIL]\n' + problems.join('\n') : '[OK] all checks passed')
process.exit(problems.length ? 2 : 0)
