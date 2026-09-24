<template>
  <div class="entry-view">
    <!-- 标题栏 -->
    <div class="pbar">
      <div class="pbar-left">
        <div class="ptag">MASTER DATA</div>
        <div class="ptitle">基础资料表 · <span>P/N 主数据（52阶料号 / 满箱量 / 客户）</span></div>
      </div>
      <div class="pright">
        <span class="count-tag">共 <strong>{{ total }}</strong> 条</span>
      </div>
    </div>

    <!-- 操作栏 -->
    <div class="top-bar">
      <div class="tb-left">
        <el-input
          v-model="keyword"
          placeholder="搜索 P/N / Model / 52阶料号 / 客户"
          clearable
          size="small"
          class="search-input"
          @input="loadData"
        />
      </div>
      <div class="tb-right">
        <button type="button" class="run-btn primary" @click="openForm(null)">
          <el-icon><Plus /></el-icon> 新增 P/N
        </button>
      </div>
    </div>

    <!-- 说明条 -->
    <div class="hint-bar">
      <span class="hint-icon">ℹ️</span>
      <span>
        每次导入计划时，自动以 <b>P/N</b> 为 Key 查找并带入对应字段；数据永久有效，人工维护。
        若预排料号在基础资料表中查无对应 P/N，相关字段将标记<b class="red">红色背景</b>，提醒排产人员补建。
      </span>
    </div>

    <!-- 表格 -->
    <div class="table-section">
      <div class="table-wrapper">
        <el-table :data="pagedRows" v-loading="loading" size="small" style="width: 100%" class="entry-table" empty-text="暂无数据，请点击右上角「新增 P/N」录入">
          <el-table-column prop="pn" label="P/N" min-width="160" align="center" show-overflow-tooltip>
            <template #default="{row}"><span class="pn-cell">{{ row.pn || '-' }}</span></template>
          </el-table-column>
          <el-table-column prop="model" label="Model" min-width="160" align="center" show-overflow-tooltip>
            <template #default="{row}"><span class="model-cell">{{ row.model || '-' }}</span></template>
          </el-table-column>
          <el-table-column prop="material_code_52" label="52阶料号" min-width="160" align="center" show-overflow-tooltip />
          <el-table-column prop="box_quantity" label="满箱量" width="100" align="center">
            <template #default="{row}"><span>{{ row.box_quantity ?? '-' }}</span></template>
          </el-table-column>
          <el-table-column prop="customer" label="客户" min-width="140" align="center" show-overflow-tooltip />
          <el-table-column prop="updated_at" label="更新时间" width="160" align="center">
            <template #default="{row}">{{ (row.updated_at||'').slice(0,16).replace('T',' ') }}</template>
          </el-table-column>
          <el-table-column label="操作" width="150" align="center">
            <template #default="{row}">
              <button type="button" class="row-btn" @click="openForm(row)">编辑</button>
              <button type="button" class="row-btn danger" @click="removeRow(row)">删除</button>
            </template>
          </el-table-column>
        </el-table>
      </div>
    </div>

    <!-- 分页（性能优化：几千条数据只渲染当前页） -->
    <div class="pagination-bar">
      <el-pagination v-model:current-page="currentPage" v-model:page-size="pageSize" :page-sizes="[50, 100, 200, 500]"
        :total="total" layout="sizes,prev,pager,next" size="small" @current-change="currentPage = $event" @size-change="currentPage = 1" />
    </div>

    <!-- 新增/编辑弹窗 -->
    <el-dialog v-model="formVisible" :title="editing ? '编辑 P/N' : '新增 P/N'" width="480px" class="entry-dialog">
      <el-form :model="form" label-width="90px" @submit.prevent>
        <el-form-item label="P/N" required>
          <el-input v-model="form.pn" placeholder="如 97.24M61.985（唯一值，作为查找 Key）" :disabled="!!editing" />
        </el-form-item>
        <el-form-item label="Model">
          <el-input v-model="form.model" placeholder="如 M215HVN02.5（可选）" />
        </el-form-item>
        <el-form-item label="52阶料号">
          <el-input v-model="form.material_code_52" placeholder="如 97.24M61.985" />
        </el-form-item>
        <el-form-item label="满箱量">
          <el-input-number v-model="form.box_quantity" :min="0" :controls="false" style="width:100%" placeholder="每箱数量" />
        </el-form-item>
        <el-form-item label="客户">
          <el-input v-model="form.customer" placeholder="客户名称" />
        </el-form-item>
      </el-form>
      <template #footer>
        <button type="button" class="run-btn sec" @click="formVisible=false">取消</button>
        <button type="button" class="run-btn primary" :disabled="saving" @click="saveForm">{{ saving ? '保存中...' : '保存' }}</button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Plus } from '@element-plus/icons-vue'
import { entryTableApi } from '../api/entryTable'
defineOptions({ name: 'EntryTableView' })

const loading = ref(false)
const allRows = ref([])
const tableData = ref([])
const total = ref(0)
const keyword = ref('')
const currentPage = ref(1)
const pageSize = ref(100)
// ★ 性能优化：本地分页，只渲染当前页，避免几千行全量渲染
const pagedRows = computed(() => {
  const start = (currentPage.value - 1) * pageSize.value
  return allRows.value.slice(start, start + pageSize.value)
})

const formVisible = ref(false)
const editing = ref(null)
const saving = ref(false)
const form = ref({ pn: '', model: '', material_code_52: '', box_quantity: 0, customer: '' })

async function loadData() {
  loading.value = true
  try {
    const params = {}
    if (keyword.value && keyword.value.trim()) {
      params.search = keyword.value.trim()
    }
    const res = await entryTableApi.list(params)
    // 兼容分页响应与数组响应
    const data = Array.isArray(res.data) ? res.data : (res.data.results || res.data.data || [])
    allRows.value = data
    tableData.value = data
    total.value = Array.isArray(res.data) ? data.length : (res.data.count ?? data.length)
    currentPage.value = 1
  } catch (e) {
    console.error(e)
    ElMessage.error('加载基础资料表失败')
  } finally {
    loading.value = false
  }
}

function openForm(row) {
  editing.value = row || null
  form.value = row
    ? { pn: row.pn, model: row.model || '', material_code_52: row.material_code_52 || '', box_quantity: row.box_quantity ?? 0, customer: row.customer || '' }
    : { pn: '', model: '', material_code_52: '', box_quantity: 0, customer: '' }
  formVisible.value = true
}

async function saveForm() {
  const pn = (form.value.pn || '').trim()
  if (!pn) {
    ElMessage.warning('请填写 P/N')
    return
  }
  saving.value = true
  try {
    const payload = {
      pn: pn,
      model: (form.value.model || '').trim(),
      material_code_52: (form.value.material_code_52 || '').trim(),
      box_quantity: form.value.box_quantity ?? 0,
      customer: (form.value.customer || '').trim()
    }
    if (editing.value?.id) {
      await entryTableApi.update(editing.value.id, payload)
      ElMessage.success('更新成功')
    } else {
      await entryTableApi.create(payload)
      ElMessage.success('新增成功')
    }
    formVisible.value = false
    await loadData()
  } catch (e) {
    const msg = e.response?.data
    // 后端唯一约束错误提示
    if (typeof msg === 'string') ElMessage.error(msg)
    else if (msg?.pn) ElMessage.error('P/N 已存在：' + msg.pn[0])
    else if (msg?.detail) ElMessage.error(msg.detail)
    else ElMessage.error('保存失败：' + (e.response?.status === 400 ? 'P/N 重复或字段不合法' : e.message))
  } finally {
    saving.value = false
  }
}

async function removeRow(row) {
  try {
    await ElMessageBox.confirm(`确定删除 P/N「${row.pn}」吗？`, '确认删除', { type: 'warning' })
  } catch {
    return
  }
  try {
    await entryTableApi.remove(row.id)
    ElMessage.success('已删除')
    await loadData()
  } catch (e) {
    ElMessage.error('删除失败：' + (e.response?.data?.detail || e.message))
  }
}

onMounted(loadData)
</script>

<style lang="scss" scoped>
.entry-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 6px;
  min-height: 0;
  background: transparent;
}

.pbar { display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }
.pbar-left { display: flex; align-items: center; gap: 8px; }
.ptag {
  background: rgba(0, 100, 170, .25);
  border: 1px solid #0d4a70;
  color: #7fc8e8;
  font-size: 10px;
  font-weight: 700;
  letter-spacing: 1px;
  padding: 3px 10px;
  border-radius: 4px;
}
.ptitle { font-size: 15px; font-weight: 500; color: #c8e0f8; span { color: #00d4aa; } }
.count-tag { font-size: 11px; color: #5d8aaa; strong { color: #00d4aa; } }

.top-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  padding: 6px 12px;
  background: linear-gradient(135deg, rgba(5, 15, 30, .6), rgba(7, 26, 46, .6));
  border: 1px solid #0d2a48;
  border-radius: 8px;
  flex-shrink: 0;
}
.search-input { width: 260px; }

.hint-bar {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 6px 12px;
  font-size: 11px;
  color: #a0c8e8;
  background: rgba(0, 60, 120, .12);
  border: 1px dashed #0d4a70;
  border-radius: 6px;
  flex-shrink: 0;
  b { color: #c8e0f8; }
  b.red { color: #ff6b6b; }
}

.table-section { flex: 1; min-height: 0; overflow: auto; }
.table-wrapper {
  background: rgba(5, 15, 30, .5);
  border: 1px solid #0d2a48;
  border-radius: 8px;
  overflow: hidden;
}
.model-cell { color: #00d4aa; font-weight: 600; }

.run-btn {
  font-size: 11px; font-weight: 600; padding: 4px 10px; border-radius: 12px; cursor: pointer;
  border: none; font-family: inherit; display: inline-flex; align-items: center; gap: 3px;
  &.primary {
    background: linear-gradient(135deg, #0055aa, #0077cc); color: #fff;
    box-shadow: 0 2px 6px rgba(0, 100, 200, .35);
    &:hover:not(:disabled) { box-shadow: 0 3px 12px rgba(0, 120, 240, .5); transform: translateY(-1px); }
    &:disabled { background: rgba(0, 40, 80, .4); color: #4d7d9e; cursor: not-allowed; }
  }
  &.sec { background: rgba(0, 40, 80, .3); color: #5a90b8; border: 1px solid #0d3050; &:hover { background: rgba(0, 60, 120, .4); color: #90c0e8; } }
}
.row-btn {
  font-size: 10px; padding: 2px 8px; border-radius: 10px; cursor: pointer; margin: 0 3px;
  border: 1px solid #0d3050; background: rgba(0, 60, 120, .3); color: #8ab8d8; font-family: inherit;
  &:hover { background: rgba(0, 100, 180, .4); color: #c8e0f8; }
  &.danger { color: #e09090; border-color: #5a2028; background: rgba(105, 24, 32, .35); &:hover { background: rgba(140, 30, 40, .5); color: #ffaaaa; } }
}

/* Element Plus 深色适配 */
.entry-table {
  --el-table-bg-color: transparent;
  --el-table-tr-bg-color: rgba(5, 15, 30, .5);
  --el-table-header-bg-color: rgba(0, 40, 80, .35);
  --el-table-border-color: #0d2a48;
  --el-table-row-hover-bg-color: rgba(0, 60, 120, .25);
  --el-table-text-color: #c8ddf5;
  --el-table-header-text-color: #a0c8e8;
  color: #c8ddf5;
}

/* 表格加载遮罩改为深色(避免转圈时整块白屏) */
.entry-view :deep(.el-loading-mask) { background: rgba(3, 9, 15, .72)!important; }
.entry-view :deep(.el-loading-spinner .circular) { color: #00a8d4; }

/* 输入框/下拉统一深色单边框(修复"双框/框内套框/浅蓝边") */
.entry-view :deep(.el-input__wrapper),
.entry-view :deep(.el-input-number .el-input__wrapper),
.entry-view :deep(.el-select__wrapper),
.entry-view :deep(.el-textarea__inner) {
  background: rgba(0, 30, 60, .5)!important;
  box-shadow: 0 0 0 1px #0d3050 inset!important;
}
/* hover / focus 一律保持深色边框,去掉 Element 默认浅蓝边框 */
.entry-view :deep(.el-input__wrapper:hover),
.entry-view :deep(.el-input__wrapper.is-focus),
.entry-view :deep(.el-input-number .el-input__wrapper:hover),
.entry-view :deep(.el-input-number .el-input__wrapper.is-focus),
.entry-view :deep(.el-select__wrapper:hover),
.entry-view :deep(.el-select__wrapper.is-focused),
.entry-view :deep(.el-textarea__inner:hover),
.entry-view :deep(.el-textarea__inner:focus) {
  box-shadow: 0 0 0 1px #0d3050 inset!important;
}
/* 输入框 inner 彻底无边框/透明背景,去掉残留小框 */
.entry-view :deep(.el-input__inner) {
  background-color: transparent!important;
  border: none!important;
  box-shadow: none!important;
  outline: none!important;
  color: #c8ddf5!important;
}
.entry-view :deep(.el-input__inner::placeholder) { color: #5d8aaa; }
.entry-view :deep(.el-input-number .el-input__inner) { background-color: transparent!important; }
.entry-view :deep(.el-select__input) { background-color: transparent!important; color: #c8ddf5!important; }
/* el-input-number 加减按钮边框也去掉浅蓝 */
.entry-view :deep(.el-input-number__increase),
.entry-view :deep(.el-input-number__decrease) {
  border-color: #0d3050!important;
  color: #8ab8d8!important;
  background: rgba(0, 40, 80, .3)!important;
}

/* 弹窗深色 */
.entry-view :deep(.el-dialog) {
  background: #0a1f38;
  border: 1px solid #0d3050;
  border-radius: 10px;
}
.entry-view :deep(.el-dialog__title) { color: #c8e0f8; }
.entry-view :deep(.el-dialog .el-form-item__label) { color: #a0c8e8; }
.entry-view :deep(.el-dialog .el-input__wrapper) { background: rgba(0, 30, 60, .5)!important; }
.pagination-bar{ display:flex; justify-content:flex-end; padding:4px 2px; flex-shrink:0; }
.entry-view :deep(.el-pagination .el-pager li){ background:rgba(0,40,80,.35)!important; color:#a8cce8!important; border-radius:4px; margin:0 2px; font-weight:600; }
.entry-view :deep(.el-pagination .el-pager li.is-active){ background:rgba(0,110,220,.6)!important; color:#fff!important; }
.entry-view :deep(.el-pagination .btn-prev),.entry-view :deep(.el-pagination .btn-next){ background:rgba(0,40,80,.35)!important; color:#a8cce8!important; }
.entry-view :deep(.el-pagination .btn-prev:hover:not(:disabled)),.entry-view :deep(.el-pagination .btn-next:hover:not(:disabled)){ background:rgba(0,80,160,.45)!important; color:#e0f0ff!important; }
.entry-view :deep(.el-pagination .btn-prev:disabled),.entry-view :deep(.el-pagination .btn-next:disabled){ background:rgba(0,25,50,.45)!important; color:#3f6a8f!important; }

/* ══════════════════════════════════════════════════════════════════════
   ★ 白天主题覆盖（2026-09-18）
   根因：本页原样式整套写死深色（标题 #c8e0f8 / 面板底 rgba(5,15,30,…) /
   表头底 rgba(0,40,80,.35) / 输入框底 rgba(0,30,60,.5) / 弹窗底 #0a1f38），
   且无 [data-theme="light"] 覆盖，切白天后浅字压浅底 → 读不清。
   此处统一改为「浅底 + 深字」，语义色加深以保证白底可读。
   scoped：用 .entry-view 承接 data-v；Element Plus 内部用 :deep。
   ══════════════════════════════════════════════════════════════════════ */
[data-theme="light"] .entry-view {
  color: #1a4070;

  .ptag { background: #dbe7f6; border-color: #bcd4ec; color: #2a5a86; }
  .ptitle { color: #0a2858; span { color: #0a8f6e; } }
  .count-tag { color: #5a7a9a; strong { color: #0a8f6e; } }

  .top-bar { background: var(--surface-2); border-color: var(--line-1); }
  .hint-bar { color: #2a5a86; background: var(--surface-2); border-color: #bcd4ec;
    b { color: #0a2858; } b.red { color: #c0392b; } }

  .table-wrapper { background: var(--surface-1); border-color: var(--line-1); }
  .model-cell { color: #0a8f6e; }

  .run-btn.sec { background: var(--well); color: #4a6a8a; border-color: #c0d2e4;
    &:hover { background: #cddcec; color: #24507a; } }
  .run-btn.primary:disabled { background: #e6edf4; color: #9ab0c4; }
  .row-btn { border-color: #c0d2e4; background: var(--surface-2); color: #3a6a94;
    &:hover { background: #cddcec; color: #0a2858; } }
  .row-btn.danger { background: #fdecec; color: #c0392b; border-color: #f0b8b8;
    &:hover { background: #fadada; color: #a02020; } }

  .entry-table { --el-table-bg-color: transparent; --el-table-tr-bg-color: #ffffff;
    --el-table-header-bg-color: #eef4fa; --el-table-border-color: var(--line-2);
    --el-table-row-hover-bg-color: #eaf3fc; --el-table-text-color: #0a2858;
    --el-table-header-text-color: #3a6a94; color: #0a2858; }

  :deep(.el-table__header-wrapper th) { background: var(--surface-2) !important; color: #3a6a94 !important; }
  :deep(.el-table__body tr:hover > td) { background: #dce8f6 !important; }
  :deep(.el-loading-mask) { background: rgba(233,240,248,.82) !important; }
  :deep(.el-loading-spinner .circular) { color: #1f8fd8; }

  :deep(.el-input__wrapper), :deep(.el-input-number .el-input__wrapper),
  :deep(.el-select__wrapper), :deep(.el-textarea__inner) {
    background: var(--field) !important; box-shadow: 0 0 0 1px #c9daea inset !important; }
  :deep(.el-input__wrapper:hover), :deep(.el-input__wrapper.is-focus),
  :deep(.el-input-number .el-input__wrapper:hover), :deep(.el-input-number .el-input__wrapper.is-focus),
  :deep(.el-select__wrapper:hover), :deep(.el-select__wrapper.is-focused),
  :deep(.el-textarea__inner:hover), :deep(.el-textarea__inner:focus) {
    box-shadow: 0 0 0 1px #9cc4e6 inset !important; }
  :deep(.el-input__inner) { background-color: transparent !important; border: none !important;
    box-shadow: none !important; outline: none !important; color: #0a2858 !important; }
  :deep(.el-input__inner::placeholder) { color: #a8bccd; }
  :deep(.el-input-number .el-input__inner) { color: #0a2858 !important; }
  :deep(.el-select__input) { background-color: transparent !important; color: #0a2858 !important; }
  :deep(.el-input-number__increase), :deep(.el-input-number__decrease) {
    border-color: #c0d2e4 !important; color: #2a5a86 !important; background: var(--surface-2) !important; }

  :deep(.el-dialog) { background: var(--surface-1); border-color: var(--line-1); }
  :deep(.el-dialog__title) { color: #0a2858; }
  :deep(.el-dialog .el-form-item__label) { color: #2a5a86; }
  :deep(.el-dialog .el-input__wrapper) { background: var(--field) !important; }

  :deep(.el-pagination__total), :deep(.el-pagination__jump) { color: #5a7a9a !important; }
  :deep(.el-pagination .el-pager li) { background: var(--surface-2) !important; color: #2a5a86 !important; }
  :deep(.el-pagination .el-pager li:hover) { background: #cddcec !important; color: #0a2858 !important; }
  :deep(.el-pagination .el-pager li.is-active) { background: #2a7fd0 !important; color: #ffffff !important; }
  :deep(.el-pagination .btn-prev), :deep(.el-pagination .btn-next) { background: var(--surface-2) !important; color: #2a5a86 !important; }
  :deep(.el-pagination .btn-prev:hover:not(:disabled)), :deep(.el-pagination .btn-next:hover:not(:disabled)) { background: #cddcec !important; color: #0a2858 !important; }
  :deep(.el-pagination .btn-prev:disabled), :deep(.el-pagination .btn-next:disabled) { background: #f2f5f8 !important; color: #a8bccd !important; }
}
</style>
