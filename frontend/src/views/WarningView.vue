<template>
  <div class="warning-view">
    <!-- 页面标题栏 -->
    <div class="pbar">
      <div class="pbar-left">
        <div class="ptag">WARNING</div>
        <div class="ptitle">实时预警监控 · <span>基于预排筛选数据（按预排月份）</span></div>
      </div>
      <div class="pright">
        <el-select v-model="filterMonth" placeholder="全部月份" clearable size="default" class="month-select" popper-class="app-select-popper">
          <el-option v-for="opt in monthOptions" :key="String(opt.ym)" :label="opt.label" :value="opt.ym" />
        </el-select>
        <button type="button" class="run-btn sec" :class="{ on: onlyExternal }" @click="onlyExternal = !onlyExternal">{{ onlyExternal ? '显示全部' : '仅计划外' }}</button>
        <button type="button" class="run-btn primary" :disabled="insertingAll || externalCount===0" @click="handleInsertAll" title="将所有计划外数据一次性插入审核决议中心（插入期间以橙色标注，完成后恢复原色）">{{ insertingAll ? '插入中...' : '将计划外插入到审核决议中心' }}</button>
        <button type="button" class="run-btn sec" :disabled="syncing" @click="handleSyncMtd">{{ syncing ? '同步中...' : '同步MTD' }}</button>
        <button type="button" class="run-btn sec" :disabled="syncing" @click="handleRefresh">刷新</button>
      </div>
    </div>

    <!-- 顶部说明 -->
    <div class="help-bar">
      <div class="help-item">
        <span class="help-icon">📊</span>
        <span class="help-text">红灯=已达到目标(可处理)，绿灯=正在生产中(未达标) · QE需送样且产能达标项已优先置顶 · 计划外数据需先回填 Type，系统自动匹配 ORT 规则后重算达标状态 · MTD OUTPUT 通过「同步MTD」实时抓取 · 计划外行可用「插入预排」开关选择是否进入预排筛选。</span>
      </div>
    </div>

    <!-- ★ 需求6：送样报警条 —— 已达可送样条件但尚未送样 -->
    <div v-if="shipAlarmCount" class="ship-alert-bar">⚠️ 已有 <b>{{ shipAlarmCount }}</b> 条「QE需送样且产能已达标」但送样未就绪（Q工单 / 箱号 / 送样日期存在缺失），请补录后自动变为「可送」并同步至审核决议中心！</div>

    <!-- 统计卡片 -->
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-label">总决议项</div>
        <div class="stat-value">{{ stats.total }}</div>
      </div>
      <div class="stat-card met">
        <div class="stat-label">已达标 · 可处理</div>
        <div class="stat-value">{{ stats.met }}</div>
        <div class="stat-sub">红灯提示</div>
      </div>
      <div class="stat-card producing">
        <div class="stat-label">生产中 · 未达标</div>
        <div class="stat-value">{{ stats.producing }}</div>
        <div class="stat-sub">绿灯提示</div>
      </div>
      <div class="stat-card pending">
        <div class="stat-label">待回填 · 计划外</div>
        <div class="stat-value">{{ stats.pending }}</div>
        <div class="stat-sub">需回填 Type</div>
      </div>
      <div class="stat-card ext">
        <div class="stat-label">MTD 查到总数</div>
        <div class="stat-value">{{ mtdTotal }}</div>
      </div>
      <div class="stat-card ext">
        <div class="stat-label">计划外数据</div>
        <div class="stat-value">{{ externalCount }}</div>
      </div>
    </div>

    <!-- 图表区 -->
    <div class="chart-grid">
      <div class="chart-box">
        <div class="chart-title">各预排月份：总行数 vs 已达标数</div>
        <div ref="barRef" class="chart-canvas"></div>
      </div>
      <div class="chart-box">
        <div class="chart-title">来源分布（S13 / S11）</div>
        <div ref="pieRef" class="chart-canvas"></div>
      </div>
    </div>

    <!-- 决议明细表（全部已通过数据，达标=红灯、未达标=绿灯） -->
    <div ref="tableWrapRef" class="table-wrapper" @mousedown="onDragStart">
      <!-- ★ Ctrl+F 搜索条（P1-2） -->
      <div v-if="searchVisible" class="table-search-bar">
        <input v-model="searchKeyword" @input="doSearch()" placeholder="输入关键字搜索（Enter 下一个 / Shift+Enter 上一个 / Esc 关闭）" class="ts-input" />
        <span class="ts-count">{{ matches.length ? (activeIdx + 1) + '/' + matches.length : '0 个匹配' }}</span>
        <button type="button" class="ts-btn" @click="jumpNext(1)">↓</button>
        <button type="button" class="ts-btn" @click="jumpNext(-1)">↑</button>
        <button type="button" class="ts-btn ts-close" @click="closeSearch()">✕</button>
      </div>
      <el-table ref="tableRef" v-loading="loading" :data="pagedRows" :row-class-name="rowClass" :cell-class-name="searchCellClass"
        :cell-style="{ background: 'transparent', textAlign: 'center' }"
        :header-cell-style="{ background: '#0a1a30', color: '#6aa3c8', textAlign: 'center' }"
        class="warning-table" empty-text="暂无数据（请先在预排页导出到决议）" style="width:100%" :max-height="tableH">
        <el-table-column label="序号" width="56" align="center"><template #default="{ $index }"><span class="row-idx">{{ (currentPage - 1) * pageSize + $index + 1 }}</span></template></el-table-column>
        <el-table-column prop="plan_month_label" label="预排月份" width="90" align="center" />
        <el-table-column prop="source" label="来源" width="120" align="center">
          <template #default="{ row }">
            <span v-if="row.is_plan_external" class="src-ext">计划外{{ row.mtd_source ? '·' + row.mtd_source.toUpperCase() : '' }}</span>
            <span v-else :class="row.source === 'S13_DPS' ? 'src-a' : 'src-b'">{{ row.source === 'S13_DPS' ? 'S13' : 'S11' }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="model" label="Model" width="110" align="center" show-overflow-tooltip />
        <el-table-column prop="pn" label="P/N" width="130" align="center" show-overflow-tooltip />
        <!-- ★ Type：计划外行可点击回填，回填后自动匹配 ORT 规则重算状态 -->
        <el-table-column prop="type" label="Type" width="96" align="center">
          <template #default="{ row }">
            <div v-if="row.is_plan_external" class="type-edit">
              <el-select v-if="typeEditingId===row.id" :model-value="row.type||''" @update:model-value="saveType(row,$event)" @click.stop size="small" placeholder=" " class="cell-select" popper-class="app-select-popper">
                <el-option value="PD" label="PD"/><el-option value="TV" label="TV"/><el-option value="DT" label="DT"/><el-option value="BIM" label="BIM"/><el-option value="SET" label="SET"/>
              </el-select>
              <span v-else class="type-tag" :class="{empty:!row.type}" :title="row.type?'点击修改 Type（自动重算达标状态）':'请回填 Type，回填后自动匹配 ORT 规则'" @click="typeEditingId=row.id">{{ row.type || '✎ 回填' }}</span>
            </div>
            <span v-else>{{ row.type || '-' }}</span>
          </template>
        </el-table-column>
        <!-- ★ 状态：红灯=已达标(可处理)、绿灯=生产中(未达标)、黄灯=计划外待回填 -->
        <el-table-column label="状态" width="100" align="center">
          <template #default="{ row }">
            <span v-if="isPending(row)" class="st-pending" title="计划外：请回填 Type 后自动匹配 ORT 规则">待回填</span>
            <span v-else :class="row.judge === '预警' ? 'st-prod' : 'st-met'">{{ row.judge === '预警' ? '生产中' : '已达标' }}</span>
          </template>
        </el-table-column>
        <!-- ★ 任务1：QE 是否需送样（基于 QE需求 字段），并据此把"需送样且产能达标"项优先置顶 -->
        <el-table-column label="QE送样" width="92" align="center">
          <template #default="{ row }">
            <span v-if="qeSendSample(row)" class="qe-yes" title="QE 需送样">需送样</span>
            <span v-else-if="qeNoSample(row)" class="qe-no" title="QE 不需送样">不送样</span>
            <span v-else class="qe-wait" title="QE 送样待定 / 未填写">待定</span>
          </template>
        </el-table-column>
        <!-- ★ 需求6/09-04：送样状态 —— 箱号 + 送样日期均填写完整且 QE=Y 且达标 → 可送；
             已达可送样条件但箱号/送样日期缺失 → 冒红「待送样」提醒补录 -->
        <el-table-column label="送样状态" width="100" align="center">
          <template #default="{ row }">
            <span v-if="canSendSample(row)" class="ship-ok" title="QE=Y 且产能达标，Q工单 / 箱号 / 送样日期 均已齐备 → 可送（判定字段与审核决议中心同源，自动同步）">可送</span>
            <span v-else-if="shippingAlarm(row)" class="ship-warn" title="QE=Y 且产能达标，但 Q工单 / 箱号 / 送样日期 未齐备，请补录后自动变为「可送」">⚠ 待送样</span>
            <span v-else class="ship-na">-</span>
          </template>
        </el-table-column>
        <el-table-column prop="ort_ok" label="ORT" width="70" align="center">
          <template #default="{ row }"><span :class="['ort-tag', row.ort_ok === 'N' ? 'ort-n' : '']">{{ row.ort_ok || '-' }}</span></template>
        </el-table-column>
        <!-- ★ ORT 预警值：预排筛选里命中规则的阈值（如 300），用户确认只显示阈值 -->
        <el-table-column label="ORT预警值" width="100" align="center">
          <template #default="{ row }">
            <span v-if="row.ort_threshold === '' || row.ort_threshold == null" class="mtd-none">-</span>
            <span v-else class="ort-threshold">{{ row.ort_threshold }}</span>
          </template>
        </el-table-column>
        <el-table-column prop="mtd_output" label="MTD OUTPUT" width="110" align="center">
          <template #default="{ row }"><span :class="mtdClass(row)">{{ mtdVal(row) }}</span></template>
        </el-table-column>
        <!-- ★ DPS 按来源显示：S13 → N+2 DPS；S11 → N+1 DPS -->
        <el-table-column label="DPS(N+1/N+2)" width="110" align="center">
          <template #default="{ row }"><span class="dps-val">{{ row.source === 'S13_DPS' ? (row.n2_dps ?? '-') : (row.n1_dps ?? '-') }}</span></template>
        </el-table-column>
        <!-- ★ 原因(备注)：支持手动编辑（如记录未送货原因）；MTD 同步不覆盖该字段 -->
        <el-table-column label="原因(备注)" min-width="170" align="center">
          <template #default="{ row }">
            <span v-if="reasonEditingId===row.id" class="reason-edit">
              <input v-focus class="reason-input" :value="row.filter_reason || ''" @blur="saveReason(row,$event)" @keydown.enter="saveReason(row,$event)" @click.stop />
            </span>
            <span v-else class="reason-text" :class="{ 'has-note': row.filter_reason }" :title="row.filter_reason || '点击编辑备注（如未送货原因）'" @click="reasonEditingId=row.id">{{ row.filter_reason || '✎ 备注' }}</span>
          </template>
        </el-table-column>
        <!-- ★ 计划外行插入状态（一键插入由顶部按钮完成，此处仅展示状态；插入中橙色标注） -->
        <el-table-column label="插入决议" width="110" align="center">
          <template #default="{ row }">
            <span v-if="row.is_plan_external" class="ins-badge" :class="row.exported ? 'ins-on' : 'ins-off'">{{ row.exported ? '计划外已插入' : '计划外未插入' }}</span>
            <span v-else class="ins-auto">自动</span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 分页（性能优化：数据量大时分页渲染） -->
    <div class="pagination-bar">
      <span class="pagination-info">共 <b class="total">{{ stats.total }}</b> 条</span>
      <el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :page-sizes="[20, 50, 100]"
        :total="stats.total" layout="sizes,prev,pager,next" size="small" @size-change="currentPage = 1" @current-change="currentPage = $event" />
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onBeforeUnmount, onActivated, onDeactivated, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import * as echarts from 'echarts/core'
import { BarChart, PieChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { useTableSearch } from '../composables/useTableSearch'
import { useFitHeight } from '../composables/useFitHeight'

defineOptions({ name: 'WarningView' })
echarts.use([BarChart, PieChart, GridComponent, TooltipComponent, LegendComponent, CanvasRenderer])

const API = import.meta.env.VITE_API_BASE || '/api'
const loading = ref(false)
const syncing = ref(false)
const allRows = ref([])
const filterMonth = ref(null)
const onlyExternal = ref(false)   // ★ 仅显示计划外
const mtdTotal = ref(0)           // ★ SQL 查到数据总数（同步MTD后更新）
const currentPage = ref(1)
const pageSize = ref(50)
const barRef = ref(null)
const pieRef = ref(null)
let barChart = null
let pieChart = null
let chartRO = null

// ★ 计划外数量（SQL 中计划里不存在的数据）
const externalCount = computed(() => allRows.value.filter(r => r.is_plan_external).length)

// ★ 计划外「待回填」判定：计划外行 Type 未回填时不参与规则达标对比，
//   初始状态为待回填，回填 Type 后由后端自动匹配 ORT 规则重算
const typeEditingId = ref(null)
function isPending(row){ return row.is_plan_external && !(row.type || '').trim() }

// ★ 任务1/任务4 通用判定助手
function isYes(v){
  const s = String(v ?? '').trim().toLowerCase()
  return ['是', 'y', 'yes', 'true', '1'].includes(s)
}
// ★ QE 是否需送样（基于 QE需求 字段）
function qeSendSample(r){ return isYes(r.qe_requirement) }
function qeNoSample(r){
  const s = String(r.qe_requirement ?? '').trim().toLowerCase()
  return s === '否' || s === 'n'
}
// ★ ORT 达标 = 产量达标：后端 judge 仅在 ORT 不满足时置「预警」（计划外待回填单独判定）
function isMet(r){
  if (isPending(r)) return false
  return (r.judge || '') !== '预警'
}
// ★ 09-04：送样信息是否齐备 —— 「Q工单」+「箱号」+「送样日期」均填写完整（送样就绪三要素；
//   与审核决议中心 judge「已同意/预警」判定同源，任一侧补录后另一侧刷新即同步）
function sampleReady(r){
  const order = String(r.q_order || '').trim()
  const box = String(r.box_number || '').trim()
  const date = String(r.sample_date || '').trim()
  return !!(order && box && date)
}
// ★ 可送：QE 需送样(Y) 且 产量达标 且 Q工单/箱号/送样日期 齐备
function canSendSample(r){
  if (isPending(r)) return false
  if (!isYes(r.qe_requirement)) return false
  if (!isMet(r)) return false
  return sampleReady(r)
}
// ★ 待送样报警：QE=Y 且 产能达标（已具备可送条件），但 Q工单 / 箱号 / 送样日期 尚未齐备 → 冒红提醒补录
function shippingAlarm(r){
  if (isPending(r)) return false
  if (!isYes(r.qe_requirement)) return false
  if (!isMet(r)) return false
  return !sampleReady(r)
}
// ★ 预警页优先级评分（越大越靠前，同组保持原顺序=稳定排序）—— 09-04 规范，清晰可维护：
//   ① 计划外已插入预排(inserted_to_preplan) → 恒置顶（+10 层，与决议中心「计划外已插入」语义一致；
//      已插入但 Type 未回填的行同样置顶展示已插入状态）
//   ② 通用三层优先级（用户规范）：
//      最优先 4 = ORT达标 且 QE=Y
//      次优先 3 = 仅 QE=Y（未达标也需优先关注回复）
//      第三   2 = 仅 ORT达标（产量达标，无 QE 送样需求）
//      其余   1
//   ③ 计划外 Type 未回填(待回填) → 置底 -1（先处理有结论的数据）
function baseWarnScore(r){
  const met = isMet(r)
  const qeY = isYes(r.qe_requirement)
  if (met && qeY) return 4
  if (qeY) return 3
  if (met) return 2
  return 1
}
function warnPriorityScore(r){
  if (r.is_plan_external && r.inserted_to_preplan) return 10 + baseWarnScore(r)
  if (isPending(r)) return -1
  return baseWarnScore(r)
}

// ★ Type 回填保存：后端收到后自动补基础资料 + 匹配 ORT 规则重算 ort_ok/judge
async function saveType(row, v){
  typeEditingId.value = null
  const val = String(v ?? '').trim()
  if ((row.type || '') === val) return
  try {
    await axios.post(`${API}/preplan/update/${row.id}/`, { type: val })
    row.type = val
    ElMessage.success(val ? 'Type 已回填，已自动匹配 ORT 规则重算' : '已清空 Type，该行回到待回填')
    await loadData()
  } catch (e) { ElMessage.error('保存失败：' + (e.response?.data?.error || e.message)) }
}

// ★ 内联编辑输入框自动聚焦
const vFocus = { mounted: (el) => el && el.focus() }

// ★ 原因(备注)编辑：作为备注使用（如记录未送货原因），保存到 filter_reason；
//   MTD 同步只更新 mtd_output/mtd_source，不覆盖该字段
const reasonEditingId = ref(null)
async function saveReason(row, e){
  reasonEditingId.value = null
  const v = (e && typeof e === 'object' && e.target !== undefined ? e.target.value : e) ?? ''
  const val = String(v).trim()
  if ((row.filter_reason || '') === val) return
  try {
    await axios.post(`${API}/preplan/update/${row.id}/`, { filter_reason: val })
    row.filter_reason = val
    ElMessage.success('原因备注已保存')
  } catch (err) { ElMessage.error('保存失败：' + (err.response?.data?.error || err.message)) }
}

// ★ 任务4改造：一键全部插入到审核决议中心 —— 所有计划外行一次性 inserted_to_preplan=True + exported=True；
//   插入期间以橙色标注计划外行，完成后 reload 恢复原有颜色显示。
const insertingAll = ref(false)
async function handleInsertAll(){
  if (insertingAll.value) return
  if (!externalCount.value){ ElMessage.warning('当前没有计划外数据'); return }
  insertingAll.value = true
  try {
    const res = await axios.post(`${API}/preplan/insert-all-external/`, {})
    if (res.data.success){
      ElMessage.success(res.data.message)
      await loadData()   // ★ 完成后刷新，恢复原有颜色显示
    } else {
      ElMessage.error(res.data.error)
    }
  } catch (e) {
    ElMessage.error('插入失败：' + (e.response?.data?.error || e.message))
  } finally {
    insertingAll.value = false
  }
}

// ★ 2026-09-20：月份筛选/图表分组改用 plan_ym（YYYYMM 数值）——
//   原 plan_month_label 是 '9月' 这种不带年份的文本，跨年的两个 9 月会被当成同一个月。
const monthOptions = computed(() => {
  const s = new Set()
  allRows.value.forEach(r => { const v = r.plan_ym; if (v !== undefined && v !== null) s.add(Number(v) || 0) })
  // ★ 2026-09-21：el-option 的 value 不接受 null（Element Plus 类型校验会 warn），
  //   「全部月份」改用 ''；本页过滤守卫是 `if (filterMonth.value)` 真值判断，'' 同样为假 → 语义不变。
  const out = [{ ym: '', label: '全部月份' }]
  const months = [...s].filter(v => v > 0).sort((a, b) => b - a)
  months.forEach(v => out.push({ ym: v, label: `${Math.floor(v / 100)}年${v % 100}月` }))
  if (s.has(0)) out.push({ ym: 0, label: '未归类' })
  return out
})
// ym → 展示标签（图表 X 轴 / 表格兜底用）
function ymLabelOf(v){ const n = Number(v) || 0; return n ? `${Math.floor(n / 100)}年${n % 100}月` : '未归类' }

const filteredRows = computed(() => {
  let list = allRows.value
  // ★ 2026-09-21 修复：筛选键必须与 monthOptions 下发的 value 同源（plan_ym 数值）。
  //   两个缺陷：
  //   ① 原实现比对 `r.plan_month_label === filterMonth.value`——下拉 value 是 YYYYMM 数字，
  //      右侧是 '9月' 文本，恒不相等 → 选任何月份表格都空（用户报的正是这个）。
  //   ② 原守卫 `if (filterMonth.value)` 是真值判断，0（未归类）为假 → 选「未归类」反而显示全量。
  //   现改为与决策/存档页同口径：null / ''（clearable 清空）不筛选，其余一律按 plan_ym 精确比对，
  //   未归类（0）也能真正收窄。
  if (filterMonth.value !== null && filterMonth.value !== '') {
    list = list.filter(r => (Number(r.plan_ym) || 0) === Number(filterMonth.value))
  }
  if (onlyExternal.value) list = list.filter(r => r.is_plan_external)
  return list
})

// ★ 任务1：预警页优先级排序（与预排同套 Q工单判定；额外把"QE需送样且产能达标"置顶）
//   稳定排序：同评分组内保持 filteredRows 的原顺序
const sortedRows = computed(() => {
  const arr = filteredRows.value.slice()
  const order = new Map(arr.map((r, i) => [r, i]))
  return arr.sort((a, b) => {
    const sa = warnPriorityScore(a), sb = warnPriorityScore(b)
    if (sa !== sb) return sb - sa
    return order.get(a) - order.get(b)
  })
})

// ★ Ctrl+F 表格搜索（P1-2）：搜索范围 = 过滤排序后的全量行（跨页）
//   ★ 参与匹配的字段 = 本页实际展示的列（下方 SEARCH_KEYS），
//     不扫 id / 时间戳 / exported / is_plan_external 等隐藏字段，避免「没包含关键字也高亮」
const SEARCH_KEYS = [
  'plan_month_label', 'source', 'mtd_source', 'model', 'pn', 'type', 'judge',
  'qe_requirement', 'q_order', 'box_number', 'sample_date',
  'ort_ok', 'ort_threshold', 'mtd_output', 'n1_dps', 'n2_dps', 'filter_reason',
]
const tableRef = ref(null)
const tableWrapRef = ref(null)
const tableMaxH = useFitHeight(tableWrapRef)
// ★ 表格高度 = 容器剩余高度（搜索条展开时扣除其高度）→ 单一内部滚动条、表头稳定吸顶
const tableH = computed(() => Math.max(120, tableMaxH.value - (searchVisible.value ? 38 : 4)))
const { visible: searchVisible, keyword: searchKeyword, matches, activeIdx,
        doSearch, jumpNext, close: closeSearch, isHit, isActive, searchCellClass, onKeydown: onTableSearchKey } = useTableSearch({
  getRows: () => sortedRows.value,
  // ★ Ctrl+F 搜索范围 = 本页实际展示的字段（不扫 id/时间戳/布尔标志等隐藏字段，防误命中）
  searchKeys: SEARCH_KEYS,
  tableRef,
  currentPage,
  pageSize,
  pageCount: () => Math.max(1, Math.ceil(sortedRows.value.length / pageSize.value)),
})

// ★ MTD OUTPUT 展示：具体数值，未生产(0)换色标注，不得用横杠代替
function mtdVal(row){
  if (row.mtd_output === '' || row.mtd_output == null) return '无'
  return row.mtd_output
}
function mtdClass(row){
  if (row.is_plan_external) return 'mtd-ext'
  if (row.mtd_output === '' || row.mtd_output == null) return 'mtd-none'
  if (row.mtd_output === '0' || row.mtd_output === 0) return 'mtd-zero'
  return 'mtd-val'
}

// ★ 状态语义（用户要求）：红灯=已达标(可处理)，绿灯=生产中(未达标)
//   judge!='预警'(ORT 满足)=已达标；judge='预警'(ORT 不满足)=生产中
//   ★ 计划外未回填 Type 的行不参与达标/生产对比，单独计「待回填」
const stats = computed(() => {
  const list = sortedRows.value
  const pending = list.filter(isPending).length
  const judged = list.filter(r => !isPending(r))
  return {
    total: list.length,
    met: judged.filter(r => r.judge !== '预警').length,
    producing: judged.filter(r => r.judge === '预警').length,
    pending,
    shipAlarm: list.filter(shippingAlarm).length,   // ★ 需求6：送样报警数
  }
})

// ★ 需求6：送样报警数量（独立 computed，供顶部报警条使用）
const shipAlarmCount = computed(() => stats.value.shipAlarm)

const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return sortedRows.value.slice(start, start + pageSize.value)
})

function rowClass({ row }){
  const base = isPending(row) ? 'row-pending' : (row.judge === '预警' ? 'row-producing' : 'row-met')
  // ★ 需求6：送样报警行整体冒红高亮
  const alarm = shippingAlarm(row) ? ' row-ship-alarm' : ''
  // ★ 一键插入进行中：计划外行临时橙色标注，完成后 loadData 恢复原有颜色
  const baseRow = insertingAll.value && row.is_plan_external ? base + ' row-inserting' + alarm : base + alarm
  // ★ Ctrl+F 搜索命中行高亮（P1-2）
  return isHit(row) ? baseRow + ' search-hit' + (isActive(row) ? ' search-active' : '') : baseRow
}

// ★ 手掌拖动横向滚动（按住拖动；监听挂全局，鼠标移出表格区不中断）
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
    // 拖动激活：禁止文本选中，避免拖出"选中数据"
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

// ★ 加载请求序号 + 超时兜底：防止重复点击/keep-alive 激活导致 loading 一直转圈或旧响应覆盖新数据
let loadSeq = 0
let chartRetry = 0
async function loadData(){
  if (loading.value) return
  loading.value = true
  chartRetry = 0
  const seq = ++loadSeq
  try {
    // ★ 先按当前 ORT 规则重算(严格同预排一套规则)，再加载
    try { await axios.post(`${API}/preplan/recompute-judge/`, {}, { timeout: 60000 }) } catch (e) { /* 重算失败不阻塞展示 */ }
    if (seq !== loadSeq) return
    // ★ 数据源：存档中心已定版数据 + 计划外
    const res = await axios.get(`${API}/preplan/rows/`, { params: { warning: 'true' }, timeout: 30000 })
    if (seq !== loadSeq) return
    // ★ 恢复「MTD 查到总数」（后端持久化最近一次同步结果，刷新/重进页面不再变 0）
    if (res.data && typeof res.data.mtd_total === 'number') mtdTotal.value = res.data.mtd_total
    allRows.value = res.data?.data || []
    currentPage.value = 1
    await nextTick()
    renderCharts()
  } catch (e) {
    if (seq !== loadSeq) return
    if (e?.code === 'ECONNABORTED') ElMessage.error('加载超时，请点击「刷新」重试')
    else ElMessage.error('加载决议数据失败：' + (e?.response?.data?.error || e?.message || ''))
  } finally { if (seq === loadSeq) loading.value = false }
}

// ★ 同步MTD：从公司 PostgreSQL 抓取 MTD OUTPUT（SQL 在 backend/mtd_monitor_config.py 配置）
async function handleSyncMtd(){
  syncing.value = true
  try {
    const res = await axios.post(`${API}/preplan/sync-mtd/`, {})
    if (res.data.success){
      mtdTotal.value = res.data.total_keys || 0
      ElMessage.success(res.data.message || 'MTD 同步完成')
      await loadData()
    }
    else ElMessage.error(res.data.error || 'MTD 同步失败')
  } catch (e) { ElMessage.error('MTD 同步失败：' + (e.response?.data?.error || e.message)) }
  finally { syncing.value = false }
}

// ★ 数据签名：用于刷新时检测数据是否有变动（决议中心补充/改动计划外数据后同步显示）
function dataSignature(rows){
  return JSON.stringify((rows || []).map(r => [r.id, r.mtd_output, r.judge, r.ort_ok, r.type, r.filter_reason, r.is_plan_external, r.exported, r.inserted_to_preplan]))
}

// ★ 刷新 = 仅本地重载（不执行 PostgreSQL MTD SQL，不删除/重建计划外行，已做修改全部保留）。
//   与「同步MTD」按钮的区别：刷新只拉取本地最新数据并就地更新，绝不触发 MTD SQL，
//   因此不会把用户已添加/已插入/已备注的计划外条目冲掉。
async function handleRefresh(){
  syncing.value = true
  const prevSig = dataSignature(allRows.value)
  try {
    await loadData()
  } finally { syncing.value = false }
  const changed = prevSig !== dataSignature(allRows.value)
  ElMessage[changed ? 'success' : 'info'](changed ? '已刷新（仅本地更新，未执行 SQL）' : '数据无变动')
}

function renderCharts(){
  // ★ P1-3：容器未就绪 / 宽度为 0（布局未稳、路由切换中、loading 遮罩未退）→ 延迟重试。
  //   加尝试上限避免死循环（30 次约 3.6s 后停止，靠后续 resize 兜底矫正）。
  if (!barRef.value || !pieRef.value){
    if (chartRetry < 30){ chartRetry++; setTimeout(renderCharts, 120) }
    return
  }
  if (barRef.value.clientWidth < 10 || pieRef.value.clientWidth < 10){
    if (chartRetry < 30){ chartRetry++; setTimeout(renderCharts, 120) }
    return
  }
  // 柱状图：各预排月份 总行数 vs 已达标数（计划外待回填不计入已达标）
  // ★ 2026-09-20：按 plan_ym 分组（原 plan_month_label 跨年同名月份会并成一根柱子）
  const monthMap = {}
  allRows.value.forEach(r => {
    const key = Number(r.plan_ym) || 0
    const m = ymLabelOf(key)
    monthMap[key] = monthMap[key] || { label: m, total: 0, met: 0 }
    monthMap[key].total++
    if (r.judge !== '预警' && !isPending(r)) monthMap[key].met++
  })
  const keys = Object.keys(monthMap).sort((a, b) => Number(a) - Number(b))
  const months = keys.map(k => monthMap[k].label)
  const line = '#1a3a5f', text = '#a0c8e8'
  if (!barChart) barChart = echarts.init(barRef.value)
  barChart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis' },
    legend: { data: ['总行数', '已达标'], textStyle: { color: text }, top: 0 },
    grid: { left: 40, right: 16, top: 32, bottom: 24 },
    xAxis: { type: 'category', data: months, axisLine: { lineStyle: { color: line } }, axisLabel: { color: text } },
    yAxis: { type: 'value', axisLine: { lineStyle: { color: line } }, axisLabel: { color: text }, splitLine: { lineStyle: { color: 'rgba(26,58,95,.4)' } } },
    series: [
      { name: '总行数', type: 'bar', data: keys.map(k => monthMap[k].total), itemStyle: { color: '#2a6fa8', borderRadius: [3, 3, 0, 0] }, barWidth: 18 },
      { name: '已达标', type: 'bar', data: keys.map(k => monthMap[k].met), itemStyle: { color: '#e04040', borderRadius: [3, 3, 0, 0] }, barWidth: 18 },
    ],
  })
  // 饼图：来源分布
  let s13 = 0, s11 = 0
  filteredRows.value.forEach(r => { r.source === 'S13_DPS' ? s13++ : s11++ })
  if (!pieChart) pieChart = echarts.init(pieRef.value)
  pieChart.setOption({
    backgroundColor: 'transparent',
    tooltip: { trigger: 'item' },
    legend: { bottom: 0, textStyle: { color: text } },
    series: [{
      type: 'pie', radius: ['30%', '48%'], center: ['50%', '42%'],
      label: { color: text, formatter: '{b}: {c} ({d}%)' },
      data: [
        { name: 'S13', value: s13, itemStyle: { color: '#2a6fa8' } },
        { name: 'S11', value: s11, itemStyle: { color: '#00b4a0' } },
      ],
    }],
  })
  // ★ P1-3：init 后立即强制 resize + 多级延迟 resize（loading 遮罩/布局稳定后再矫正一次），
  //   保证进页面即显示，无需 F12 触发
  fitCharts()
  setTimeout(fitCharts, 150)
  setTimeout(fitCharts, 500)
  setTimeout(fitCharts, 1200)
  // ★ 容器尺寸变化（侧栏折叠/缩放/布局变化）自动重算
  if (typeof ResizeObserver !== 'undefined' && !chartRO){
    chartRO = new ResizeObserver(() => { if (barChart) barChart.resize(); if (pieChart) pieChart.resize() })
    try { chartRO.observe(barRef.value); chartRO.observe(pieRef.value) } catch (e) {}
  }
}

function fitCharts(){
  try { if (barChart) barChart.resize() } catch (e) {}
  try { if (pieChart) pieChart.resize() } catch (e) {}
}

// ★ 图表 resize：统一 handler（避免匿名函数导致 removeEventListener 失效）
function onWindowResize(){
  if (!barChart || !pieChart){
    renderCharts()   // ★ 兜底：首次未 init 成功 → 重建
    return
  }
  fitCharts()
}

onMounted(() => {
  // ★ 数据加载统一放 onActivated（keep-alive 首次激活紧随 mounted 触发），避免重复请求
  window.addEventListener('resize', onWindowResize)
})
// ★ keep-alive：激活时注册 Ctrl+F 监听、重载数据与图表尺寸矫正（F12 不再必需）；
//   停用时移除监听
onActivated(()=>{
  window.addEventListener('keydown', onTableSearchKey)
  loadData()
  nextTick(() => requestAnimationFrame(fitCharts))
})
onDeactivated(()=>window.removeEventListener('keydown', onTableSearchKey))
onBeforeUnmount(() => {
  window.removeEventListener('resize', onWindowResize)
  window.removeEventListener('keydown', onTableSearchKey)
  if (chartRO){ try { chartRO.disconnect() } catch (e) {} chartRO = null }
  barChart?.dispose()
  pieChart?.dispose()
})
</script>

<style lang="scss" scoped>
.warning-view{ height:100%; display:flex; flex-direction:column; gap:8px; padding:4px 6px; min-height:0; background:transparent; }
.pbar{ display:flex; align-items:center; justify-content:space-between; flex-shrink:0; }
.pbar-left{ display:flex; align-items:center; gap:8px; }
.ptag{ background:rgba(200,60,60,.22); border:1px solid #7a2028; color:#ff9a9a; font-size:10px; font-weight:700; letter-spacing:1px; padding:3px 10px; border-radius:4px; }
.ptitle{ font-size:15px; font-weight:500; color:#c8e0f8; span{ color:#ff8a8a; } }
.run-btn{ font-size:11px; font-weight:600; padding:4px 10px; border-radius:12px; cursor:pointer; border:none; font-family:inherit; &.primary{ background:linear-gradient(135deg,#0055aa,#0077cc); color:#fff; box-shadow:0 2px 8px rgba(0,100,200,.35); &:hover{ background:linear-gradient(135deg,#0066bb,#0088dd); } &:disabled{ background:rgba(0,50,90,.45); color:#6a8fae; box-shadow:none; cursor:not-allowed; } } &.sec{ background:rgba(0,40,80,.3); color:#5a90b8; border:1px solid #0d3050; &:hover{ background:rgba(0,60,120,.4); color:#90c0e8; } &.on{ background:rgba(255,213,79,.25); color:#ffd54f; border-color:#8a5a20; } } }

.help-bar{ display:flex; align-items:center; gap:8px; padding:6px 12px; font-size:11px; color:#a0c8e8; background:rgba(0,60,120,.12); border:1px dashed #0d4a70; border-radius:6px; flex-shrink:0; }

.stat-grid{ display:grid; grid-template-columns:repeat(6,1fr); gap:6px; flex-shrink:0; }
.stat-card{ display:flex; align-items:center; gap:6px; padding:5px 10px; background:rgba(5,15,30,.5); border:1px solid #0d2a48; border-radius:6px; &.met{ border-color:rgba(224,64,64,.5) } &.producing{ border-color:rgba(0,212,170,.5) } &.pending{ border-color:rgba(232,184,56,.5) } &.ext{ border-color:rgba(255,213,79,.5) } }
.stat-label{ font-size:9px; color:#5d8aaa; }
.stat-value{ font-size:16px; font-weight:700; color:#c8e0f8; line-height:1; }
.stat-sub{ font-size:8px; color:#5d6a7a; }
.stat-card.met .stat-value{ color:#ff6b6b } .stat-card.producing .stat-value{ color:#00d4aa } .stat-card.pending .stat-value{ color:#e8b838 } .stat-card.ext .stat-value{ color:#ffd54f }

.chart-grid{ display:grid; grid-template-columns:1fr 1fr; gap:8px; flex-shrink:0; }
.chart-box{ background:rgba(5,15,30,.5); border:1px solid #0d2a48; border-radius:8px; padding:6px 10px; }
.chart-title{ font-size:11px; color:#6aa3c8; margin-bottom:2px; }
.chart-canvas{ width:100%; height:150px; }

.table-wrapper{ flex:1; min-height:0; overflow:hidden; display:flex; flex-direction:column; background:rgba(5,15,30,.5); border:1px solid #0d2a48; border-radius:8px; cursor:grab; }
.table-wrapper.dragging{ cursor:grabbing; user-select:none; -webkit-user-select:none; }
.warning-view :deep(.el-table){ --el-table-bg-color:transparent; --el-table-tr-bg-color:rgba(5,15,30,.5); --el-table-header-bg-color:rgba(0,40,80,.35); --el-table-border-color:#0d2a48; --el-table-row-hover-bg-color:rgba(0,60,120,.25); --el-table-text-color:#c8ddf5; --el-table-header-text-color:#a0c8e8; color:#c8ddf5; }
.warning-view :deep(.el-loading-mask){ background:rgba(3,9,15,.72)!important; }
/* ★ 状态行颜色：已达标=红灯、生产中=绿灯、待回填=黄灯 */
.warning-view :deep(.row-met td){ background:rgba(255,107,107,.07)!important; }
.warning-view :deep(.row-producing td){ background:rgba(0,212,170,.06)!important; }
.warning-view :deep(.row-pending td){ background:rgba(232,184,56,.08)!important; }
.row-idx{ color:#4d7d9e; font-size:11px; }
.src-a{ color:#4d9fd8; font-weight:600; } .src-b{ color:#00b4a0; font-weight:600; }
.src-ext{ color:#ffd54f; font-weight:700; }
.st-met{ color:#ff6b6b; font-weight:700; }
.st-prod{ color:#00d4aa; font-weight:700; }
.st-pending{ color:#e8b838; font-weight:700; }
/* ★ 需求6：送样报警（已达可送样条件但未送样 → 冒红） */
.ship-alert-bar{ display:flex; align-items:center; gap:6px; padding:7px 12px; font-size:12px; font-weight:600; color:#ff9a9a; background:linear-gradient(90deg,rgba(224,64,64,.18),rgba(224,64,64,.05)); border:1px solid rgba(224,64,64,.55); border-radius:6px; flex-shrink:0; animation:shipBlink 1.6s ease-in-out infinite; }
.ship-alert-bar b{ color:#ff5555; font-size:14px; }
@keyframes shipBlink{ 0%,100%{ box-shadow:0 0 0 0 rgba(224,64,64,0); } 50%{ box-shadow:0 0 14px 1px rgba(224,64,64,.45); } }
.ship-warn{ color:#ff6b6b; font-weight:700; text-shadow:0 0 6px rgba(255,90,90,.6); }
.ship-ok{ color:#00d4aa; font-weight:600; }
.ship-na{ color:#5d6a7a; }
.warning-view :deep(.row-ship-alarm td){ background:rgba(224,64,64,.16)!important; box-shadow:inset 0 0 0 1px rgba(224,64,64,.4)!important; }
.type-edit{ cursor:pointer; }
.cell-select{ width:100%; }
.cell-select :deep(.el-select__wrapper){ width:100%!important; padding:1px 6px!important; }
.cell-select :deep(.el-select__selected-item){ font-size:12px; color:#c8ddf5!important; }
.type-tag{ display:inline-block; min-width:40px; padding:1px 8px; border-radius:4px; font-size:12px; font-weight:600; color:#ffd54f; background:rgba(232,184,56,.12); border:1px solid rgba(232,184,56,.35); &:hover{ background:rgba(232,184,56,.22); border-color:#e8b838 } &.empty{ color:#e8b838; border-style:dashed; } }
/* ★ 原因(备注)列：点击编辑，空显示「✎ 备注」虚线，有内容实线高亮 */
.reason-text{ display:inline-block; max-width:100%; padding:1px 8px; border-radius:4px; font-size:12px; color:#8aa4bd; border:1px dashed rgba(90,120,150,.45); cursor:pointer; &:hover{ background:rgba(0,110,220,.2); border-color:#0077cc; } &.has-note{ color:#c8ddf5; border-style:solid; border-color:rgba(0,180,230,.4); background:rgba(0,160,220,.06); } }
.reason-edit{ display:inline-block; width:100%; }
.reason-input{ width:100%; box-sizing:border-box; font-size:12px; padding:2px 6px; color:#c8ddf5; background:rgba(0,30,60,.9); border:1px solid #0077cc; border-radius:4px; outline:none; }
.ort-tag{ &.ort-n{ color:#ff6b6b; font-weight:700; } }
.ort-threshold{ color:#ffd54f; font-weight:700; }
.mtd-val{ color:#00d4aa; font-weight:600; }
.mtd-zero{ color:#5d8aaa; font-weight:600; }
.mtd-none{ color:#5d6a7a; font-weight:500; }
.mtd-ext{ color:#ffd54f; font-weight:700; }
.qe-yes{ color:#ff9a9a; font-weight:700; }
.qe-no{ color:#5d8aaa; font-weight:600; }
.qe-wait{ color:#e8b838; font-weight:600; }
.ins-auto{ color:#5d8aaa; font-weight:600; }
.ins-badge{ display:inline-block; padding:1px 8px; border-radius:10px; font-size:11px; font-weight:600; }
.ins-badge.ins-on{ color:#00d4aa; background:rgba(0,212,170,.12); border:1px solid rgba(0,212,170,.45); }
.ins-badge.ins-off{ color:#8aa4bd; background:rgba(60,80,100,.15); border:1px solid rgba(90,120,150,.4); }
/* ★ 一键插入进行中：计划外行橙色标注（完成后 loadData 恢复原有颜色） */
.warning-view :deep(.row-inserting td){ background:rgba(255,170,0,.20)!important; }
.pagination-bar{ display:flex; justify-content:flex-end; align-items:center; gap:8px; padding:4px 2px; flex-shrink:0; }
.pagination-info{ font-size:11px; color:#6aa3c8; }
.pagination-info .total{ color:#c8e0f8; }
.warning-view :deep(.el-pagination .el-pager li){ background:rgba(0,40,80,.35)!important; color:#a8cce8!important; border-radius:4px; margin:0 2px; font-weight:600; }
.warning-view :deep(.el-pagination .el-pager li.is-active){ background:rgba(0,110,220,.6)!important; color:#fff!important; }
.warning-view :deep(.el-pagination .btn-prev),.warning-view :deep(.el-pagination .btn-next){ background:rgba(0,40,80,.35)!important; color:#a8cce8!important; }
.warning-view :deep(.el-pagination .btn-prev:disabled),.warning-view :deep(.el-pagination .btn-next:disabled){ background:rgba(0,25,50,.45)!important; color:#3f6a8f!important; }
.warning-view :deep(.el-select__wrapper){ background:rgba(0,30,60,.5)!important; box-shadow:0 0 0 1px #0d3050 inset!important; }

/* ══════════════════════════════════════════════════════════════════════
   ★ 白天主题覆盖（2026-09-18）
   根因：本页原样式整套写死深色（主文字 #c8e0f8/#c8ddf5、面板底 rgba(5,15,30,.5)、
   边框 #0d2a48/#0d3050、表头底 #0a1a30 / rgba(0,40,80,.35)、计划外与阈值 #ffd54f、
   红灯 #ff6b6b 等），且无 [data-theme="light"] 覆盖 → 切白天后浅字压浅底读不清。
   此处统一改为「浅底 + 深字」，语义色（红=警 / 绿=好 / 黄=注意）加深以保证白底可读。
   scoped：用 .warning-view 承接 data-v；Element Plus 内部用 :deep。
   注意：模板上 :header-cell-style 为行内样式，必须 !important 才能覆盖。
   ══════════════════════════════════════════════════════════════════════ */
[data-theme="light"] .warning-view {
  color: #1a4070;

  .ptag { background: #fdecec; border-color: #f0b8b8; color: #c0392b; }
  .ptitle { color: #0a2858; span { color: #d02828; } }
  .run-btn {
    &.sec { background: var(--well); color: #4a6a8a; border-color: #c0d2e4;
      &:hover { background: #cddcec; color: #24507a; }
      &.on { background: #fdf3e2; color: #b8860b; border-color: #e6d0a0; } }
    &.primary:disabled { background: #e6edf4; color: #9ab0c4; }
  }

  .help-bar { color: #2a5a86; background: var(--surface-2); border-color: #bcd4ec; }

  .stat-card { background: var(--surface-1); border-color: var(--line-1);
    &.met { border-color: rgba(208,40,40,.42); } &.producing { border-color: rgba(10,143,110,.42); }
    &.pending { border-color: rgba(176,120,0,.42); } &.ext { border-color: rgba(184,134,11,.42); } }
  .stat-label { color: #5a7a9a; }
  .stat-value { color: #0a2858; }
  .stat-sub { color: #93a9bd; }
  .stat-card.met .stat-value { color: #d02828; }
  .stat-card.producing .stat-value { color: #0a8f6e; }
  .stat-card.pending .stat-value { color: #b07800; }
  .stat-card.ext .stat-value { color: #b8860b; }

  .chart-box { background: var(--surface-1); border-color: var(--line-1); }
  .chart-title { color: #3a6a94; }

  .table-wrapper { background: var(--surface-1); border-color: var(--line-1); }
  .row-idx { color: #7a93ab; }
  .src-a { color: #0a6fd0; } .src-b { color: #1f8f3f; } .src-ext { color: #b8860b; }
  .st-met { color: #d02828; } .st-prod { color: #0a8f6e; } .st-pending { color: #b07800; }

  .ship-alert-bar { color: #c0392b; background: #fdecec; border-color: #f0b8b8; }
  .ship-alert-bar b { color: #c0392b; }
  .ship-warn { color: #d02828; text-shadow: none; }
  .ship-ok { color: #0a8f6e; }
  .ship-na { color: #93a9bd; }

  .cell-select :deep(.el-select__selected-item) { color: #0a2858 !important; }
  .type-tag { color: #b8860b; background: #fdf3e2; border-color: #e6d0a0;
    &:hover { background: #f7e9cf; border-color: #d9b45a; }
    &.empty { color: #b8860b; } }
  .reason-text { color: #5a7a9a; border-color: #b8c9db;
    &:hover { background: #dbe7f6; border-color: #7fb2e0; }
    &.has-note { color: #0a2858; border-color: rgba(60,150,220,.45); background: rgba(60,150,220,.06); } }
  .reason-input { color: #0a2858; background: var(--field); border-color: #1f8fd8; }

  .ort-tag.ort-n { color: #d02828; }
  .ort-threshold { color: #b8860b; }
  .mtd-val { color: #0a8f6e; } .mtd-zero { color: #5a7a9a; }
  .mtd-none { color: #93a9bd; } .mtd-ext { color: #b8860b; }
  .qe-yes { color: #c0392b; } .qe-no { color: #5a7a9a; } .qe-wait { color: #b07800; }
  .ins-auto { color: #5a7a9a; }
  .ins-badge.ins-on { color: #0a8f6e; background: rgba(10,143,110,.10); border-color: rgba(10,143,110,.35); }
  .ins-badge.ins-off { color: #5a7a9a; background: var(--surface-2); border-color: #c0d2e4; }

  .pagination-info { color: #5a7a9a; }
  .pagination-info .total { color: #0a2858; }

  /* Element Plus：表头 / 行 / 分页 / 下拉 / loading */
  :deep(.el-table) { --el-table-bg-color: transparent; --el-table-tr-bg-color: #ffffff;
    --el-table-header-bg-color: #eef4fa; --el-table-border-color: var(--line-2);
    --el-table-row-hover-bg-color: #eaf3fc; --el-table-text-color: #0a2858;
    --el-table-header-text-color: #3a6a94; color: #0a2858; }
  :deep(.el-table__header-wrapper th) { background: var(--surface-2) !important; color: #3a6a94 !important; }
  :deep(.el-table__body tr:hover > td) { background: #dce8f6 !important; }
  :deep(.el-loading-mask) { background: rgba(233,240,248,.82) !important; }
  :deep(.row-met td) { background: #fdecec !important; }
  :deep(.row-producing td) { background: #eaf7f2 !important; }
  :deep(.row-pending td) { background: #fdf6e3 !important; }
  :deep(.row-ship-alarm td) { background: #fdecec !important; box-shadow: inset 0 0 0 1px #f0b8b8 !important; }
  :deep(.row-inserting td) { background: #fdf3e2 !important; }
  :deep(.el-select__wrapper) { background: var(--field) !important; box-shadow: 0 0 0 1px #c9daea inset !important; }
  :deep(.el-pagination__total), :deep(.el-pagination__jump) { color: #5a7a9a !important; }
  :deep(.el-pagination .el-pager li) { background: var(--surface-2) !important; color: #2a5a86 !important; }
  :deep(.el-pagination .el-pager li:hover) { background: #cddcec !important; color: #0a2858 !important; }
  :deep(.el-pagination .el-pager li.is-active) { background: #2a7fd0 !important; color: #ffffff !important; }
  :deep(.el-pagination .btn-prev), :deep(.el-pagination .btn-next) { background: var(--surface-2) !important; color: #2a5a86 !important; }
  :deep(.el-pagination .btn-prev:hover:not(:disabled)), :deep(.el-pagination .btn-next:hover:not(:disabled)) { background: #cddcec !important; color: #0a2858 !important; }
  :deep(.el-pagination .btn-prev:disabled), :deep(.el-pagination .btn-next:disabled) { background: #f2f5f8 !important; color: #a8bccd !important; }
}
</style>
