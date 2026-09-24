<template>
  <div class="archive-view">
    <div class="pbar">
      <div class="pbar-left">
        <div class="ptag">ARCHIVE</div>
        <div class="ptitle">存档中心 · <span>已最终定版的数据</span></div>
      </div>
      <div class="pright">
        <!-- ★ 导出选项（2026-09-14）：按「预排月份」拆 Sheet，一次拿到分月明细 -->
        <label class="split-opt" :class="{ on: splitByMonth }" title="勾选后导出按预排月份拆分为多个 Sheet">
          <input type="checkbox" v-model="splitByMonth" /><span>按月分 Sheet</span>
        </label>
        <button type="button" class="run-btn primary" :disabled="!filteredRows.length" @click="handleExport">导出</button>
        <button type="button" class="naming-gear" title="自定义导出文件名" @click="openNaming('archive')"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M19.14 12.94a7.5 7.5 0 0 0 .05-1.88l2.03-1.58a.5.5 0 0 0 .12-.64l-1.92-3.32a.5.5 0 0 0-.6-.22l-2.39.96a7.03 7.03 0 0 0-1.62-.94l-.36-2.54a.5.5 0 0 0-.5-.42h-3.84a.5.5 0 0 0-.5.42l-.36 2.54c-.59.24-1.13.55-1.62.94l-2.39-.96a.5.5 0 0 0-.6.22L2.74 8.84a.5.5 0 0 0 .12.64l2.03 1.58a7.5 7.5 0 0 0 0 1.88l-2.03 1.58a.5.5 0 0 0-.12.64l1.92 3.32c.13.22.4.31.6.22l2.39-.96c.49.39 1.03.7 1.62.94l.36 2.54c.04.24.25.42.5.42h3.84c.25 0 .46-.18.5-.42l.36-2.54c.59-.24 1.13-.55 1.62-.94l2.39.96c.2.09.47 0 .6-.22l1.92-3.32a.5.5 0 0 0-.12-.64l-2.03-1.58zM12 15.5A3.5 3.5 0 1 1 12 8.5a3.5 3.5 0 0 1 0 7z"/></svg></button>
        <ExportNamingDialog v-model="namingOpen" :type="namingType" :ctx="exportNamingCtx" />
        <button type="button" class="run-btn sec" :disabled="!filteredRows.length" @click="handleClearArchive">清空存档</button>
        <button type="button" class="run-btn sec" :disabled="loading" @click="loadData">{{ loading ? '加载中...' : '刷新' }}</button>
      </div>
    </div>

    <div class="help-bar">
      <span class="help-icon">🗄️</span>
      <span class="help-text">在「审核决议中心」完成决议后点「保存到存档中心」，数据即在此定版存档。可按年/月筛选查看。</span>
    </div>

    <!-- 筛选 -->
    <div class="filter-bar">
      <div class="filter-group">
        <span class="filter-label">📅 年份：</span>
        <el-select v-model="filterYear" placeholder="全部年份" clearable size="default" class="year-select" popper-class="app-select-popper">
          <el-option v-for="y in yearOptions" :key="y" :label="String(y)" :value="y" />
        </el-select>
      </div>
      <div class="filter-group">
        <span class="filter-label">📆 月份：</span>
        <el-select v-model="filterMonth" placeholder="全部月份" clearable size="default" class="month-select" popper-class="app-select-popper">
          <el-option v-for="opt in monthOptions" :key="String(opt.ym)" :label="opt.label" :value="opt.ym" />
        </el-select>
      </div>
      <div class="filter-group total-group">
        <span class="filter-label">共 <b class="total-num">{{ filteredRows.length }}</b> 行</span>
      </div>
    </div>

    <!-- 定版数据表格（与审核决议中心相同格式） -->
    <div ref="tableWrapRef" class="table-wrapper" @mousedown="onDragStart">
      <!-- ★ Ctrl+F 搜索条（2026-09-14 接入，与预排/决议页同款） -->
      <div v-if="searchVisible" class="table-search-bar">
        <input v-model="searchKeyword" @input="doSearch()" @keydown.enter="jumpNext(1)" @keydown.shift.enter="jumpNext(-1)" placeholder="输入关键字搜索（Enter 下一个 / Shift+Enter 上一个 / Esc 关闭）" class="ts-input" />
        <span class="ts-count">{{ matches.length ? (activeIdx + 1) + '/' + matches.length : '0 个匹配' }}</span>
        <button type="button" class="ts-btn" @click="jumpNext(1)">↓</button>
        <button type="button" class="ts-btn" @click="jumpNext(-1)">↑</button>
        <button type="button" class="ts-btn ts-close" @click="closeSearch()">✕</button>
      </div>
      <el-table ref="tableRef" v-loading="loading" :data="pagedRows" :row-class-name="archiveRowClass" :cell-class-name="searchCellClass"
        :cell-style="{ background: 'transparent', textAlign: 'center' }"
        :header-cell-style="{ background: 'rgba(0,40,80,.6)', color: '#6aa3c8', textAlign: 'center' }"
        class="archive-table" empty-text="暂无存档数据（请先在决议中心保存到存档中心）" style="width:100%" :max-height="tableH">
        <el-table-column label="序号" width="60" align="center"><template #default="{ $index }"><span class="row-idx">{{ (currentPage - 1) * pageSize + $index + 1 }}</span></template></el-table-column>
        <el-table-column v-for="col in TABLE_COLUMNS" :key="col.key" :prop="col.key" :label="col.label" :min-width="col.width || 100" align="center">
          <template #default="{ row }">
            <span v-if="isDecisionField(col.key)" class="decision-text" :class="['decision-' + ((row[col.key] || 'none'))]">{{ row[col.key] || '' }}</span>
            <span v-else :class="col.key === 'source' ? (row.is_plan_external ? 'src-ext' : (row.source === 'S13_DPS' ? 'src-a' : 'src-b')) : ''">
              <template v-if="col.key === 'source' && row.is_plan_external">计划外</template>
              <template v-else>{{ formatCell(row[col.key]) }}</template>
            </span>
          </template>
        </el-table-column>
        <!-- ★ 定版时间列（2026-09-14）：追溯该行何时保存到存档中心
             ★ 取消固定（2026-09-15 用户明确）：原为 fixed="right"，会一直黏在视口右侧，
             无论横向怎么滚都占着 300px；用户要求「固定在它原本的位置」= 作为普通列排在
             表格最右，随内容一起滚走（与预排/决议/预警页表格一致）。 -->
        <el-table-column label="定版时间" width="150" align="center">
          <template #default="{ row }"><span class="archived-at">{{ row.archived_at || '—' }}</span></template>
        </el-table-column>
        <!-- ★ 行级操作（2026-09-14）：撤销存档（回决议中心）/ 删除单行（同上，取消 fixed="right"） -->
        <el-table-column label="操作" width="150" align="center">
          <template #default="{ row }">
            <button type="button" class="op-btn op-unarchive" @click.stop="handleUnarchive(row)">撤销存档</button>
            <button type="button" class="op-btn op-del" @click.stop="handleDeleteRow(row)">删除</button>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <div class="pagination-bar">
      <el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :page-sizes="[20, 50, 100]"
        :total="filteredRows.length" layout="sizes,prev,pager,next" size="small" @current-change="currentPage = $event" @size-change="currentPage = 1" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onActivated, onDeactivated, onBeforeUnmount } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
import { TABLE_COLUMNS, DECISION_FIELDS } from '../config/preplanColumns'
import { useTableSearch } from '../composables/useTableSearch'
import { useFitHeight } from '../composables/useFitHeight'
import { buildFileName, monthLabelFromYm, fullLabelFromYm } from '../composables/useExportNaming.js'
import ExportNamingDialog from '../components/common/ExportNamingDialog.vue'

defineOptions({ name: 'HistoryView' })

const API = import.meta.env.VITE_API_BASE || '/api'
const loading = ref(false)
const allRows = ref([])
const filterYear = ref('')
const filterMonth = ref(null)
const currentPage = ref(1)
const pageSize = ref(50)
// ★ 导出选项（2026-09-14）：是否按预排月份拆分 Sheet
const splitByMonth = ref(false)

// ★ 导出命名菜单（2026-09-18）：每个导出按钮旁的小齿轮打开对应类型的命名配置弹窗
const namingOpen = ref(false)
const namingType = ref('archive')
function openNaming(t) { namingType.value = t; namingOpen.value = true }

const DECISION_KEYS = DECISION_FIELDS.map(f => f.key)
function isDecisionField(k){ return DECISION_KEYS.includes(k) }

// ★ 2026-09-20：导出命名上下文（真实导出与命名配置弹窗预览共用同一份）
//   {month} 跟随「预排月份」筛选、{label} 为「年+月」复合标签、{split} 跟随「按月分 Sheet」勾选。
//   预览再也不会是写死的样本；导出的文件名与预览必然一致。
const exportNamingCtx = computed(() => {
  const envYear = filterYear.value || ''
  const ymv = filterMonth.value
  return {
    year: envYear || '全部',
    month: monthLabelFromYm(ymv),
    label: fullLabelFromYm(ymv, envYear || '全部'),
    splitByMonth: splitByMonth.value,
  }
})

// ★ 导出存档数据（2026-09-14：跟随页面年/月筛选，不再固定导出全部；文件名带筛选条件）
//   2026-09-20：改传 ym（YYYYMM 数值），后端按 plan_ym 精确匹配 —— 比 '9月' 文本更稳，跨年同名月不冲突
async function handleExport(){
  try {
    const expYear = filterYear.value || ''
    const expYm = filterMonth.value || ''      // null/'' = 全部月份
    const res = await axios.post(`${API}/preplan/export-archive-excel/`, {
      year: expYear,
      ym: expYm,
      split_by_month: splitByMonth.value,
    }, { responseType: 'blob' })
    if (res.data instanceof Blob && res.data.type.includes('json')) {
      const err = JSON.parse(await res.data.text())
      ElMessage.error(err.error || '导出失败'); return
    }
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a'); a.href = url
    // 命名走自定义模板（兜底文件名也由模板统一生成）；上下文与配置弹窗预览共用同一份
    a.download = buildFileName('archive', exportNamingCtx.value); a.click()
    URL.revokeObjectURL(url)
  } catch (e) { ElMessage.error('导出失败：' + (e.response?.data?.error || e.message)) }
}

// ★ 撤销存档（2026-09-14）：单行 archived 置回 False，数据回到审核决议中心
async function handleUnarchive(row){
  try {
    await ElMessageBox.confirm('确定撤销该行存档？数据将回到「审核决议中心」，可修改决议后重新定版。', '撤销存档', { type: 'warning' })
  } catch { return }
  try {
    const res = await axios.post(`${API}/preplan/unarchive/${row.id}/`)
    ElMessage.success(res.data?.message || '已撤销存档')
    await loadData()
  } catch (e) { ElMessage.error('撤销失败：' + (e.response?.data?.error || e.message)) }
}

// ★ 删除单行（2026-09-14）：复用后端 preplan_delete（删除前自动备份）
async function handleDeleteRow(row){
  try {
    await ElMessageBox.confirm('确定删除该行？删除前会自动备份数据库，但行本身不可恢复。', '删除确认', { type: 'warning' })
  } catch { return }
  try {
    const res = await axios.post(`${API}/preplan/delete/${row.id}/`)
    ElMessage.success(res.data?.message || '已删除该行')
    await loadData()
  } catch (e) { ElMessage.error('删除失败：' + (e.response?.data?.error || e.message)) }
}

// ★ 清空存档（只清已定版存档的计划内数据；计划外行保留，2026-09-02 优化）
//   ★ 2026-09-21：改为「由后端回执驱动提示」——
//     deleted>0 → 绿色；deleted==0 → **黄色告警**（说明还剩多少「计划外」按设计保留），
//     避免用户看到绿色「成功」却发现表格还有行、误判成「没生效」；
//     失败带出真实原因；**finally 无条件 loadData()**（旧实现失败会跳过刷新，页面留着旧数据）。
async function handleClearArchive(){
  try {
    await ElMessageBox.confirm('确定清空存档中心所有计划数据？此操作不可恢复（计划外数据将保留）', '清空确认', { type: 'warning' })
  } catch { return }
  try {
    const res = await axios.post(`${API}/preplan/clear-archive/`, {})
    const d = res.data || {}
    const deleted = Number(d.deleted) || 0
    const kept = Number(d.kept_external) || 0
    if (deleted > 0) {
      ElMessage.success(d.message || `已清空存档中心 ${deleted} 条`)
    } else {
      ElMessage.warning(d.message || (kept > 0
        ? `本次未删除任何行：存档中心仍有 ${kept} 条「计划外」数据按设计保留（见「来源」列标黄的行）`
        : '本次未删除任何行：存档中心当前没有计划内存档数据'))
      console.warn('[存档中心] 清空未删除任何行', d)
    }
  } catch (e) {
    ElMessage.error('清空失败：' + (e.response?.data?.error || e.message))
  } finally {
    await loadData()      // ★ 无论成功/失败都刷新，避免页面残留旧数据
  }
}

const yearOptions = computed(() => {
  const s = new Set()
  allRows.value.forEach(r => { if (r.plan_year) s.add(r.plan_year) })
  if (!s.size) s.add(new Date().getFullYear())
  return [...s].sort((a, b) => b - a)
})
// ★ 2026-09-20：月份选项改由 plan_ym（YYYYMM）派生。
//   历史实现用「plan_year + plan_month_label」复合文本键，虽能区分跨年同名月，
//   但一旦 plan_month_label 为空（计划外行未回填）该行就永远进不了任何月份选项。
//   plan_ym 是数值、且计划外行同步时会自动补，故统一改用它。
const monthOptions = computed(() => {
  const s = new Set()
  allRows.value.forEach(r => { const v = r.plan_ym; if (v !== undefined && v !== null) s.add(Number(v) || 0) })
  // ★ 2026-09-21：el-option 的 value 不接受 null（Element Plus 类型校验会 warn），
  //   「全部月份」改用 '' —— 本页 expYm 与过滤守卫本来就按 null / '' 双兼容写的，语义不变。
  const out = [{ ym: '', label: '全部月份' }]
  const months = [...s].filter(v => v > 0).sort((a, b) => b - a)
  months.forEach(v => out.push({ ym: v, label: `${Math.floor(v / 100)}年${v % 100}月` }))
  if (s.has(0)) out.push({ ym: 0, label: '未归类' })
  return out
})
const filteredRows = computed(() => {
  let list = allRows.value
  if (filterYear.value) list = list.filter(r => r.plan_year === filterYear.value)
  if (filterMonth.value !== null && filterMonth.value !== '') {
    list = list.filter(r => (Number(r.plan_ym) || 0) === Number(filterMonth.value))
  }
  return list
})
const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return filteredRows.value.slice(start, start + pageSize.value)
})

// ★ Ctrl+F 搜索（2026-09-14 接入，与预排/决议页同款 composable）
const tableWrapRef = ref(null)
const tableRef = ref(null)
const tableMaxH = useFitHeight(tableWrapRef)
// 表格高度 = 容器剩余高度（搜索条展开时扣 38px）→ 单一内部滚动条、表头吸顶
const tableH = computed(() => Math.max(120, tableMaxH.value - (searchVisible.value ? 38 : 4)))
const { visible: searchVisible, keyword: searchKeyword, matches, activeIdx,
        doSearch, jumpNext, close: closeSearch, isHit, isActive, searchCellClass, onKeydown: onTableSearchKey } = useTableSearch({
  getRows: () => filteredRows.value,
  // ★ 只在表格展示的列内匹配（不扫 id/时间戳/布尔标志等隐藏字段，防误命中）
  //   末位 archived_at = 「定版时间」列（不在共享列内）
  searchKeys: [...TABLE_COLUMNS.map(c => c.key), 'archived_at'],
  tableRef,
  currentPage,
  pageSize,
  pageCount: () => Math.max(1, Math.ceil(filteredRows.value.length / pageSize.value)),
})
// ★ 搜索命中行高亮 + 当前项闪烁（叠加在原有行样式之上）
function archiveRowClass({ row }){
  const cls = []
  if (isHit(row)) cls.push('search-hit')
  if (isActive(row)) cls.push('search-active')
  return cls
}
function formatCell(v){ if (v === null || v === undefined) return ''; if (typeof v === 'string'){ const t = v.trim(); return (!t || t === 'undefined' || t === 'null' || t === 'NaN') ? '' : t } return String(v) }

// ★ 表格横向拖动（与预排/决议/预警一致；监听挂全局，鼠标移出表格区不中断）
let dragState = null
function getScrollEl(wrapper){
  // 优先取「实际可横向滚动」的容器：EP el-table 内部 scrollbar 的 wrap，其次 body wrapper，兜底容器自身
  const wrap = wrapper.querySelector('.el-scrollbar__wrap')
  if (wrap && wrap.scrollWidth > wrap.clientWidth) return wrap
  const body = wrapper.querySelector('.el-table__body-wrapper')
  if (body && body.scrollWidth > body.clientWidth) return body
  return wrapper
}
function blockSelect(e){ e.preventDefault() }
function onDragStart(e){
  // 忽略从可交互元素（下拉/开关/按钮/输入框等）开始的拖动，避免干扰原有交互
  if (e.target.closest && e.target.closest('input,textarea,select,button,.el-select,.el-switch,label,a')) return
  const wrapper = e.currentTarget
  const sc = getScrollEl(wrapper)
  if (!sc) return
  dragState = { wrapper, sc, startX: e.clientX, left: sc.scrollLeft, moved: false }
  document.addEventListener('mousemove', onDragMove)
  document.addEventListener('mouseup', onDragEnd)
  document.addEventListener('selectstart', blockSelect, true)
}
function onDragMove(e){
  if (!dragState) return
  const dx = e.clientX - dragState.startX
  if (!dragState.moved && Math.abs(dx) > 3){
    dragState.moved = true
    dragState.wrapper.classList.add('dragging')
  }
  if (dragState.moved){
    dragState.sc.scrollLeft = dragState.left - dx
    // ★ 兜底：内部容器不可横向滚动时，回退到 wrapper 自身滚动
    if (dragState.sc.scrollWidth <= dragState.sc.clientWidth && dragState.wrapper.scrollWidth > dragState.wrapper.clientWidth){
      dragState.wrapper.scrollLeft = dragState.left - dx
    }
    e.preventDefault()
  }
}
function onDragEnd(){
  if (dragState){
    if (dragState.moved) dragState.wrapper.classList.remove('dragging')
    document.removeEventListener('mousemove', onDragMove)
    document.removeEventListener('mouseup', onDragEnd)
    document.removeEventListener('selectstart', blockSelect, true)
    dragState = null
  }
}

async function loadData(){
  loading.value = true
  try {
    const res = await axios.get(`${API}/preplan/rows/`, { params: { archived: 'true' } })
    allRows.value = res.data?.data || []
    currentPage.value = 1
  } catch (e) {
    // ★ 2026-09-21：失败时清空并说明原因，避免页面继续显示上一次的旧数据
    //   （旧数据 + 「清空 0 条」会被用户误读成「清空没生效」）
    allRows.value = []
    ElMessage.error('加载存档数据失败：' + (e.response?.data?.error || e.message))
  } finally { loading.value = false }
}

// ★ 用 onActivated：keep-alive 缓存组件时，每次进入页面都重新加载
onActivated(() => {
  loadData()
  // keep-alive：激活时注册 Ctrl+F 监听、停用时移除（避免缓存页面同时响应）
  window.addEventListener('keydown', onTableSearchKey)
})
onDeactivated(() => window.removeEventListener('keydown', onTableSearchKey))
onBeforeUnmount(() => window.removeEventListener('keydown', onTableSearchKey))
</script>

<style lang="scss" scoped>
.archive-view{ height:100%; display:flex; flex-direction:column; gap:8px; padding:4px 6px; min-height:0; background:transparent; }
.pbar{ display:flex; align-items:center; justify-content:space-between; flex-shrink:0; }
.pbar-left{ display:flex; align-items:center; gap:8px; }
.ptag{ background:rgba(0,120,220,.18); border:1px solid #0d4a80; color:#6ab8f0; font-size:10px; font-weight:700; letter-spacing:1px; padding:3px 10px; border-radius:4px; }
.ptitle{ font-size:15px; font-weight:500; color:#c8e0f8; span{ color:#8ab8d8; } }
.run-btn{ font-size:11px; font-weight:600; padding:4px 10px; border-radius:12px; cursor:pointer; border:none; font-family:inherit; display:inline-flex; align-items:center; gap:2px; &.primary{ background:linear-gradient(135deg,#0055aa,#0077cc); color:#fff; box-shadow:0 2px 6px rgba(0,100,200,.35); &:hover:not(:disabled){ box-shadow:0 3px 12px rgba(0,120,240,.5); } &:disabled{ background:rgba(0,40,80,.4); color:#4d7d9e; box-shadow:none; cursor:not-allowed; } } &.sec{ background:rgba(0,40,80,.3); color:#5a90b8; border:1px solid #0d3050; &:hover:not(:disabled){ background:rgba(0,60,120,.4); color:#90c0e8; } &:disabled{ opacity:.4; } } }
.help-bar{ display:flex; align-items:center; gap:8px; padding:6px 12px; font-size:11px; color:#a0c8e8; background:rgba(0,60,120,.12); border:1px dashed #0d4a70; border-radius:6px; flex-shrink:0; }
.filter-bar{ display:flex; align-items:center; gap:14px; padding:6px 12px; background:rgba(5,15,30,.5); border:1px solid #0d2a48; border-radius:8px; flex-shrink:0; flex-wrap:wrap; }
.filter-group{ display:flex; align-items:center; gap:6px; flex-shrink:0; }
.filter-label{ font-size:11px; color:#6aa3c8; white-space:nowrap; }
.year-select,.month-select{ width:120px!important; }
.total-group{ margin-left:auto; }
.total-num{ color:#c8e0f8; font-size:13px; }
/* ★ 行级操作按钮（2026-09-14） */
.op-btn{ font-size:10px; font-weight:600; padding:2px 8px; border-radius:9px; cursor:pointer; border:1px solid #0d3050; background:rgba(0,40,80,.3); color:#5a90b8; font-family:inherit; margin:0 2px; &:hover{ color:#e0f0ff; } }
.op-btn.op-unarchive{ &:hover{ background:rgba(0,150,120,.35); border-color:#0d7a62; color:#7df0d8; } }
.op-btn.op-del{ &:hover{ background:rgba(200,60,60,.3); border-color:#8a3030; color:#ff9b9b; } }
/* ★ 导出「按月分 Sheet」开关（2026-09-14）：自绘深色控件，避免 Element Plus 浅色痕迹 */
.split-opt{ display:inline-flex; align-items:center; gap:5px; font-size:11px; color:#5a90b8; cursor:pointer; user-select:none; padding:3px 9px; border:1px solid #0d3050; border-radius:11px; background:rgba(0,40,80,.3);
  input{ appearance:none; width:11px; height:11px; margin:0; border:1px solid #1c5a86; border-radius:3px; background:rgba(3,15,30,.8); cursor:pointer; position:relative;
    &:checked{ background:#0d7fd6; border-color:#3aa8f0;
      &::after{ content:'✓'; position:absolute; left:1px; top:-3px; font-size:9px; color:#fff; } } }
  &.on{ color:#7dc4f0; border-color:#1c6fa8; background:rgba(0,90,160,.28); }
  &:hover{ color:#c8e4ff; border-color:#1c6fa8; } }
.archived-at{ color:#8ab8d8; font-size:11px; }
/* ★ 与审核决议中心 / 实时预警页逐字一致（2026-09-15）：
   原为 overflow:auto（本页独有），会让 .table-wrapper 变成「第二个滚动容器」，
   与 el-table 内部的 .el-scrollbar__wrap 形成嵌套滚动 —— 横向拖动时固定列
   的 sticky 参照被夹在两个 scrollport 之间，看起来就会「跟着滚动条滑动」。
   改成 overflow:hidden + flex column 后，全页只剩 el-table 内部一条滚动条，
   与其它页面表现完全一致。 */
.table-wrapper{ flex:1; min-height:0; overflow:hidden; display:flex; flex-direction:column; cursor:grab; background:rgba(5,15,30,.5); border:1px solid #0d2a48; border-radius:8px; }
.archive-table{ flex:1 1 auto; min-height:0; }
.table-wrapper.dragging{ cursor:grabbing; user-select:none; -webkit-user-select:none; }
.archive-view :deep(.el-table){ --el-table-bg-color:transparent; --el-table-tr-bg-color:rgba(5,15,30,.5); --el-table-header-bg-color:rgba(0,40,80,.35); --el-table-border-color:#0d2a48; --el-table-row-hover-bg-color:rgba(0,60,120,.25); --el-table-text-color:#c8ddf5; --el-table-header-text-color:#a0c8e8; color:#c8ddf5; }
/* ★ 固定列相关样式已全部移除（2026-09-15 用户明确「不要固定列」）：
   定版时间 / 操作两列取消 fixed="right" 后，下面这些规则的选择器再也匹配不到元素，
   属于死代码，一并删除 —— 之前为它加过的整套东西：
   ① 固定列 z-index 硬锁定（calc(var(--el-table-index) + 2)）
   ② fixed 单元格实色背景（#061426 / #050e17 / hover #0c2036）
   ③ 固定列左侧分隔线 + 阴影
   ④ .el-table__inner-wrapper::before 去底色
   注意：上面 el-table 的 --el-table-bg-color:transparent 保留即可，普通列本来就
   透明，由 .table-wrapper 的底色透出，视觉与其它页面一致。 */
.archive-view :deep(.el-loading-mask){ background:rgba(3,9,15,.72)!important; }
.row-idx{ color:#4d7d9e; font-size:11px; }
.src-a{ color:#4d9fd8; font-weight:600; } .src-b{ color:#00b4a0; font-weight:600; }
.src-ext{ color:#ffd54f; font-weight:700; }
.decision-text{ display:block; }
.decision-Y{ color:#00d4aa; font-weight:600; }
.decision-N{ color:#ff6b6b; font-weight:600; }
.decision-待定{ color:#e8b838; font-weight:600; }
.pagination-bar{ display:flex; justify-content:flex-end; padding:4px 2px; flex-shrink:0; }
.archive-view :deep(.el-select__wrapper){ background:rgba(0,30,60,.5)!important; box-shadow:0 0 0 1px #0d3050 inset!important; }
.archive-view :deep(.el-pagination .btn-prev),.archive-view :deep(.el-pagination .btn-next){ background:rgba(0,40,80,.35)!important; color:#a8cce8!important; border-radius:4px; }
.archive-view :deep(.el-pagination .btn-prev:hover:not(:disabled)),.archive-view :deep(.el-pagination .btn-next:hover:not(:disabled)){ background:rgba(0,80,160,.45)!important; color:#e0f0ff!important; }
.archive-view :deep(.el-pagination .btn-prev:disabled),.archive-view :deep(.el-pagination .btn-next:disabled){ background:rgba(0,25,50,.45)!important; color:#3f6a8f!important; }
.archive-view :deep(.el-pagination .el-pager li){ background:rgba(0,40,80,.35)!important; color:#a8cce8!important; border-radius:4px; margin:0 2px; font-weight:600; }
.archive-view :deep(.el-pagination .el-pager li.is-active){ background:rgba(0,110,220,.6)!important; color:#fff!important; }

/* ══════════════════════════════════════════════════════════════════════
   ★ 白天主题覆盖（2026-09-18）
   根因：本页原样式整套写死深色（主文字 #c8e0f8/#c8ddf5、面板底 rgba(5,15,30,.5)、
   边框 #0d2a48/#0d3050、表头底 rgba(0,40,80,.6)/.35、计划外 #ffd54f、
   决议 Y/N #00d4aa / #ff6b6b 等），且无 [data-theme="light"] 覆盖
   → 切白天后浅字压浅底读不清。此处统一改为「浅底 + 深字」，
   语义色（红=警 / 绿=好 / 黄=注意）加深以保证白底可读。
   scoped：用 .archive-view 承接 data-v；Element Plus 内部用 :deep。
   注意：模板上 :header-cell-style 为行内样式，必须 !important 才能覆盖。
   ══════════════════════════════════════════════════════════════════════ */
[data-theme="light"] .archive-view {
  color: #1a4070;

  .ptag { background: #dbe7f6; border-color: #bcd4ec; color: #2a5a86; }
  .ptitle { color: #0a2858; span { color: #5a7a9a; } }
  .run-btn {
    &.sec { background: var(--well); color: #4a6a8a; border-color: #c0d2e4;
      &:hover:not(:disabled) { background: #cddcec; color: #24507a; } }
    &.primary:disabled { background: #e6edf4; color: #9ab0c4; }
  }

  .help-bar { color: #2a5a86; background: var(--surface-2); border-color: #bcd4ec; }
  .filter-bar { background: var(--surface-2); border-color: var(--line-1); }
  .filter-label { color: #5a7a9a; }
  .total-num { color: #0a2858; }

  .op-btn { border-color: #c0d2e4; background: var(--surface-2); color: #4a6a8a;
    &:hover { color: #0a2858; } }
  .op-btn.op-unarchive:hover { background: #d4f0e6; border-color: #7fc7b0; color: #0a7a5e; }
  .op-btn.op-del:hover { background: #fadada; border-color: #e8a0a0; color: #a02020; }

  .split-opt { color: #4a6a8a; border-color: #c0d2e4; background: var(--surface-2);
    input { border-color: #9cc4e6; background: var(--field);
      &:checked { background: #2a7fd0; border-color: #7fb2e0;
        &::after { color: #ffffff; } } }
    &.on { color: #14508c; border-color: #7fb2e0; background: #c9ddf3; }
    &:hover { color: #0a2858; border-color: #7fb2e0; } }

  .archived-at { color: #5a7a9a; }
  .table-wrapper { background: var(--surface-1); border-color: var(--line-1); }
  .row-idx { color: #7a93ab; }
  .src-a { color: #0a6fd0; } .src-b { color: #1f8f3f; } .src-ext { color: #b8860b; }
  .decision-Y { color: #0a8f6e; }
  .decision-N { color: #d02828; }
  .decision-待定 { color: #b07800; }

  /* Element Plus：表头 / 行 / 分页 / 下拉 / loading */
  :deep(.el-table) { --el-table-bg-color: transparent; --el-table-tr-bg-color: #ffffff;
    --el-table-header-bg-color: #eef4fa; --el-table-border-color: var(--line-2);
    --el-table-row-hover-bg-color: #eaf3fc; --el-table-text-color: #0a2858;
    --el-table-header-text-color: #3a6a94; color: #0a2858; }
  :deep(.el-table__header-wrapper th) { background: var(--surface-2) !important; color: #3a6a94 !important; }
  :deep(.el-table__body tr:hover > td) { background: #dce8f6 !important; }
  :deep(.el-loading-mask) { background: rgba(233,240,248,.82) !important; }
  :deep(.el-select__wrapper) { background: var(--field) !important; box-shadow: 0 0 0 1px #c9daea inset !important; }
  :deep(.el-pagination .btn-prev), :deep(.el-pagination .btn-next) { background: var(--surface-2) !important; color: #2a5a86 !important; }
  :deep(.el-pagination .btn-prev:hover:not(:disabled)), :deep(.el-pagination .btn-next:hover:not(:disabled)) { background: #cddcec !important; color: #0a2858 !important; }
  :deep(.el-pagination .btn-prev:disabled), :deep(.el-pagination .btn-next:disabled) { background: #f2f5f8 !important; color: #a8bccd !important; }
  :deep(.el-pagination .el-pager li) { background: var(--surface-2) !important; color: #2a5a86 !important; }
  :deep(.el-pagination .el-pager li:hover) { background: #cddcec !important; color: #0a2858 !important; }
  :deep(.el-pagination .el-pager li.is-active) { background: #2a7fd0 !important; color: #ffffff !important; }
}
</style>
