// ============================================================
// 导出文件命名（2026-09-18 新增）
// 每种导出（预排筛选 / 审核决议 / 存档中心）一套独立命名模板，
// 模板存 localStorage，导出时按当前上下文替换变量拼出文件名。
// 变量：{year}{month}{date}{time}{label}{split}{type}
//   year  当前选择年份（如 2026，无则 全部）
//   month 月份标签（如 9月）
//   date  当前日期 YYYY-MM-DD
//   time  当前时间 YYYYMMDD_HHMMSS
//   label 存档中心复合标签（如 2026年9月 / 全部）
//   split 勾选「按月分 Sheet」时取 _分月，否则空
//   type  该类导出基础名（预排筛选结果 / 审核决议 / 存档中心）
// ============================================================

const STORAGE_KEY = 'ym_export_naming_v1'

// 三类导出的元数据：标签、默认模板、可用变量
export const NAMING_TYPES = {
  preplan: {
    key: 'preplan',
    label: '预排筛选结果',
    defaultTpl: '预排筛选结果_{year}',
    vars: ['year', 'month', 'date', 'time', 'type'],
  },
  decision: {
    key: 'decision',
    label: '审核决议',
    defaultTpl: '审核决议_{date}',
    vars: ['year', 'month', 'date', 'time', 'type'],
  },
  archive: {
    key: 'archive',
    label: '存档中心',
    defaultTpl: '存档中心_{label}{split}_{time}',
    vars: ['year', 'month', 'date', 'time', 'label', 'split', 'type'],
  },
}

function loadRaw() {
  try {
    const s = localStorage.getItem(STORAGE_KEY)
    return s ? JSON.parse(s) : {}
  } catch {
    return {}
  }
}

export function getTpl(type) {
  if (!NAMING_TYPES[type]) return ''
  const raw = loadRaw()
  return (raw[type] && typeof raw[type].tpl === 'string' && raw[type].tpl.trim())
    ? raw[type].tpl.trim()
    : NAMING_TYPES[type].defaultTpl
}

export function saveTpl(type, tpl) {
  const raw = loadRaw()
  raw[type] = { tpl: (tpl || '').trim() }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(raw))
}

// 样本上下文：仅在调用方「没有传当前页面上下文」时兜底（如后续新增的独立入口）。
// ★ 2026-09-20 修复：此前配置弹窗的「实时预览」全程用这份写死的样本（year/month 固定 2026 / 9月），
//   于是在预排页把月份切到 7 月后，预览里的 {month} 依旧是 9 月 —— 用户看到的就是「固定版 / 设置失效」。
//   现在真实调用方（预排筛选 / 审核决议 / 存档中心）都会把自己当前筛选作为 ctx 传进弹窗，
//   样本只保留兜底职责，不再参与正常预览。
export function sampleCtx(type) {
  const meta = NAMING_TYPES[type] || { label: '' }
  return {
    year: '2026',
    month: '9月',
    date: '2026-09-18',
    time: '20260918_090910',
    label: '2026年9月',
    split: '_分月',
    type: meta.label,
  }
}

// ★ 2026-09-20：从 plan_ym（YYYYMM 数值）派生命名变量，三处导出共用，
//   免得每个视图各写一遍 `% 100` / `Math.floor(/100)` 而出现口径漂移。
export function monthLabelFromYm(ym) {
  const n = Number(ym)
  return n ? `${n % 100}月` : ''
}
export function yearFromYm(ym) {
  const n = Number(ym)
  return n ? String(Math.floor(n / 100)) : ''
}
export function fullLabelFromYm(ym, fallback = '全部') {
  const n = Number(ym)
  return n ? `${Math.floor(n / 100)}年${n % 100}月` : fallback
}

function nowParts() {
  const d = new Date()
  const p = (n) => String(n).padStart(2, '0')
  return {
    date: `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())}`,
    time: `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}_${p(d.getHours())}${p(d.getMinutes())}${p(d.getSeconds())}`,
  }
}

// Windows 非法文件名字符：< > : " / \ | ? * ；折叠多余下划线、清理首尾空白与下划线
function sanitizeName(name) {
  let s = String(name)
    .replace(/[<>:"/\\|?*]/g, '_')
    .replace(/\s+/g, ' ')
    .trim()
  s = s.replace(/_+/g, '_').replace(/^_+|_+$/g, '')
  return s
}

// 用「显式模板 + 显式上下文」拼文件名。
// 单独抽出来是为了：配置弹窗用「正在编辑中的模板」实时预览，导出时用「已保存的模板」，
// 两者共用同一套替换 / 清洗规则 —— 预览与真实导出必然一致，不会再出现「预览是固定版」。
export function buildNameFromTpl(tpl, type, ctx = {}) {
  const meta = NAMING_TYPES[type]
  if (!meta) return 'export.xlsx'
  const { date, time } = nowParts()
  const vars = {
    year: ctx.year ?? '',
    month: ctx.month ?? '',
    date,
    time,
    label: ctx.label ?? '全部',
    split: ctx.splitByMonth ? '_分月' : '',
    type: meta.label,
  }
  let name = String(tpl ?? '').replace(/\{(\w+)\}/g, (m, k) => (k in vars ? vars[k] : m))
  name = sanitizeName(name)
  if (!name) name = meta.label   // 模板被清空时不留下 '.xlsx' 这种空壳名
  if (!/\.(xlsx?|json|svg)$/i.test(name)) name += '.xlsx'
  return name
}

// 按类型 + 上下文拼出最终文件名（模板取 localStorage 里已保存的）；模板缺失变量原样保留（方便预览发现问题）
export function buildFileName(type, ctx = {}) {
  return buildNameFromTpl(getTpl(type), type, ctx)
}
