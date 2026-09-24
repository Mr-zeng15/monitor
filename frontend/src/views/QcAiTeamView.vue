<template>
  <div class="qcai-view">
    <!-- ══ 页面标题栏（沿用项目 .pbar 约定）══ -->
    <div class="pbar">
      <div class="pbar-left">
        <div class="ptag">QC_AI_TEAM</div>
        <div class="ptitle">AI Agent 专案登记管理系统 · <span>V4</span></div>
      </div>
      <div class="pright">
        <div class="qclock">{{ clockDate }}<br>{{ clockTime }}</div>
      </div>
    </div>

    <!-- ══ 数据说明条（★ 已由 localStorage 改为服务端持久化）══ -->
    <div class="data-banner">
      <span class="db-ico">🗄️</span>
      <div>
        数据已保存到 <strong>服务器数据库</strong>，换电脑 / 换浏览器都能看到，多人共用同一份。
        建议定期点「备份 JSON」下载留档；需要还原或迁移时用「汇入 JSON」。
      </div>
    </div>

    <!-- ══ 命名原则说明（可折叠）══ -->
    <div class="naming-panel">
      <button type="button" class="naming-toggle" :class="{ open: namingOpen }" @click="namingOpen = !namingOpen">
        <span>📋</span> 命名原则说明
        <span class="chevron">▼</span>
      </button>
      <div class="naming-body" :class="{ open: namingOpen }">
        <div v-for="c in namingCards" :key="c.name" class="naming-card">
          <h4>{{ c.icon }} {{ c.name }}</h4>
          <div class="naming-code">{{ c.prefix }}_001_FUNCTION_XXX</div>
          <p>
            <span class="seg seg-prefix">{{ c.prefix }}</span>{{ c.name }}
            <span class="seg seg-num">001</span>流水码
            <span class="seg seg-func">FUNCTION</span>子分类
            <span class="seg seg-work">XXX</span>具体工作
          </p>
        </div>
      </div>
    </div>

    <!-- ══ 统计卡片 ══ -->
    <div class="stats-row">
      <div class="stat-card">
        <div class="stat-label">TOTAL AGENTS</div>
        <div class="stat-value">{{ stats.total }}</div>
        <div class="stat-sub">有效 {{ stats.active }} 笔</div>
      </div>
      <div v-for="g in stats.groups" :key="g.name" class="stat-card">
        <div class="stat-label">{{ g.name }}</div>
        <div class="stat-value">{{ g.count }}</div>
        <div class="stat-sub">使用中/开发中</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">AVG 成功率</div>
        <div class="stat-value sm">{{ stats.avgSuccess }}%</div>
      </div>
      <div class="stat-card">
        <div class="stat-label">AVG 耗时</div>
        <div class="stat-value sm">{{ stats.avgTime }}s</div>
      </div>
    </div>

    <!-- ══ 工具栏 ══ -->
    <div class="toolbar">
      <div class="toolbar-left">
        <div class="search-box">
          <span class="search-icon">🔍</span>
          <input v-model="search" type="text" placeholder="搜索 Agent名称 / 开发者…">
        </div>
        <el-select v-model="filterGroup" class="filter-sel" popper-class="app-select-popper" placeholder="全部群组" clearable>
          <el-option v-for="i in cats.group" :key="i" :label="i" :value="i" />
        </el-select>
        <el-select v-model="filterSubtype" class="filter-sel" popper-class="app-select-popper" placeholder="全部子类型" clearable>
          <el-option v-for="i in cats.subtype" :key="i" :label="i" :value="i" />
        </el-select>
        <el-select v-model="filterDev" class="filter-sel" popper-class="app-select-popper" placeholder="全部开发者" clearable>
          <el-option v-for="i in cats.dev" :key="i" :label="i" :value="i" />
        </el-select>
        <el-select v-model="filterStatus" class="filter-sel" popper-class="app-select-popper" placeholder="全部状态" clearable>
          <el-option v-for="s in statuses" :key="s" :label="s" :value="s" />
        </el-select>
      </div>
      <div class="toolbar-right">
        <button type="button" class="btn btn-teal" @click="exportSVGModal">🖼️ 输出 SVG</button>
        <button type="button" class="btn btn-indigo" :disabled="busy" @click="doExportJSON">📤 备份 JSON</button>
        <label class="btn btn-orange" :class="{ disabled: busy }">
          📥 汇入 JSON
          <input ref="importInput" type="file" accept=".json" style="display:none" @change="onImportFile">
        </label>
        <button type="button" class="btn btn-primary" @click="openModal('')">＋ 新增 Agent</button>
      </div>
    </div>

    <!-- ══ 表格 ══ -->
    <div class="table-wrap">
      <div class="table-header">
        <span class="table-title">🤖 Agent 专案列表</span>
        <span class="table-count">共 {{ filtered.length }} 笔</span>
      </div>
      <div class="table-scroll">
        <table>
          <thead>
            <tr>
              <th>Agent 名称</th><th>功能群组</th><th>子类型</th><th>技术架构</th><th>状态</th>
              <th>成功率</th><th>准确率</th><th>Token/次</th><th>耗时(s)</th>
              <th>效益类型</th><th>效益数值</th><th>开发者</th><th>操作</th>
            </tr>
          </thead>
          <tbody>
            <tr v-if="loading">
              <td colspan="13"><div class="no-data"><div class="icon">⏳</div>加载中…</div></td>
            </tr>
            <tr v-else-if="!filtered.length">
              <td colspan="13"><div class="no-data"><div class="icon">📭</div>暂无资料</div></td>
            </tr>
            <!-- ★ 不要写成 <tr v-for ... v-else>：Vue 3 里 v-if 优先级高于 v-for，
                 同元素混用属于反模式。这里用 template 包一层，语义最清晰。 -->
            <template v-else>
              <tr v-for="p in filtered" :key="p.id" :class="{ 'row-off': p.status === '废除' }">
                <td class="agent-name" :title="p.name">{{ p.name }}</td>
                <td>{{ p.group }}</td>
                <td>{{ p.subtype }}</td>
                <td>{{ p.arch }}</td>
                <td><span class="badge" :class="badgeCls(p.status)">{{ p.status }}</span></td>
                <td>{{ p.success !== '' && p.success !== undefined && p.success !== null ? p.success + '%' : '—' }}</td>
                <td>{{ p.accuracy !== '' && p.accuracy !== undefined && p.accuracy !== null ? p.accuracy + '%' : '—' }}</td>
                <td>{{ p.token || '—' }}</td>
                <td>{{ p.time !== '' && p.time !== undefined && p.time !== null ? p.time + 's' : '—' }}</td>
                <td>{{ p.btype || '—' }}</td>
                <td>{{ p.bval ? `${p.bval} ${p.btype === '耗时' ? '小时' : '人'}` : '—' }}</td>
                <td>{{ p.dev || '—' }}</td>
                <td>
                  <div class="ops">
                    <button v-if="p.status !== '废除'" type="button" class="btn btn-success-sm" @click="openModal(p.id)">修改</button>
                    <button v-if="p.status !== '废除'" type="button" class="btn btn-warn-sm" @click="chStatus(p.id, '废除')">废除</button>
                    <button v-if="p.status === '废除'" type="button" class="btn btn-grey-sm" @click="chStatus(p.id, '开发中')">恢复</button>
                    <button type="button" class="btn btn-danger-sm" @click="askDel(p.id)">删除</button>
                  </div>
                </td>
              </tr>
            </template>
          </tbody>
        </table>
      </div>
    </div>

    <!-- ══ 新增/编辑弹窗 ══ -->
    <div v-if="mainModal" class="modal-overlay" @click.self="closeModal">
      <div class="modal">
        <div class="modal-head">
          <h2>{{ form.id ? '✏️ 修改 Agent' : '＋ 新增 Agent' }}</h2>
          <button type="button" class="modal-close" @click="closeModal">✕</button>
        </div>
        <div class="modal-body">
          <div class="form-section">
            <div class="form-section-title">📌 基本信息</div>
            <div class="form-grid">
              <div class="form-group">
                <label>功能群组 <span class="req">*</span></label>
                <div class="form-row">
                  <el-select v-model="form.group" class="form-sel" popper-class="app-select-popper" placeholder="请选择…">
                    <el-option v-for="i in cats.group" :key="i" :label="i" :value="i" />
                  </el-select>
                  <button type="button" class="btn-add-cat" title="管理分类" @click="openCatModal('group')">＋</button>
                </div>
              </div>
              <div class="form-group">
                <label>子类型 (Function) <span class="req">*</span></label>
                <div class="form-row">
                  <el-select v-model="form.subtype" class="form-sel" popper-class="app-select-popper" placeholder="请选择…">
                    <el-option v-for="i in cats.subtype" :key="i" :label="i" :value="i" />
                  </el-select>
                  <button type="button" class="btn-add-cat" title="管理分类" @click="openCatModal('subtype')">＋</button>
                </div>
              </div>
              <div class="form-group">
                <label>工作(英文) <span class="req">*</span></label>
                <input v-model="form.work" type="text" class="form-ctrl" placeholder="英文，如 AnomalyDetect" maxlength="30"
                       @input="form.work = form.work.replace(/[^A-Za-z0-9_]/g, '')">
                <span class="hint">仅限英文字母与数字</span>
              </div>
              <div class="form-group">
                <label>流水码 <span class="req">*</span></label>
                <div class="form-row">
                  <input v-model="form.seq" type="text" class="form-ctrl seq-input" placeholder="001" maxlength="3"
                         :readonly="!!form.id" @input="form.seq = form.seq.replace(/[^0-9]/g, '').slice(0, 3)">
                  <button type="button" class="btn btn-outline btn-sm" @click="autoAssign">⚡ 自动分配</button>
                </div>
                <span class="hint">废除专案编号保留，不被重新分配</span>
              </div>
              <div class="form-group form-full">
                <label>Agent 名称（自动生成）</label>
                <input :value="genName" type="text" class="form-ctrl generated" readonly placeholder="请先填写上方栏位">
              </div>
              <div class="form-group">
                <label>技术架构 <span class="req">*</span></label>
                <div class="form-row">
                  <el-select v-model="form.arch" class="form-sel" popper-class="app-select-popper" placeholder="请选择…">
                    <el-option v-for="i in cats.arch" :key="i" :label="i" :value="i" />
                  </el-select>
                  <button type="button" class="btn-add-cat" title="管理分类" @click="openCatModal('arch')">＋</button>
                </div>
              </div>
              <div class="form-group">
                <label>状态 <span class="req">*</span></label>
                <el-select v-model="form.status" class="form-sel" popper-class="app-select-popper">
                  <el-option v-for="s in statuses" :key="s" :label="s" :value="s" />
                </el-select>
              </div>
              <div class="form-group">
                <label>开发者</label>
                <div class="form-row">
                  <el-select v-model="form.dev" class="form-sel" popper-class="app-select-popper" placeholder="请选择…">
                    <el-option v-for="i in cats.dev" :key="i" :label="i" :value="i" />
                  </el-select>
                  <button type="button" class="btn-add-cat" title="管理开发者" @click="openCatModal('dev')">＋</button>
                </div>
              </div>
              <div class="form-group form-full">
                <label>专案说明</label>
                <input v-model="form.desc" type="text" class="form-ctrl" placeholder="简短说明用途…">
              </div>
            </div>
          </div>

          <div class="form-section">
            <div class="form-section-title">📊 评估指标</div>
            <div class="form-grid col3">
              <div class="form-group"><label>成功率 (%)</label>
                <input v-model="form.success" type="number" class="form-ctrl" min="0" max="100" step="0.1" placeholder="0~100"></div>
              <div class="form-group"><label>准确率 (%)</label>
                <input v-model="form.accuracy" type="number" class="form-ctrl" min="0" max="100" step="0.1" placeholder="0~100"></div>
              <div class="form-group"><label>Token 消耗 (单次)</label>
                <input v-model="form.token" type="number" class="form-ctrl" min="0" placeholder="tokens"></div>
              <div class="form-group"><label>单次耗时 (秒)</label>
                <input v-model="form.time" type="number" class="form-ctrl" min="0" step="0.1" placeholder="秒"></div>
            </div>
          </div>

          <div class="form-section">
            <div class="form-section-title">💰 效益评估</div>
            <div class="form-grid">
              <div class="form-group">
                <label>效益类型</label>
                <el-select v-model="form.btype" class="form-sel" popper-class="app-select-popper">
                  <el-option label="不填写" value="" />
                  <el-option label="耗时节省" value="耗时" />
                  <el-option label="人力节省" value="人力" />
                </el-select>
              </div>
              <div v-if="form.btype" class="form-group">
                <label>{{ form.btype === '耗时' ? '节省耗时数值' : '节省人力数值' }}</label>
                <div class="form-row">
                  <input v-model="form.bval" type="number" class="form-ctrl" min="0" step="0.1" placeholder="请填入数值">
                  <span class="unit-label">{{ form.btype === '耗时' ? '小时' : '人' }}</span>
                </div>
              </div>
            </div>
          </div>
        </div>
        <div class="modal-footer">
          <button type="button" class="btn btn-outline" @click="closeModal">取消</button>
          <button type="button" class="btn btn-primary" :disabled="busy" @click="saveRecord">💾 储存</button>
        </div>
      </div>
    </div>

    <!-- ══ 分类管理弹窗 ══ -->
    <div v-if="catModal" class="cat-modal" @click.self="closeCat">
      <div class="cat-box">
        <div class="cat-head">
          <h3>管理 — {{ catTitles[catKey] }}</h3>
          <button type="button" class="modal-close" @click="closeCat">✕</button>
        </div>
        <div class="cat-body">
          <div class="cat-list">
            <div v-for="(it, i) in (cats[catKey] || [])" :key="it + i" class="cat-item" :class="{ builtin: isBuiltin(catKey, it) }">
              <span>{{ it }}</span>
              <button type="button" class="del-cat" @click="removeCat(it)">✕</button>
            </div>
            <div v-if="!(cats[catKey] || []).length" class="cat-empty">暂无项目</div>
          </div>
          <div class="cat-add-row">
            <input v-model="catNew" type="text" class="form-ctrl" placeholder="输入新项目…" @keydown.enter="addCatItem">
            <button type="button" class="btn btn-primary btn-sm" :disabled="busy" @click="addCatItem">新增</button>
          </div>
        </div>
        <div class="cat-foot"><button type="button" class="btn btn-primary btn-sm" @click="closeCat">完成</button></div>
      </div>
    </div>

    <!-- ══ 确认弹窗 ══ -->
    <div v-if="confirm.show" class="cat-modal" @click.self="closeConfirm">
      <div class="confirm-box">
        <div class="confirm-head"><strong>{{ confirm.title }}</strong></div>
        <div class="confirm-body" v-html="confirm.msg"></div>
        <div class="confirm-foot">
          <button type="button" class="btn btn-outline btn-sm" @click="closeConfirm">取消</button>
          <button type="button" class="btn btn-sm btn-danger" :disabled="busy" @click="runConfirm">确认</button>
        </div>
      </div>
    </div>

    <!-- ══ SVG 预览弹窗（★ 输出给 PPT，刻意保持白底）══ -->
    <div v-if="svgModal" class="modal-overlay" @click.self="svgModal = false">
      <div class="svg-modal">
        <div class="modal-head">
          <h2>🖼️ SVG 预览 — 可直接插入 PPT</h2>
          <button type="button" class="modal-close" @click="svgModal = false">✕</button>
        </div>
        <div class="svg-preview-area" v-html="svgContent"></div>
        <div class="modal-footer wrap">
          <span class="svg-tip">在 PPT 中：插入 → 图片 → 此设备 → 选择 .svg 文件即可</span>
          <button type="button" class="btn btn-outline" @click="svgModal = false">关闭</button>
          <button type="button" class="btn btn-teal" @click="downloadSVG">⬇️ 下载 SVG</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, watch, onMounted, onUnmounted } from 'vue'
import { ElMessage } from 'element-plus'
import {
  qcBootstrap, qcNextSeq, qcSaveProject, qcSetStatus, qcDeleteProject,
  qcCatAdd, qcCatRemove, qcExport, qcImport,
} from '../api/qcai'

defineOptions({ name: 'QcAiTeamView' })

// ── 状态 ──
const projects = ref([])
const cats = reactive({ group: [], subtype: [], arch: [], dev: [] })
const builtins = ref({})
const prefixMap = ref({})
const statuses = ref(['开发中', '使用中', '废除'])
const loading = ref(true)
const busy = ref(false)

const search = ref('')
const filterGroup = ref('')
const filterSubtype = ref('')
const filterDev = ref('')
const filterStatus = ref('')
const namingOpen = ref(false)

const mainModal = ref(false)
const catModal = ref(false)
const catKey = ref('group')
const catNew = ref('')
const svgModal = ref(false)
const svgContent = ref('')
const importInput = ref(null)

const confirm = reactive({ show: false, title: '', msg: '', cb: null })

const CAT_TITLES = { group: '功能群组', subtype: '子类型 (Function)', arch: '技术架构', dev: '开发者' }
const catTitles = CAT_TITLES

const NAMING_CARDS = [
  { name: '风控卫士', prefix: 'QCWF', icon: '🛡️' },
  { name: '问答型', prefix: 'QCRG', icon: '💬' },
  { name: '流程自动化', prefix: 'QCAF', icon: '⚙️' },
  { name: '邮件自动化', prefix: 'QCMF', icon: '📧' },
]
const namingCards = ref(NAMING_CARDS)

const form = reactive({
  id: '', group: '', subtype: '', work: '', seq: '', arch: '', status: '开发中',
  dev: '', desc: '', success: '', accuracy: '', token: '', time: '', btype: '', bval: '',
})

// ── 头部时钟 ──
const clockDate = ref('')
const clockTime = ref('')
let clockTimer = null
function tick() {
  const n = new Date()
  clockDate.value = n.toLocaleDateString('zh-Hans', { year: 'numeric', month: '2-digit', day: '2-digit' })
  clockTime.value = n.toLocaleTimeString('zh-Hans', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

// ── 服务端状态落地 ──
function applyState(d) {
  if (!d || d.success === false) return
  if (Array.isArray(d.projects)) projects.value = d.projects
  if (d.cats) for (const k of ['group', 'subtype', 'arch', 'dev']) cats[k] = d.cats[k] || []
}

async function load() {
  loading.value = true
  try {
    const d = await qcBootstrap()
    applyState(d)
    if (d.prefix_map) {
      prefixMap.value = d.prefix_map
      // 命名说明卡片按服务端前缀映射渲染，避免前后端两套常量漂移
      namingCards.value = NAMING_CARDS.map(c => ({ ...c, prefix: d.prefix_map[c.name] || c.prefix }))
    }
    if (d.builtins) builtins.value = d.builtins
    if (Array.isArray(d.statuses) && d.statuses.length) statuses.value = d.statuses
  } catch (e) {
    ElMessage.error('加载 QC_AI_TEAM 数据失败：' + (e?.message || e))
  } finally {
    loading.value = false
  }
}

// ★ 统一处理写接口回包：失败弹提示并返回 null，成功则整体替换状态
function consume(d, okMsg) {
  if (!d || d.success === false) {
    ElMessage.error(d?.error || '操作失败')
    return null
  }
  applyState(d)
  if (okMsg) ElMessage.success(okMsg)
  return d
}

// ── 统计（与原版 renderStats 同口径：仅统计非废除，空值不计入均值）──
const stats = computed(() => {
  const active = projects.value.filter(p => p.status !== '废除')
  const grp = {}
  active.forEach(p => { grp[p.group] = (grp[p.group] || 0) + 1 })
  const nums = (key) => active.map(p => parseFloat(p[key])).filter(v => !isNaN(v))
  const avg = (arr) => (arr.length ? (arr.reduce((a, b) => a + b, 0) / arr.length).toFixed(1) : '—')
  return {
    total: projects.value.length,
    active: active.length,
    groups: Object.entries(grp).map(([name, count]) => ({ name, count })),
    avgSuccess: avg(nums('success')),
    avgTime: avg(nums('time')),
  }
})

// ── 表格筛选（与原版 renderTable 同口径）──
const filtered = computed(() => {
  const q = (search.value || '').toLowerCase()
  return projects.value.filter(p => {
    if (filterGroup.value && p.group !== filterGroup.value) return false
    if (filterSubtype.value && p.subtype !== filterSubtype.value) return false
    if (filterDev.value && p.dev !== filterDev.value) return false
    if (filterStatus.value && p.status !== filterStatus.value) return false
    if (q && !(String(p.name).toLowerCase().includes(q)
      || String(p.dev || '').toLowerCase().includes(q)
      || String(p.desc || '').toLowerCase().includes(q))) return false
    return true
  })
})

// ── SVG 导出的数据源（与原版 generateSVG 同口径 —— 刻意与表格分开）──
// 原页两处搜索范围不同：表格 renderTable 搜「名称/开发者/专案说明」三个字段，
// 而 generateSVG 只搜「名称/开发者」两个字段。为保持与原页一模一样，这里不复用 filtered。
const svgRows = computed(() => {
  const q = (search.value || '').toLowerCase()
  return projects.value.filter(p => {
    if (filterGroup.value && p.group !== filterGroup.value) return false
    if (filterSubtype.value && p.subtype !== filterSubtype.value) return false
    if (filterDev.value && p.dev !== filterDev.value) return false
    if (filterStatus.value && p.status !== filterStatus.value) return false
    if (q && !(String(p.name).toLowerCase().includes(q)
      || String(p.dev || '').toLowerCase().includes(q))) return false
    return true
  })
})

function badgeCls(s) {
  return s === '使用中' ? 'badge-active' : s === '开发中' ? 'badge-dev' : 'badge-off'
}

// ── 名称预览（等价原版 updateName）──
const genName = computed(() => {
  const prefix = prefixMap.value[form.group] || ''
  if (!prefix) return ''
  // ★ 2026-09-21（用户）：流水码未填时不再塞 '___' 占位。
  //   原写法 `${prefix}_${seq || '___'}_…` 会把「分隔符 + 占位 + 分隔符」连成 5 个下划线
  //   （QCWF_____FUNCTION_XXX）；现在空段直接跳过，只留一个下划线：QCWF_FUNCTION_XXX。
  //   流水码填了则保持原样 3 位补零：QCWF_001_FUNCTION_XXX（手打 "1" 也要补成 "001"）。
  const seq = String(form.seq || '').trim()
  const seqS = seq ? seq.padStart(3, '0') : ''
  const seg = [prefix, seqS, form.subtype || 'FUNCTION', form.work || 'XXX']
  return seg.filter(s => s !== '').join('_')
})

// ── 新增/编辑 ──
function openModal(id) {
  if (id) {
    const p = projects.value.find(x => x.id === id)
    if (!p) return
    Object.assign(form, {
      id: p.id, group: p.group || '', subtype: p.subtype || '', work: p.work || '', seq: p.seq || '',
      arch: p.arch || '', status: p.status || '开发中', dev: p.dev || '', desc: p.desc || '',
      success: p.success ?? '', accuracy: p.accuracy ?? '', token: p.token ?? '', time: p.time ?? '',
      btype: p.btype || '', bval: p.bval ?? '',
    })
  } else {
    Object.assign(form, {
      id: '', group: '', subtype: '', work: '', seq: '', arch: '', status: '开发中',
      dev: '', desc: '', success: '', accuracy: '', token: '', time: '', btype: '', bval: '',
    })
  }
  mainModal.value = true
}
function closeModal() { mainModal.value = false }

async function autoAssign() {
  if (!form.group || !form.subtype) {
    ElMessage.warning('请先填写：功能群组、子类型')
    return
  }
  const g = form.group
  const s = form.subtype
  try {
    const d = await qcNextSeq(g, s, form.work, form.id)
    // 用户在校准切换群组/子类型时丢弃过期回覆，避免旧号覆盖新号
    if (form.group !== g || form.subtype !== s) return
    if (d && d.success) form.seq = d.seq
    else ElMessage.error(d?.error || '自动分配失败')
  } catch (e) { ElMessage.error('自动分配失败：' + (e?.message || e)) }
}

// ★ 2026-09-24（用户）：新增专案时自动取号 —— 「功能群组 + 子类型」选齐即分配流水码，
//   无需再点 ⚡ 按钮；换群组/子类型时自动重新分配。编辑既有专案（form.id 存在）不动已有号。
watch(() => [form.group, form.subtype], ([g, s]) => {
  if (form.id) return
  if (!g || !s) return
  autoAssign()
})

async function saveRecord() {
  if (!form.group || !form.subtype || !form.work || !form.seq || !form.arch || !form.status) {
    ElMessage.warning('请填写所有必填栏位（*）并确认 Agent 名称已生成。')
    return
  }
  busy.value = true
  try {
    const d = await qcSaveProject({ ...form })
    const r = consume(d, form.id ? '已保存修改' : '已新增')
    if (r) closeModal()
  } catch (e) { ElMessage.error('保存失败：' + (e?.message || e)) }
  finally { busy.value = false }
}

// ── 状态 / 删除 ──
function chStatus(id, ns) {
  const p = projects.value.find(x => x.id === id)
  if (!p) return
  if (ns === '废除') {
    openConfirm('废除确认',
      `确定要废除 <b>${escHtml(p.name)}</b>？<br>流水码将保留，不会被重新分配。`,
      async () => { consume(await qcSetStatus(id, '废除'), '已废除') })
  } else {
    doStatus(id, ns)
  }
}
async function doStatus(id, ns) {
  try { consume(await qcSetStatus(id, ns), ns === '开发中' ? '已恢复' : null) }
  catch (e) { ElMessage.error('操作失败：' + (e?.message || e)) }
}
function askDel(id) {
  const p = projects.value.find(x => x.id === id)
  if (!p) return
  openConfirm('删除确认',
    `确定要永久删除 <b>${escHtml(p.name)}</b>？<br>此操作无法复原。`,
    async () => { consume(await qcDeleteProject(id), '已删除') })
}

// ── 确认弹窗 ──
function openConfirm(title, msg, cb) {
  confirm.title = title; confirm.msg = msg; confirm.cb = cb; confirm.show = true
}
function closeConfirm() { confirm.show = false; confirm.cb = null }
async function runConfirm() {
  const cb = confirm.cb
  confirm.show = false; confirm.cb = null
  if (!cb) return
  busy.value = true
  try { await cb() }
  catch (e) { ElMessage.error('操作失败：' + (e?.message || e)) }
  finally { busy.value = false }
}

// ── 分类管理 ──
function openCatModal(k) { catKey.value = k; catNew.value = ''; catModal.value = true }
function closeCat() { catModal.value = false }
function isBuiltin(kind, name) { return (builtins.value[kind] || []).includes(name) }
async function addCatItem() {
  const v = (catNew.value || '').trim()
  if (!v) return
  busy.value = true
  try {
    const d = await qcCatAdd(catKey.value, v)
    if (consume(d)) catNew.value = ''
  } catch (e) { ElMessage.error('新增失败：' + (e?.message || e)) }
  finally { busy.value = false }
}
async function removeCat(name) {
  if (isBuiltin(catKey.value, name)) { ElMessage.warning('内建项目无法删除'); return }
  busy.value = true
  try { consume(await qcCatRemove(catKey.value, name)) }
  catch (e) { ElMessage.error('删除失败：' + (e?.message || e)) }
  finally { busy.value = false }
}

// ── 备份 / 汇入 ──
function download(name, text, mime) {
  const blob = new Blob([text], { type: mime })
  const a = document.createElement('a')
  a.href = URL.createObjectURL(blob)
  a.download = name
  a.click()
  setTimeout(() => URL.revokeObjectURL(a.href), 1000)
}
async function doExportJSON() {
  try {
    const d = await qcExport()
    const stamp = new Date().toISOString().slice(0, 10)
    download(`QC_AI_TEAM_V4_backup_${stamp}.json`, JSON.stringify(d, null, 2), 'application/json')
    ElMessage.success(`已导出 ${(d.projects || []).length} 笔`)
  } catch (e) { ElMessage.error('导出失败：' + (e?.message || e)) }
}
function onImportFile(e) {
  const file = e.target.files && e.target.files[0]
  if (!file) return
  const reader = new FileReader()
  reader.onload = (ev) => {
    let d
    try { d = JSON.parse(ev.target.result) } catch (err) { ElMessage.error('❌ 汇入失败：格式错误'); return }
    if (!d || !Array.isArray(d.projects)) { ElMessage.error('❌ 汇入失败：格式错误'); return }
    openConfirm('汇入确认',
      `即将汇入 <b>${d.projects.length}</b> 笔专案资料，将覆盖现有数据，确认继续？`,
      async () => {
        const r = consume(await qcImport(d), `✅ 汇入成功（${d.projects.length} 笔）`)
        if (r && r.skipped) ElMessage.warning(`有 ${r.skipped} 笔因重名/重复被跳过`)
      })
    if (importInput.value) importInput.value.value = ''
  }
  reader.readAsText(file)
}

// ── SVG 输出 ──
// ★ 刻意保持白底浅色：这是给 PPT 用的导出物，不属于页面主题
function exportSVGModal() {
  svgContent.value = generateSVG()
  svgModal.value = true
}
function downloadSVG() {
  if (!svgContent.value) return
  const stamp = new Date().toISOString().slice(0, 10)
  download(`QC_AI_TEAM_V4_${stamp}.svg`, svgContent.value, 'image/svg+xml;charset=utf-8')
}
function generateSVG() {
  const now = new Date()
  const dateStr = now.toLocaleDateString('zh-Hans', { year: 'numeric', month: '2-digit', day: '2-digit' })
  const rows = svgRows.value

  const W = 1640, PAD = 36
  const COLS = [
    { label: 'Agent 名称', key: 'name', w: 340 }, { label: '功能群组', key: 'group', w: 120 },
    { label: '子类型', key: 'subtype', w: 90 }, { label: '技术架构', key: 'arch', w: 100 },
    { label: '状态', key: 'status', w: 88 }, { label: '成功率', key: 'success', w: 78 },
    { label: '准确率', key: 'accuracy', w: 78 }, { label: 'Token/次', key: 'token', w: 88 },
    { label: '耗时(s)', key: 'time', w: 78 }, { label: '效益类型', key: 'btype', w: 90 },
    { label: '效益数值', key: 'bval', w: 95 }, { label: '开发者', key: 'dev', w: 110 },
  ]
  const HEADER_H = 100, STATS_H = 72, TH_H = 44, ROW_H = 38, FOOTER_H = 44
  const TABLE_TOP = HEADER_H + STATS_H + 18
  const H = TABLE_TOP + TH_H + rows.length * ROW_H + FOOTER_H + 20
  const xs = []; let cx = PAD
  COLS.forEach(c => { xs.push(cx); cx += c.w })
  const TABLE_W = cx - PAD

  const total = projects.value.length
  const using = projects.value.filter(p => p.status === '使用中').length
  const devC = projects.value.filter(p => p.status === '开发中').length
  const offC = projects.value.filter(p => p.status === '废除').length

  const xe = (s) => String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
  const clip = (s, m) => { s = String(s == null ? '' : s); return s.length > m ? s.slice(0, m - 1) + '…' : s }

  const p = []
  p.push(`<rect width="${W}" height="${H}" fill="#ffffff"/>`)
  p.push(`<defs><linearGradient id="hg" x1="0" y1="0" x2="1" y2="0"><stop offset="0%" stop-color="#003a63"/><stop offset="55%" stop-color="#005087"/><stop offset="100%" stop-color="#0078d4"/></linearGradient></defs>`)
  p.push(`<rect width="${W}" height="${HEADER_H}" fill="url(#hg)"/>`)
  p.push(`<rect x="28" y="20" width="58" height="58" rx="10" fill="rgba(255,255,255,0.18)"/>`)
  p.push(`<text x="57" y="57" text-anchor="middle" font-size="26" fill="white">🤖</text>`)
  p.push(`<text x="102" y="50" font-family="Microsoft JhengHei,PingFang SC,Arial" font-size="25" font-weight="bold" fill="white" letter-spacing="2">QC_AI_TEAM</text>`)
  p.push(`<rect x="298" y="32" width="34" height="18" rx="4" fill="rgba(255,255,255,0.22)" stroke="rgba(255,255,255,0.4)" stroke-width="1"/>`)
  p.push(`<text x="315" y="45" text-anchor="middle" font-family="Arial" font-size="11" font-weight="bold" fill="white">V4</text>`)
  p.push(`<text x="102" y="74" font-family="Microsoft JhengHei,PingFang SC,Arial" font-size="13" fill="rgba(255,255,255,0.78)">AI Agent 专案登记管理系统</text>`)
  p.push(`<text x="${W - PAD}" y="50" font-family="Microsoft JhengHei,Arial" font-size="13" fill="rgba(255,255,255,0.75)" text-anchor="end">输出日期：${xe(dateStr)}</text>`)
  p.push(`<text x="${W - PAD}" y="70" font-family="Microsoft JhengHei,Arial" font-size="13" fill="rgba(255,255,255,0.75)" text-anchor="end">显示 ${rows.length} 笔 / 共 ${total} 笔</text>`)

  const statList = [{ l: 'Total', v: String(total), c: '#005087' }, { l: '使用中', v: String(using), c: '#107c10' },
    { l: '开发中', v: String(devC), c: '#c67400' }, { l: '废除', v: String(offC), c: '#888888' }]
  const SY = HEADER_H + 8, SW = 155, SG = 14
  statList.forEach((s, i) => {
    const sx = PAD + i * (SW + SG)
    p.push(`<rect x="${sx}" y="${SY}" width="${SW}" height="${STATS_H - 16}" rx="8" fill="#f6faff" stroke="#cce0f5" stroke-width="1"/>`)
    p.push(`<rect x="${sx}" y="${SY}" width="5" height="${STATS_H - 16}" rx="2" fill="${s.c}"/>`)
    p.push(`<text x="${sx + 16}" y="${SY + 20}" font-family="Microsoft JhengHei,Arial" font-size="11" fill="#5a6a88" font-weight="600">${xe(s.l)}</text>`)
    p.push(`<text x="${sx + 16}" y="${SY + 44}" font-family="Microsoft JhengHei,Arial" font-size="26" font-weight="700" fill="${s.c}">${s.v}</text>`)
  })

  p.push(`<rect x="${PAD}" y="${TABLE_TOP}" width="${TABLE_W}" height="${TH_H + rows.length * ROW_H}" rx="8" fill="#ffffff" stroke="#cce0f5" stroke-width="1"/>`)
  p.push(`<rect x="${PAD}" y="${TABLE_TOP}" width="${TABLE_W}" height="4" rx="0" fill="#005087"/>`)
  p.push(`<rect x="${PAD}" y="${TABLE_TOP}" width="${TABLE_W}" height="${TH_H}" fill="#f0f6fc"/>`)
  COLS.forEach((c, i) => {
    p.push(`<text x="${xs[i] + 10}" y="${TABLE_TOP + TH_H / 2 + 5}" font-family="Microsoft JhengHei,Arial" font-size="12" font-weight="700" fill="#005087">${xe(c.label)}</text>`)
    if (i > 0) p.push(`<line x1="${xs[i]}" y1="${TABLE_TOP + 4}" x2="${xs[i]}" y2="${TABLE_TOP + TH_H + rows.length * ROW_H}" stroke="#ddeaf8" stroke-width="1"/>`)
  })

  rows.forEach((row, ri) => {
    const ry = TABLE_TOP + TH_H + ri * ROW_H
    const alt = ri % 2 === 1
    p.push(`<rect x="${PAD}" y="${ry}" width="${TABLE_W}" height="${ROW_H}" fill="${row.status === '废除' ? '#f8f8f8' : alt ? '#f9fbff' : '#ffffff'}"/>`)
    p.push(`<line x1="${PAD}" y1="${ry + ROW_H}" x2="${PAD + TABLE_W}" y2="${ry + ROW_H}" stroke="#eef3fb" stroke-width="1"/>`)
    const cy = ry + ROW_H / 2 + 5
    const op = row.status === '废除' ? '0.5' : '1'
    COLS.forEach((c, ci) => {
      const tx = xs[ci] + 10
      let v = '—'
      if (c.key === 'name') v = clip(row.name, 38)
      else if (c.key === 'success') v = (row.success !== '' && row.success != null) ? row.success + '%' : '—'
      else if (c.key === 'accuracy') v = (row.accuracy !== '' && row.accuracy != null) ? row.accuracy + '%' : '—'
      else if (c.key === 'time') v = (row.time !== '' && row.time != null) ? row.time + 's' : '—'
      else if (c.key === 'bval') v = row.bval ? `${row.bval} ${row.btype === '耗时' ? '小时' : '人'}` : '—'
      else v = clip(row[c.key] || '—', 16)

      if (c.key === 'status') {
        const bc = row.status === '使用中' ? '#e6f4e6' : row.status === '开发中' ? '#fff4e0' : '#f0f0f0'
        const fc = row.status === '使用中' ? '#107c10' : row.status === '开发中' ? '#c67400' : '#888888'
        p.push(`<rect x="${xs[ci] + 6}" y="${ry + 9}" width="70" height="20" rx="10" fill="${bc}"/>`)
        p.push(`<text x="${xs[ci] + 41}" y="${ry + 23}" text-anchor="middle" font-family="Microsoft JhengHei,Arial" font-size="11" font-weight="700" fill="${fc}">${xe(row.status)}</text>`)
      } else if (c.key === 'name') {
        p.push(`<text x="${tx}" y="${cy}" font-family="Consolas,Courier New,monospace" font-size="11.5" font-weight="700" fill="#003a63" opacity="${op}">${xe(v)}</text>`)
      } else {
        p.push(`<text x="${tx}" y="${cy}" font-family="Microsoft JhengHei,Arial" font-size="12.5" fill="${row.status === '废除' ? '#999' : '#12213a'}" opacity="${op}">${xe(v)}</text>`)
      }
    })
  })

  const FY = TABLE_TOP + TH_H + rows.length * ROW_H + 14
  p.push(`<text x="${PAD}" y="${FY + 16}" font-family="Microsoft JhengHei,Arial" font-size="11.5" fill="#aab8cc">QC_AI_TEAM V4 — AI Agent 专案管理系统 | 生成时间：${xe(now.toLocaleString('zh-Hans'))} | 总计 ${total} 笔</text>`)
  return `<svg xmlns="http://www.w3.org/2000/svg" width="${W}" height="${H}" viewBox="0 0 ${W} ${H}">${p.join('')}</svg>`
}

function escHtml(s) {
  return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
}

onMounted(() => {
  tick()
  clockTimer = setInterval(tick, 1000)
  load()
})
onUnmounted(() => { if (clockTimer) clearInterval(clockTimer) })
</script>

<style lang="scss" scoped>
/* ══════════════════════════════════════════════════════════
   QC_AI_TEAM —— 深色版（原单文件页为浅色，此处按项目深色工业风重做）
   配色一律走全局变量：--bg-main / --bg-card / --bc / --t1..--t4 / --ac / --ok / --wn / --bd
   ══════════════════════════════════════════════════════════ */
.qcai-view {
  height: 100%;
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 4px 6px;
  min-height: 0;
  overflow-y: auto;
  background: transparent;
}
.qcai-view::-webkit-scrollbar { width: 6px; }
.qcai-view::-webkit-scrollbar-thumb { background: rgba(30, 120, 200, .32); border-radius: 3px; }

/* ── 页面标题栏（沿用项目 .pbar 约定）── */
.pbar { display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; }
.pbar-left { display: flex; align-items: center; gap: 8px; }
.ptag { background: rgba(0, 120, 220, .22); border: 1px solid rgba(40, 150, 255, .45); color: var(--ac); font-size: 10px; font-weight: 700; letter-spacing: 1px; padding: 3px 10px; border-radius: 4px; }
.ptitle { font-size: 15px; font-weight: 500; color: var(--tna); }
.ptitle span { color: var(--ac); font-weight: 700; }
.qclock { font-size: 10px; line-height: 1.45; color: var(--t2); text-align: right; white-space: nowrap; }

/* ── 数据说明条 ── */
.data-banner {
  display: flex; align-items: center; gap: 10px; flex-shrink: 0;
  background: rgba(0, 120, 220, .10); border: 1px solid var(--bc);
  border-left: 3px solid var(--ac);
  border-radius: var(--radius, 10px); padding: 9px 14px;
  font-size: 12px; color: var(--t2); line-height: 1.6;
}
.data-banner strong { color: var(--tna); font-weight: 600; }
.db-ico { font-size: 16px; flex-shrink: 0; }

/* ── 命名原则说明 ── */
.naming-panel { flex-shrink: 0; background: var(--bg-card); border: 1px solid var(--bc); border-radius: var(--radius, 10px); overflow: hidden; }
.naming-toggle {
  display: flex; align-items: center; gap: 10px; width: 100%; text-align: left; cursor: pointer;
  padding: 10px 16px; border: none; font-family: inherit; font-size: 12px; font-weight: 600;
  background: rgba(0, 100, 180, .14); color: var(--tna); transition: background .2s;
}
.naming-toggle:hover { background: rgba(0, 120, 220, .22); }
.naming-toggle .chevron { margin-left: auto; font-size: 10px; transition: transform .25s; }
.naming-toggle.open .chevron { transform: rotate(180deg); }
.naming-body { display: none; padding: 12px 16px; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 10px; }
.naming-body.open { display: grid; }
.naming-card { background: rgba(8, 18, 38, .55); border: 1px solid var(--bc); border-radius: 6px; padding: 10px 12px; }
.naming-card h4 { font-size: 11px; color: var(--tna); margin-bottom: 6px; font-weight: 700; }
.naming-code { font-family: Consolas, "Courier New", monospace; font-size: 12px; font-weight: 700; color: var(--ac); background: rgba(0, 120, 220, .14); padding: 3px 8px; border-radius: 4px; display: inline-block; margin-bottom: 6px; }
.naming-card p { font-size: 11px; color: var(--t3); line-height: 1.8; }
.seg { display: inline-block; padding: 0 5px; border-radius: 3px; font-size: 10px; margin: 1px; font-weight: 600; }
.seg-prefix { background: rgba(0, 150, 255, .22); color: #6cc4ff; }
.seg-num { background: rgba(255, 208, 64, .18); color: var(--wn); }
.seg-func { background: rgba(0, 240, 176, .16); color: var(--ok); }
.seg-work { background: rgba(160, 120, 255, .20); color: #b79cff; }

/* ── 统计卡 ── */
.stats-row { display: grid; grid-template-columns: repeat(auto-fit, minmax(130px, 1fr)); gap: 10px; flex-shrink: 0; }
.stat-card { position: relative; overflow: hidden; background: var(--bg-card); border: 1px solid var(--bc); border-radius: var(--radius, 10px); padding: 12px 14px; }
.stat-card::before { content: ''; position: absolute; top: 0; left: 0; width: 3px; height: 100%; background: linear-gradient(180deg, #0077cc, var(--ac)); }
.stat-label { font-size: 10px; color: var(--t3); margin-bottom: 5px; font-weight: 600; letter-spacing: .5px; }
.stat-value { font-size: 22px; font-weight: 700; color: var(--ac); line-height: 1.2; }
.stat-value.sm { font-size: 18px; }
.stat-sub { font-size: 10px; color: var(--t3); margin-top: 2px; }

/* ── 工具栏 ── */
.toolbar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; flex-shrink: 0; background: var(--bg-card); border: 1px solid var(--bc); border-radius: var(--radius, 10px); padding: 10px 14px; }
.toolbar-left { display: flex; flex-wrap: wrap; gap: 7px; flex: 1; }
.toolbar-right { display: flex; gap: 7px; flex-wrap: wrap; align-items: center; }

.search-box { position: relative; min-width: 190px; flex: 1; }
.search-box input {
  width: 100%; padding: 6px 12px 6px 32px; font-size: 12px; font-family: inherit;
  background: rgba(8, 18, 38, .70); border: 1px solid var(--bc); border-radius: 6px;
  color: var(--t1); transition: border-color .2s, box-shadow .2s;
}
.search-box input::placeholder { color: var(--t4); }
.search-box input:focus { outline: none; border-color: var(--bf); box-shadow: 0 0 0 2px rgba(40, 150, 255, .16); }
.search-icon { position: absolute; left: 10px; top: 50%; transform: translateY(-50%); font-size: 12px; color: var(--t3); }

.filter-sel {
  /* el-select 根节点默认 width:100%，这里恢复成工具栏里的紧凑宽度（等价旧原生 select 观感） */
  width: 130px; font-size: 12px; cursor: pointer;
}

.btn {
  display: inline-flex; align-items: center; gap: 5px; padding: 6px 13px;
  border: none; border-radius: 6px; font-size: 12px; font-family: inherit; font-weight: 600;
  cursor: pointer; white-space: nowrap; transition: filter .18s, background .18s, color .18s;
}
.btn:disabled, .btn.disabled { opacity: .5; cursor: not-allowed; }
.btn-primary { background: linear-gradient(135deg, #0055aa, #0077cc); color: #fff; box-shadow: 0 2px 8px rgba(0, 100, 200, .35); }
.btn-primary:hover:not(:disabled) { background: linear-gradient(135deg, #0066bb, #0088dd); }
.btn-outline { background: rgba(0, 40, 80, .30); color: #5a90b8; border: 1px solid #0d3050; }
.btn-outline:hover { background: rgba(0, 60, 120, .40); color: #90c0e8; }
.btn-teal { background: rgba(0, 151, 167, .85); color: #fff; }
.btn-teal:hover { background: #0097a7; }
.btn-indigo { background: rgba(63, 81, 181, .85); color: #fff; }
.btn-indigo:hover { background: #3f51b5; }
.btn-orange { background: rgba(230, 81, 0, .85); color: #fff; }
.btn-orange:hover { background: #e65100; }
.btn-danger { background: rgba(192, 57, 43, .90); color: #fff; }
.btn-danger:hover { background: #c0392b; }
.btn-sm { padding: 4px 11px; font-size: 11px; }

/* ── 表格 ── */
.table-wrap { flex: 1; min-height: 240px; display: flex; flex-direction: column; background: var(--bg-card); border: 1px solid var(--bc); border-radius: var(--radius, 10px); overflow: hidden; }
.table-header { display: flex; align-items: center; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid var(--bc); flex-shrink: 0; }
.table-title { font-size: 12px; font-weight: 700; color: var(--tna); }
.table-count { font-size: 11px; color: var(--t3); }
.table-scroll { flex: 1; overflow: auto; min-height: 0; }
.table-scroll::-webkit-scrollbar { width: 7px; height: 7px; }
.table-scroll::-webkit-scrollbar-thumb { background: rgba(30, 120, 200, .35); border-radius: 4px; }
.table-scroll::-webkit-scrollbar-corner { background: transparent; }

table { width: 100%; border-collapse: collapse; font-size: 12px; }
thead th {
  position: sticky; top: 0; z-index: 2;
  background: rgba(0, 40, 80, .92); color: #a0c8e8; font-weight: 700; font-size: 11px;
  text-align: left; padding: 9px 10px; white-space: nowrap; border-bottom: 1px solid #0d2a48;
}
tbody td { padding: 8px 10px; color: #c8ddf5; border-bottom: 1px solid rgba(13, 42, 72, .6); white-space: nowrap; }
tbody tr { background: rgba(5, 15, 30, .5); transition: background .15s; }
tbody tr:nth-child(even) { background: rgba(8, 20, 40, .55); }
tbody tr:hover { background: rgba(0, 60, 120, .25); }
tbody tr.row-off td { opacity: .5; }
.agent-name { font-family: Consolas, "Courier New", monospace; font-weight: 700; color: var(--ac); max-width: 320px; overflow: hidden; text-overflow: ellipsis; }

.badge { display: inline-block; padding: 2px 9px; border-radius: 10px; font-size: 11px; font-weight: 700; }
.badge-active { background: var(--okg); color: var(--ok); border: 1px solid rgba(0, 240, 176, .35); }
.badge-dev { background: var(--wng); color: var(--wn); border: 1px solid rgba(255, 208, 64, .35); }
.badge-off { background: rgba(90, 122, 154, .18); color: var(--t3); border: 1px solid rgba(90, 122, 154, .35); }

.ops { display: flex; gap: 4px; }
.btn-success-sm { background: rgba(0, 200, 150, .18); color: var(--ok); border: 1px solid rgba(0, 240, 176, .35); padding: 3px 9px; font-size: 11px; border-radius: 5px; cursor: pointer; font-family: inherit; font-weight: 600; }
.btn-success-sm:hover { background: rgba(0, 240, 176, .28); }
.btn-warn-sm { background: rgba(255, 208, 64, .16); color: var(--wn); border: 1px solid rgba(255, 208, 64, .35); padding: 3px 9px; font-size: 11px; border-radius: 5px; cursor: pointer; font-family: inherit; font-weight: 600; }
.btn-warn-sm:hover { background: rgba(255, 208, 64, .26); }
.btn-grey-sm { background: rgba(90, 122, 154, .20); color: #9ac0d8; border: 1px solid rgba(90, 122, 154, .40); padding: 3px 9px; font-size: 11px; border-radius: 5px; cursor: pointer; font-family: inherit; font-weight: 600; }
.btn-grey-sm:hover { background: rgba(90, 122, 154, .32); }
.btn-danger-sm { background: rgba(255, 96, 96, .16); color: #ff8a8a; border: 1px solid rgba(255, 96, 96, .35); padding: 3px 9px; font-size: 11px; border-radius: 5px; cursor: pointer; font-family: inherit; font-weight: 600; }
.btn-danger-sm:hover { background: rgba(255, 96, 96, .28); }

.no-data { padding: 46px 0; text-align: center; color: var(--t3); font-size: 12px; }
.no-data .icon { font-size: 30px; margin-bottom: 8px; opacity: .7; }

/* ── 弹窗 ── */
.modal-overlay { position: fixed; inset: 0; z-index: 2000; background: rgba(2, 6, 14, .72); display: flex; align-items: center; justify-content: center; padding: 20px; backdrop-filter: blur(2px); }
.modal { width: min(880px, 96vw); max-height: 92vh; display: flex; flex-direction: column; background: var(--bg-pop); border: 1px solid var(--bpop); border-radius: 10px; box-shadow: var(--bpop-g); overflow: hidden; }
.modal-head { display: flex; align-items: center; justify-content: space-between; padding: 14px 18px; border-bottom: 1px solid var(--bc); flex-shrink: 0; }
.modal-head h2 { font-size: 14px; font-weight: 700; color: var(--tna); }
.modal-close { background: none; border: none; color: var(--t3); font-size: 15px; cursor: pointer; padding: 2px 6px; border-radius: 5px; font-family: inherit; }
.modal-close:hover { background: rgba(255, 96, 96, .18); color: #ff8a8a; }
.modal-body { padding: 16px 18px; overflow-y: auto; flex: 1; min-height: 0; }
.modal-body::-webkit-scrollbar { width: 6px; }
.modal-body::-webkit-scrollbar-thumb { background: rgba(30, 120, 200, .32); border-radius: 3px; }
.modal-footer { display: flex; justify-content: flex-end; gap: 8px; padding: 12px 18px; border-top: 1px solid var(--bc); flex-shrink: 0; }
.modal-footer.wrap { flex-wrap: wrap; }

.form-section { margin-bottom: 18px; }
.form-section:last-child { margin-bottom: 0; }
.form-section-title { font-size: 12px; font-weight: 700; color: var(--ac); padding-bottom: 7px; margin-bottom: 11px; border-bottom: 1px solid var(--bc); }
.form-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 11px; }
.form-grid.col3 { grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); }
.form-group { display: flex; flex-direction: column; gap: 5px; min-width: 0; }
.form-group.form-full { grid-column: 1 / -1; }
.form-group label { font-size: 11px; color: var(--t2); font-weight: 600; }
.form-group .req { color: #ff8a8a; }
.form-row { display: flex; gap: 6px; align-items: center; }
.form-ctrl {
  width: 100%; padding: 7px 10px; font-size: 12px; font-family: inherit;
  background: rgba(8, 18, 38, .80); border: 1px solid var(--bc); border-radius: 6px; color: var(--t1);
  transition: border-color .2s, box-shadow .2s;
}
.form-ctrl::placeholder { color: var(--t4); }
.form-ctrl:focus { outline: none; border-color: var(--bf); box-shadow: 0 0 0 2px rgba(40, 150, 255, .16); }
.form-ctrl option { background: #0d172a; color: var(--t1); }
.form-ctrl[readonly] { background: rgba(8, 18, 38, .45); color: var(--t2); cursor: default; }
.form-ctrl.generated { color: var(--ac); font-family: Consolas, "Courier New", monospace; font-weight: 700; letter-spacing: .3px; }
.seq-input { width: 88px; flex: none; }
/* 弹窗里的 el-select：占满 form-group；在 form-row（旁边有 ＋ 按钮）里则弹性收缩 */
.form-sel { width: 100%; }
.form-row > .form-sel { flex: 1; min-width: 0; }
.form-row > .btn-add-cat { flex: none; }
.hint { font-size: 10px; color: var(--t4); }
.unit-label { font-size: 11px; color: var(--t2); white-space: nowrap; }
.btn-add-cat { flex: none; width: 30px; height: 30px; border-radius: 6px; border: 1px solid var(--bf); background: rgba(0, 120, 220, .18); color: var(--ac); font-size: 14px; font-weight: 700; cursor: pointer; font-family: inherit; line-height: 1; }
.btn-add-cat:hover { background: rgba(0, 130, 240, .32); }

/* ── 分类管理 / 确认（小弹窗）── */
.cat-modal { position: fixed; inset: 0; z-index: 2100; background: rgba(2, 6, 14, .72); display: flex; align-items: center; justify-content: center; padding: 20px; }
.cat-box { width: min(440px, 94vw); background: var(--bg-pop); border: 1px solid var(--bpop); border-radius: 10px; box-shadow: var(--bpop-g); overflow: hidden; }
.cat-head { display: flex; align-items: center; justify-content: space-between; padding: 12px 16px; border-bottom: 1px solid var(--bc); }
.cat-head h3 { font-size: 13px; font-weight: 700; color: var(--tna); }
.cat-body { padding: 14px 16px; }
.cat-list { max-height: 260px; overflow-y: auto; display: flex; flex-direction: column; gap: 6px; margin-bottom: 12px; }
.cat-list::-webkit-scrollbar { width: 6px; }
.cat-list::-webkit-scrollbar-thumb { background: rgba(30, 120, 200, .32); border-radius: 3px; }
.cat-item { display: flex; align-items: center; justify-content: space-between; padding: 6px 10px; border-radius: 6px; font-size: 12px; color: var(--t1); background: rgba(8, 18, 38, .60); border: 1px solid var(--bc); }
.cat-item.builtin { border-color: rgba(0, 240, 176, .28); }
.cat-item.builtin span::after { content: ' 内建'; font-size: 9px; color: var(--ok); opacity: .75; }
.cat-empty { color: var(--t3); font-size: 11px; padding: 4px; }
.del-cat { background: none; border: none; color: var(--t3); cursor: pointer; font-size: 12px; padding: 0 4px; font-family: inherit; }
.del-cat:hover { color: #ff8a8a; }
.cat-add-row { display: flex; gap: 8px; }
.cat-foot { padding: 10px 16px; border-top: 1px solid var(--bc); display: flex; justify-content: flex-end; }

.confirm-box { width: min(400px, 94vw); background: var(--bg-pop); border: 1px solid rgba(255, 96, 96, .40); border-radius: 10px; box-shadow: var(--bpop-g); overflow: hidden; }
.confirm-head { padding: 12px 16px; border-bottom: 1px solid var(--bc); font-size: 13px; color: var(--tna); }
.confirm-body { padding: 16px; font-size: 12.5px; color: var(--t1); line-height: 1.7; }
.confirm-body b { color: var(--ac); }
.confirm-foot { padding: 10px 16px; border-top: 1px solid var(--bc); display: flex; justify-content: flex-end; gap: 8px; }

/* ── SVG 预览 ── */
.svg-modal { width: min(1400px, 97vw); max-height: 94vh; display: flex; flex-direction: column; background: var(--bg-pop); border: 1px solid var(--bpop); border-radius: 10px; box-shadow: var(--bpop-g); overflow: hidden; }
.svg-preview-area { flex: 1; overflow: auto; padding: 12px; background: #16233a; min-height: 0; display: flex; align-items: flex-start; justify-content: center; }
.svg-preview-area :deep(svg) { max-width: 100%; height: auto; box-shadow: 0 4px 24px rgba(0, 0, 0, .45); }
.svg-tip { flex: 1; font-size: 11px; color: var(--t3); }

/* ══════════════════════════════════════════════════════════════════════
   ★ 白天主题覆盖（2026-09-18）
   根因：本页大部分颜色走全局变量（已随主题切换），但输入框/表头/表格行/小按钮/
   遮罩/命名卡等仍写死深色（rgba(8,18,38,*) / thead 底 rgba(0,40,80,.92)+#a0c8e8 /
   tbody 字 #c8ddf5 / 遮罩 rgba(2,6,14,.72) / option 底 #0d172a），
   切白天后浅字压浅底 → 读不清。此处统一改「浅底 + 深字」，语义色加深。
   scoped：用 .qcai-view 承接 data-v；Element Plus 内部用 :deep。
   ══════════════════════════════════════════════════════════════════════ */
[data-theme="light"] .qcai-view {
  color: #1a4070;

  &::-webkit-scrollbar-thumb { background: rgba(31,143,216,.30); }

  /* ── 标题栏 / 说明条 ── */
  .ptag { background: #dbe7f6; border-color: #bcd4ec; color: #0a6fd0; }
  .data-banner { background: var(--surface-2); border-color: var(--line-1); border-left-color: #1f8fd8; }

  /* ── 命名原则说明 ── */
  .naming-panel { background: var(--surface-1); border-color: var(--line-1); }
  .naming-toggle { background: var(--surface-2);
    &:hover { background: #dbe7f6; } }
  .naming-card { background: var(--surface-2); border-color: var(--line-2); }
  .naming-code { background: #dbe7f6; }
  .seg-prefix { background: #dbe7f6; color: #0a6fd0; }
  .seg-num { background: #fdf3e2; color: #b07800; }
  .seg-func { background: #e6f6f0; color: #0a8f6e; }
  .seg-work { background: #efe8fb; color: #6a3fc0; }

  /* ── 统计卡 / 工具栏 ── */
  .stat-card { background: var(--surface-1); border-color: var(--line-1); }
  .stat-value { color: #0a6fd0; }
  .toolbar { background: var(--surface-1); border-color: var(--line-1); }
  .search-box input { background: var(--field); border-color: #c0d2e4; color: #0a2858;
    &::placeholder { color: #a8bccd; }
    &:focus { border-color: #1f8fd8; box-shadow: 0 0 0 2px rgba(31,143,216,.16); } }
  .search-icon { color: #7a93ab; }
  .btn-outline { background: var(--surface-2); color: #3a6a94; border-color: #c0d2e4;
    &:hover { background: #cddcec; color: #0a2858; } }

  /* ── 表格 ── */
  .table-wrap { background: var(--surface-1); border-color: var(--line-1); }
  .table-scroll::-webkit-scrollbar-thumb { background: rgba(31,143,216,.32); }
  .table-scroll::-webkit-scrollbar-corner { background: transparent; }
  thead th { background: var(--surface-2); color: #3a6a94; border-bottom-color: var(--line-1); }
  tbody td { color: #0a2858; border-bottom-color: var(--line-2); }
  tbody tr { background: var(--surface-1); }
  tbody tr:nth-child(even) { background: var(--surface-2); }
  tbody tr:hover { background: #dce8f6; }
  .agent-name { color: #0a6fd0; }
  .badge-active { background: #e6f6f0; color: #0a7050; border-color: #a8ddca; }
  .badge-dev { background: #fdf3e2; color: #b07800; border-color: #efd79a; }
  .badge-off { background: var(--surface-2); color: #5a7a9a; border-color: #c0d2e4; }

  .btn-success-sm { background: #e6f6f0; color: #0a7050; border-color: #a8ddca;
    &:hover { background: #d6efe6; } }
  .btn-warn-sm { background: #fdf3e2; color: #b07800; border-color: #efd79a;
    &:hover { background: #faeacd; } }
  .btn-grey-sm { background: var(--surface-2); color: #2a5a86; border-color: #c0d2e4;
    &:hover { background: #cddcec; } }
  .btn-danger-sm { background: #fbdede; color: #c0392b; border-color: #f0b8b8;
    &:hover { background: #fadada; color: #a02020; } }
  .no-data { color: #7a93ab; }

  /* ── 弹窗（新增/编辑、分类、确认、SVG 预览）── */
  .modal-overlay, .cat-modal { background: rgba(20,45,80,.42); }
  .modal { background: var(--surface-1); border-color: var(--line-1); box-shadow: 0 24px 80px rgba(20,60,110,.18); }
  .modal-close { color: #7a93ab; &:hover { background: #fadada; color: #c0392b; } }
  .modal-body::-webkit-scrollbar-thumb { background: rgba(31,143,216,.32); }
  .form-section-title { color: #0a6fd0; border-bottom-color: var(--line-2); }
  .form-group label { color: #1a4070; }
  .form-group .req { color: #d02828; }
  .form-ctrl { background: var(--field); border-color: #c0d2e4; color: #0a2858;
    &::placeholder { color: #a8bccd; }
    &:focus { border-color: #1f8fd8; box-shadow: 0 0 0 2px rgba(31,143,216,.16); }
    option { background: var(--field); color: #0a2858; } }
  .form-ctrl[readonly] { background: var(--well); color: #4a6a8a; }
  .form-ctrl.generated { color: #0a6fd0; }
  .hint { color: #7a93ab; }
  .unit-label { color: #1a4070; }
  .btn-add-cat { border-color: #7fb2e0; background: #dbe7f6; color: #0a6fd0;
    &:hover { background: #c9ddf3; } }

  .cat-box { background: var(--surface-1); border-color: var(--line-1); box-shadow: 0 24px 80px rgba(20,60,110,.18); }
  .cat-list::-webkit-scrollbar-thumb { background: rgba(31,143,216,.32); }
  .cat-item { background: var(--surface-2); border-color: var(--line-2); color: #0a2858; }
  .cat-item.builtin { border-color: #a8ddca; }
  .cat-item.builtin span::after { color: #0a8f6e; }
  .cat-empty { color: #7a93ab; }
  .del-cat { color: #7a93ab; &:hover { color: #c0392b; } }

  .confirm-box { background: var(--surface-1); border-color: rgba(208,40,40,.45); box-shadow: 0 24px 80px rgba(20,60,110,.18); }
  .confirm-body b { color: #0a6fd0; }

  .svg-modal { background: var(--surface-1); border-color: var(--line-1); box-shadow: 0 24px 80px rgba(20,60,110,.18); }
  .svg-preview-area { background: var(--surface-2); }
  .svg-preview-area :deep(svg) { box-shadow: 0 4px 24px rgba(20,60,110,.18); }
  .svg-tip { color: #7a93ab; }
}
</style>
