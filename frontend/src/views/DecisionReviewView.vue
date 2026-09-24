<template>
  <div class="decision-review-view">
    <!-- 页面标题栏 -->
    <div class="pbar">
      <div class="pbar-left">
        <div class="ptag">DECISION</div>
        <div class="ptitle">审核决议中心 · <span>预排筛选表格</span></div>
      </div>
      <div class="pright">
        <button type="button" class="run-btn primary" :disabled="!stats.total || saving" @click="handleArchive">{{ saving ? '保存中...' : '保存到存档中心' }}</button>
        <button type="button" class="run-btn sec" :disabled="!stats.total" @click="handleExport">导出</button>
        <button type="button" class="naming-gear" title="自定义导出文件名" @click="openNaming('decision')"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M19.14 12.94a7.5 7.5 0 0 0 .05-1.88l2.03-1.58a.5.5 0 0 0 .12-.64l-1.92-3.32a.5.5 0 0 0-.6-.22l-2.39.96a7.03 7.03 0 0 0-1.62-.94l-.36-2.54a.5.5 0 0 0-.5-.42h-3.84a.5.5 0 0 0-.5.42l-.36 2.54c-.59.24-1.13.55-1.62.94l-2.39-.96a.5.5 0 0 0-.6.22L2.74 8.84a.5.5 0 0 0 .12.64l2.03 1.58a7.5 7.5 0 0 0 0 1.88l-2.03 1.58a.5.5 0 0 0-.12.64l1.92 3.32c.13.22.4.31.6.22l2.39-.96c.49.39 1.03.7 1.62.94l.36 2.54c.04.24.25.42.5.42h3.84c.25 0 .46-.18.5-.42l.36-2.54c.59-.24 1.13-.55 1.62-.94l2.39.96c.2.09.47 0 .6-.22l1.92-3.32a.5.5 0 0 0-.12-.64l-2.03-1.58zM12 15.5A3.5 3.5 0 1 1 12 8.5a3.5 3.5 0 0 1 0 7z"/></svg></button>
        <ExportNamingDialog v-model="namingOpen" :type="namingType" :ctx="exportNamingCtx" />
        <button type="button" class="run-btn sec" :disabled="!stats.total || backfilling" @click="handleBackfill" title="以基础资料表(52阶料号/满箱量/客户)按 P/N 比对回填本页数据，两侧互相参照校正">{{ backfilling ? '回填中...' : '基础资料比对回填' }}</button>
        <button type="button" class="run-btn danger" @click="handleClear">清空</button>
        <el-popover placement="bottom-end" width="340" trigger="manual" :visible="filterVisible" popper-class="app-popover">
          <template #reference>
            <button type="button" class="run-btn sec filter-ref" :class="{on:hasColFilter}" @click="filterVisible=!filterVisible">筛选<span v-if="hasColFilter" class="filter-dot">●</span></button>
          </template>
          <div class="filter-panel">
            <div class="fp-row"><label>Type</label>
              <el-select v-model="colFilters.types" multiple size="small" popper-class="app-select-popper" placeholder="全部" class="fp-sel">
                <el-option v-for="t in TYPE_OPTIONS" :key="t" :label="t" :value="t" />
              </el-select>
            </div>
            <div class="fp-row"><label>FAB</label><input v-model="colFilters.fab" class="fp-input" placeholder="包含匹配" /></div>
            <div class="fp-row"><label>客户</label><input v-model="colFilters.customer" class="fp-input" placeholder="包含匹配" /></div>
            <div class="fp-row"><label>关键字</label><input v-model="colFilters.keyword" class="fp-input" placeholder="P/N 或 Model 包含" /></div>
            <div class="fp-btns">
              <button type="button" class="run-btn sec" @click="clearColFilter">重置</button>
              <button type="button" class="run-btn primary" @click="applyColFilter">应用</button>
            </div>
          </div>
        </el-popover>
        <button type="button" class="run-btn sec" :class="{on:mtdSyncing}" :disabled="mtdSyncing" @click="handleSyncMtdDecision" title="从 PostgreSQL 拉取 MTD 产量并回填到本中心表格（与筛选预排页面逻辑一致）">{{ mtdSyncing ? '同步中...' : '同步MTD' }}</button>
        <button type="button" class="run-btn sec" @click="loadData">刷新</button>
      </div>
    </div>

    <!-- 顶部说明 -->
    <div class="help-bar">
      <div class="help-item">
        <span class="help-icon">📋</span>
        <span class="help-text">本页面展示「预排筛选」表格的完整数据（字段/表头与原页面一致），QE 与 GPC 在此进行「Y / N」决议（仅严格标识，不预设其他选项），决议结果保存到预排行。</span>
      </div>
    </div>

    <!-- 顶部 4 个统计卡片 -->
    <div class="stat-grid">
      <div class="stat-card">
        <div class="stat-icon">📊</div>
        <div class="stat-info">
          <div class="stat-label">总决议项</div>
          <div class="stat-value">{{ stats.total }}</div>
        </div>
      </div>
      <div class="stat-card pass">
        <div class="stat-icon">🎯</div>
        <div class="stat-info">
          <div class="stat-label">筛选通过</div>
          <div class="stat-value">{{ stats.passed }}</div>
          <div class="stat-sub">预排筛选通过项数</div>
        </div>
      </div>
      <div class="stat-card pending">
        <div class="stat-icon">⏳</div>
        <div class="stat-info">
          <div class="stat-label">待定</div>
          <div class="stat-value">{{ stats.pending }}</div>
          <div class="stat-sub">需立即处理</div>
        </div>
      </div>
      <div class="stat-card approved">
        <div class="stat-icon">✅</div>
        <div class="stat-info">
          <div class="stat-label">通过</div>
          <div class="stat-value">{{ stats.approved }}</div>
        </div>
      </div>
      <div class="stat-card rejected">
        <div class="stat-icon">❌</div>
        <div class="stat-info">
          <div class="stat-label">拒绝</div>
          <div class="stat-value">{{ stats.rejected }}</div>
        </div>
      </div>
    </div>

    <!-- 筛选/工具栏（右拉布局：状态按钮不压缩、月份下拉完整显示） -->
    <div class="filter-bar">
      <div class="filter-group month-group">
        <span class="filter-label">📅 决议月份：</span>
        <el-select v-model="filterMonth" placeholder="全部月份" clearable size="default" class="month-select" popper-class="app-select-popper">
          <el-option v-for="opt in monthOptions" :key="String(opt.ym)" :label="opt.label" :value="opt.ym" />
        </el-select>
      </div>

      <div class="filter-group tabs-group">
        <span class="filter-label">🔍 决议状态：</span>
        <div class="decision-tabs">
          <div class="dt-tab" :class="{ active: filterDecision === 'all' }" @click="filterDecision = 'all'">全部 <span class="dt-count">{{ stats.total }}</span></div>
          <div class="dt-tab pending" :class="{ active: filterDecision === '待定' }" @click="filterDecision = '待定'">待定 <span class="dt-count">{{ stats.pending }}</span></div>
          <div class="dt-tab approved" :class="{ active: filterDecision === 'Y' }" @click="filterDecision = 'Y'">通过 <span class="dt-count">{{ stats.approved }}</span></div>
          <div class="dt-tab rejected" :class="{ active: filterDecision === 'N' }" @click="filterDecision = 'N'">拒绝 <span class="dt-count">{{ stats.rejected }}</span></div>
          <div class="dt-tab none" :class="{ active: filterDecision === 'none' }" @click="filterDecision = 'none'">未决议 <span class="dt-count">{{ stats.undecided }}</span></div>
        </div>
      </div>

      <div class="filter-group total-group">
        <span class="filter-label">共 <b class="total-num">{{ stats.total }}</b> 行</span>
      </div>
    </div>

    <!-- 决议列表：预排筛选表格原样导出 -->
    <div ref="tableWrapRef" class="table-wrapper" @mousedown="onDragStart">
      <!-- ★ Ctrl+F 搜索条（P1-2） -->
      <div v-if="searchVisible" class="table-search-bar">
        <input v-model="searchKeyword" @input="doSearch()" @keydown.enter="jumpNext(1)" @keydown.shift.enter="jumpNext(-1)" placeholder="输入关键字搜索（Enter 下一个 / Shift+Enter 上一个 / Esc 关闭）" class="ts-input" />
        <span class="ts-count">{{ matches.length ? (activeIdx + 1) + '/' + matches.length : '0 个匹配' }}</span>
        <button type="button" class="ts-btn" @click="jumpNext(1)">↓</button>
        <button type="button" class="ts-btn" @click="jumpNext(-1)">↑</button>
        <button type="button" class="ts-btn ts-close" @click="closeSearch()">✕</button>
      </div>
      <el-table ref="tableRef" v-loading="loading" :data="pagedRows" :row-class-name="decisionRowClass" :cell-class-name="searchCellClass"
        :cell-style="{ background: 'transparent', textAlign: 'center' }"
        :header-cell-style="{ background: '#0a1a30', color: '#6aa3c8', textAlign: 'center' }"
        class="decision-table" empty-text="暂无决议项" style="width: 100%;" :max-height="tableH">
        <!-- ★ 序号取自「条目在过滤结果中的位置」(row._seq)，不再用 $index（2026-09-16）
             两个原因：
             ① 需求：LongLife=Y 复制出来的那一行要和原件显示【同一个序号】，用 $index 必然错位；
             ② 插入副本行后 $index 会整体偏移，用 $index 会把后面所有行的序号挤偏一位。 -->
        <el-table-column label="序号" width="66" align="center">
          <template #default="{ row }">
            <span class="row-idx">{{ row._seq }}</span>
            <span v-if="row._copy" class="ll-copy-tag" title="LongLife=Y 自动复制出来的副本行（可独立编辑）">副本</span>
          </template>
        </el-table-column>

        <!-- ★ 预排筛选表格字段原封不动（列定义来自共享 config/preplanColumns.js）+ 决议页专属的 LongLife 列；编辑方式与预排筛选页完全一致 -->
        <el-table-column v-for="col in DECISION_COLUMNS" :key="col.key" :prop="col.key" :label="col.label" :min-width="col.width || 100" align="center" :class-name="col.key==='source' ? 'col-source' : ''">
          <template #default="{ row }">
            <!-- ★ 懒编辑（与预排筛选页一致）：仅 isEditable 字段可编辑，其余列只读 -->
            <div v-if="isEditable(row,col.key)" class="cell-inline-edit" @click="startEdit(row,col.key,$event)">
              <el-select v-if="isEditing(row,col.key) && (col.key==='qe_requirement'||col.key==='gpc_reply'||col.key==='oqc_hold'||col.key==='longlife')" :model-value="row[col.key]||''" @update:model-value="saveCell(row,col.key,$event)" @click.stop size="small" clearable placeholder=" " class="cell-select" popper-class="app-select-popper"><el-option value="Y" label="Y"/><el-option value="N" label="N"/></el-select>
              <el-select v-else-if="isEditing(row,col.key) && col.key==='type'" :model-value="row[col.key]||''" @update:model-value="saveCell(row,col.key,$event)" @click.stop size="small" clearable placeholder=" " class="cell-select" popper-class="app-select-popper"><el-option value="PD" label="PD"/><el-option value="TV" label="TV"/><el-option value="DT" label="DT"/><el-option value="BIM" label="BIM"/><el-option value="SET" label="SET"/></el-select>
              <!-- ★ 预排月份（仅计划外行可编辑）：计划外无来源计划文件，月份需人工确认/补填 -->
              <el-select v-else-if="isEditing(row,col.key) && col.key==='plan_month_label'" :model-value="row[col.key]||''" @update:model-value="saveCell(row,col.key,$event)" @click.stop size="small" clearable placeholder=" " class="cell-select" popper-class="app-select-popper"><el-option v-for="m in 12" :key="m" :value="m+'月'" :label="m+'月'"/></el-select>
              <input v-else-if="isEditing(row,col.key) && col.key!=='sample_date'" :value="getEditVal(row,col.key)" @blur="saveCell(row,col.key,$event)" @keydown.enter="saveCell(row,col.key,$event)" @click.stop class="cell-input" :class="cellCls(row,col.key)" />
              <span v-else class="cell-text" :class="cellCls(row,col.key)">{{ col.key==='type' && row.is_plan_external && !row.type ? '✎ 回填' : (col.key==='plan_month_label' && row.is_plan_external && !row.plan_month_label ? '✎ 补月份' : formatCell(row[col.key])) }}</span>
            </div>
            <!-- ★ 2026-09-23：来源文件列加 title —— 该列单行省略（见 .col-source 样式），
                 文件名较长时靠悬停查看全名。「计划外」行显示的是标签、无文件名可取，故不给 title。 -->
            <span v-else :class="cellCls(row,col.key)" :title="(col.key==='source' && !row.is_plan_external) ? formatCell(row[col.key]) : ''">
              <span v-if="col.key==='source' && row.is_plan_external" class="src-ext">计划外{{ row.mtd_source ? '·' + row.mtd_source.toUpperCase() : '' }}</span>
              <!-- ★ Judge 列：数据不完整→预警(红)；决策同意+产量达标→已同意(绿)；其余空 -->
              <template v-else-if="col.key==='judge'"><b :class="judgeCls(row)">{{ judgeDisplay(row) }}</b></template>
              <template v-else>{{ formatCell(row[col.key]) }}</template>
            </span>
          </template>
        </el-table-column>
      </el-table>
    </div>

    <!-- 分页 -->
    <div class="pagination-bar">
      <el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :page-sizes="[20, 50, 100, 200]"
        :total="filteredTotal" layout="sizes,prev,pager,next" size="small" @current-change="currentPage = $event" @size-change="currentPage = 1" />
    </div>

    <!-- ★ 送样日期：自绘深色主题日历弹层（与预排筛选页一致，锚定在输入框下方弹出） -->
    <div v-if="calVisible" class="cal-mask" @click.self="calVisible=false">
      <div class="cal-panel" :style="calStyle">
        <div class="cal-head">
          <button type="button" class="cal-nav" @click="calShiftYear(-1)">«</button>
          <button type="button" class="cal-nav" @click="calShiftMonth(-1)">‹</button>
          <span class="cal-title">{{ calView.year }}年{{ calView.month }}月</span>
          <button type="button" class="cal-nav" @click="calShiftMonth(1)">›</button>
          <button type="button" class="cal-nav" @click="calShiftYear(1)">»</button>
          <button v-if="calRow && calRow.sample_date" type="button" class="cal-clear" @click="clearSampleDate" title="清空送样日期（填错时叉掉）">✕ 清空</button>
          <button type="button" class="cal-close" @click="calVisible=false">✕</button>
        </div>
        <div class="cal-week">
          <span v-for="w in ['日','一','二','三','四','五','六']" :key="w">{{ w }}</span>
        </div>
        <div class="cal-grid">
          <span v-for="(d, i) in calDays" :key="i" class="cal-day" :class="{ 'is-out': !d.inMonth, 'is-today': isCalToday(d), 'is-picked': isCalPicked(d) }" @click="d.inMonth && pickCalDay(d)">{{ d.day }}</span>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, onActivated, onDeactivated } from 'vue'
import { ElMessage } from 'element-plus'
import axios from 'axios'
import { TABLE_COLUMNS, DECISION_FIELDS } from '../config/preplanColumns'

// ★ 2026-09-16：LongLife(Y/N) 列【只加在审核决议中心】
//   刻意不并入共享的 TABLE_COLUMNS —— 那是预排页与决议页共用的，改它会连带改动预排页，
//   而本次需求明确只要决议页有这一列。
const DECISION_COLUMNS = [...TABLE_COLUMNS, { key: 'longlife', label: 'LongLife', width: 90 }]
import { useTableSearch } from '../composables/useTableSearch'
import { useFitHeight } from '../composables/useFitHeight'
import { buildFileName, monthLabelFromYm, fullLabelFromYm } from '../composables/useExportNaming.js'
import ExportNamingDialog from '../components/common/ExportNamingDialog.vue'

defineOptions({ name: 'DecisionReviewView' })

const API = import.meta.env.VITE_API_BASE || '/api'
const loading = ref(false)
const mtdSyncing = ref(false)
const allRows = ref([])

// ★ 导出命名菜单（2026-09-18）：每个导出按钮旁的小齿轮打开对应类型的命名配置弹窗
const namingOpen = ref(false)
const namingType = ref('decision')
function openNaming(t) { namingType.value = t; namingOpen.value = true }
// ★ 2026-09-20：月份筛选键从 plan_month_label 文本改为 plan_ym（YYYYMM 数值）——
//   文本 '9月' 不带年份，跨年的两个 9 月会被当成同一个月；plan_ym 天然区分。
//   null = 全部月份；0 = 未归类（历史行）；>0 = 具体年月。
const filterMonth = ref(null)
const filterDecision = ref('all')
const currentPage = ref(1)
const pageSize = ref(50)

const DECISION_KEYS = DECISION_FIELDS.map(f => f.key)

// ★★★ 类 Excel 列筛选（与预排筛选页一致）★★★
const TYPE_OPTIONS = ['PD','TV','DT','BIM','SET']
const filterVisible = ref(false)
const colFilters = reactive({ types: [], fab: '', customer: '', keyword: '' })
const hasColFilter = computed(() => colFilters.types.length>0 || !!colFilters.fab.trim() || !!colFilters.customer.trim() || !!colFilters.keyword.trim())
function applyColFilter(){ filterVisible.value = false; currentPage.value = 1 }
function clearColFilter(){ colFilters.types=[]; colFilters.fab=''; colFilters.customer=''; colFilters.keyword=''; currentPage.value=1 }
// ★ 点击屏幕其他区域关闭筛选菜单（弹层自身/内部下拉/触发按钮除外，触发按钮由 @click 开合）
function onDocClickForFilter(e){
  if(!filterVisible.value) return
  const t = e.target
  if(!t || !t.closest) return
  if(t.closest('.el-popper') || t.closest('.filter-ref')) return
  filterVisible.value = false
}

// ★★★ 置顶/置底排序判定 ★★★
// mtd 产量达标：ORT 通过(非 N) 且 非预警/待回填 —— 独立判定
function isYes(v){
  const s = String(v ?? '').trim().toLowerCase()
  return ['是', 'y', 'yes', 'true', '1'].includes(s)
}
function isMtdMet(r){
  const j = (r.judge || '').trim()
  return (r.ort_ok || '').trim() !== 'N' && j !== '预警' && j !== '待回填'
}
// 决议有 Y：QE 或 GPC 任一回复是/Y
function hasDecisionY(r){ return isYes(r.qe_requirement) || isYes(r.gpc_reply) }
// ★ 预警项（与实时监控报警逻辑一致）：产量达标 且 QE/GPC 有 Y → 需要处理
function warnPriority(r){ return isMtdMet(r) && hasDecisionY(r) }
// 置顶：预警项（达标 + 有Y）→ 最前方
function topPriority(r){ return warnPriority(r) }
// 置底：未达标 且 无Y → 最后方
function bottomPriority(r){ return !isMtdMet(r) && !hasDecisionY(r) }

// ★ 分层排序评分：预警(达标+有Y) > 已插入 > 达标 > 其余；分数越高越靠前
function priorityScore(r){
  if (warnPriority(r)) return 5                                  // ★ 达标 + QE/GPC 任一Y
  if (r.is_plan_external && r.inserted_to_preplan) return 3      // ★ 计划外已插入预排
  if (isMtdMet(r)) return 2                                      // 产量达标
  return 1
}

// ★ 送样信息是否齐备（与实时预警页「可送」同源判定：Q工单 + 箱号 + 送样日期 均填写完整；
//   任一侧补录保存后，另一侧刷新即自动同步）
function isMissingSampleInfo(r){
  const order = String(r.q_order || '').trim()
  const box = String(r.box_number || '').trim()
  const date = String(r.sample_date || '').trim()
  return !order || !box || !date
}

// ★ Judge 列显示（用户 09-02/09-03/09-04 语义：与实时监控预警同一套规则）：
//   计划外已插入 → '计划外已插入'(蓝青)    计划外未回填 Type → '待回填'(黄)
//   产量达标 && QE/GPC 有 Y：
//     送样信息未齐（Q工单/箱号/送样日期缺失）→ '预警'(红，提示补录 → 与实时监控「待送样」一致)
//     信息齐备 → '已同意'(绿)（对应预警页「可送」）
//   其他情况 → 空（不显示）
function judgeDisplay(r){
  if (r.is_plan_external){
    if (r.inserted_to_preplan) return '计划外已插入'
    if (!(r.type || '').trim()) return '待回填'
    return ''
  }
  if (!warnPriority(r)) return ''
  if (isYes(r.qe_requirement) && isMissingSampleInfo(r)) return '预警'   // ★ QE需送样且未补送样信息
  return '已同意'
}
function judgeCls(r){
  if (r.is_plan_external){
    if (r.inserted_to_preplan) return 'judge-inserted'
    if (!(r.type || '').trim()) return 'judge-pending'
    return ''
  }
  if (!warnPriority(r)) return ''
  if (isYes(r.qe_requirement) && isMissingSampleInfo(r)) return 'judge-warn'
  return 'judge-ok'
}

// ★★★ 内联编辑（与预排筛选页完全一致：仅 editableKeys 字段可编辑，其余列只读）★★★
// ★ Judge 列不在可编辑集合：judge 为派生状态机展示列（预警/已同意/计划外已插入/待回填，
//   规则与实时监控预警一致），不允许手改，保证语义一致不被覆盖。
// ★ 2026-09-16：'longlife' 必须在这里 —— 否则 LongLife 列会渲染成只读文本、根本点不动，
//   「填 Y 才复制一行」就无从操作（模板里给它写了 Y/N 下拉，但 isEditable 会先把单元格拦掉）。
const editableKeys = new Set(['gpc_reply','oqc_hold','q_order','box_number','sample_date','qe_requirement','qe_remark','ra_remark','longlife'])
// ★ mtd_output(MTD OUTPUT监控) 不在可编辑集合内：该列由「同步MTD」回填，禁止手动修改
// ★ plan_month_label(预排月份) 仅计划外行可编辑：计划外无来源计划文件，历史行月份恒空，
//   新行已由 sync-mtd 写入「执行 SQL 时刻所属月份」，此处供人工校正/补填存量。
// ★ 2026-09-16 副本行（LongLife=Y 复制出来的那一行）：除 LongLife 外都可独立编辑。
//   LongLife 本身是"要不要复制"的开关，只能在原件上改 —— 在副本上改它没有意义，
//   而且后端也刻意不接收副本的 longlife（见 preplan_update 的 _copy 分支）。
function isEditable(row,k){
  if (row._copy) return k !== 'longlife' && editableKeys.has(k)
  return editableKeys.has(k) || (row.is_plan_external && (k==='type' || k==='plan_month_label'))
}
function getEditVal(row,k){ return row[k] || '' }
// ★ 懒编辑：只有点击的单元格才渲染编辑组件，其余显示纯文本（大幅降低表格渲染开销）
const editingCell = ref(null)
// ★ 用 row._ck（原件 = id，副本 = id#copy）作为编辑态标识，而不是 row.id：
//   副本行与原行共用同一个 id，只比对 id 会导致「点副本时原件单元格也一起弹出编辑器」。
function isEditing(row,key){ return editingCell.value && editingCell.value.ck===row._ck && editingCell.value.key===key }
function startEdit(row,key,e){
  if(key==='sample_date'){ openCal(row,e); return }
  editingCell.value = { ck: row._ck, key }
}
async function saveCell(row,k,e){
  let v = e && typeof e==='object' && e.target!==undefined ? e.target.value : e
  if(v===null||v===undefined) v=''
  if(row[k]===v){ editingCell.value=null; return }
  try{
    // ★ 副本行（LongLife=Y 复制出来的那一行）带 _copy 标记提交：
    //   后端只把该字段写进【原行】的 longlife_copy（JSON 覆盖值），完全不触碰原行自身字段，
    //   从而实现"两份数据各自独立编辑"，同时保持序号/总项数不变。
    const payload = row._copy ? { _copy: true, [k]: v } : { [k]: v }
    const res = await axios.post(`${API}/preplan/update/${row.id}/`, payload)
    // ★ 就地更新 allRows 里的【原件】对象（副本行是它的派生视图，会自动跟着刷新）：
    //   - 改原件字段 → 用后端返回的 row 覆盖（含重算的 ort_ok/judge 等）
    //   - 改副本字段 → 后端返回的 row 带最新 longlife_copy
    //   注意：模板传入的 row 是 decoratedRows 的浅拷贝，必须定位 allRows 中的原对象更新才会触发响应式。
    const src = allRows.value.find(r => r.id === row.id)
    if (src && res.data && res.data.row){
      Object.assign(src, res.data.row)
    } else if (src){
      src[k] = v
    }
  }catch(err){
    ElMessage.error(row._copy ? '副本行保存失败' : '保存失败')
  }finally{
    editingCell.value = null
  }
}

// ★ 送样日期：自绘深色主题日历弹层（与预排筛选页一致）
const calVisible = ref(false)
const calRow = ref(null)
const calView = reactive({ year: new Date().getFullYear(), month: new Date().getMonth() + 1 })
const calPos = ref({ left: 0, top: 0 })
const calStyle = computed(() => ({ left: calPos.value.left + 'px', top: calPos.value.top + 'px' }))
function openCal(row, e){
  calRow.value = row
  // ★ 打开一律定位到「今天」（与预排筛选页一致，2026-09-15）
  //   不再跟随预排月份 / 已填送样日期，否则点开永远停在旧月份，没法直接点今天
  const t = new Date()
  calView.year = t.getFullYear()
  calView.month = t.getMonth() + 1
  // ★ 锚定到输入框下方
  if (e && e.currentTarget){
    const r = e.currentTarget.getBoundingClientRect()
    let left = r.left
    if (left + 280 > window.innerWidth) left = window.innerWidth - 292
    calPos.value = { left, top: r.bottom + 4 }
  }
  calVisible.value = true
}
const calDays = computed(() => {
  const y = calView.year, m = calView.month
  const first = new Date(y, m - 1, 1)
  const startDow = first.getDay()
  const daysInMonth = new Date(y, m, 0).getDate()
  const daysInPrev = new Date(y, m - 1, 0).getDate()
  const arr = []
  for (let i = startDow - 1; i >= 0; i--) arr.push({ day: daysInPrev - i, inMonth: false })
  for (let d = 1; d <= daysInMonth; d++) arr.push({ day: d, inMonth: true })
  const remain = (7 - arr.length % 7) % 7
  for (let d = 1; d <= remain; d++) arr.push({ day: d, inMonth: false })
  return arr
})
function isCalToday(d){
  const t = new Date()
  return d.inMonth && calView.year === t.getFullYear() && calView.month === t.getMonth() + 1 && d.day === t.getDate()
}
// ★ 该行原本已填的送样日期（2026-09-15）：打开一律跳今天后，仍要能看出"已填过的是哪天"。
//   按 YYYY-MM-DD 手动拆解，避免 ISO 纯日期串按 UTC 解析的跨月偏移。
function isCalPicked(d){
  const m = /^(\d{4})-(\d{2})-(\d{2})/.exec((calRow.value && calRow.value.sample_date) || '')
  return !!(m && d.inMonth && calView.year === parseInt(m[1]) && calView.month === parseInt(m[2]) && d.day === parseInt(m[3]))
}
function calShiftMonth(delta){ let m = calView.month + delta; if (m < 1){ m = 12; calView.year-- } else if (m > 12){ m = 1; calView.year++ } calView.month = m }
function calShiftYear(delta){ calView.year += delta }
function pickCalDay(d){
  const val = `${calView.year}-${String(calView.month).padStart(2, '0')}-${String(d.day).padStart(2, '0')}`
  if (calRow.value) saveCell(calRow.value, 'sample_date', { target: { value: val } })
  calVisible.value = false
}
// ★ 送样日期填错 → 日历弹层点「✕ 清空」把日期叉掉（空值入库）
function clearSampleDate(){
  const r = calRow.value
  if (r && r.sample_date) saveCell(r, 'sample_date', '')
  calVisible.value = false
}

// ★ 2026-09-20：月份选项改由 plan_ym 派生（与预排页同口径），跨年同名月份不再合并
//   { ym, label }；ym=null 表示「全部月份」，ym=0 表示「未归类」（老数据/计划外未回填月份）
const monthOptions = computed(() => {
  const s = new Set()
  allRows.value.forEach(r => { const v = r.plan_ym; if (v !== undefined && v !== null) s.add(Number(v) || 0) })
  // ★ 2026-09-21：el-option 的 value 不接受 null —— Element Plus 会抛
  //   "Invalid prop: type check failed for prop \"value\". Expected String | Number | Boolean | Object, got Null"。
  //   而本页的筛选守卫本来就同时兼容 null / ''（clearable 清空也是 ''），
  //   所以「全部月份」这一项直接改用 ''（String，类型合法），语义与原来的 null 完全一致。
  const out = [{ ym: '', label: '全部月份' }]
  const unclassified = s.has(0)
  const months = [...s].filter(v => v > 0).sort((a, b) => b - a)
  months.forEach(v => out.push({ ym: v, label: `${Math.floor(v / 100)}年${v % 100}月` }))
  if (unclassified) out.push({ ym: 0, label: '未归类' })
  return out
})

// ★ 2026-09-21（补）：导出命名的「当前页面上下文」——真实导出与命名配置弹窗的实时预览共用这一份。
//   ★ 此前本页只在模板与 handleExport 里**引用**了 exportNamingCtx，却漏了这里的声明，
//     导致 Vue 在渲染时抛：Property "exportNamingCtx" was accessed during render but is not defined on instance。
//   口径：{year} 沿用本页既有 Math.max(plan_year)；{month} 跟随「决议月份」筛选（未归类(0) → '未归类'）；
//        {label} 为「年+月」复合标签，未选月份时退化为「xxxx年」/「全部」。
const exportNamingCtx = computed(() => {
  const years = allRows.value.map(r => r.plan_year).filter(Boolean)
  const yr = years.length ? String(Math.max(...years)) : ''
  const ymv = filterMonth.value
  const isUnclassified = ymv !== null && ymv !== '' && Number(ymv) === 0
  return {
    year: yr || '全部',
    month: isUnclassified ? '未归类' : monthLabelFromYm(ymv),
    label: isUnclassified ? '未归类' : fullLabelFromYm(ymv, yr ? `${yr}年` : '全部'),
  }
})

// 决议状态判断（严格 Y / N；空值=未决议）
function normDecision(v){
  const s = String(v ?? '').trim().toLowerCase()
  if (['y','yes','是','true','1','ok'].includes(s)) return 'Y'
  if (['n','no','否','false','0'].includes(s)) return 'N'
  if (s === '待定') return '待定'
  return ''
}
function decisionState(r){
  const vals = DECISION_KEYS.map(k => normDecision(r[k])).filter(Boolean)
  if (!vals.length) return 'none'
  if (vals.includes('待定')) return '待定'
  if (vals.includes('Y')) return 'Y'
  if (vals.includes('N')) return 'N'
  return 'none'
}

const filteredRows = computed(() => {
  let list = allRows.value
  // ★ 类 Excel 列筛选（Type / FAB / 客户 / 关键字）
  if (colFilters.types.length) list = list.filter(r => colFilters.types.includes((r.type || '').trim()))
  if (colFilters.fab.trim()){ const k = colFilters.fab.trim().toLowerCase(); list = list.filter(r => (r.fab || '').toLowerCase().includes(k)) }
  if (colFilters.customer.trim()){ const k = colFilters.customer.trim().toLowerCase(); list = list.filter(r => (r.customer || '').toLowerCase().includes(k)) }
  if (colFilters.keyword.trim()){ const k = colFilters.keyword.trim().toLowerCase(); list = list.filter(r => (r.pn || '').toLowerCase().includes(k) || (r.model || '').toLowerCase().includes(k)) }
  // 月份（plan_ym：null=全部 / 0=未归类 / >0 具体年月）
  if (filterMonth.value !== null && filterMonth.value !== '') list = list.filter(r => (Number(r.plan_ym) || 0) === Number(filterMonth.value))
  // 决议状态
  if (filterDecision.value === 'none') list = list.filter(r => decisionState(r) === 'none')
  else if (filterDecision.value !== 'all') list = list.filter(r => decisionState(r) === filterDecision.value)
  // ★ 分层排序（P1-4）：决策Y / 已插入 / 达标 优先 → 其余；同分保持原顺序
  const indexed = list.map((r, i) => ({ r, i }))
  indexed.sort((a, b) => {
    const sa = priorityScore(a.r), sb = priorityScore(b.r)
    if (sa !== sb) return sb - sa
    return a.i - b.i
  })
  return indexed.map(x => x.r)
})

// ★ 仅按月份过滤的列表（用于统计：总决议项/各状态数字只在月份变化时变动，不随状态切换变化）
const monthFilteredRows = computed(() => {
  if (filterMonth.value === null || filterMonth.value === '') return allRows.value
  return allRows.value.filter(r => (Number(r.plan_ym) || 0) === Number(filterMonth.value))
})

// ★ 行装饰：来源分隔线 + 稳定的行标识/序号（2026-09-16）
//   _ck  = 单元格编辑态标识（原件 = String(id)，副本 = id#copy）—— 副本与原行共用同一个 id，
//          必须靠 _ck 区分，否则编辑其中一份会让另一份也弹出编辑器。
//   _seq = 序号（条目在「过滤后完整列表」中的位置 +1）。序号取自条目位置而非页内 $index，
//          才可能让副本行与原件显示同一个序号。
const decoratedRows = computed(() => {
  const list = filteredRows.value
  const arr = list.map((r, i) => ({ ...r, _isSourceChange: false, _ck: String(r.id), _seq: i + 1 }))
  for (let i = 0; i < arr.length - 1; i++) {
    if (arr[i].source !== arr[i + 1].source) {
      arr[i]._isSourceChange = true
    }
  }
  return arr
})

// ★ LongLife 副本行（2026-09-16）：为「LongLife = Y」的条目生成一份派生行，显示在原件【下方】
//   - 数据 = 原行 + longlife_copy（副本被单独改过的字段）→ 天然"一模一样"，改过哪些字段就覆盖哪些
//   - _copy=true 供 saveCell 分流（写进 longlife_copy）、供模板锁住 LongLife 列并显示「副本」标记
//   - 不覆盖 _seq、_ck 之外的派生字段；_seq 沿袭原件 → 满足需求「序号不变」
//   - 不参与 filteredTotal / stats → 满足需求「总项数还是不变的」
function longlifeCopyRow(r){
  const ov = (r.longlife_copy && typeof r.longlife_copy === 'object') ? r.longlife_copy : {}
  return { ...r, ...ov, _copy: true, _ck: `${r.id}#copy` }
}

const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  // ★ 先按「条目」分页，再在页内展开副本行：
  //   这样每页仍是 pageSize 个条目，副本只是附加显示在原件下方，不会把后面的条目挤到下一页。
  const page = decoratedRows.value.slice(start, start + pageSize.value)
  const out = []
  for (const r of page){
    out.push(r)
    if ((r.longlife || '') === 'Y') out.push(longlifeCopyRow(r))
  }
  return out
})

const stats = computed(() => {
  // ★ 统计基于「月份过滤后、状态过滤前」，点击状态按钮数字不再变化
  const list = monthFilteredRows.value
  return {
    total: list.length,
    passed: list.filter(r => !r.is_plan_external).length,   // ★ 筛选通过项数 = 预排通过并已导出到决议的行（不含计划外）
    pending: list.filter(r => decisionState(r) === '待定').length,
    approved: list.filter(r => decisionState(r) === 'Y').length,
    rejected: list.filter(r => decisionState(r) === 'N').length,
    undecided: list.filter(r => decisionState(r) === 'none').length,
  }
})

// ★ 分页总数 = 实际过滤后行数（含列筛选/月份/决议状态），避免翻到空页
//   ★ 2026-09-16：按【条目】计数，不含 LongLife 副本行 —— 满足需求「总项数还是不变的」。
const filteredTotal = computed(() => filteredRows.value.length)

// ★ Ctrl+F 表格搜索（P1-2）：搜索范围 = 过滤排序后的全量行（跨页）
const tableRef = ref(null)
const tableWrapRef = ref(null)
const tableMaxH = useFitHeight(tableWrapRef)
// ★ 表格高度 = 容器剩余高度（搜索条展开时扣除其高度）→ 单一内部滚动条、表头稳定吸顶
const tableH = computed(() => Math.max(120, tableMaxH.value - (searchVisible.value ? 38 : 4)))
const { visible: searchVisible, keyword: searchKeyword, matches, activeIdx,
        doSearch, jumpNext, close: closeSearch, isHit, isActive, searchCellClass, onKeydown: onTableSearchKey } = useTableSearch({
  getRows: () => filteredRows.value,
  // ★ 只在表格展示的列内匹配（不扫 id/时间戳/布尔标志等隐藏字段，防误命中）
  searchKeys: DECISION_COLUMNS.map(c => c.key),
  tableRef,
  currentPage,
  pageSize,
  pageCount: () => Math.max(1, Math.ceil(filteredTotal.value / pageSize.value)),
})

function formatCell(v){ if (v === null || v === undefined) return ''; if (typeof v === 'string'){ const t = v.trim(); return (!t || t === 'undefined' || t === 'null' || t === 'NaN') ? '' : t } return String(v) }
function cellCls(row, key){ const cls = []; if (row.ort_ok === 'N' && key === 'ort_ok') cls.push('cell-ort-n'); if (key === 'judge' && row.judge === '预警') cls.push('cell-ort-n'); return cls }
function decisionRowClass({ row }){
  const st = decisionState(row); const cls = []
  // ★ LongLife 副本行（2026-09-16）：加标记类，用于左侧加一道青色竖线 + 浅底，
  //   让"这一行是副本、和上一行同序号"一眼可见。
  if (row._copy) cls.push('row-longlife-copy')
  if (st === '待定') cls.push('row-pending')
  if (st === 'Y') cls.push('row-approved')
  if (st === 'N') cls.push('row-rejected')
  if (row._isSourceChange) cls.push('row-source-split')
  if (row.is_plan_external) cls.push('row-external')
  // ★ 置顶优先：决议同意 且 mtd 产量达标
  if (topPriority(row)) cls.push('row-top-priority')
  // ★ 置底：两者都没有（无决议同意 且 mtd 未达标）→ 弱化显示
  if (bottomPriority(row)) cls.push('row-bottom-priority')
  // ★ Ctrl+F 搜索命中行高亮
  if (isHit(row)) cls.push('search-hit')
  if (isActive(row)) cls.push('search-active')
  return cls
}

// ★ 加载请求序号：防 keep-alive 激活/手动刷新重叠请求导致 loading 异常或旧响应覆盖新数据
let loadSeq = 0
async function loadData(){
  if (loading.value) return
  loading.value = true
  const seq = ++loadSeq
  try {
    // ★ 显示已纳入决议中心的行（导出标记 + 同步MTD 纳入的计划外数据）
    const res = await axios.get(`${API}/preplan/rows/`, { params: { exported: 'true' }, timeout: 30000 })
    if (seq !== loadSeq) return
    const data = res.data?.data || []
    allRows.value = data.map(r => ({ ...r }))
  } catch (e) {
    if (seq !== loadSeq) return
    if (e?.code === 'ECONNABORTED') ElMessage.error('加载超时，请点击「刷新」重试')
    else ElMessage.error('加载预排数据失败：' + (e?.response?.data?.error || e?.message || ''))
  } finally { if (seq === loadSeq) loading.value = false }
}

// ★ 同步MTD：与「筛选预排」页面复用同一套后端逻辑（POST /preplan/sync-mtd/）。
//   交互流程与预排筛选页面完全一致：仅传 year，成功提示用后端返回的 message，
//   同步完成后刷新本中心数据。计划外数据由后端统一处理（不纳入决议中心，与预排一致）。
async function handleSyncMtdDecision(){
  if (mtdSyncing.value) return
  mtdSyncing.value = true
  try {
    const years = allRows.value.map(r => r.plan_year).filter(Boolean)
    const year = years.length ? Math.max(...years) : ''
    const fd = new FormData()
    if (year) fd.append('year', String(year))
    const res = await axios.post(`${API}/preplan/sync-mtd/`, fd)
    if (res.data.success){
      ElMessage.success(res.data.message || 'MTD 同步完成')
      await loadData()
    } else {
      ElMessage.error(res.data.error || 'MTD 同步失败')
    }
  } catch (e) {
    ElMessage.error('MTD 同步失败：' + (e.response?.data?.error || e.message))
  } finally {
    mtdSyncing.value = false
  }
}

// ★ 清空审核决议（清除导出标记，页面回到空；选中某个月份时只清该月）
async function handleClear(){
  try {
    const body = {}
    if (filterMonth.value) body.ym = filterMonth.value
    const res = await axios.post(`${API}/preplan/clear-decision/`, body)
    ElMessage.success(res.data.message || '已清空')
    await loadData()
  } catch (e) {
    ElMessage.error('清空失败：' + (e.response?.data?.error || e.message))
  }
}

// ★ 基础资料比对回填：以基础资料表(EntryTable)按 P/N 比对，把 52阶料号/满箱量/客户 等
//   回填到本页决议行（与预排筛选页「刷新」同一套后端 refresh-entry），实现两侧互相参照校正
const backfilling = ref(false)
async function handleBackfill(){
  if (backfilling.value) return
  if (!allRows.value.length){ ElMessage.warning('暂无决议数据可回填，请先在预排页导入并导出到审核决议'); return }
  backfilling.value = true
  try {
    const fd = new FormData()
    const years = allRows.value.map(r => r.plan_year).filter(Boolean)
    const year = years.length ? Math.max(...years) : ''
    if (year) fd.append('year', String(year))
    const res = await axios.post(`${API}/preplan/refresh-entry/`, fd)
    if (res.data.success){
      ElMessage.success((res.data.message || '回填完成') + '（基础资料表 → 审核决议中心）')
      await loadData()
    } else {
      ElMessage.error(res.data.error || '比对回填失败')
    }
  } catch (e) {
    ElMessage.error('比对回填失败：' + (e.response?.data?.error || e.message))
  } finally {
    backfilling.value = false
  }
}

// ★ 保存到存档中心（把当前决议数据标记为定版）
const saving = ref(false)
async function handleArchive(){
  saving.value = true
  try {
    const body = {}
    if (filterMonth.value) body.ym = filterMonth.value   // ★ 选中月份时只定版该月
    const res = await axios.post(`${API}/preplan/archive/`, body)
    if (res.data.success) {
      ElMessage.success(res.data.message || '已保存到存档中心')
    } else {
      ElMessage.error(res.data.error || '保存失败')
    }
  } catch (e) {
    ElMessage.error('保存失败：' + (e.response?.data?.error || e.message))
  } finally { saving.value = false }
}

// ★ 导出审核决议中心数据为 Excel（顺序与页面一致；选中月份时只导该月）
async function handleExport(){
  try {
    const body = {}
    if (filterMonth.value) body.ym = filterMonth.value
    const res = await axios.post(`${API}/preplan/export-decision-excel/`, body, { responseType: 'blob' })
    if (res.data instanceof Blob && res.data.type.includes('json')) {
      const err = JSON.parse(await res.data.text())
      ElMessage.error(err.error || '导出失败')
      return
    }
    const url = URL.createObjectURL(new Blob([res.data]))
    const a = document.createElement('a')
    a.href = url
    // 命名上下文与配置弹窗预览共用同一份（见上方 exportNamingCtx）
    a.download = buildFileName('decision', exportNamingCtx.value)
    document.body.appendChild(a)
    a.click()
    a.remove()
    URL.revokeObjectURL(url)
    ElMessage.success('导出成功')
  } catch (e) { ElMessage.error('导出失败：' + (e.response?.data?.error || e.message)) }
}

// 表格横向拖动（与预排页一致；监听挂全局，鼠标移出表格区不中断）
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

// ★ 用 onActivated：keep-alive 缓存组件时，每次进入页面都重新加载（导出到决议后跳转能立即显示数据）
onActivated(loadData)
// ★ 点击屏幕其他区域关闭筛选菜单（监听随组件挂载/销毁）
onMounted(()=>document.addEventListener('click', onDocClickForFilter))
// ★ keep-alive：激活时注册 Ctrl+F 监听、停用时移除（避免缓存页面同时响应）
onActivated(()=>window.addEventListener('keydown', onTableSearchKey))
onDeactivated(()=>window.removeEventListener('keydown', onTableSearchKey))
onBeforeUnmount(()=>{document.removeEventListener('click', onDocClickForFilter);window.removeEventListener('keydown', onTableSearchKey)})
</script>

<style lang="scss" scoped>
.decision-review-view{ height:100%; display:flex; flex-direction:column; gap:8px; padding:4px 6px; min-height:0; background:transparent; }
.pbar{ display:flex; align-items:center; justify-content:space-between; flex-shrink:0; }
.pbar-left{ display:flex; align-items:center; gap:8px; }
.ptag{ background:rgba(0,100,170,.25); border:1px solid #0d4a70; color:#7fc8e8; font-size:10px; font-weight:700; letter-spacing:1px; padding:3px 10px; border-radius:4px; }
.ptitle{ font-size:15px; font-weight:500; color:#c8e0f8; span{ color:#00d4aa; } }
.run-btn{ font-size:11px; font-weight:600; padding:4px 10px; border-radius:12px; cursor:pointer; border:none; font-family:inherit; display:inline-flex; align-items:center; gap:2px; &.primary{ background:linear-gradient(135deg,#0055aa,#0077cc); color:#fff; box-shadow:0 2px 6px rgba(0,100,200,.35); &:hover:not(:disabled){ box-shadow:0 3px 12px rgba(0,120,240,.5); transform:translateY(-1px); } &:disabled{ background:rgba(0,40,80,.4); color:#4d7d9e; box-shadow:none; cursor:not-allowed; } } &.sec{ background:rgba(0,40,80,.3); color:#5a90b8; border:1px solid #0d3050; &:hover:not(:disabled){ background:rgba(0,60,120,.4); color:#90c0e8; } &:disabled{ opacity:.4; } } &.danger{ background:rgba(105,24,32,.35); color:#e09090; border:1px solid #5a2028; &:hover{ background:rgba(140,30,40,.5); color:#ffaaaa; } } }

.help-bar{ display:flex; align-items:center; gap:8px; padding:6px 12px; font-size:11px; color:#a0c8e8; background:rgba(0,60,120,.12); border:1px dashed #0d4a70; border-radius:6px; flex-shrink:0; }

.stat-grid{ display:grid; grid-template-columns:repeat(auto-fit,minmax(118px,1fr)); gap:6px; flex-shrink:0; }
.stat-card{ display:flex; align-items:center; gap:6px; padding:5px 10px; background:rgba(5,15,30,.5); border:1px solid #0d2a48; border-radius:6px; &.pending{ border-color:rgba(232,184,56,.4) } &.approved{ border-color:rgba(0,212,170,.4) } &.rejected{ border-color:rgba(255,107,107,.4) } &.pass{ border-color:rgba(0,150,255,.45) } }
.stat-icon{ font-size:14px; }
.stat-label{ font-size:9px; color:#5d8aaa; }
.stat-value{ font-size:16px; font-weight:700; color:#c8e0f8; line-height:1; }
.stat-sub{ display:none; }
.stat-card.pending .stat-value{ color:#e8b838 } .stat-card.approved .stat-value{ color:#00d4aa } .stat-card.rejected .stat-value{ color:#ff6b6b }

.filter-bar{ display:flex; align-items:center; gap:14px; padding:6px 12px; background:rgba(5,15,30,.5); border:1px solid #0d2a48; border-radius:8px; flex-shrink:0; flex-wrap:wrap; }
.filter-group{ display:flex; align-items:center; gap:6px; flex-shrink:0; }
/* ★ 布局修复：月份下拉加宽完整显示；状态按钮不压缩、不换行；整体右拉 */
.filter-group.month-group{ min-width:150px; }
.month-select{ width:130px!important; }
.filter-group.tabs-group{ flex-shrink:0; }
.filter-group.total-group{ margin-left:auto; flex-shrink:0; }
.total-num{ color:#c8e0f8; font-size:13px; }
.filter-label{ font-size:11px; color:#6aa3c8; white-space:nowrap; }
.decision-tabs{ display:flex; gap:4px; flex-shrink:0; flex-wrap:nowrap; }
.dt-tab{ font-size:11px; padding:4px 10px; border-radius:12px; cursor:pointer; color:#5a90b8; background:rgba(0,40,80,.3); border:1px solid #0d3050; white-space:nowrap; flex-shrink:0; &.active{ background:rgba(0,80,160,.35); border-color:#0077cc; color:#90c0e8; } &.pending{ color:#e8b838 } &.approved{ color:#00d4aa } &.rejected{ color:#ff6b6b } }
.dt-count{ margin-left:4px; opacity:.9; font-size:11px; font-weight:600; display:inline-block; min-width:16px; text-align:center; }

.table-section{ display:flex; flex-direction:column; flex:1; min-height:0; }
.table-wrapper{ flex:1; min-height:0; overflow:hidden; display:flex; flex-direction:column; cursor:grab; background:rgba(5,15,30,.5); border:1px solid #0d2a48; border-radius:8px; }
.table-wrapper.dragging{ cursor:grabbing; user-select:none; -webkit-user-select:none; }
.row-idx{ color:#4d7d9e; font-size:11px; }
/* ★ LongLife 副本行（2026-09-16）：「副本」小标记 + 序号下方竖排 */
.ll-copy-tag{ display:block; margin:1px auto 0; width:fit-content; font-size:9px; line-height:12px; padding:0 4px; border-radius:3px; color:#00d4aa; background:rgba(0,212,170,.14); box-shadow:inset 0 0 0 1px rgba(0,212,170,.35); }
/* 副本行：左侧青色竖线 + 极浅底色，与上一行（原件）形成"成对"的视觉关系 */
.decision-review-view :deep(.row-longlife-copy td){ box-shadow: inset 3px 0 0 #00d4aa; background: rgba(0,212,170,.05)!important; }
.decision-review-view :deep(.row-longlife-copy td .cell-text){ box-shadow: inset 0 0 0 1px rgba(0,212,170,.5); background: rgba(0,212,170,.07); }
.cell-inline-edit{ width:100%; overflow:hidden; }
.cell-text{ display:block; width:100%; min-height:22px; line-height:22px; cursor:pointer; padding:0 4px; border-radius:3px; box-shadow:inset 0 0 0 1px rgba(0,180,230,.4); background:rgba(0,160,220,.06); }
.cell-text:hover{ box-shadow:inset 0 0 0 1px #00b8e6; background:rgba(0,160,220,.16); }
.cell-text.cell-missing{ background:rgba(220,50,50,.28); color:#ffaaaa; font-weight:600; }
.cell-text.cell-ort-n{ background:rgba(220,50,50,.28); color:#ffaaaa; font-weight:700; }
.cell-input{ width:100%; text-align:center; font-size:12.5px; padding:3px 4px; border:1px solid #0d3050; border-radius:3px; background:transparent; color:#c8ddf5; font-family:inherit; outline:none; transition:.15s; }
.cell-input:focus{ border-color:#0077cc; background:rgba(0,40,80,.3); }
.cell-input.cell-missing{ background:rgba(220,50,50,.28); color:#ffaaaa; }
.cell-input.cell-ort-n{ background:rgba(220,50,50,.28); color:#ffaaaa; }
.cell-select{ width:100%; }
.cell-select :deep(.el-select__wrapper){ width:100%!important; padding:1px 6px!important; }
.cell-select :deep(.el-select__selected-item){ font-size:12px; color:#c8ddf5!important; }

/* ★ 自绘深色主题日历弹层（锚定输入框下方，与预排筛选页一致） */
.cal-mask{ position:fixed; inset:0; z-index:200; }
.cal-panel{ position:absolute; background:#0a2640; border:1px solid #1a3a5f; border-radius:12px; padding:12px 14px; box-shadow:0 20px 60px rgba(0,10,30,.8); width:280px; }
/* ★ 年月标题不换行：导航/清空/关闭按钮禁止收缩，标题独占剩余空间且 nowrap（字号由 14→12 保证 280px 面板装得下一行） */
.cal-head{ display:flex; align-items:center; gap:3px; margin-bottom:8px; flex-wrap:nowrap; }
.cal-title{ flex:1 1 auto; min-width:0; text-align:center; font-size:12px; line-height:1.2; font-weight:600; color:#c8e0f8; white-space:nowrap; }
.cal-nav{ flex:0 0 auto; background:rgba(0,60,120,.3); border:1px solid #0d3050; color:#7ab8e0; border-radius:5px; width:22px; height:22px; padding:0; cursor:pointer; font-size:12px; line-height:1; }
.cal-nav:hover{ background:rgba(0,100,180,.4); color:#e0f0ff; }
.cal-close{ flex:0 0 auto; background:none; border:none; color:#5a90b8; font-size:13px; line-height:1; cursor:pointer; margin-left:4px; padding:0; }
.cal-close:hover{ color:#ff9a9a; }
.cal-clear{ flex:0 0 auto; background:rgba(200,60,60,.15); border:1px solid rgba(255,120,120,.35); color:#ff9a9a; font-size:10px; line-height:1.4; border-radius:4px; padding:2px 5px; cursor:pointer; margin-left:auto; font-family:inherit; transition:all .15s; white-space:nowrap; }
.cal-clear:hover{ background:rgba(220,70,70,.3); color:#ffc0c0; }
.cal-week{ display:grid; grid-template-columns:repeat(7,1fr); gap:2px; margin-bottom:4px; }
.cal-week span{ text-align:center; font-size:11px; color:#6aa3c8; padding:3px 0; }
.cal-grid{ display:grid; grid-template-columns:repeat(7,1fr); gap:2px; }
.cal-day{ text-align:center; font-size:12px; color:#c8ddf5; padding:6px 0; border-radius:5px; cursor:pointer; transition:background .12s; }
.cal-day:hover{ background:rgba(0,110,220,.35); color:#fff; }
.cal-day.is-out{ color:#3a5a78; cursor:default; }
.cal-day.is-out:hover{ background:none; color:#3a5a78; }
.cal-day.is-today{ box-shadow:inset 0 0 0 1px #00d4aa; color:#00d4aa; font-weight:700; }
.cal-day.is-picked{ background:rgba(0,150,120,.25); color:#7df0d8; font-weight:700; }
.cal-day.is-today.is-picked{ background:rgba(0,150,120,.35); color:#8ff5e0; }

.decision-review-view :deep(.el-table){ --el-table-bg-color:transparent; --el-table-tr-bg-color:rgba(5,15,30,.5); --el-table-header-bg-color:rgba(0,40,80,.35); --el-table-border-color:#0d2a48; --el-table-row-hover-bg-color:rgba(0,60,120,.25); --el-table-text-color:#c8ddf5; --el-table-header-text-color:#a0c8e8; color:#c8ddf5; }
.decision-review-view :deep(.el-loading-mask){ background:rgba(3,9,15,.72)!important; }
.decision-review-view :deep(.row-pending td){ background:rgba(232,184,56,.06)!important; }
.decision-review-view :deep(.row-approved td){ background:rgba(0,212,170,.05)!important; }
.decision-review-view :deep(.row-rejected td){ background:rgba(255,107,107,.07)!important; }
/* ★ 来源分隔线（与预排页合并视图一致）：S13 组最后一行底部绿色线 */
.decision-review-view :deep(.row-source-split td){ border-bottom:2px solid rgba(0,212,170,.85)!important; }

/* ★ 2026-09-23：来源文件列单行省略
   根因：该列宽 160px，而文件名常达 30+ 字符（如 `Monthly input target s110623.xlsx`），
   默认 white-space:normal 会折成 2~3 行 → 把整行行高撑高、表格很难看。
   改为单行 + 溢出省略号；全名见单元格 title（悬停）。
   注：用 `td.col-source` 精确定位（class-name 会加在 <td> 上），不波及其它列。 */
.decision-review-view :deep(td.col-source) .cell{
  white-space:nowrap; overflow:hidden; text-overflow:ellipsis;
}
/* ★ 置顶优先行：mtd 产量达标 且 QE/GPC 均回复 Y（左侧绿色强调条） */
.decision-review-view :deep(.row-top-priority td){ box-shadow: inset 3px 0 0 #00d4aa; background:rgba(0,212,170,.07)!important; }
/* ★ 置底行：无决议同意 且 mtd 未达标（灰色左条 + 弱化背景） */
.decision-review-view :deep(.row-bottom-priority td){ box-shadow: inset 3px 0 0 #3a5a78; background:rgba(58,90,120,.08)!important; }
/* ★ Judge 列显示色：预警=红 / 已同意=绿 / 计划外已插入=蓝青 / 待回填=黄（仅 Judge 列标色，不整行变红） */
.judge-warn{ color:#ff6b6b; font-weight:700; }
.judge-ok{ color:#00d4aa; font-weight:700; }
.judge-inserted{ color:#4fc3f7; font-weight:700; }
.judge-pending{ color:#e8b838; font-weight:700; }
.cell-ort-n{ color:#ff6b6b; font-weight:600; }

.decision-review-view :deep(.el-select__wrapper){ background:rgba(0,30,60,.5)!important; box-shadow:0 0 0 1px #0d3050 inset!important; }
.decision-review-view :deep(.el-select__wrapper.is-focused){ box-shadow:0 0 0 1px #0077cc inset!important; }
.decision-review-view :deep(.el-select__selected-item){ font-size:12px; color:#c8ddf5!important; }
.decision-review-view :deep(.el-select__wrapper:hover){ box-shadow:0 0 0 1px #0d3050 inset!important; }

.pagination-bar{ display:flex; justify-content:flex-end; padding:4px 2px; flex-shrink:0; }
/* 分页深色适配：按钮/页码清晰可见，禁用态(第一/最后一页)不再白色 */
.decision-review-view :deep(.el-pagination__total),
.decision-review-view :deep(.el-pagination__jump){ color:#5a90b8!important; }
.decision-review-view :deep(.el-pagination .el-pager li){
  background:rgba(0,40,80,.35)!important;
  color:#a8cce8!important;
  border-radius:4px;
  margin:0 2px;
  font-weight:600;
}
.decision-review-view :deep(.el-pagination .el-pager li:hover){ background:rgba(0,80,160,.45)!important; color:#e0f0ff!important; }
.decision-review-view :deep(.el-pagination .el-pager li.is-active){
  background:rgba(0,110,220,.6)!important;
  color:#fff!important;
}
.decision-review-view :deep(.el-pagination .btn-prev),
.decision-review-view :deep(.el-pagination .btn-next){
  background:rgba(0,40,80,.35)!important;
  color:#a8cce8!important;
  border-radius:4px;
}
.decision-review-view :deep(.el-pagination .btn-prev:hover:not(:disabled)),
.decision-review-view :deep(.el-pagination .btn-next:hover:not(:disabled)){ background:rgba(0,80,160,.45)!important; color:#e0f0ff!important; }
.decision-review-view :deep(.el-pagination .btn-prev:disabled),
.decision-review-view :deep(.el-pagination .btn-next:disabled){
  background:rgba(0,25,50,.45)!important;
  color:#3f6a8f!important;
}
.row-btn{ font-size:11px; padding:2px 8px; border-radius:6px; cursor:pointer; border:none; font-family:inherit; &.danger{ background:rgba(105,24,32,.35); color:#e09090; border:1px solid #5a2028; &:hover{ background:rgba(140,30,40,.5); color:#ffaaaa; } } }
.src-ext{ color:#ffd54f; font-weight:700; }
.decision-review-view :deep(.row-external td){ background:rgba(255,213,79,.08)!important; }

/* ══════════════════════════════════════════════════════════════════════
   ★ 白天主题覆盖（2026-09-18）——原样式整套写死深色，切白天后浅字压浅底不可读。
   统一改「浅底深字」，语义色加深；el-* 用 :deep。范式同 PreplanView。
   ══════════════════════════════════════════════════════════════════════ */
[data-theme="light"] .decision-review-view {
  color: #1a4070;
  .ptag { background: #dbe7f6; border-color: #bcd4ec; color: #2a5a86; }
  .ptitle { color: #0a2858; span { color: #0a8f6e; } }
  .run-btn.sec { background: var(--well); color: #4a6a8a; border-color: #c0d2e4;
    &:hover:not(:disabled) { background: #cddcec; color: #24507a; } }
  .run-btn.primary:disabled { background: #e6edf4; color: #9ab0c4; }
  .row-btn.danger { background: #fdecec; color: #c0392b; border-color: #f0b8b8;
    &:hover { background: #fadada; color: #a02020; } }

  .help-bar { color: #2a5a86; background: var(--surface-2); border-color: #bcd4ec; }

  .stat-card { background: var(--surface-1); border-color: var(--line-1);
    &.pending { border-color: rgba(176,120,0,.4); } &.approved { border-color: rgba(10,143,110,.4); }
    &.rejected { border-color: rgba(208,40,40,.4); } &.pass { border-color: rgba(10,111,208,.45); } }
  .stat-label { color: #5a7a9a; }
  .stat-value { color: #0a2858; }
  .stat-card.pending .stat-value { color: #b07800; } .stat-card.approved .stat-value { color: #0a8f6e; } .stat-card.rejected .stat-value { color: #d02828; }

  .filter-bar { background: var(--surface-2); border-color: var(--line-1); }
  .filter-label { color: #5a7a9a; }
  .total-num { color: #0a2858; }
  .dt-tab { color: #4a6a8a; background: var(--surface-2); border-color: #c0d2e4;
    &.active { background: #c9ddf3; border-color: #7fb2e0; color: #14508c; }
    &.pending { color: #b07800; } &.approved { color: #0a8f6e; } &.rejected { color: #d02828; } }

  .table-wrapper { background: var(--surface-1); border-color: var(--line-1); }
  .row-idx { color: #7a93ab; }
  .ll-copy-tag { color: #0a8f6e; background: rgba(10,143,110,.10); box-shadow: inset 0 0 0 1px rgba(10,143,110,.35); }
  .cell-text { box-shadow: inset 0 0 0 1px rgba(60,150,220,.35); background: rgba(60,150,220,.05); }
  .cell-text:hover { box-shadow: inset 0 0 0 1px #1f8fd8; background: rgba(60,150,220,.13); }
  .cell-input { border-color: #c0d2e4; color: #0a2858;
    &:focus { border-color: #1f8fd8; background: #dcebfa; } }
  .cell-text.cell-missing, .cell-text.cell-ort-n, .cell-input.cell-missing, .cell-input.cell-ort-n { background: #fbdede; color: #c0392b; }
  .cell-select :deep(.el-select__selected-item) { color: #0a2858 !important; }
  .judge-warn, .cell-ort-n { color: #d02828; }
  .judge-ok { color: #0a8f6e; }
  .judge-inserted { color: #0a6fd0; }
  .judge-pending { color: #b07800; }
  .src-ext { color: #b8860b; }

  .cal-panel { background: var(--surface-1); border-color: var(--line-1); box-shadow: 0 20px 60px rgba(20,60,110,.18); }
  .cal-title { color: #0a2858; }
  .cal-nav { background: var(--well); border-color: #c0d2e4; color: #2a5a86; &:hover { background: #cddcec; color: #0a2858; } }
  .cal-close { color: #5a7a9a; &:hover { color: #c0392b; } }
  .cal-clear { background: #fdecec; border-color: #f0b8b8; color: #c0392b; &:hover { background: #fadada; color: #a02020; } }
  .cal-week span { color: #5a7a9a; }
  .cal-day { color: #0a2858; &:hover { background: #cadcf0; color: #0a2858; } }
  .cal-day.is-out { color: #a8bccd; &:hover { background: none; color: #a8bccd; } }
  .cal-day.is-today { box-shadow: inset 0 0 0 1px #0a8f6e; color: #0a8f6e; }
  .cal-day.is-picked { background: #d4f0e6; color: #0a7a5e; }
  .cal-day.is-today.is-picked { background: #c4ecdf; color: #0a7a5e; }

  :deep(.el-table) { --el-table-bg-color: transparent; --el-table-tr-bg-color: #ffffff;
    --el-table-header-bg-color: #eef4fa; --el-table-border-color: var(--line-2);
    --el-table-row-hover-bg-color: #eaf3fc; --el-table-text-color: #0a2858; --el-table-header-text-color: #3a6a94; color: #0a2858; }
  :deep(.el-table__header-wrapper th) { background: var(--surface-2) !important; color: #3a6a94 !important; }
  :deep(.el-table__body tr:hover > td) { background: #dce8f6 !important; }
  :deep(.el-loading-mask) { background: rgba(233,240,248,.82) !important; }
  :deep(.row-pending td) { background: #fdf6e3 !important; }
  :deep(.row-approved td) { background: #eaf7f2 !important; }
  :deep(.row-rejected td) { background: #fdecec !important; }
  :deep(.row-top-priority td) { box-shadow: inset 3px 0 0 #0a8f6e; background: #e8f6f1 !important; }
  :deep(.row-bottom-priority td) { box-shadow: inset 3px 0 0 #9ab0c4; background: #f2f5f8 !important; }
  :deep(.row-longlife-copy td) { box-shadow: inset 3px 0 0 #0a8f6e; background: #eefaf5 !important; }
  :deep(.row-longlife-copy td .cell-text) { box-shadow: inset 0 0 0 1px rgba(10,143,110,.45); background: rgba(10,143,110,.06); }
  :deep(.row-external td) { background: #fdf3e2 !important; }
  :deep(.row-source-split td) { border-bottom: 2px solid rgba(10,143,110,.85) !important; }
  :deep(.el-select__wrapper) { background: var(--field) !important; box-shadow: 0 0 0 1px #c9daea inset !important; }
  :deep(.el-select__wrapper.is-focused) { box-shadow: 0 0 0 1px #1f8fd8 inset !important; }
  :deep(.el-select__wrapper:hover) { box-shadow: 0 0 0 1px #c9daea inset !important; }
  :deep(.el-select__selected-item) { color: #0a2858 !important; }

  :deep(.el-pagination__total), :deep(.el-pagination__jump) { color: #5a7a9a !important; }
  :deep(.el-pagination .el-pager li) { background: var(--surface-2) !important; color: #2a5a86 !important; }
  :deep(.el-pagination .el-pager li:hover) { background: #cddcec !important; color: #0a2858 !important; }
  :deep(.el-pagination .el-pager li.is-active) { background: #2a7fd0 !important; color: #ffffff !important; }
  :deep(.el-pagination .btn-prev), :deep(.el-pagination .btn-next) { background: var(--surface-2) !important; color: #2a5a86 !important; }
  :deep(.el-pagination .btn-prev:hover:not(:disabled)), :deep(.el-pagination .btn-next:hover:not(:disabled)) { background: #cddcec !important; color: #0a2858 !important; }
  :deep(.el-pagination .btn-prev:disabled), :deep(.el-pagination .btn-next:disabled) { background: #f2f5f8 !important; color: #a8bccd !important; }
}


</style>
