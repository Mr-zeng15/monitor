<template>
  <div class="preplan-view">
    <!-- 标题栏 -->
    <div class="pbar">
      <div class="pbar-left">
        <div class="ptag">PREPLAN</div>
        <div class="ptitle">预排筛选 · <span>S13_DPS + Monthly input target（S11）</span></div>
      </div>
      <div class="pright">
        <div class="bsm" :class="{act:activeTab==='S13_DPS'}" @click="activeTab='S13_DPS'">S13</div>
        <div class="bsm" :class="{act:activeTab==='Monthly_Input'}" @click="activeTab='Monthly_Input'">S11</div>
        <div class="bsm" :class="{act:activeTab==='all'}" @click="activeTab='all'">合并</div>
      </div>
    </div>

    <!-- 紧凑上传+操作栏 -->
    <div class="top-bar">
      <div class="upload-compact" @dragover.prevent @drop.prevent>
        <div class="uc-item" :class="{'has-file':fileAList.length,'is-error':fileAError,'drag-over':dragOverA}" @click="pickFile('A')" @dragenter.prevent="onDragEnter('A')" @dragleave="onDragLeave('A',$event)" @dragover.prevent @drop.prevent="onDropFiles('A',$event)" title="点击选择，或将 Excel 文件直接拖到此处">
          <span class="uc-tag tag-a">A</span><span class="uc-label">S13_DPS</span>
          <input ref="fileARef" type="file" accept=".xlsx,.xlsm,.xls" multiple class="hidden" @change="onFileAChange" />
          <button v-if="!fileAList.length" type="button" class="uc-pick" @click.stop="pickFile('A')">选择 / 拖拽</button>
          <template v-else><span class="uc-name" :title="fileAList.map(f=>f.name).join('、')">{{ fileAList.length }} 个文件</span><button type="button" class="uc-remove" @click.stop="removeFileA">✕</button></template>
          <span v-if="importAResult" class="uc-result">✓ {{ importAResult.stats.kept }}行</span>
          <span v-if="dragOverA" class="uc-drop-hint">松开导入文件</span>
        </div>
        <div class="uc-item" :class="{'has-file':fileBList.length,'is-error':fileBError,'drag-over':dragOverB}" @click="pickFile('B')" @dragenter.prevent="onDragEnter('B')" @dragleave="onDragLeave('B',$event)" @dragover.prevent @drop.prevent="onDropFiles('B',$event)" title="点击选择，或将 Excel 文件直接拖到此处">
          <span class="uc-tag tag-b">B</span><span class="uc-label">S11</span>
          <input ref="fileBRef" type="file" accept=".xlsx,.xlsm,.xls" multiple class="hidden" @change="onFileBChange" />
          <button v-if="!fileBList.length" type="button" class="uc-pick" @click.stop="pickFile('B')">选择 / 拖拽</button>
          <template v-else><span class="uc-name" :title="fileBList.map(f=>f.name).join('、')">{{ fileBList.length }} 个文件</span><button type="button" class="uc-remove" @click.stop="removeFileB">✕</button></template>
          <span v-if="importBResult" class="uc-result">✓ {{ importBResult.stats.kept }}行</span>
          <span v-if="dragOverB" class="uc-drop-hint">松开导入文件</span>
        </div>
      </div>
      <div class="top-actions">
        <button type="button" class="run-btn primary" :disabled="importingA||importingB" @click="handleImportA">{{ importingA?'导入A中...':'导入 A' }}</button>
        <button v-if="importingA" type="button" class="run-btn danger" @click="cancelImport('A')">取消</button>
        <button type="button" class="run-btn primary green" :disabled="importingA||importingB" @click="handleImportB">{{ importingB?'导入B中...':'导入 B' }}</button>
        <button v-if="importingB" type="button" class="run-btn danger" @click="cancelImport('B')">取消</button>
        <el-select v-model="planYear" size="small" class="year-sel" popper-class="app-select-popper" @change="onYearChange">
          <el-option v-for="y in yearOptions" :key="y" :label="String(y)" :value="y" />
        </el-select>
        <el-select v-model="planYm" size="small" class="month-sel" popper-class="app-select-popper" @change="onMonthChange">
          <el-option label="全部月份" :value="0" />
          <el-option v-for="o in ymOptions" :key="o.ym" :label="`${o.label}（${o.count}）`" :value="o.ym" />
        </el-select>
        <button type="button" class="run-btn sec" :disabled="!total" @click="handleExport">导出</button>
        <button type="button" class="naming-gear" title="自定义导出文件名" @click="openNaming('preplan')"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M19.14 12.94a7.5 7.5 0 0 0 .05-1.88l2.03-1.58a.5.5 0 0 0 .12-.64l-1.92-3.32a.5.5 0 0 0-.6-.22l-2.39.96a7.03 7.03 0 0 0-1.62-.94l-.36-2.54a.5.5 0 0 0-.5-.42h-3.84a.5.5 0 0 0-.5.42l-.36 2.54c-.59.24-1.13.55-1.62.94l-2.39-.96a.5.5 0 0 0-.6.22L2.74 8.84a.5.5 0 0 0 .12.64l2.03 1.58a7.5 7.5 0 0 0 0 1.88l-2.03 1.58a.5.5 0 0 0-.12.64l1.92 3.32c.13.22.4.31.6.22l2.39-.96c.49.39 1.03.7 1.62.94l.36 2.54c.04.24.25.42.5.42h3.84c.25 0 .46-.18.5-.42l.36-2.54c.59-.24 1.13-.55 1.62-.94l2.39.96c.2.09.47 0 .6-.22l1.92-3.32a.5.5 0 0 0-.12-.64l-2.03-1.58zM12 15.5A3.5 3.5 0 1 1 12 8.5a3.5 3.5 0 0 1 0 7z"/></svg></button>
        <ExportNamingDialog v-model="namingOpen" :type="namingType" :ctx="exportNamingCtx" />
        <button type="button" class="run-btn sec" :disabled="mtdSyncing" @click="handleSyncMtd">{{ mtdSyncing ? '同步中...' : '同步MTD' }}</button>
        <button type="button" class="run-btn sec" :disabled="refreshing" @click="handleRefreshEntry">{{ refreshing ? '刷新中...' : '刷新' }}</button>
        <button type="button" class="run-btn sec" :disabled="!total" @click="goDecisionReview">导入到审核决议中心</button>
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
        <el-popover placement="bottom-end" width="260" trigger="click" popper-class="app-popover">
          <template #reference>
            <button type="button" class="run-btn sec">列显示</button>
          </template>
          <div class="col-picker">
            <el-checkbox v-for="c in TABLE_COLUMNS" :key="c.key" :model-value="!hiddenCols.has(c.key)" @change="(v) => toggleCol(c.key, v)">{{ c.label }}</el-checkbox>
          </div>
        </el-popover>
        <button type="button" class="run-btn danger" @click="handleClear">清空</button>
      </div>
    </div>

    <div v-if="errorMsg" class="err-bar"><span class="err-icon">⚠</span><span class="err-text">{{ errorMsg }}</span><button type="button" class="err-close" @click="errorMsg=''">✕</button></div>

    <!-- 滚动区 -->
    <div class="scroll-area">
      <!-- 规则行 -->
      <div class="rule-bar">
        <div class="rule-bar-left">
          <span class="rule-bar-title">ORT 规则</span>
          <span class="rule-bar-pills">
            <span v-for="rule in ortRules" :key="rule.id" class="rule-pill-xs" :class="{off:!rule.is_active}" @click="openOrtForm(rule)" :title="rule.remark||'点击编辑'">
              {{ rule.type_name || '全部' }} {{ rule.operator }}{{ rule.threshold }}<em class="rp-source">{{ rule.source==='S13'?'S13':rule.source==='MONTHLY'?'S11':'A' }}</em>
            </span>
          </span>
        </div>
        <div class="rule-bar-right">
          <span class="rt-hint">共 <strong>{{ total }}</strong> 条 · {{ activeTabLabel }}</span>
          <el-radio-group v-model="statusFilter" size="small">
            <el-radio-button value="kept">通过</el-radio-button>
            <el-radio-button value="filtered">过滤</el-radio-button>
            <el-radio-button value="">全部</el-radio-button>
          </el-radio-group>
          <button type="button" class="row-btn" @click="openOrtForm(null)">+ 规则</button>
        </div>
      </div>

      <!-- ========= 预排表格（合并视图 A+B 分隔线 / 单 Tab 视图共用，切换只换数据不重建 DOM） ========= -->
      <div class="table-section" v-if="tableData.length>0">
        <!-- ★ Ctrl+F 搜索条（P1-2） -->
        <div v-if="searchVisible" class="table-search-bar">
          <input v-model="searchKeyword" @input="doSearch()" placeholder="输入关键字搜索（Enter 下一个 / Shift+Enter 上一个 / Esc 关闭）" class="ts-input" />
          <span class="ts-count">{{ matches.length ? (activeIdx + 1) + '/' + matches.length : '0 个匹配' }}</span>
          <button type="button" class="ts-btn" @click="jumpNext(1)">↓</button>
          <button type="button" class="ts-btn" @click="jumpNext(-1)">↑</button>
          <button type="button" class="ts-btn ts-close" @click="closeSearch()">✕</button>
        </div>
        <div ref="tableWrapRef" class="table-wrapper" @mousedown="onDragStart">
          <el-table ref="tableRef" :data="tableData" v-loading="loading" style="width:100%" size="small" :row-class-name="getRowClass" :cell-class-name="searchCellClass" :row-key="(r)=>r.id" class="preplan-table" :max-height="tableMaxH">
            <el-table-column label="序号" width="58" align="center"><template #default="{row,$index}"><span class="row-idx">{{ (currentPage-1)*pageSize + $index + 1 }}</span><span v-if="row.exported" class="exp-tag" title="已导出到审核决议中心">已导出</span></template></el-table-column>
            <el-table-column v-for="col in activeColumns" :key="col.key" :prop="col.key" :label="col.label" :min-width="col.width||100" align="center" :class-name="col.key==='source' ? 'col-source' : ''">
              <template #default="{row}">
                <!-- ★ 懒编辑：默认显示纯文本(轻量)，点击才渲染编辑组件；送样日期点击弹日历 -->
                <div v-if="isEditable(row,col.key)" class="cell-inline-edit" @click="startEdit(row,col.key,$event)">
                  <el-select v-if="isEditing(row,col.key) && (col.key==='qe_requirement'||col.key==='gpc_reply')" :model-value="row[col.key]||''" @update:model-value="saveCell(row,col.key,$event)" @click.stop size="small" clearable placeholder=" " class="cell-select" popper-class="app-select-popper"><el-option value="Y" label="Y"/><el-option value="N" label="N"/><el-option value="待定" label="待定"/></el-select>
                  <el-select v-else-if="isEditing(row,col.key) && col.key==='oqc_hold'" :model-value="row[col.key]||''" @update:model-value="saveCell(row,col.key,$event)" @click.stop size="small" clearable placeholder=" " class="cell-select" popper-class="app-select-popper"><el-option value="Y" label="Y"/><el-option value="N" label="N"/></el-select>
                  <el-select v-else-if="isEditing(row,col.key) && col.key==='type'" :model-value="row[col.key]||''" @update:model-value="saveCell(row,col.key,$event)" @click.stop size="small" clearable placeholder=" " class="cell-select" popper-class="app-select-popper"><el-option value="PD" label="PD"/><el-option value="TV" label="TV"/><el-option value="DT" label="DT"/><el-option value="BIM" label="BIM"/><el-option value="SET" label="SET"/></el-select>
                  <input v-else-if="isEditing(row,col.key) && col.key!=='sample_date'" :value="getEditVal(row,col.key)" @blur="saveCell(row,col.key,$event)" @keydown.enter="saveCell(row,col.key,$event)" @click.stop class="cell-input" :class="cellCls(row,col.key)" />
                  <span v-else class="cell-text" :class="cellCls(row,col.key)">{{ col.key==='type' && row.is_plan_external && !row.type ? '✎ 回填' : formatCell(row[col.key]) }}</span>
                </div>
                <!-- ★ 2026-09-23：来源文件列加 title —— 该列单行省略（见 .col-source 样式），
                     文件名较长时靠悬停查看全名。「计划外」行显示的是标签、无文件名可取，故不给 title。 -->
                <span v-else :class="cellCls(row,col.key)" :title="(col.key==='source' && !row.is_plan_external) ? formatCell(row[col.key]) : ''">
                  <span v-if="col.key==='source' && row.is_plan_external" class="src-ext">计划外{{ row.mtd_source ? '·' + row.mtd_source.toUpperCase() : '' }}</span>
                  <!-- ★ Judge 列不显示内容（用户要求留空，列保留） -->
                  <template v-else-if="col.key !== 'judge'">{{ formatCell(row[col.key]) }}</template>
                </span>
              </template>
            </el-table-column>
            <el-table-column label="过滤原因" width="180" align="center" v-if="statusFilter==='filtered'"><template #default="{row}"><span class="filter-reason">{{ row.filter_reason||'-' }}</span></template></el-table-column>
          </el-table>
        </div>
        <div class="pagination-bar">
          <span v-if="activeTab==='all'" class="pagination-info">A: <b class="src-a">{{ countA }}</b> 行 &nbsp;|&nbsp; B: <b class="src-b">{{ countB }}</b> 行 &nbsp;|&nbsp; 合计 <b class="total">{{ total }}</b> 条</span>
          <span v-else class="pagination-info">共 <b class="total">{{ total }}</b> 条</span>
          <el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :page-sizes="[20,50,100,200]" :total="total" layout="sizes,prev,pager,next" size="small" />
        </div>
      </div>

      <div class="empty-state" v-else-if="!loading"><span class="empty-icon">📂</span><span class="empty-text">暂无数据，请上传并导入 Excel</span></div>
    </div>

    <!-- ORT 弹窗 -->
    <div class="runov" :class="{show:ortFormVisible}" @click.self="ortFormVisible=false">
      <div class="runbox">
        <div class="runbox-close" @click="ortFormVisible=false">✕</div>
        <div class="run-title">{{ editingOrtRule?'编辑 ORT 规则':'新增 ORT 规则' }}</div>
        <div class="run-subtitle">设置 Type / 来源 / 阈值</div>
        <div class="form-section">
          <div class="form-grid">
            <div class="form-row"><label class="form-lbl">Type</label><select v-model="ortForm.type_name" class="form-select"><option value="">全部（所有Type）</option><option value="S13">S13</option><option value="PD">PD</option><option value="TV">TV</option><option value="DT">DT</option><option value="BIM">BIM</option><option value="SET">SET</option></select></div>
            <div class="form-row"><label class="form-lbl">来源</label><select v-model="ortForm.source" class="form-select"><option value="S13">S13_DPS</option><option value="MONTHLY">Monthly_Input</option><option value="ALL">全部</option></select></div>
            <div class="form-row"><label class="form-lbl">运算符</label><select v-model="ortForm.operator" class="form-select"><option value=">=">>=</option><option value=">">></option><option value="<="><=</option><option value="<"><</option><option value="==">=</option></select></div>
            <div class="form-row"><label class="form-lbl">阈值</label><input v-model.number="ortForm.threshold" type="text" inputmode="numeric" class="form-input" placeholder="如300" /></div>
            <div class="form-row"><label class="form-lbl">启用</label><label class="form-check"><input type="checkbox" v-model="ortForm.is_active" /><span>{{ ortForm.is_active?'已启用':'已停用' }}</span></label></div>
            <div class="form-row" style="grid-column:span 2"><label class="form-lbl">备注</label><input v-model="ortForm.remark" class="form-input" placeholder="可选" /></div>
          </div>
        </div>
        <div class="run-btns">
          <button type="button" class="run-btn sec" @click="ortFormVisible=false">取消</button>
          <button type="button" class="run-btn primary" @click="saveOrtRule">保存</button>
          <button v-if="editingOrtRule" type="button" class="run-btn danger" @click="handleDeleteOrtRule(editingOrtRule);ortFormVisible=false">删除</button>
        </div>
      </div>
    </div>

    <!-- ★ 送样日期：自绘深色主题日历弹层（锚定在输入框下方弹出） -->
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

    <!-- ★ 导入「归属预排月份」确认（2026-09-20）：默认按文件自动识别，可手动指定 -->
    <div v-if="importMonthOpen" class="im-mask" @click.self="importMonthOpen=false">
      <div class="im-panel">
        <div class="im-head">
          <span class="im-title">确认导入{{ importMonthSlot==='A' ? ' S13_DPS（Plan A）' : ' S11（Monthly）' }}</span>
          <button type="button" class="im-close" @click="importMonthOpen=false">✕</button>
        </div>
        <div class="im-body">
          <div class="im-tip">本次数据要归到哪个「预排月份」？同月同名文件互相覆盖，不同月份互不影响。</div>
          <div class="im-rows">
            <label class="im-opt" :class="{ on: importMonthMode==='auto' }" @click="importMonthMode='auto'">
              <span class="im-radio" :class="{ on: importMonthMode==='auto' }"></span>
              <span class="im-opt-txt">
                <b>按文件自动识别</b>
                <i>推荐：按表格「预排月份」列 → 文件名日期码 → 当前月 依次判定</i>
              </span>
            </label>
            <label class="im-opt" :class="{ on: importMonthMode==='manual' }" @click="importMonthMode='manual'">
              <span class="im-radio" :class="{ on: importMonthMode==='manual' }"></span>
              <span class="im-opt-txt">
                <b>手动指定月份</b>
                <i>用于补做历史月份 / 文件名不含日期码等情况</i>
              </span>
            </label>
          </div>
          <div v-if="importMonthMode==='manual'" class="im-sel-row">
            <span class="im-sel-label">归属月份</span>
            <el-select v-model="importMonthYm" size="small" class="im-sel" popper-class="app-select-popper">
              <el-option v-for="o in importYmChoices" :key="o.ym" :label="o.label" :value="o.ym" />
            </el-select>
          </div>
        </div>
        <div class="im-foot">
          <button type="button" class="run-btn sec" @click="importMonthOpen=false">取消</button>
          <button type="button" class="run-btn primary" @click="confirmImportMonth">开始导入</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onBeforeUnmount, onActivated, onDeactivated, watch } from 'vue'
import { useRouter } from 'vue-router'
defineOptions({ name: 'PreplanView' })
import { ElMessage, ElMessageBox } from 'element-plus'
import axios from 'axios'
// ★ 表格列定义从共享配置导入（与审核决议页方案2 保持一致，保证"原封不动"）
import { TABLE_COLUMNS as SHARED_COLUMNS } from '../config/preplanColumns'
import { useTableSearch } from '../composables/useTableSearch'
import { useFitHeight } from '../composables/useFitHeight'
import { buildFileName, monthLabelFromYm, fullLabelFromYm } from '../composables/useExportNaming.js'
import ExportNamingDialog from '../components/common/ExportNamingDialog.vue'
const router = useRouter()

const API = import.meta.env.VITE_API_BASE || '/api'
const planYear = ref(new Date().getFullYear())
// ★ 2026-09-20「按月分类」：planYm = 预排年月（YYYYMM）；0 = 全部月份（不按月收窄，兼容旧视图）。
//   公司每月都要筛选计划、同月还可能要处理未来数月的计划，仅靠「年」会让多个月的数据混在一起
//   且同名文件换月导入会互相顶掉。现在月份升为一级维度：查询/清空/导出/定版/重算全部可选月份。
const planYm = ref(0)
const ymOptions = ref([])          // 后端 _ym_summary 返回：{ ym, label, count }
let ymInited = false               // 首次拿到月份清单时，默认切到最新的那个月
function ymParam() { return planYm.value ? planYm.value : undefined }
function onMonthChange() {
  cacheLoaded.value.clear()        // 月份变了，缓存的「年:视图」不再适用
  loadData()
}
// ★ 年份变了：清空月份清单与视图缓存，让下一次加载重新决定默认月份
function onYearChange() {
  ymInited = false
  ymOptions.value = []
  planYm.value = 0
  cacheLoaded.value.clear()
  loadData()
}
// ★ ym(YYYYMM) → 可读中文，口径与后端 _ym_summary 的 label 一致（202609 → '2026年9月'）
function ymText(ym){ return ym ? `${Math.floor(ym / 100)}年${ym % 100}月` : '全部月份' }
const ymLabel = computed(() => {
  const hit = ymOptions.value.find(o => o.ym === planYm.value)
  return hit ? hit.label : ymText(planYm.value)
})

// ★ 2026-09-20：导出命名的「当前页面上下文」——真实导出与命名配置弹窗的实时预览共用这一份，
//   于是预览里看到的 {year} / {month} 就是导出文件名里真正会用的值（此前弹窗预览用的是写死样本）。
const exportNamingCtx = computed(() => ({
  year: planYear.value || '全部',
  month: monthLabelFromYm(planYm.value),
  label: fullLabelFromYm(planYm.value, planYear.value ? `${planYear.value}年` : '全部'),
}))

// ★ 导出命名菜单（2026-09-18）：每个导出按钮旁的小齿轮打开对应类型的命名配置弹窗
const namingOpen = ref(false)
const namingType = ref('preplan')
function openNaming(t) { namingType.value = t; namingOpen.value = true }
const yearOptions = computed(() => Array.from({length:7},(_,i)=>new Date().getFullYear()-3+i))
const activeTab = ref('all')
const activeTabLabel = computed(() => ({S13_DPS:'S13',Monthly_Input:'S11',all:'合并'}[activeTab.value]||''))

const fileARef=ref(null),fileBRef=ref(null),fileAList=ref([]),fileBList=ref([]),fileAError=ref(''),fileBError=ref('')
// ★ 拖拽导入：拖入高亮状态（用计数器规避子元素 dragleave 闪烁）
const dragOverA=ref(false),dragOverB=ref(false)
let dragDepthA=0,dragDepthB=0
const importingA=ref(false),importingB=ref(false),importAResult=ref(null),importBResult=ref(null)
const refreshing=ref(false)
const mtdSyncing=ref(false)
const loading=ref(false),tableData=ref([]),total=ref(0),currentPage=ref(1),pageSize=ref(50),statusFilter=ref('kept'),errorMsg=ref('')
const countA=ref(0),countB=ref(0)
// ★ 全量数据缓存（本地过滤/分页用，避免大列表切换状态时重复请求与全量渲染）
const cacheA=ref([]),cacheB=ref([])
const cacheLoaded=ref(new Set())
// ★ Ctrl+F 表格搜索（P1-2）：搜索范围 = 当前筛选状态下的全量行（跨页）
//   v2：currentPage 由下方 watch 驱动 applyView 重算分页 → 搜索切页真正生效；
//       isActive 供当前定位行加强高亮（闪烁）。
const tableRef = ref(null)
const tableWrapRef = ref(null)
const tableMaxH = useFitHeight(tableWrapRef)
const { visible: searchVisible, keyword: searchKeyword, matches, activeIdx,
        doSearch, jumpNext, close: closeSearch, isHit, isActive, searchCellClass, onKeydown: onTableSearchKey } = useTableSearch({
  getRows: getFilteredList,
  // ★ 只在表格展示的列内匹配（不扫 id/时间戳/布尔标志等隐藏字段，防误命中）
  //   末位 filter_reason = 本页 statusFilter==='filtered' 时的「过滤原因」列，不在共享列内
  searchKeys: [...SHARED_COLUMNS.map(c => c.key), 'filter_reason'],
  tableRef,
  currentPage,
  pageSize,
  pageCount: () => Math.max(1, Math.ceil(total.value / pageSize.value)),
})

const ortRules=ref([]),ortFormVisible=ref(false),editingOrtRule=ref(null)
const ortForm=reactive({type_name:'',source:'ALL',operator:'>=',threshold:300,is_active:true,remark:''})

const TABLE_COLUMNS = SHARED_COLUMNS
// ★ 列可见性控制：默认显示全部列，可隐藏不常用列以减少渲染开销
const hiddenCols = ref(new Set())
const activeColumns = computed(() => TABLE_COLUMNS.filter(c => !hiddenCols.value.has(c.key)))
function toggleCol(key, show){
  const s = new Set(hiddenCols.value)
  if (show) s.delete(key); else s.add(key)
  hiddenCols.value = s
}
// ★ 2026-09-23：'judge' 移出可编辑集合 —— 模板里「Judge 列留空」的判断在【非可编辑分支】
//   （见模板 `v-else-if="col.key !== 'judge'"`，用户要求该列只占位、不显示内容）。
//   根因：judge 混进过本集合 → isEditable() 恒为 true → 模板走**可编辑分支** →
//   把库里的 judge 值（如 预警）显示出来了，导致「预排页莫名出现 judge」。
//   移除本项后，judge 落到 v-else 分支，被 `col.key !== 'judge'` 拦下 → 恢复留空。
const editableKeys=new Set(['gpc_reply','oqc_hold','q_order','box_number','sample_date','qe_requirement','qe_remark','ra_remark'])
// ★ mtd_output(MTD OUTPUT监控) 不在可编辑集合内：该列由「同步MTD」回填，禁止手动修改

// ★ 类 Excel 筛选（Task 2）：客户端按列值过滤，与页面视图一致后跟随导出
const filterVisible = ref(false)
const TYPE_OPTIONS = ['PD','TV','DT','BIM','SET']
const colFilters = reactive({ types: [], fab: '', customer: '', keyword: '' })
const hasColFilter = computed(() => colFilters.types.length>0 || !!colFilters.fab.trim() || !!colFilters.customer.trim() || !!colFilters.keyword.trim())
// ★ 导出严格跟随页面：缓存当前视图过滤+排序后的全部行（非分页），供导出使用
const exportRows = ref([])

// ★ 任务1：Q工单优先判定 —— QE 与 GPC 均确认需求(是/Y)，或其中之一有 Q工单(q_order 非空)
function isYes(v){
  const s = String(v ?? '').trim().toLowerCase()
  return ['是', 'y', 'yes', 'true', '1'].includes(s)
}
function isQPriority(r){
  const qe=isYes(r.qe_requirement)
  const gpc=isYes(r.gpc_reply)
  const bothConfirmed = qe && gpc
  const hasOrder = !!(r.q_order && String(r.q_order).trim())
  return bothConfirmed || hasOrder
}
// ★ 优先级排序：保持来源分组(S13 在前、Monthly 在后)，组内 Q工单优先组排最前，再按序号
const SRC_ORDER = { S13_DPS: 0, Monthly_Input: 1 }
function sortRows(list){
  return list.slice().sort((a,b)=>{
    const sa=SRC_ORDER[a.source]??1, sb=SRC_ORDER[b.source]??1
    if(sa!==sb) return sa-sb
    const pa=isQPriority(a)?1:0, pb=isQPriority(b)?1:0
    if(pa!==pb) return pb-pa
    return (a.serial_number||0)-(b.serial_number||0)
  })
}
// ★ 当前视图的完整过滤+排序结果（不含分页），供显示与导出共用
function getFilteredList(){
  let src
  if(activeTab.value==='all') src=[...cacheA.value, ...cacheB.value]
  else if(activeTab.value==='S13_DPS') src=cacheA.value
  else src=cacheB.value
  let list = src
  // ★ 只按 status 分组，不再掺入 ort_ok 判定（2026-09-15 修正）。
  //   背景：后端「是否满足ORT量」ort_ok 现已与筛选结果严格绑定（DPS 预测量 vs ORT 规则，
  //   通过=Y / 未通过=N 并被 filter_ort_n 置为 filtered），kept ⟺ ort_ok!=='N' 由后端保证。
  //   旧写法在这里再按 ort_ok!=='N' 二次过滤，会在 ort_ok 被重算成 N 时把 kept 行悄悄藏掉
  //   ——表现为「导入后看得到、切个页面回来少一截」，且头部行数与表格对不上。
  if(statusFilter.value==='kept') list=list.filter(r=>r.status==='kept')
  else if(statusFilter.value==='filtered') list=list.filter(r=>r.status==='filtered')
  // ★ 类 Excel 筛选
  if(colFilters.types.length) list=list.filter(r=>colFilters.types.includes((r.type||'').trim()))
  if(colFilters.fab.trim()){ const k=colFilters.fab.trim().toLowerCase(); list=list.filter(r=>(r.fab||'').toLowerCase().includes(k)) }
  if(colFilters.customer.trim()){ const k=colFilters.customer.trim().toLowerCase(); list=list.filter(r=>(r.customer||'').toLowerCase().includes(k)) }
  if(colFilters.keyword.trim()){ const k=colFilters.keyword.trim().toLowerCase(); list=list.filter(r=>(r.pn||'').toLowerCase().includes(k)||(r.model||'').toLowerCase().includes(k)) }
  // ★ 优先级排序（任务1）
  list = sortRows(list)
  return list
}
function applyColFilter(){ filterVisible.value=false; currentPage.value=1; applyView() }
function clearColFilter(){ colFilters.types=[]; colFilters.fab=''; colFilters.customer=''; colFilters.keyword=''; currentPage.value=1; applyView() }
// ★ 点击屏幕其他区域关闭筛选菜单（弹层自身/内部下拉/触发按钮除外，触发按钮由 @click 开合）
function onDocClickForFilter(e){
  if(!filterVisible.value) return
  const t = e.target
  if(!t || !t.closest) return
  if(t.closest('.el-popper') || t.closest('.filter-ref')) return
  filterVisible.value = false
}
// ★ 计划外行允许回填 Type（回填后后端自动匹配 ORT 规则重算达标状态）
function isEditable(row,k){return editableKeys.has(k)||(k==='type'&&row.is_plan_external)}
function getEditVal(row,k){return row[k]||''}
// ★ 懒编辑：只有点击的单元格才渲染编辑组件，其余显示纯文本（大幅降低表格渲染开销）
const editingCell=ref(null)
function isEditing(row,key){return editingCell.value && editingCell.value.rowId===row.id && editingCell.value.key===key}
function startEdit(row,key,e){
  if(key==='sample_date'){ openCal(row,e); return }
  editingCell.value={rowId:row.id,key}
}
// ★ 2026-09-16 修复「改完切页/切标签后修改被还原」：
//   applyView 会给「来源分界行」做浅拷贝（{...pageList[localIdx], _isSourceChange:true}），
//   那一行在模板里的 row 是副本、不是 cache 里的原对象。旧写法只执行 row[k]=v，
//   改动落在副本上 → 当场看得到，但下一次 applyView（切分页/切标签/切页面回来）由 cache
//   重新派生 tableData 时就被还原，表现为"改完切一下页就没了"。
//   现改为同时写回 cacheA/cacheB 中 id 相同的原对象，与审核决议页的 saveCell 口径一致。
async function saveCell(row,k,e){
  let v=e&&typeof e==='object'&&e.target!==undefined?e.target.value:e
  if(v===null||v===undefined)v=''
  if(row[k]===v){editingCell.value=null;return}
  try{
    await axios.post(`${API}/preplan/update/${row.id}/`,{[k]:v})
    const src=cacheA.value.find(r=>r.id===row.id)||cacheB.value.find(r=>r.id===row.id)
    if(src)src[k]=v            // 写回缓存原对象（切页/切标签后才不会回退）
    row[k]=v                   // 同步当前行（该行可能是浅拷贝）
    if(row.is_plan_external&&k==='type')await loadData()
  }catch(err){ElMessage.error('保存失败')}
  finally{editingCell.value=null}
}

const MISSING_LABELS=['52阶料号','Model','满箱量','客户']
// ★ 性能优化：预计算 key→label 映射，避免每格渲染时 TABLE_COLUMNS.find 遍历
const COLUMN_LABEL_MAP=Object.fromEntries(TABLE_COLUMNS.map(c=>[c.key,c.label]))
function cellCls(row,key){
  const cls=[];const missing=Array.isArray(row.missing_fields)?row.missing_fields:[]
  const label=COLUMN_LABEL_MAP[key]||key
  // ★ S13 本身没有 52阶料号列，缺失时直接留空，不标红
  const skipMissing = key==='material_code_52' && row.source==='S13_DPS'
  if(!skipMissing && (missing.includes(label)||(MISSING_LABELS.includes(label)&&missing.length>0)))cls.push('cell-missing')
  if(key==='ort_ok'&&row.ort_ok==='N')cls.push('cell-ort-n')
  // ★ 2026-09-23：不再给 judge 列标红 —— 该列要求留空。
  //   为什么必须一起删：.cell-ort-n 带 `background + padding + display:inline-block`，
  //   只把文字去掉仍会渲染出一个**红色空块**，看着还是"有东西"，与「留空」冲突。
  return cls
}
function getRowClass({row}){
  const cls=[];if(row.status==='filtered')cls.push('row-filtered');if(activeTab.value==='all'&&row._isSourceChange)cls.push('row-source-split');if(row.is_plan_external)cls.push('row-external');if(row.exported)cls.push('row-exported');if(isHit(row))cls.push('search-hit');if(isActive(row))cls.push('search-active');return cls
}
function formatCell(v){if(v===null||v===undefined)return'';if(typeof v==='string'){const t=v.trim();return(!t||t==='undefined'||t==='null'||t==='NaN')?'':t}return String(v)}

function onFileAChange(e){const files=Array.from(e.target.files||[]);if(!files.length)return;const ok=files.filter(f=>/\.(xlsx|xlsm|xls)$/i.test(f.name));fileAError.value=ok.length!==files.length?('有 '+(files.length-ok.length)+' 个文件格式不正确'):'';fileAList.value=ok;importAResult.value=null;if(fileARef.value)fileARef.value.value=''}
function onFileBChange(e){const files=Array.from(e.target.files||[]);if(!files.length)return;const ok=files.filter(f=>/\.(xlsx|xlsm|xls)$/i.test(f.name));fileBError.value=ok.length!==files.length?('有 '+(files.length-ok.length)+' 个文件格式不正确'):'';fileBList.value=ok;importBResult.value=null;if(fileBRef.value)fileBRef.value.value=''}
// ★ 点叉叉直接移除该文件：清除该来源「未导出到审核决议」的预排数据 + 清空本地选择；
//   已导出到审核决议的数据不受影响（与决议中心解耦，2026-09-04）
async function removeFileA(){
  try{ await ElMessageBox.confirm('确定移除 S13_DPS 文件及其预排数据？已导出到审核决议的数据不受影响', '移除文件', { type: 'warning' }) }catch{ return }
  try{
    const res=await axios.post(`${API}/preplan/clear/`, { year: planYear.value, source: 'S13_DPS', ym: ymParam() })
    fileAList.value=[];importAResult.value=null;if(fileARef.value)fileARef.value.value=''
    activeTab.value='all'  // ★ 切回合并视图，避免停留在单视图导致表格看起来被清空
    // ★ 2026-09-21：不再无条件弹「已移除」——后端一条没删时给告警并说明生效范围
    reportClearOutcome(res.data||{}, `${ymLabel.value} S13_DPS`, '已移除 S13_DPS 文件（审核决议数据不受影响）')
  }catch(e){
    console.error('[预排] 移除 S13 文件失败：', e.response?.status, e.response?.data||e.message)
    ElMessage.error('移除失败：' + ((e.response?.data&&(e.response.data.error||e.response.data.detail)) || e.message))
  }finally{
    await loadData()   // ★ 无论成败都刷新
  }
}
async function removeFileB(){
  try{ await ElMessageBox.confirm('确定移除 Monthly input target 文件及其预排数据？已导出到审核决议的数据不受影响', '移除文件', { type: 'warning' }) }catch{ return }
  try{
    const res=await axios.post(`${API}/preplan/clear/`, { year: planYear.value, source: 'Monthly_Input', ym: ymParam() })
    fileBList.value=[];importBResult.value=null;if(fileBRef.value)fileBRef.value.value=''
    activeTab.value='all'  // ★ 切回合并视图
    // ★ 2026-09-21：不再无条件弹「已移除」——后端一条没删时给告警并说明生效范围
    reportClearOutcome(res.data||{}, `${ymLabel.value} Monthly_Input`, '已移除 S11 文件（审核决议数据不受影响）')
  }catch(e){
    console.error('[预排] 移除 S11 文件失败：', e.response?.status, e.response?.data||e.message)
    ElMessage.error('移除失败：' + ((e.response?.data&&(e.response.data.error||e.response.data.detail)) || e.message))
  }finally{
    await loadData()   // ★ 无论成败都刷新
  }
}
// ★ 单击即打开文件选择：整个上传框可点；先清空 input.value 保证同一文件也能触发 change
function pickFile(kind){
  const el = kind==='A' ? fileARef.value : fileBRef.value
  if(el){ el.value=''; el.click() }
}

// ★ 拖拽导入：把 Excel 文件拖到 S13/S11 上传框即加入待导入列表（追加+按文件名去重）
function onDragEnter(kind){
  if(kind==='A'){ dragDepthA++; dragOverA.value=true }
  else{ dragDepthB++; dragOverB.value=true }
}
function onDragLeave(kind, e){
  // 子元素间 dragleave 会闪烁：离开当前框及其子元素范围才熄灭高亮
  if(kind==='A'){ if(--dragDepthA<=0){ dragDepthA=0; dragOverA.value=false } }
  else{ if(--dragDepthB<=0){ dragDepthB=0; dragOverB.value=false } }
}
function onDropFiles(kind, e){
  dragDepthA=0;dragDepthB=0;dragOverA.value=false;dragOverB.value=false
  const raw=Array.from((e.dataTransfer&&e.dataTransfer.files)||[])
  const ok=raw.filter(f=>/\.(xlsx|xlsm|xls)$/i.test(f.name))
  if(!ok.length){
    const msg=raw.length?('有 '+(raw.length-ok.length)+' 个文件格式不正确（仅支持 .xlsx/.xlsm/.xls）'):'请拖入 Excel 文件（.xlsx/.xlsm/.xls）'
    if(kind==='A')fileAError.value=msg;else fileBError.value=msg
    return
  }
  if(kind==='A'){
    const seen=new Set(fileAList.value.map(f=>f.name));const added=ok.filter(f=>!seen.has(f.name))
    fileAList.value=[...fileAList.value,...added];fileAError.value='';importAResult.value=null
    ElMessage.success(`已添加 ${added.length} 个 S13_DPS 文件，点击「导入 A」开始`)
  }else{
    const seen=new Set(fileBList.value.map(f=>f.name));const added=ok.filter(f=>!seen.has(f.name))
    fileBList.value=[...fileBList.value,...added];fileBError.value='';importBResult.value=null
    ElMessage.success(`已添加 ${added.length} 个 S11 文件，点击「导入 B」开始`)
  }
}

// ★ 导入可中断：导入前生成 task_id 随请求发给后端（后端以此注册任务），
//   导入中可点「取消」→ POST import-cancel → 后端在写入前中止并回滚，不会产生脏数据
const importTaskId=ref('')
// ★ 2026-09-20 导入「归属预排月份」确认：
//   - 默认「按文件自动识别」——后端按 表格预排月份列 > 文件名日期码 > 当前月 依次定夺，
//     真实数据带「预排月份」列时最准，且不会因文件名缺日期码而静默落到当月；
//   - 可切「手动指定」强制归到某个月（例如手工补做历史月份的计划）。
//   目的：堵住「同名文件跨月导入互相顶掉」，并让每月数据天然分桶。
const importMonthOpen=ref(false)
const importMonthSlot=ref('A')
const importMonthMode=ref('auto')
const importMonthYm=ref(0)
// 手选月份下拉：以当前月为基准前后各 12 个月，够覆盖 N+1/N+2 与补做历史
const importYmChoices=computed(()=>{
  const out=[];const n=new Date();let y=n.getFullYear(),m=n.getMonth()+1
  for(let i=12;i>=-12;i--){
    let yy=y,mm=m+i
    while(mm<=0){mm+=12;yy-=1}
    while(mm>12){mm-=12;yy+=1}
    out.push({ym:yy*100+mm,label:`${yy}年${mm}月`})
  }
  return out.sort((a,b)=>b.ym-a.ym)
})
function openImportConfirm(slot){
  const list = slot==='A' ? fileAList.value : fileBList.value
  if(!list.length){ElMessage.warning(`请先选择 ${slot==='A'?'S13_DPS':'S11'} 文件（可多选）`);return}
  importMonthSlot.value=slot
  importMonthMode.value='auto'
  // 手动指定时的默认月份 = 系统规则（S13=N+2 / S11=N+1），用户可改
  const n=new Date();let y=n.getFullYear(),mm=n.getMonth()+1+(slot==='A'?2:1)
  while(mm>12){mm-=12;y+=1}
  importMonthYm.value=y*100+mm
  importMonthOpen.value=true
}
function confirmImportMonth(){
  importMonthOpen.value=false
  const override = importMonthMode.value==='manual' ? importMonthYm.value : 0
  if(importMonthSlot.value==='A') doImportA(override)
  else doImportB(override)
}
function handleImportA(){ openImportConfirm('A') }
function handleImportB(){ openImportConfirm('B') }

async function doImportA(ymOverride){
  if(!fileAList.value.length){ElMessage.warning('请先选择 S13_DPS 文件（可多选）');return}
  importingA.value=true;errorMsg.value='';importTaskId.value='imp_'+Date.now()+'_'+Math.random().toString(36).slice(2,8)
  try{
    const results=[]
    for(const f of fileAList.value){
      const fd=new FormData();fd.append('file',f);if(planYear.value)fd.append('year',String(planYear.value));fd.append('task_id',importTaskId.value)
      if(ymOverride)fd.append('ym',String(ymOverride))     // ★ 人工确认的归属月份（优先级最高）
      // ★ P2-1：附带文件「修改日期」年份（浏览器可直接读 lastModified），供后端月份一致性校验补齐年份
      const fy=new Date(f.lastModified||Date.now()).getFullYear()
      if(fy>2000)fd.append('file_year',String(fy))
      const res=await axios.post(`${API}/preplan/import-a/`,fd,{headers:{'Content-Type':'multipart/form-data'}})
      if(res.data.success) results.push(res.data)
      else { ElMessage.error(res.data.error); break }
    }
    if(results.length){
      const kept=results.reduce((s,r)=>s+(r.stats?.kept||0),0)
      const replaced=results.reduce((s,r)=>s+(r.replaced||0),0)
      importAResult.value=results[results.length-1]
      const landed=results[results.length-1]?.plan_ym||0
      const mlab=landed?` 归入 ${Math.floor(landed/100)}年${landed%100}月`:''
      ElMessage.success('导入完成：'+results.length+' 份文件，共通过 '+kept+' 行'+mlab+(replaced?('；同月同名文件旧数据已自动覆盖 '+replaced+' 行，不追加（审核决议数据不受影响）'):''))
      // ★ P2-1：月份不一致提示
      if(results.some(r=>r.month_warning)) ElMessage.warning(results.map(r=>r.month_warning).filter(Boolean).join('；'))
      // ★ 导入后自动切到该月份视图，立刻看到新数据（否则可能停在别的月份上"看不到刚导入的"）
      if(landed){ ymInited=true; planYm.value=landed; cacheLoaded.value.clear() }
      activeTab.value='all';await loadData()
    }
  }catch(e){const cancelled=e.response?.data?.cancelled;const m=cancelled?'导入已取消':('导入A失败：'+(e.response?.data?.error||e.message));if(cancelled)ElMessage.info(m);else{errorMsg.value=m;ElMessage.error(m)}}finally{importingA.value=false;importTaskId.value=''}
}
async function doImportB(ymOverride){
  if(!fileBList.value.length){ElMessage.warning('请先选择 S11 文件（可多选）');return}
  importingB.value=true;errorMsg.value='';importTaskId.value='imp_'+Date.now()+'_'+Math.random().toString(36).slice(2,8)
  // ★ 导入 B 后切到「合并」视图展示 A+B 全部来源，避免看起来像 B 覆盖了 A
  try{
    const results=[]
    for(const f of fileBList.value){
      const fd=new FormData();fd.append('file',f);if(planYear.value)fd.append('year',String(planYear.value));fd.append('task_id',importTaskId.value)
      if(ymOverride)fd.append('ym',String(ymOverride))     // ★ 人工确认的归属月份（优先级最高）
      // ★ P2-1：附带文件「修改日期」年份（浏览器可直接读 lastModified），供后端月份一致性校验补齐年份
      const fy=new Date(f.lastModified||Date.now()).getFullYear()
      if(fy>2000)fd.append('file_year',String(fy))
      const res=await axios.post(`${API}/preplan/import-b/`,fd,{headers:{'Content-Type':'multipart/form-data'}})
      if(res.data.success) results.push(res.data)
      else { ElMessage.error(res.data.error); break }
    }
    if(results.length){
      const kept=results.reduce((s,r)=>s+(r.stats?.kept||0),0)
      const replaced=results.reduce((s,r)=>s+(r.replaced||0),0)
      importBResult.value=results[results.length-1]
      const landed=results[results.length-1]?.plan_ym||0
      const mlab=landed?` 归入 ${Math.floor(landed/100)}年${landed%100}月`:''
      ElMessage.success('导入完成：'+results.length+' 份文件，共通过 '+kept+' 行'+mlab+(replaced?('；同月同名文件旧数据已自动覆盖 '+replaced+' 行，不追加（审核决议数据不受影响）'):''))
      // ★ P2-1：月份不一致提示
      if(results.some(r=>r.month_warning)) ElMessage.warning(results.map(r=>r.month_warning).filter(Boolean).join('；'))
      if(landed){ ymInited=true; planYm.value=landed; cacheLoaded.value.clear() }
      activeTab.value='all';await loadData()
    }
  }catch(e){const cancelled=e.response?.data?.cancelled;const m=cancelled?'导入已取消':('导入B失败：'+(e.response?.data?.error||e.message));if(cancelled)ElMessage.info(m);else{errorMsg.value=m;ElMessage.error(m)}}finally{importingB.value=false;importTaskId.value=''}
}
// ★ 取消导入：立即请求后端停止该任务后续读取与写入（后端校验通过后回滚未写入的中间数据）
async function cancelImport(kind){
  const tid=importTaskId.value
  if(!tid){importingA.value=false;importingB.value=false;return}
  try{await axios.post(`${API}/preplan/import-cancel/`,{task_id:tid})}catch(e){}
  ElMessage.info(kind==='A'?'正在取消导入A...':'正在取消导入B...')
}

// ★ AbortController：每次 loadData 取消上一次未完成的请求，防止竞态导致旧响应覆盖新数据
let _loadAbort = null
async function loadData(){
  // ★ 取消上一次还在飞的请求（切页/快速操作时旧响应不再覆盖新数据）
  if(_loadAbort) _loadAbort.abort()
  const ctrl = new AbortController()
  _loadAbort = ctrl
  loading.value=true
  try{
    const mapRow=r=>({...r,missing_fields:typeof r.missing_fields==='string'?JSON.parse(r.missing_fields||'[]'):(r.missing_fields||[])})
    if(activeTab.value==='all'){
      // ★ include_exported=true（2026-09-15）：已导出到决议中心的行继续留在预排工作区，
      //   只打「已导出」标记，避免导出后整页变空（头部计数还在、表格无行）。
      const p={year:planYear.value,include_exported:'true'}
      const _ym=ymParam(); if(_ym)p.ym=_ym
      const[rA,rB]=await Promise.all([
        axios.get(`${API}/preplan/rows/`,{params:{...p,source:'S13_DPS'},signal:ctrl.signal}),
        axios.get(`${API}/preplan/rows/`,{params:{...p,source:'Monthly_Input'},signal:ctrl.signal})
      ])
      cacheA.value=(rA.data.data||[]).map(mapRow)
      cacheB.value=(rB.data.data||[]).map(mapRow)
      // ★ 首次加载默认切到最新月份 → 本次结果作废，按新月份重新加载（避免用全年数据渲染）
      if(applyYmOptions(rA.data.yms||rB.data.yms||[])){ await loadData(); return }
      // 计数统一由 applyView → syncSourceCounts 派生，此处不再单独赋值（单一数据源）
    }else{
      // ★ 单视图缓存按来源独立存放(cacheA=S13、cacheB=S11),互不覆盖,避免切换显示错数据
      const params={year:planYear.value,source:activeTab.value,include_exported:'true'}
      const _ym=ymParam(); if(_ym)params.ym=_ym
      const res=await axios.get(`${API}/preplan/rows/`,{params,signal:ctrl.signal})
      const data=(res.data.data||[]).map(mapRow)
      if(activeTab.value==='S13_DPS')cacheA.value=data
      else if(activeTab.value==='Monthly_Input')cacheB.value=data
      if(applyYmOptions(res.data.yms||[])){ await loadData(); return }
      // ★ 2026-09-16 修复：此处原为 countA=0;countB=0，导致「点单视图标签 → 切回合并」时
      //   A/B 计数永久停在 0（切回合并走的是缓存分支，只 applyView 不重新请求，计数不会被重建）
      //   → 页面显示「A: 0 行 | B: 0 行 | 合计 92 条」，被误判为"数据全没了"。
      //   单视图分支写入的 cacheA/cacheB 与合并分支同源同义（都按 source 过滤），
      //   因此计数保持一致即可，不需要清零；countA/countB 统一由 applyView 同步。
      syncSourceCounts()
    }
    applyView()
    // ★ 记录该「年份+视图」已加载，切换回来直接本地渲染，不再重复请求
    cacheLoaded.value.add(tabCacheKey())
    // ★ 刷新/切换后恢复上传入口的文件名（数据里存了 source_file_name，表格在文件名就保留）
    restoreFileNames()
  }catch(e){
    // ★ 被 abort 的请求静默忽略（不是真正错误，是竞态取消）
    if(e?.name === 'CanceledError' || e?.code === 'ERR_CANCELED') return
    console.error(e)
    // ★ 不再静默清空：失败时保留已有数据并显示错误条（否则"切回来暂无数据"无从排查）
    errorMsg.value = '加载失败：' + (e?.response?.data?.error || e?.message || e)
    if(!tableData.value.length){ tableData.value=[]; total.value=0 }
  }finally{loading.value=false}
}

// ★ 从已加载数据恢复 A/B 文件名（刷新页面/切换年份后不消失；清空后无数据则保持空）
function restoreFileNames(){
  const all = [...cacheA.value, ...cacheB.value]
  const nA = all.find(r => r.source === 'S13_DPS' && r.source_file_name)?.source_file_name
  const nB = all.find(r => r.source === 'Monthly_Input' && r.source_file_name)?.source_file_name
  if(!fileAList.value.length && nA) fileAList.value = [{ name: nA }]
  if(!fileBList.value.length && nB) fileBList.value = [{ name: nB }]
}

// ★ 视图切换性能优化：已加载过的「年份:月份:视图」直接本地 applyView 秒切；未加载过才请求
function tabCacheKey(){ return `${planYear.value}:${planYm.value}:${activeTab.value}` }

// ★ 2026-09-20：同步「预排年月」下拉选项
//   - ym=0（未归类）不单独出选项，避免与「全部月份」语义混淆（未归类行只在「全部月份」下可见）
//   - 首次拿到清单时默认切到最新月份，让页面天然按月分类，而不是把多个月混在一张表里
//   返回 true 表示「已改选月份、调用方需按新月份重新加载」（避免用旧的全年数据渲染）。
function applyYmOptions(list){
  let opts=(list||[]).filter(o=>o && o.ym).sort((a,b)=>b.ym-a.ym)
  // ★ 2026-09-21：当前所选月份若已从清单里消失（例如刚被清空、该月已无任何行），
  //   按 0 条把它补回下拉 —— 否则 el-select 的 v-model 指向一个没有对应选项的"悬空值"，
  //   输入框显示空白/裸数字，用户不知道自己在看哪个月，也容易把"该月已空"误判成"清空没生效"。
  if(planYm.value && !opts.some(o=>o.ym===planYm.value)){
    opts=[...opts,{ ym: planYm.value, label: ymText(planYm.value), count: 0 }].sort((a,b)=>b.ym-a.ym)
  }
  ymOptions.value=opts
  if(!ymInited && opts.length){
    ymInited=true
    if(opts[0].ym!==planYm.value){ planYm.value=opts[0].ym; cacheLoaded.value.clear(); return true }
  }
  return false
}

// ★ 同步「A: N 行 / B: M 行」来源计数（2026-09-16）
//   根因：单视图分支曾把 countA/countB 清零，而切回合并视图走缓存分支（不重新请求），
//   计数再也没被重建 → 页面显示 A:0 / B:0 而被误判为"数据全没了"。
//   现在统一从 cache 派生，任何路径（首次加载/单视图/缓存切换）都保持一致。
function syncSourceCounts(){
  countA.value=cacheA.value.length
  countB.value=cacheB.value.length
}
// ★ 本地过滤 + 本地分页（切换 通过/过滤/全部、翻页都只走这里，不重新请求）
function applyView(){
  syncSourceCounts()
  const list = getFilteredList()
  total.value=list.length

  const pages=Math.max(1,Math.ceil(total.value/pageSize.value))
  if(currentPage.value>pages)currentPage.value=pages
  const start=(currentPage.value-1)*pageSize.value
  let pageList=list.slice(start,start+pageSize.value)

  // 合并视图：分隔线画在来源边界处(前一组最后一行底部)，顺序跟随导入先后，不写死来源
  if(activeTab.value==='all'){
    for(let i=0;i<list.length-1;i++){
      if(list[i].source !== list[i+1].source){
        const localIdx=i-start
        if(localIdx>=0 && localIdx<pageList.length){
          pageList[localIdx]={...pageList[localIdx],_isSourceChange:true}
        }
        break
      }
    }
  }
  tableData.value=pageList
  // ★ 导出严格跟随页面：缓存当前视图完整行（与页面显示完全一致，含筛选/优先级排序）
  exportRows.value=list
}

// ★ 表格横向拖动：按住鼠标拖动即可横向滚动（点击单元格仍正常，仅实际拖动时接管）
//   注意：el-table 的真实横向滚动容器在组件内部(.el-scrollbar__wrap)，必须滚动它而非外层 wrapper
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

async function handleExport(){
  const rows = exportRows.value || []
  if(!rows.length){ ElMessage.warning('当前视图没有可导出的数据'); return }
  try{
    // ★ 严格跟随页面：把当前视图过滤+排序后的全部行 id 发给后端，导出顺序与页面完全一致
    const ids = rows.map(r=>r.id)
    const res=await axios.post(`${API}/preplan/export/`,{year:planYear.value, ids, ym:ymParam()},{responseType:'blob'})
    const url=URL.createObjectURL(new Blob([res.data]));const a=document.createElement('a');a.href=url;a.download=buildFileName('preplan',exportNamingCtx.value);document.body.appendChild(a);a.click();a.remove();URL.revokeObjectURL(url);ElMessage.success('导出成功（与当前页面视图一致）')
  }catch(e){ElMessage.error('导出失败')}
}
// ★ 刷新回填：先重抓 MTD（计划外记录随最新 SQL 更新/清除）→ 基础资料表 回填 + ORT 规则条 + 表格数据 全量同步
async function handleRefreshEntry(){
  refreshing.value=true
  try{
    const fd=new FormData();if(planYear.value)fd.append('year',String(planYear.value))
    // ★ 1) 先重抓 MTD：回填数据后旧计划外记录会被更新/清除，刷新时应加载最新
    let mtdMsg=''
    try{
      const mr=await axios.post(`${API}/preplan/sync-mtd/`,fd)
      if(mr.data.success)mtdMsg=mr.data.message||'MTD 已同步'
    }catch(e){/* MTD 抓取失败不阻断刷新，仅提示 */}
    // ★ 2) 基础资料表回填 + ORT 规则重算
    const res=await axios.post(`${API}/preplan/refresh-entry/`,fd)
    if(res.data.success){
      await Promise.all([loadData(), loadOrtRules()])
      ElMessage.success(mtdMsg ? (res.data.message||'刷新完成')+'；'+mtdMsg : (res.data.message||'刷新完成'))
    } else ElMessage.error(res.data.error||'刷新失败')
  }catch(e){ElMessage.error('刷新失败：'+(e.response?.data?.error||e.message))}
  finally{refreshing.value=false}
}
// ★ 导出到审核决议页：范围跟随当前视图(S13→S13通过 / S11→S11通过 / 合并→全部通过)，先写导出标记(覆盖式)再跳转
async function goDecisionReview(){
  try{
    const fd=new FormData()
    if(planYear.value)fd.append('year',String(planYear.value))
    if(planYm.value)fd.append('ym',String(planYm.value))     // ★ 2026-09-20 只导出当前所选预排年月
    if(activeTab.value==='S13_DPS'||activeTab.value==='Monthly_Input')fd.append('source',activeTab.value)
    const res=await axios.post(`${API}/preplan/export-decision/`,fd)
    ElMessage.success((res.data.message||'已导入到审核决议中心')+'；该批「通过」行已叠加进审核决议页，预排页保留全部数据并标注「已导出」')
    router.push('/decision-review')
  }catch(e){ElMessage.error('导出到决议失败：'+(e.response?.data?.error||e.message))}
}
// ★ MTD OUTPUT 实时抓取：执行后端配置的 PostgreSQL SQL，更新 MTD OUTPUT监控列
async function handleSyncMtd(){
  mtdSyncing.value=true
  try{
    const fd=new FormData();if(planYear.value)fd.append('year',String(planYear.value))
    const res=await axios.post(`${API}/preplan/sync-mtd/`,fd)
    if(res.data.success){ElMessage.success(res.data.message||'MTD 同步完成');await loadData()}
    else ElMessage.error(res.data.error||'MTD 同步失败')
  }catch(e){ElMessage.error('MTD 同步失败：'+(e.response?.data?.error||e.message))}
  finally{mtdSyncing.value=false}
}
// ★ 自绘深色主题日历（送样日期用，不依赖 Element/原生）
const calVisible=ref(false)
const calRow=ref(null)
const calView=reactive({year:new Date().getFullYear(),month:new Date().getMonth()+1})
const calPos=ref({left:0,top:0})
const calStyle=computed(()=>({left:calPos.value.left+'px',top:calPos.value.top+'px'}))
function openCal(row,e){
  calRow.value=row
  // ★ 打开一律定位到「今天」（2026-09-15 用户明确：点进去默认跳到今天）
  //   不再跟随该行的预排月份 / 已填送样日期 —— 实测表格里几乎每行都已填过日期，
  //   跟随旧值会导致点开永远停在几个月前，没法直接点今天。
  const t=new Date()
  calView.year=t.getFullYear()
  calView.month=t.getMonth()+1
  // ★ 锚定到输入框下方
  if(e && e.currentTarget){
    const r=e.currentTarget.getBoundingClientRect()
    let left=r.left
    if(left+280>window.innerWidth)left=window.innerWidth-292
    calPos.value={left,top:r.bottom+4}
  }
  calVisible.value=true
}
const calDays=computed(()=>{
  const y=calView.year,m=calView.month
  const first=new Date(y,m-1,1)
  const startDow=first.getDay()
  const daysInMonth=new Date(y,m,0).getDate()
  const daysInPrev=new Date(y,m-1,0).getDate()
  const arr=[]
  for(let i=startDow-1;i>=0;i--)arr.push({day:daysInPrev-i,inMonth:false})
  for(let d=1;d<=daysInMonth;d++)arr.push({day:d,inMonth:true})
  const remain=(7-arr.length%7)%7
  for(let d=1;d<=remain;d++)arr.push({day:d,inMonth:false})
  return arr
})
function isCalToday(d){
  const t=new Date()
  return d.inMonth && calView.year===t.getFullYear() && calView.month===t.getMonth()+1 && d.day===t.getDate()
}
// ★ 该行原本已填的送样日期（2026-09-15）：打开一律跳今天后，仍要能看出"已填过的是哪天"，
//   避免误以为日期被重置。按 YYYY-MM-DD 手动拆解，避免 ISO 纯日期串按 UTC 解析的跨月偏移。
function isCalPicked(d){
  const m=/^(\d{4})-(\d{2})-(\d{2})/.exec((calRow.value&&calRow.value.sample_date)||'')
  return !!(m && d.inMonth && calView.year===parseInt(m[1]) && calView.month===parseInt(m[2]) && d.day===parseInt(m[3]))
}
function calShiftMonth(delta){let m=calView.month+delta;if(m<1){m=12;calView.year--}else if(m>12){m=1;calView.year++}calView.month=m}
function calShiftYear(delta){calView.year+=delta}
function pickCalDay(d){
  const val=`${calView.year}-${String(calView.month).padStart(2,'0')}-${String(d.day).padStart(2,'0')}`
  if(calRow.value)saveCell(calRow.value,'sample_date',{target:{value:val}})
  calVisible.value=false
}
// ★ 送样日期填错 → 日历弹层点「✕ 清空」把日期叉掉（空值入库）
function clearSampleDate(){
  const r=calRow.value
  if(r && r.sample_date) saveCell(r,'sample_date','')
  calVisible.value=false
}
// ★ 2026-09-21 清空/移除「静默空转」修复（用户报：某月数据清空了但页面数据仍旧保留）
//   根因形态：后端一条都没删时接口照样返回 200 +「已清空N条」，前端也只弹绿色成功 ——
//   于是「点了清空、表格一行没少」看起来像前端没刷新，实际可能是 ① 生效范围（年/月/来源）
//   与表格不一致 ② 数据被保护（已导出到审核决议）③ 请求其实失败了但只弹了句笼统文案。
//   现在统一由后端回执驱动提示：deleted=0 一律黄色告警并说明后端实际生效的 scope。
function reportClearOutcome(d, scopeLabel, okText){
  const del = (d && typeof d.deleted === 'number') ? d.deleted : 0
  const kept = (d && d.kept_exported) || 0
  if(del > 0){ ElMessage.success(okText || d.message || `已清空 ${del} 条`); return del }
  if(kept > 0){
    ElMessage.warning(`本次未删除任何数据：${scopeLabel} 内 ${kept} 条已导出到审核决议的数据受保护，需到审核决议页清理`)
  }else{
    ElMessage.warning(`本次未删除任何数据：${scopeLabel} 内没有可清空的预排行。若表格仍有数据，请核对顶部「年份/月份」与当前来源是否和表格一致`)
  }
  console.warn('[预排] 清空空转（后端未删除任何行）', { scopeLabel, resp: d })
  return 0
}
async function handleClear(){
  const source=activeTab.value!=='all'?activeTab.value:''
  // ★ ymLabel 自带年份（'2026年9月'）——旧文案又拼了一次 planYear，会渲染成「2026年2026年9月」
  const scopeLabel=(planYm.value ? ymLabel.value : `${planYear.value}年全部月份`)+(source?` ${activeTabLabel.value}`:' 全部来源')
  try{await ElMessageBox.confirm(`确定清空 ${scopeLabel}？`,'确认清空',{type:'warning'})}catch{return}
  try{
    const res=await axios.post(`${API}/preplan/clear/`,{year:planYear.value,source,ym:ymParam()})
    const d=res.data||{}
    // 用后端回显的实际生效范围做提示，用户能直接看出"我清的是哪个月"
    const echo=d.scope?`${d.scope.year||'全部年份'}年${d.scope.ym?`${d.scope.ym%100}月`:'（全部月份）'}${d.scope.source?` ${d.scope.source}`:' 全部来源'}`:scopeLabel
    reportClearOutcome(d, echo)
    if(!source||source==='S13_DPS'){importAResult.value=null;fileAList.value=[]}
    if(!source||source==='Monthly_Input'){importBResult.value=null;fileBList.value=[]}
  }catch(e){
    const detail=(e.response?.data&&(e.response.data.error||e.response.data.detail))||e.message||e
    console.error('[预排] 清空失败：', e.response?.status, e.response?.data||e.message)
    ElMessage.error('清空失败：'+detail)
  }finally{
    // ★ 无论成败都刷新：失败/空转时也要让页面反映数据库的真实状态（旧代码失败会跳过刷新）
    await loadData()
  }
}

// ★ 增量筛选（性能优化）：保存/删除规则后，只对该规则影响的 source/type 范围重算 ort_ok/judge，
//   不再全量重算。规则为空 Type + ALL 时视为全局兜底规则 → 才走全量。
async function recomputeScoped(rule){
  const srcMap={S13:'S13_DPS',MONTHLY:'Monthly_Input'}
  const payload={}
  if(rule?.source && rule.source!=='ALL') payload.source=srcMap[rule.source]
  if(rule?.type_name) payload.type_name=rule.type_name
  else if(rule?.source && rule.source!=='ALL') payload.type_name=''
  try{const res=await axios.post(`${API}/preplan/recompute-judge/`,payload);return res.data.updated||0}catch(e){return 0}
}
async function loadOrtRules(){try{const res=await axios.get(`${API}/ort-rules/`);ortRules.value=Array.isArray(res.data)?res.data:(res.data.results||[])}catch(e){}}
function openOrtForm(rule){editingOrtRule.value=rule;if(rule)Object.assign(ortForm,{type_name:rule.type_name,source:rule.source,operator:rule.operator,threshold:rule.threshold,is_active:rule.is_active,remark:rule.remark||''});else Object.assign(ortForm,{type_name:'',source:'ALL',operator:'>=',threshold:300,is_active:true,remark:''});ortFormVisible.value=true}
async function saveOrtRule(){
  try{
    const rule=editingOrtRule.value?{...editingOrtRule.value,...ortForm}:{...ortForm}
    if(editingOrtRule.value?.id)await axios.put(`${API}/ort-rules/${editingOrtRule.value.id}/`,{...ortForm})
    else await axios.post(`${API}/ort-rules/`,{...ortForm})
    ortFormVisible.value=false
    await loadOrtRules()
    // ★ 增量筛选：仅重算该规则影响范围
    const updated=await recomputeScoped(rule)
    ElMessage.success(updated?`保存成功，已增量重算 ${updated} 行`: '保存成功')
    await loadData()
  }catch(e){ElMessage.error('保存失败')}
}
async function handleDeleteOrtRule(rule){
  if(!rule?.id)return
  try{
    await axios.delete(`${API}/ort-rules/${rule.id}/`)
    await loadOrtRules()
    // ★ 增量筛选：仅重算被删除规则影响范围
    const updated=await recomputeScoped(rule)
    ElMessage.success(updated?`已删除，已增量重算 ${updated} 行`: '已删除')
    await loadData()
  }catch(e){}
}

watch(activeTab,()=>{
  currentPage.value=1
  // ★ 已加载过的视图秒切（本地渲染），未加载过才发起请求
  if(cacheLoaded.value.has(tabCacheKey()))applyView()
  else loadData()
})
watch(statusFilter,()=>{currentPage.value=1;applyView()})
// ★ 翻页/每页条数 → 本地重算分页（搜索跳页也走这里，确保页面真正切过去再高亮定位）
watch([currentPage, pageSize], ([np, ns], [op, os]) => {
  if (ns !== os && currentPage.value !== 1) { currentPage.value = 1; return }
  applyView()
})
onMounted(()=>{loadOrtRules();document.addEventListener('click', onDocClickForFilter)})
// ★ keep-alive：激活时注册 Ctrl+F 监听、重载数据（决议中心/预警页可能已改动本页数据，
//   每次切回都从后端刷新，避免"切回来显示旧数据/空数据"）；停用时移除监听
onActivated(()=>{window.addEventListener('keydown', onTableSearchKey);loadData()})
onDeactivated(()=>window.removeEventListener('keydown', onTableSearchKey))
onBeforeUnmount(()=>{document.removeEventListener('click', onDocClickForFilter);window.removeEventListener('keydown', onTableSearchKey)})
</script>

<style lang="scss" scoped>
.preplan-view{flex:1;display:flex;flex-direction:column;gap:6px;min-height:0;height:100%;padding:2px 0;overflow:hidden}
.scroll-area{flex:1;min-height:0;overflow:hidden;display:flex;flex-direction:column}

.pbar{display:flex;align-items:center;justify-content:space-between;flex-shrink:0}
.pbar-left{display:flex;align-items:center;gap:6px}
.ptag{background:rgba(0,60,120,.4);border:1px solid #0d3050;color:#5a90b8;font-size:10px;padding:3px 10px;border-radius:4px}
.ptitle{font-size:15px;font-weight:500;color:#c8e0f8;margin-left:10px;span{color:#00d4aa}}
.pright{display:flex;gap:6px}
.bsm{font-size:10px;padding:4px 12px;border-radius:12px;cursor:pointer;border:1px solid #0d3050;background:rgba(0,40,90,.2);color:#3a6070;transition:.15s;&:hover{background:rgba(0,60,130,.28);color:#7098b8}&.act{background:rgba(0,70,160,.28);border-color:#0050a0;color:#90c0e8}}

.top-bar{display:flex;align-items:center;justify-content:space-between;gap:10px;padding:5px 12px;background:linear-gradient(135deg,rgba(5,15,30,.6),rgba(7,26,46,.6));border:1px solid #0d2a48;border-radius:8px;flex-shrink:0}
.upload-compact{display:flex;align-items:center;gap:10px}
.uc-item{display:flex;align-items:center;gap:5px;font-size:11px;padding:2px 8px;border-radius:5px;background:rgba(0,30,60,.3);border:1px solid #0d3050;position:relative;transition:all .15s;&.has-file{border-color:#0077cc;background:rgba(0,60,120,.2)}&.drag-over{border-color:#22aaff;background:rgba(0,110,210,.32);box-shadow:0 0 0 1px rgba(0,160,255,.55),0 0 12px rgba(0,140,255,.25)}}
.uc-drop-hint{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:12px;font-weight:600;color:#fff;background:rgba(0,120,220,.55);border-radius:5px;pointer-events:none;letter-spacing:1px;z-index:3}
.uc-tag{display:inline-flex;align-items:center;justify-content:center;width:16px;height:16px;border-radius:50%;font-size:9px;font-weight:700;color:#fff;flex-shrink:0;&.tag-a{background:linear-gradient(135deg,#0055aa,#0077cc)}&.tag-b{background:linear-gradient(135deg,#2e7d32,#43a047)}}
.uc-label{color:#6aa3c8;font-weight:600;font-size:10px}
.uc-pick{font-size:10px;padding:2px 8px;border-radius:4px;cursor:pointer;background:rgba(0,80,160,.3);border:1px dashed rgba(0,119,204,.4);color:#5a90b8;font-family:inherit;&:hover{background:rgba(0,100,180,.4);color:#90c0e8}}
.uc-name{color:#c8e0f8;font-weight:500;max-width:320px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;font-size:11px}
.uc-remove{background:none;border:none;color:#ff8888;cursor:pointer;font-size:11px;&:hover{color:#ffaaaa}}
.uc-result{color:#00d4aa;font-weight:700;font-size:10px}
.top-actions{display:flex;align-items:center;gap:6px}
.year-sel{width:80px}
/* ★ 2026-09-20 预排月份下拉：与年份下拉同尺寸风格 */
.month-sel{width:132px}
.run-btn{font-size:11px;font-weight:600;padding:4px 10px;border-radius:12px;cursor:pointer;border:none;font-family:inherit;display:inline-flex;align-items:center;gap:2px;&.primary{background:linear-gradient(135deg,#0055aa,#0077cc);color:#fff;box-shadow:0 2px 6px rgba(0,100,200,.35);&:hover:not(:disabled){box-shadow:0 3px 12px rgba(0,120,240,.5);transform:translateY(-1px)}&:disabled{background:rgba(0,40,80,.4);color:#4d7d9e;box-shadow:none;cursor:not-allowed}}&.green{background:linear-gradient(135deg,#2e7d32,#43a047);box-shadow:0 2px 6px rgba(46,125,50,.35)}&.sec{background:rgba(0,40,80,.3);color:#5a90b8;border:1px solid #0d3050;&:hover:not(:disabled){background:rgba(0,60,120,.4);color:#90c0e8}&:disabled{opacity:.4}}&.danger{background:rgba(105,24,32,.5);color:#e09090;border:1px solid #5a2028;&:hover:not(:disabled){background:rgba(140,30,40,.6);color:#ffaaaa}}}
.row-btn{font-size:12px;padding:6px 14px;border-radius:12px;cursor:pointer;border:1px solid #0d3050;background:rgba(0,60,120,.3);color:#8ab8d8;font-family:inherit;&:hover{background:rgba(0,100,180,.4);color:#c8e0f8}}

.err-bar{display:flex;align-items:center;gap:8px;padding:5px 12px;background:rgba(160,30,40,.2);border:1px solid #5a2028;border-radius:6px;flex-shrink:0}.err-text{font-size:12px;color:#e09090;flex:1}.err-close{background:none;border:none;color:#e09090;cursor:pointer}

.rule-bar{display:flex;align-items:center;justify-content:space-between;padding:10px 14px;background:linear-gradient(135deg,rgba(5,15,30,.8),rgba(7,26,46,.8));border:1px solid #0d2a48;border-radius:8px 8px 0 0;flex-shrink:0}
.rule-bar-left{display:flex;align-items:center;gap:8px}.rule-bar-title{font-size:13px;font-weight:700;color:#c8e0f8}
.rule-bar-pills{display:flex;gap:5px;flex-wrap:wrap}
.rule-pill-xs{font-size:12px;padding:5px 10px;border-radius:10px;background:rgba(0,60,120,.4);border:1px solid rgba(0,119,204,.3);color:#8ab8d8;white-space:nowrap;cursor:pointer;transition:.15s;&:hover{background:rgba(0,100,180,.5);color:#c0e0f8}&.off{opacity:.4;text-decoration:line-through}em{font-style:normal;font-size:9px;margin-left:3px;padding:1px 3px;border-radius:3px;background:rgba(0,0,0,.3);color:#5a90b8}}
.rule-bar-right{display:flex;align-items:center;gap:10px}
.rt-hint{font-size:12px;color:#4d7d9e;strong{color:#00d4aa;font-size:13px}}

.table-section{display:flex;flex-direction:column;flex:1;min-height:0}.table-wrapper{flex:1;min-height:0;overflow:hidden;background:rgba(5,15,30,.5);border:1px solid #0d2a48;border-top:none;cursor:grab}.table-wrapper.dragging{cursor:grabbing;user-select:none;-webkit-user-select:none}.row-idx{color:#4d7d9e;font-size:11px}.filter-reason{color:#e8b838;font-size:11px}
.cell-missing{background:rgba(220,50,50,.28);color:#ffaaaa;font-weight:600;display:inline-block;width:100%;padding:2px 4px;border-radius:3px}
.cell-ort-n{background:rgba(220,50,50,.28);color:#ffaaaa;font-weight:700;display:inline-block;width:100%;padding:2px 4px;border-radius:3px}
.pagination-bar{display:flex;align-items:center;justify-content:space-between;padding:6px 12px;background:rgba(5,15,30,.6);border:1px solid #0d2a48;border-top:none;border-radius:0 0 8px 8px;flex-shrink:0}
.pagination-info{font-size:11px;color:#5a90b8;.total{color:#00d4aa;font-weight:700;font-size:13px}}
.src-a{color:#0099ff}.src-b{color:#43a047}.src-ext{color:#ffd54f;font-weight:700}
/* ★ 2026-09-23：来源文件列单行省略
   根因：文件名常达 30+ 字符（如 `Monthly input target s110623.xlsx`），
   默认 white-space:normal 会折成 2~3 行 → 把整行行高撑高。
   改为单行 + 溢出省略号；全名见单元格 title（悬停）。
   注：`td.col-source` 由 el-table-column 的 :class-name 加上，不波及其它列。 */
:deep(td.col-source) .cell{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.empty-state{display:flex;flex-direction:column;align-items:center;justify-content:center;padding:80px 20px;color:#3a6080;gap:10px;.empty-icon{font-size:40px;opacity:.5}.empty-text{font-size:14px}}

.runov{position:fixed;inset:0;background:rgba(0,3,10,.85);z-index:100;display:flex;align-items:center;justify-content:center;opacity:0;pointer-events:none;transition:opacity .2s;&.show{opacity:1;pointer-events:all}}
.runbox{background:linear-gradient(135deg,#040e1e,#061828);border:1px solid rgba(0,100,200,.3);border-radius:14px;width:640px;max-height:84vh;padding:24px 28px;position:relative;box-shadow:0 24px 80px rgba(0,20,80,.8);overflow-y:auto}
.runbox-close{position:absolute;top:12px;right:16px;font-size:16px;color:#2a5070;cursor:pointer;&:hover{color:#90c0e8}}
.run-title{font-size:16px;font-weight:600;color:#c8e0f8;margin-bottom:2px}.run-subtitle{font-size:10px;color:#3a6080;margin-bottom:12px}
.form-section{background:rgba(0,25,60,.3);border:1px solid #0d3050;border-radius:8px;padding:10px 12px;margin-bottom:10px}
.form-grid{display:grid;grid-template-columns:1fr 1fr;gap:0 12px}.form-row{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.form-lbl{font-size:10px;color:#6aa3c8;width:45px;text-align:right;flex-shrink:0}
.form-input,.form-select{flex:1;background:rgba(0,20,40,.6);border:1px solid #0d3050;border-radius:4px;padding:4px 8px;color:#c8ddf5;font-size:11px;font-family:inherit;&:focus{outline:none;border-color:#0077cc}&::placeholder{color:#3a5870}}
.form-select{cursor:pointer}.form-check{display:flex;align-items:center;gap:6px;color:#c8ddf5;font-size:11px}
.run-btns{display:flex;gap:8px;justify-content:center;margin-top:12px}.hidden{display:none}

.cell-inline-edit{width:100%;overflow:hidden}
.cell-text{display:block;width:100%;min-height:22px;line-height:22px;cursor:pointer;padding:0 4px;border-radius:3px;box-shadow:inset 0 0 0 1px rgba(0,180,230,.4);background:rgba(0,160,220,.06)}
.cell-text:hover{box-shadow:inset 0 0 0 1px #00b8e6;background:rgba(0,160,220,.16)}
/* 可编辑格同时是缺失/预警红色时，红色优先，不被青色可编辑提示覆盖 */
.cell-text.cell-missing{background:rgba(220,50,50,.28);color:#ffaaaa;font-weight:600}
.cell-text.cell-ort-n{background:rgba(220,50,50,.28);color:#ffaaaa;font-weight:700}
.cell-input{width:100%;text-align:center;font-size:12.5px;padding:3px 4px;border:1px solid #0d3050;border-radius:3px;background:transparent;color:#c8ddf5;font-family:inherit;outline:none;transition:.15s;&:focus{border-color:#0077cc;background:rgba(0,40,80,.3)}&.cell-missing{background:rgba(220,50,50,.28);color:#ffaaaa}&.cell-ort-n{background:rgba(220,50,50,.28);color:#ffaaaa}}

/* QE/GPC 下拉 Y/N */
.cell-select{width:100%}
.cell-select :deep(.el-select__wrapper){width:100%!important;padding:1px 6px!important}
.cell-select :deep(.el-select__selected-item){font-size:12px;color:#c8ddf5!important}

.preplan-view :deep(.el-select__wrapper),.preplan-view :deep(.el-input__wrapper){background:rgba(0,30,60,.5)!important;box-shadow:0 0 0 1px #0d3050 inset!important}
.preplan-view :deep(.el-radio-button__inner){background:rgba(0,30,60,.5);border-color:#0d3050;color:#6aa3c8;font-size:10px}
.preplan-view :deep(.el-radio-button__original-radio:checked+.el-radio-button__inner){background:rgba(0,100,180,.5);color:#c8e0f8}
.preplan-view :deep(.el-table){--el-table-bg-color:transparent;--el-table-tr-bg-color:transparent;--el-table-header-bg-color:#0a1a30;--el-table-row-hover-bg-color:rgba(0,60,120,.15);--el-table-border-color:#0d2a48;--el-table-header-text-color:#6aa3c8;--el-table-text-color:#c8ddf5;font-size:11px}
.preplan-view :deep(.el-loading-mask){background:rgba(5,15,30,.8)!important}
.preplan-view :deep(.el-table__body tr:hover>td){background:rgba(0,80,160,.15)!important}
.preplan-view :deep(.row-filtered){opacity:.6;background:rgba(180,150,50,.06)}
.preplan-view :deep(.row-source-split td){border-bottom:2px solid rgba(0,212,170,.85)!important}
.preplan-view :deep(.row-external td){background:rgba(230,150,30,.10)!important}
/* ★ 已导出到决议中心的行（2026-09-15）：保留在预排工作区，仅加淡色角标，不做整行染色（避免与 hover/搜索高亮抢样式） */
.exp-tag{display:block;font-size:9px;line-height:1.3;color:#5b8fb0;border:1px dashed #1d4a6e;border-radius:6px;padding:0 3px;margin:1px auto 0;max-width:44px;white-space:nowrap}
.preplan-view :deep(.row-exported .row-idx){opacity:.5}
.preplan-view :deep(.el-pagination__total),.preplan-view :deep(.el-pagination__jump){color:#5a90b8!important}
.preplan-view :deep(.el-pagination .el-pager li){background:rgba(0,40,80,.35)!important;color:#a8cce8!important;border-radius:4px;margin:0 2px;font-weight:600}
.preplan-view :deep(.el-pagination .el-pager li:hover){background:rgba(0,80,160,.45)!important;color:#e0f0ff!important}
.preplan-view :deep(.el-pagination .el-pager li.is-active){background:rgba(0,110,220,.6)!important;color:#fff!important}
.preplan-view :deep(.el-pagination .btn-prev),.preplan-view :deep(.el-pagination .btn-next){background:rgba(0,40,80,.35)!important;color:#a8cce8!important;border-radius:4px}
.preplan-view :deep(.el-pagination .btn-prev:hover:not(:disabled)),.preplan-view :deep(.el-pagination .btn-next:hover:not(:disabled)){background:rgba(0,80,160,.45)!important;color:#e0f0ff!important}
.preplan-view :deep(.el-pagination .btn-prev:disabled),.preplan-view :deep(.el-pagination .btn-next:disabled){background:rgba(0,25,50,.45)!important;color:#3f6a8f!important}
.preplan-view :deep(.el-pagination button){background:transparent!important;color:#6aa3c8!important;border-color:#0d3050!important}
.preplan-view :deep(.btn-prev),.preplan-view :deep(.btn-next){background:transparent!important}
.preplan-view :deep(.el-input__wrapper){background:rgba(0,30,60,.5)!important;box-shadow:0 0 0 1px #0d3050 inset!important}
.form-input::-webkit-inner-spin-button,.form-input::-webkit-outer-spin-button{-webkit-appearance:none;margin:0}
/* ★ 自绘深色主题日历弹层（锚定输入框下方） */
.cal-mask{position:fixed;inset:0;z-index:200}
.cal-panel{position:absolute;background:#0a2640;border:1px solid #1a3a5f;border-radius:12px;padding:12px 14px;box-shadow:0 20px 60px rgba(0,10,30,.8);width:280px}
/* ★ 年月标题不换行：导航/清空/关闭按钮禁止收缩，标题独占剩余空间且 nowrap（字号由 14→12 保证 280px 面板装得下一行） */
.cal-head{display:flex;align-items:center;gap:3px;margin-bottom:8px;flex-wrap:nowrap}
.cal-title{flex:1 1 auto;min-width:0;text-align:center;font-size:12px;line-height:1.2;font-weight:600;color:#c8e0f8;white-space:nowrap}
.cal-nav{flex:0 0 auto;background:rgba(0,60,120,.3);border:1px solid #0d3050;color:#7ab8e0;border-radius:5px;width:22px;height:22px;padding:0;cursor:pointer;font-size:12px;line-height:1}
.cal-nav:hover{background:rgba(0,100,180,.4);color:#e0f0ff}
.cal-close{flex:0 0 auto;background:none;border:none;color:#5a90b8;font-size:13px;line-height:1;cursor:pointer;margin-left:4px;padding:0}
.cal-close:hover{color:#ff9a9a}
.cal-clear{flex:0 0 auto;background:rgba(200,60,60,.15);border:1px solid rgba(255,120,120,.35);color:#ff9a9a;font-size:10px;line-height:1.4;border-radius:4px;padding:2px 5px;cursor:pointer;margin-left:auto;font-family:inherit;transition:all .15s;white-space:nowrap}
.cal-clear:hover{background:rgba(220,70,70,.3);color:#ffc0c0}
.cal-week{display:grid;grid-template-columns:repeat(7,1fr);gap:2px;margin-bottom:4px}
.cal-week span{text-align:center;font-size:11px;color:#6aa3c8;padding:3px 0}
.cal-grid{display:grid;grid-template-columns:repeat(7,1fr);gap:2px}
.cal-day{text-align:center;font-size:12px;color:#c8ddf5;padding:6px 0;border-radius:5px;cursor:pointer;transition:background .12s}
.cal-day:hover{background:rgba(0,110,220,.35);color:#fff}
.cal-day.is-out{color:#3a5a78;cursor:default}
.cal-day.is-out:hover{background:none;color:#3a5a78}
.cal-day.is-today{box-shadow:inset 0 0 0 1px #00d4aa;color:#00d4aa;font-weight:700}
.cal-day.is-picked{background:rgba(0,150,120,.25);color:#7df0d8;font-weight:700}
.cal-day.is-today.is-picked{background:rgba(0,150,120,.35);color:#8ff5e0}

/* ★ 2026-09-20 导入「归属预排月份」确认弹层（自绘深色，与日历弹层同风格） */
.im-mask{position:fixed;inset:0;z-index:300;background:rgba(2,8,18,.55);display:flex;align-items:center;justify-content:center}
.im-panel{width:420px;background:#0a2640;border:1px solid #1a3a5f;border-radius:12px;box-shadow:0 20px 60px rgba(0,10,30,.8);overflow:hidden}
.im-head{display:flex;align-items:center;justify-content:space-between;padding:12px 16px;border-bottom:1px solid #12314f}
.im-title{font-size:13px;font-weight:700;color:#c8e0f8}
.im-close{background:none;border:none;color:#5a90b8;font-size:14px;line-height:1;cursor:pointer;padding:0}
.im-close:hover{color:#ff9a9a}
.im-body{padding:14px 16px}
.im-tip{font-size:12px;color:#8ab8d8;line-height:1.6;margin-bottom:12px}
.im-rows{display:flex;flex-direction:column;gap:8px}
.im-opt{display:flex;align-items:flex-start;gap:10px;padding:10px 12px;border:1px solid #12314f;border-radius:8px;cursor:pointer;transition:all .15s;background:rgba(6,20,38,.6)}
.im-opt:hover{border-color:#1e4a78;background:rgba(10,32,58,.8)}
.im-opt.on{border-color:#0077cc;background:rgba(0,80,160,.22)}
.im-radio{flex:0 0 auto;width:14px;height:14px;border-radius:50%;border:1.5px solid #2a5a86;margin-top:2px;position:relative}
.im-radio.on{border-color:#3fa9f5}
.im-radio.on::after{content:"";position:absolute;inset:2.5px;border-radius:50%;background:#3fa9f5}
.im-opt-txt{display:flex;flex-direction:column;gap:3px;min-width:0}
.im-opt-txt b{font-size:12.5px;color:#d8ecff;font-weight:600}
.im-opt-txt i{font-style:normal;font-size:11px;color:#6aa3c8;line-height:1.5}
.im-sel-row{display:flex;align-items:center;gap:10px;margin-top:12px;padding-top:12px;border-top:1px dashed #12314f}
.im-sel-label{font-size:12px;color:#8ab8d8;flex:0 0 auto}
.im-sel{width:150px}
.im-foot{display:flex;justify-content:flex-end;gap:8px;padding:12px 16px;border-top:1px solid #12314f;background:rgba(4,14,28,.5)}

/* ══════════════════════════════════════════════════════════════════════
   ★ 白天主题覆盖（2026-09-18）
   根因：本页原样式整套写死深色（文字 #c8ddf5 / 表头底 #0a1a30 / ORT-N 格
   rgba(220,50,50,.28)+#ffaaaa / 面板底 rgba(5,15,30,…)），且无 [data-theme="light"] 覆盖，
   切白天后浅字压浅底 → 糊成一片；红底浅红字 → 完全读不出。
   此处统一改为「浅底 + 深字」，语义色（红/黄/绿）加深以保证白底可读。
   scoped：用 .preplan-view 承接 data-v；Element Plus 内部用 :deep。
   ══════════════════════════════════════════════════════════════════════ */
[data-theme="light"] .preplan-view {
  color: #1a4070;

  .ptag { background: #dbe7f6; border-color: #bcd4ec; color: #2a5a86; }
  .ptitle { color: #0a2858; span { color: #0a8f6e; } }
  .bsm { border-color: #c0d2e4; background: var(--surface-2); color: #4a6a8a;
    &:hover { background: #cddcec; color: #24507a; }
    &.act { background: #c9ddf3; border-color: #7fb2e0; color: #14508c; } }

  .top-bar { background: var(--surface-2); border-color: var(--line-1); }
  .uc-item { background: var(--surface-2); border-color: #c0d2e4;
    &.has-file { border-color: #7fb2e0; background: #dbe7f6; }
    &.drag-over { border-color: #1f8fd8; background: #cadcf0; box-shadow: 0 0 0 1px rgba(31,143,216,.45), 0 0 12px rgba(31,143,216,.18); } }
  .uc-drop-hint { color: #fff; background: rgba(31,143,216,.72); }
  .uc-label { color: #5a7a9a; }
  .uc-name { color: #0a2858; }
  .uc-pick { background: #dbe7f6; border-color: #9cc4e6; color: #2a5a86;
    &:hover { background: #d3e5f8; color: #14508c; } }
  .uc-remove { color: #d24a4a; &:hover { color: #b81f1f; } }
  .uc-result { color: #0a8f6e; }
  .row-btn { border-color: #c0d2e4; background: var(--surface-2); color: #3a6a94;
    &:hover { background: #cddcec; color: #0a2858; } }
  .run-btn.sec { background: var(--well); color: #4a6a8a; border-color: #c0d2e4;
    &:hover:not(:disabled) { background: #cddcec; color: #24507a; } }
  .run-btn.primary:disabled { background: #e6edf4; color: #9ab0c4; }

  .err-bar { background: #fdecec; border-color: #f0b8b8; }
  .err-text, .err-close { color: #c0392b; }

  .rule-bar { background: var(--surface-2); border-color: var(--line-1); }
  .rule-bar-title { color: #0a2858; }
  .rule-pill-xs { background: #dbe7f6; border-color: #b8d4ec; color: #2a5a86;
    &:hover { background: #d3e5f8; color: #14508c; }
    em { background: rgba(0,0,0,.06); color: #5a7a9a; } }
  .rt-hint { color: #5a7a9a; strong { color: #0a8f6e; } }

  .table-wrapper { background: var(--surface-1); border-color: var(--line-1); }
  .row-idx { color: #7a93ab; }
  .filter-reason { color: #b8860b; }
  .cell-text { box-shadow: inset 0 0 0 1px rgba(60,150,220,.35); background: rgba(60,150,220,.05); }
  .cell-text:hover { box-shadow: inset 0 0 0 1px #1f8fd8; background: rgba(60,150,220,.13); }
  .cell-input { border-color: #c0d2e4; color: #0a2858;
    &:focus { border-color: #1f8fd8; background: #dcebfa; } }
  .cell-missing, .cell-ort-n { background: #fbdede; color: #c0392b; }
  .cell-text.cell-missing, .cell-text.cell-ort-n, .cell-input.cell-missing, .cell-input.cell-ort-n { background: #fbdede; color: #c0392b; }
  .exp-tag { color: #5a7a9a; border-color: #bcd4ec; }
  .cell-select :deep(.el-select__selected-item) { color: #0a2858 !important; }

  .pagination-bar { background: var(--surface-2); border-color: var(--line-1); }
  .pagination-info { color: #5a7a9a; .total { color: #0a8f6e; } }
  .src-a { color: #0a6fd0; } .src-b { color: #1f8f3f; } .src-ext { color: #b8860b; }
  .empty-state { color: #93a9bd; .empty-icon { opacity: .4; } }

  .runov { background: rgba(20,45,80,.42); }
  .runbox { background: var(--surface-1); border-color: var(--line-1); box-shadow: 0 24px 80px rgba(20,60,110,.18); }
  .runbox-close { color: #9ab0c4; &:hover { color: #14508c; } }
  .run-title { color: #0a2858; } .run-subtitle { color: #93a9bd; }
  .form-section { background: var(--surface-2); border-color: var(--line-2); }
  .form-lbl { color: #5a7a9a; }
  .form-input, .form-select { background: var(--field); border-color: #c0d2e4; color: #0a2858;
    &:focus { border-color: #1f8fd8; } &::placeholder { color: #a8bccd; } }
  .form-check { color: #0a2858; }

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

  /* ★ 导入「归属月份」确认弹层（白天主题） */
  .im-mask { background: rgba(20,50,90,.28); }
  .im-panel { background: var(--surface-1); border-color: var(--line-1); box-shadow: 0 20px 60px rgba(20,60,110,.18); }
  .im-head { border-bottom-color: var(--line-2); }
  .im-title { color: #0a2858; }
  .im-close { color: #5a7a9a; &:hover { color: #c0392b; } }
  .im-tip { color: #4a6a8a; }
  .im-opt { background: var(--surface-2); border-color: var(--line-2); &:hover { background: #dcebfa; border-color: #bcd4ec; } }
  .im-opt.on { background: #e6f1fc; border-color: #2a7fd0; }
  .im-radio { border-color: #a8bccd; }
  .im-radio.on { border-color: #2a7fd0; &::after { background: #2a7fd0; } }
  .im-opt-txt b { color: #0a2858; }
  .im-opt-txt i { color: #5a7a9a; }
  .im-sel-row { border-top-color: var(--line-2); }
  .im-sel-label { color: #4a6a8a; }
  .im-foot { border-top-color: var(--line-2); background: var(--surface-2); }

  /* Element Plus：表头 / 行 / 分页 / 下拉 / 单选 / loading */
  :deep(.el-table) { --el-table-bg-color: transparent; --el-table-tr-bg-color: transparent;
    --el-table-header-bg-color: #eef4fa; --el-table-row-hover-bg-color: #eaf3fc;
    --el-table-border-color: var(--line-2); --el-table-header-text-color: #3a6a94; --el-table-text-color: #0a2858; }
  :deep(.el-table__header-wrapper th) { background: var(--surface-2) !important; color: #3a6a94 !important; }
  :deep(.el-table__body tr:hover > td) { background: #dce8f6 !important; }
  :deep(.el-loading-mask) { background: rgba(233,240,248,.82) !important; }
  :deep(.row-external td) { background: #fdf3e2 !important; }
  :deep(.row-filtered) { opacity: .72; background: rgba(180,150,50,.10); }
  :deep(.el-select__wrapper), :deep(.el-input__wrapper) { background: var(--field) !important; box-shadow: 0 0 0 1px #c9daea inset !important; }
  :deep(.el-radio-button__inner) { background: var(--surface-2); border-color: #c0d2e4; color: #4a6a8a; }
  :deep(.el-radio-button__original-radio:checked + .el-radio-button__inner) { background: #cfe4f8; color: #14508c; }
  :deep(.el-pagination__total), :deep(.el-pagination__jump) { color: #5a7a9a !important; }
  :deep(.el-pagination .el-pager li) { background: var(--surface-2) !important; color: #2a5a86 !important; }
  :deep(.el-pagination .el-pager li:hover) { background: #cddcec !important; color: #0a2858 !important; }
  :deep(.el-pagination .el-pager li.is-active) { background: #2a7fd0 !important; color: #ffffff !important; }
  :deep(.el-pagination .btn-prev), :deep(.el-pagination .btn-next) { background: var(--surface-2) !important; color: #2a5a86 !important; }
  :deep(.el-pagination .btn-prev:disabled), :deep(.el-pagination .btn-next:disabled) { background: #f2f5f8 !important; color: #a8bccd !important; }
  :deep(.el-pagination button) { background: transparent !important; color: #4a6a8a !important; border-color: #c0d2e4 !important; }
}
</style>