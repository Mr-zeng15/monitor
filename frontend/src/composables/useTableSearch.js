// ============================================================
//  useTableSearch — 表格 Ctrl+F 搜索（可复用 composable，v2 增强）
//  功能：Ctrl+F / F3 打开搜索条（拦截浏览器默认查找）、全量数据即时匹配、
//        命中行高亮 + 当前项闪烁、Enter 下一个 / Shift+Enter 上一个、
//        跨页自动跳转（切页后等待渲染再精确定位滚动）、Esc 关闭
//  用法（任意表格页）：
//    const { visible, keyword, matches, activeIdx, doSearch, jumpNext, close, isHit, isActive, onKeydown } =
//      useTableSearch({ getRows, tableRef, currentPage, pageSize, pageCount, onPageSwitch })
//    - getRows: () => 全量行数组（搜索匹配范围，跨页，注意与表格排序/筛选一致）
//    - onPageSwitch: 可选，页面 currentPage 变更后需手动重算表格数据时传入
//      （如 PreplanView 的 applyView），搜索跳页后保证页面真正切过去
//    - onActivated/onDeactivated 里注册/注销 onKeydown（keep-alive 页面）
//    ★ searchKeys 强烈建议传「表格实际展示的列 key」：
//      不传则扫描行对象全部字段，会命中 id / 时间戳 / 布尔标志等隐藏字段 → 出现
//      「明明这行没包含关键字却高亮」的误判（2026-09-20 已修：布尔/对象值不再参与）。
//    模板：搜索条 UI + row-class-name 叠加 isHit(row)/isActive(row)
// ============================================================
import { ref, nextTick } from 'vue'

export function useTableSearch({
  getRows,        // () => 全量行数组（搜索匹配范围，跨页）
  tableRef,       // () => el-table 组件实例（滚动定位用）
  currentPage,    // ref 当前页
  pageSize,       // ref 每页条数
  pageCount,      // () => 总页数（用于跳页钳制）
  searchKeys,     // 可选：指定参与搜索的字段名数组；缺省扫描所有字段
  onPageSwitch,   // 可选：页码变更后的手动数据重算回调（如 PreplanView.applyView）
}) {
  const visible = ref(false)
  const keyword = ref('')
  const matches = ref([])      // 命中行 id 列表
  const activeIdx = ref(-1)    // 当前定位到第几个匹配
  const hitIds = ref(new Set())

  function idOf(r) { return r != null && r.id != null ? r.id : r }

  // ★ 2026-09-20 修复「未包含关键字的行也被染黄」：
  //   行对象里除了表格展示的字段，还带 id / 时间戳 / 布尔标志（exported、archived、
  //   is_plan_external…）/ 嵌套对象（longlife_copy）等隐藏字段。原实现 String(v) 全扫，
  //   于是 String(false)==='false'、String({})==='[object Object]'，
  //   搜单个字母（如 "a"、"e"）或 "object" 会把几乎所有行判为命中。
  //   修法：① 优先只在 searchKeys（= 表格实际展示的列）内匹配；
  //         ② 只取「字符串 / 数字」这类可读标量，跳过对象、数组、布尔、函数。
  function keysOf(r) { return searchKeys && searchKeys.length ? searchKeys : Object.keys(r) }

  function scalarText(v) {
    if (v == null) return ''
    const t = typeof v
    if (t === 'string') return v
    if (t === 'number') return String(v)
    return ''   // 对象 / 数组 / 布尔 / 函数：不参与搜索，避免 "false" / "[object Object]" 误命中
  }

  function textOf(r) {
    return keysOf(r).map(k => scalarText(r[k])).join('\u0001').toLowerCase()
  }

  function doSearch() {
    const kw = keyword.value.trim().toLowerCase()
    const all = (getRows && getRows()) || []
    if (!kw) {
      matches.value = []
      hitIds.value = new Set()
      activeIdx.value = -1
      return
    }
    const ids = []
    all.forEach(r => { if (textOf(r).includes(kw)) ids.push(idOf(r)) })
    matches.value = ids
    hitIds.value = new Set(ids)
    activeIdx.value = ids.length ? 0 : -1
    if (ids.length) go(0)
  }

  // ★ 当前行是否命中（供 row-class-name 叠加高亮）
  function isHit(row) { return hitIds.value.has(idOf(row)) }
  // ★ 当前定位项（闪烁/加强高亮，随 Enter 切换移动）
  function isActive(row) {
    if (activeIdx.value < 0 || !matches.value.length) return false
    return matches.value[activeIdx.value] === idOf(row)
  }
  // ★ 某单元格是否命中（供 cell-class-name 给「真正匹配的那一格」单独加框）
  function isCellHit(row, key) {
    if (!key) return false
    // 该列不在搜索字段范围内 → 整列不参与（与 textOf 同口径）
    if (searchKeys && searchKeys.length && searchKeys.indexOf(key) < 0) return false
    if (!hitIds.value.has(idOf(row))) return false
    const kw = keyword.value.trim().toLowerCase()
    if (!kw) return false
    const t = scalarText(row[key])            // 只认字符串/数字，与 textOf 一致
    return !!t && t.toLowerCase().includes(kw)
  }
  // ★ el-table :cell-class-name 处理器：命中行的匹配单元格加框，当前定位行再加强
  function searchCellClass({ row, column }) {
    const key = column && column.property
    if (!isCellHit(row, key)) return ''
    return isActive(row) ? 'search-cell-hit search-cell-active' : 'search-cell-hit'
  }

  function jumpNext(dir = 1) {
    if (!matches.value.length) return
    const n = matches.value.length
    activeIdx.value = (activeIdx.value + dir + n) % n
    go(activeIdx.value)
  }

  // ★ 定位到第 idx 个匹配：跨页自动切页码；切页后等待表格渲染再滚动
  function go(idx) {
    const id = matches.value[idx]
    if (id == null) return
    const all = (getRows && getRows()) || []
    const pos = all.findIndex(r => idOf(r) === id)
    if (pos < 0) return

    let needSwitch = false
    if (currentPage && pageSize && pageCount) {
      const page = Math.min(Math.floor(pos / pageSize.value) + 1, pageCount())
      if (currentPage.value !== page) {
        currentPage.value = page
        needSwitch = true
        if (onPageSwitch) {
          try { onPageSwitch() } catch (e) { /* 页数据重算失败不阻断滚动 */ }
        }
      }
    }
    // 数据由响应式 computed 驱动时，先等 DOM 更新；再等一帧确保行已渲染
    const doScroll = () => requestAnimationFrame(() => scrollToRow(pos))
    if (needSwitch) nextTick(() => doScroll())
    else doScroll()
  }

  // ★ 精确定位滚动：直接操作表格纵向滚动容器，按行顶到视区顶部偏下一点
  //   （EP 的 scrollTo 在部分版本/大数据分页下不稳定，DOM 级定位最可靠）
  function scrollToRow(pos) {
    const inst = tableRef ? tableRef.value : null
    if (!inst) return
    const root = inst.$el || inst
    let wrap = null
    if (root && root.querySelector) {
      const body = root.querySelector('.el-table__body-wrapper')
      if (body) {
        wrap = body.querySelector('.el-scrollbar__wrap') || body
      }
    }
    const rowIdx = currentPage && pageSize ? pos % pageSize.value : pos
    if (wrap && wrap.querySelectorAll) {
      const rows = wrap.querySelectorAll('.el-table__row')
      const tr = rows[rowIdx]
      if (tr) {
        const rect = tr.getBoundingClientRect()
        const wrect = wrap.getBoundingClientRect()
        wrap.scrollTop += rect.top - wrect.top - 84
      }
    }
    // 兜底：EP 官方 scrollTo
    try {
      if (typeof inst.scrollTo === 'function') inst.scrollTo({ index: rowIdx, offset: -80 })
    } catch (e) {
      try {
        if (typeof inst.scrollTo === 'function') inst.scrollTo({ row: rowIdx, offset: -80 })
      } catch (e2) { /* 版本不支持时静默 */ }
    }
  }

  function close() {
    visible.value = false
    keyword.value = ''
    matches.value = []
    hitIds.value = new Set()
    activeIdx.value = -1
  }

  // ★ 全局键盘：Ctrl+F / F3 打开；Enter/Shift+Enter 上下切换；Esc 关闭
  function onKeydown(e) {
    if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'f') {
      e.preventDefault()
      visible.value = true
      // ★ 打开后自动聚焦搜索输入框（光标激活即可直接输入，无需再点一下）
      focusSearch()
      return
    }
    if (visible.value) {
      // ★ 若焦点在页面其它输入框/下拉内，Enter 不抢走（避免干扰正常编辑）
      const tag = e.target && e.target.tagName
      const inEditable = tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT'
      if (inEditable && e.target !== searchBoxEl()) return
      if (e.key === 'Enter') { e.preventDefault(); jumpNext(e.shiftKey ? -1 : 1) }
      else if (e.key === 'Escape') { e.preventDefault(); close() }
      else if (e.key === 'F3') { e.preventDefault(); jumpNext(e.shiftKey ? -1 : 1) }
    }
  }

  // 当前页面搜索条输入框（只有激活页面注册了监听，不会串页）
  function searchBoxEl() {
    return document.querySelector('.table-search-bar .ts-input')
  }
  // ★ 自动聚焦：打开后立即 + 多次重试（v-if 渲染/布局重算/加载遮罩退场等时机差异都能抢回光标）
  function focusSearch() {
    const attempt = (left) => {
      const el = searchBoxEl()
      if (el && el.focus) {
        try { el.focus() } catch (e) {}
        try { el.select() } catch (e) {}
        return true
      }
      if (left > 0) setTimeout(() => attempt(left - 1), 80)
      return false
    }
    nextTick(() => { if (!attempt(0)) attempt(6) })
  }

  return { visible, keyword, matches, activeIdx, doSearch, jumpNext, close, isHit, isActive, isCellHit, searchCellClass, onKeydown }
}
