<template>
  <div class="excel-flow-view">
    <div class="page-head">
      <span class="ptag">流程自动化</span>
      <h1 class="ptitle">🧪 Excel 处理测试</h1>
      <p class="ptip">拖入 Excel → 调用 Dify 工作流处理 → 完成后下载结果文件。</p>
    </div>

    <!-- 拖拽上传区 -->
    <div
      class="drop-zone"
      :class="{ over: dragOver, busy: isActive }"
      @dragover.prevent="dragOver = true"
      @dragleave.prevent="dragOver = false"
      @drop.prevent="onDrop"
      @click="!isActive && pickFile()"
    >
      <input ref="fileInput" type="file" accept=".xlsx,.xls,.csv" hidden @change="onPick" />
      <div class="dz-icon">📄</div>
      <div class="dz-main">{{ isActive ? '任务处理中…' : '拖拽 Excel 到此处，或点击选择文件' }}</div>
      <div class="dz-sub">支持 .xlsx / .xls / .csv，单个文件，≤ {{ maxMb }}MB</div>
    </div>

    <!-- 任务状态卡 -->
    <div v-if="task" class="status-card" :class="task.status">
      <div class="sc-row">
        <span class="sc-file">📎 {{ task.filename }}</span>
        <span class="sc-badge" :class="task.status">{{ statusText(task.status) }}</span>
      </div>
      <div class="sc-progress">
        <span v-if="isActive" class="spinner"></span>
        <span>{{ task.progress || statusText(task.status) }}</span>
      </div>
      <div v-if="task.status === 'failed'" class="sc-error">⚠️ {{ task.error || '处理失败' }}</div>
      <div class="sc-actions">
        <a v-if="task.status === 'done'" class="btn btn-primary" :href="downloadUrl" @click="onDownload">⬇️ 下载结果</a>
        <button v-if="!isActive" class="btn btn-outline" @click="reset()">再来一个</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import { excelFlowUpload, excelFlowStatus, EXCEL_FLOW_DOWNLOAD_URL } from '../api/excelflow'

const fileInput = ref(null)
const dragOver = ref(false)
const task = ref(null)
const maxMb = 20
const downloadUrl = EXCEL_FLOW_DOWNLOAD_URL

let pollTimer = null

const ACTIVE = ['queued', 'uploading', 'running', 'downloading']
const isActive = computed(() => !!task.value && ACTIVE.includes(task.value.status))

function statusText(s) {
  return ({
    queued: '排队中', uploading: '上传中', running: '处理中',
    downloading: '下载结果', done: '已完成', failed: '失败',
  }[s]) || s
}

function pickFile() { fileInput.value && fileInput.value.click() }
function onPick(e) { const f = e.target.files && e.target.files[0]; if (f) submit(f); e.target.value = '' }
function onDrop(e) {
  dragOver.value = false
  const f = e.dataTransfer && e.dataTransfer.files && e.dataTransfer.files[0]
  if (f) submit(f)
}

async function submit(file) {
  const ext = '.' + (file.name.split('.').pop() || '').toLowerCase()
  if (!['.xlsx', '.xls', '.csv'].includes(ext)) { ElMessage.warning('仅支持 .xlsx / .xls / .csv'); return }
  if (file.size > maxMb * 1024 * 1024) { ElMessage.warning(`文件超过 ${maxMb}MB 上限`); return }
  try {
    const d = await excelFlowUpload(file)
    if (d && d.success) { task.value = d.task; startPoll() }
    else ElMessage.error(d?.error || '上传失败')
  } catch (e) {
    ElMessage.error(e?.response?.data?.error || ('上传失败：' + (e?.message || e)))
  }
}

function startPoll() {
  stopPoll()
  pollTimer = setInterval(async () => {
    try {
      const d = await excelFlowStatus()
      if (d && d.task) {
        task.value = d.task
        if (!ACTIVE.includes(d.task.status)) stopPoll()
      }
    } catch (e) { /* 轮询失败静默重试 */ }
  }, 2000)
}
function stopPoll() { if (pollTimer) { clearInterval(pollTimer); pollTimer = null } }

function onDownload() { ElMessage.success('开始下载结果文件') }
function reset() { task.value = null; stopPoll() }

onMounted(async () => {
  // 刷新页面后若仍有任务在跑，恢复轮询
  try {
    const d = await excelFlowStatus()
    if (d && d.task) { task.value = d.task; if (ACTIVE.includes(d.task.status)) startPoll() }
  } catch (e) { /* 忽略 */ }
})
onUnmounted(stopPoll)
</script>

<style scoped>
.excel-flow-view { padding: 18px 22px; overflow-y: auto; height: 100%; color: var(--t2); }
.page-head { margin-bottom: 16px; }
.ptag { display: inline-block; font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 6px;
  background: var(--acg); color: var(--ac); border: 1px solid var(--bc); }
.ptitle { font-size: 20px; font-weight: 800; color: var(--t1); margin: 8px 0 4px; }
.ptip { font-size: 12px; color: var(--t4); margin: 0; }

.drop-zone {
  border: 2px dashed var(--line-1); border-radius: 14px; background: var(--surface-1);
  padding: 40px 20px; text-align: center; cursor: pointer; transition: border-color .15s, background .15s;
}
.drop-zone:hover { border-color: var(--ac); }
.drop-zone.over { border-color: var(--ac); background: var(--acg); }
.drop-zone.busy { cursor: default; opacity: .85; }
.dz-icon { font-size: 40px; margin-bottom: 10px; }
.dz-main { font-size: 15px; font-weight: 700; color: var(--t1); }
.dz-sub { font-size: 12px; color: var(--t4); margin-top: 6px; }

.status-card { margin-top: 16px; background: var(--surface-1); border: 1px solid var(--line-1);
  border-radius: 12px; padding: 14px 16px; box-shadow: var(--bc-g); }
.sc-row { display: flex; align-items: center; justify-content: space-between; gap: 10px; }
.sc-file { font-size: 13px; font-weight: 600; color: var(--t1); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.sc-badge { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 8px; flex: none; }
.sc-badge.done { background: var(--okg); color: var(--ok); }
.sc-badge.failed { background: var(--bdg); color: var(--bd); }
.sc-badge.uploading, .sc-badge.running, .sc-badge.downloading, .sc-badge.queued { background: var(--acg); color: var(--ac); }
.sc-progress { display: flex; align-items: center; gap: 8px; font-size: 12px; color: var(--t3); margin-top: 8px; }
.sc-error { font-size: 12px; color: var(--bd); margin-top: 8px; }
.sc-actions { display: flex; gap: 10px; margin-top: 14px; }

.spinner { width: 14px; height: 14px; border: 2px solid var(--ac); border-top-color: transparent;
  border-radius: 50%; display: inline-block; animation: efspin .8s linear infinite; }
@keyframes efspin { to { transform: rotate(360deg); } }

.btn { display: inline-flex; align-items: center; gap: 4px; font-size: 13px; font-weight: 700;
  padding: 8px 16px; border-radius: 8px; cursor: pointer; text-decoration: none; border: 1px solid transparent; }
.btn-primary { background: var(--ac); color: #fff; }
.btn-primary:hover { filter: brightness(1.08); }
.btn-outline { background: var(--surface-2); color: var(--t2); border-color: var(--line-1); }
.btn-outline:hover { background: var(--well); }
</style>
