<template>
  <div class="warning-rules-view">
    <!-- 页面标题栏 -->
    <div class="pbar">
      <div class="pbar-left">
        <div class="ptag">RULE</div>
        <div class="ptitle">预警规则配置 · <span>多维度组合筛选</span></div>
      </div>
      <div class="pright">
        <div class="bsm act">全部</div>
        <div class="bsm">启用中</div>
        <div class="bsm">已停用</div>
        <button class="btn-add-rule" @click="openRuleForm">
          <span class="bar-plus">+</span>
          <span>新增规则</span>
        </button>
      </div>
    </div>

    <!-- 规则说明 -->
    <div class="help-bar">
      <div class="help-item">
        <span class="help-label">触发条件</span>
        <span class="help-desc">实际产量累计值 vs 阈值。例如：阈值1000，运算符 >=，达到时自动预警</span>
      </div>
      <div class="help-item">
        <span class="help-label">多维筛选</span>
        <span class="help-desc">按客户/Fab/BU/Model/52阶料号/成品料号组合筛选，不填=不限制</span>
      </div>
    </div>

    <!-- 规则卡片网格 -->
    <div class="rule-grid">
      <div v-if="rules.length === 0" class="empty-state">
        <p>暂无预警规则，请点击"新增规则"添加</p>
      </div>

      <div
        v-for="rule in rules"
        :key="rule.id"
        class="rule-card"
        :class="{ 'is-inactive': !rule.is_active }"
      >
        <div class="rc-header">
          <div class="rc-name">
            <span class="rc-dot" :class="rule.is_active ? 'on' : 'off'"></span>
            {{ rule.name }}
          </div>
          <div class="rc-actions">
            <button class="rc-btn" @click="toggleRule(rule)" :title="rule.is_active ? '停用' : '启用'">
              <span :class="rule.is_active ? 'icon-pause' : 'icon-play'">⏯</span>
            </button>
            <button class="rc-btn" @click="openRuleForm(rule)" title="编辑">✎</button>
            <button class="rc-btn danger" @click="handleDelete(rule)" title="删除">✕</button>
          </div>
        </div>

        <div class="rc-target">
          <span class="rc-target-label">应用范围：</span>
          {{ formatRuleTarget(rule) }}
        </div>

        <div class="rc-condition">
          <div class="rc-cond-item">
            <span class="rc-cond-l">条件类型</span>
            <span class="rc-cond-v">{{ getConditionLabel(rule.condition_type) }}</span>
          </div>
          <div class="rc-cond-item">
            <span class="rc-cond-l">运算符</span>
            <span class="rc-cond-v op">{{ getOperatorLabel(rule.operator) }}</span>
          </div>
          <div class="rc-cond-item">
            <span class="rc-cond-l">阈值</span>
            <span class="rc-cond-v threshold">{{ formatThreshold(rule.condition_type, rule.threshold) }}</span>
          </div>
        </div>

        <div class="rc-status">
          <span class="rc-status-text" :class="rule.is_active ? 'on' : 'off'">
            {{ rule.is_active ? '● 运行中' : '○ 已停用' }}
          </span>
        </div>
      </div>
    </div>

    <!-- 规则表单弹窗 -->
    <div class="runov" :class="{ show: formVisible }" @click.self="formVisible = false">
      <div class="runbox">
        <div class="runbox-close" @click="formVisible = false">✕</div>
        <div class="run-title">{{ editingRule ? '编辑规则' : '新增规则' }}</div>
        <div class="run-subtitle">设置产品产量预警触发条件</div>

        <div class="form-section">
          <div class="section-title-mini">📌 规则名称</div>
          <input
            v-model="ruleForm.name"
            class="form-input"
            placeholder="例如：A客户M11产品预警"
          />
        </div>

        <div class="form-section">
          <div class="section-title-mini">🎯 匹配条件（不填 = 不限制）</div>

          <div class="form-row">
            <label class="form-lbl">客户</label>
            <select v-model="ruleForm.customer" class="form-select">
              <option :value="null">所有客户</option>
              <option v-for="c in customers" :key="c.id" :value="c.id">
                {{ c.name }} ({{ c.code }})
              </option>
            </select>
          </div>

          <div class="form-row">
            <label class="form-lbl">具体产品</label>
            <select v-model="ruleForm.product" class="form-select">
              <option :value="null">所有产品</option>
              <option v-for="p in products" :key="p.id" :value="p.id">
                {{ p.code }} - {{ p.finished_product_code || p.name }}
              </option>
            </select>
          </div>

          <div class="form-grid">
            <div class="form-row">
              <label class="form-lbl">Fab</label>
              <input v-model="ruleForm.fab" class="form-input" placeholder="如 2A" />
            </div>
            <div class="form-row">
              <label class="form-lbl">BU</label>
              <input v-model="ruleForm.bu" class="form-input" placeholder="如 M11" />
            </div>
            <div class="form-row">
              <label class="form-lbl">Model</label>
              <input v-model="ruleForm.mode" class="form-input" placeholder="如 T1" />
            </div>
            <div class="form-row">
              <label class="form-lbl">52阶料号</label>
              <input v-model="ruleForm.material_code_52" class="form-input" placeholder="如 52-ABC-001" />
            </div>
            <div class="form-row" style="grid-column: span 2;">
              <label class="form-lbl">成品料号</label>
              <input v-model="ruleForm.finished_product_code" class="form-input" placeholder="如 PROD-XYZ" />
            </div>
          </div>
        </div>

        <div class="form-section">
          <div class="section-title-mini">⚡ 触发条件</div>

          <div class="form-grid">
            <div class="form-row">
              <label class="form-lbl">运算符</label>
              <select v-model="ruleForm.operator" class="form-select">
                <option value=">=">大于等于 (&gt;=)</option>
                <option value=">">大于 (&gt;)</option>
                <option value="<=">小于等于 (&lt;=)</option>
                <option value="<">小于 (&lt;)</option>
                <option value="==">等于 (==)</option>
              </select>
            </div>
            <div class="form-row">
              <label class="form-lbl">阈值</label>
              <el-input-number
                v-model="ruleForm.threshold"
                :precision="0"
                :step="100"
                :min="0"
                controls-position="right"
                class="rule-number-input"
              />
            </div>
            <div class="form-row" style="grid-column: span 2;">
              <label class="form-lbl">启用状态</label>
              <div class="switch-row">
                <span class="switch-label">{{ ruleForm.is_active ? '已启用' : '已停用' }}</span>
                <label class="tech-switch">
                  <input type="checkbox" v-model="ruleForm.is_active" />
                  <span class="switch-slider"></span>
                </label>
              </div>
            </div>
          </div>
        </div>

        <div class="run-btns">
          <button class="run-btn sec" @click="formVisible = false">取消</button>
          <button class="run-btn primary" @click="saveRule">保存规则</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { warningRuleApi } from '../api/warningRule'
import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

const rules = ref([])
const products = ref([])
const customers = ref([])
const formVisible = ref(false)
const editingRule = ref(null)

const ruleForm = reactive({
  name: '',
  customer: null,
  product: null,
  fab: '',
  bu: '',
  mode: '',
  material_code_52: '',
  finished_product_code: '',
  condition_type: 'cumulative_vs_plan',
  operator: '>=',
  threshold: 1000,
  is_active: true
})

const getConditionLabel = (type) => type === 'cumulative_vs_plan' ? '实际产量累计值' : type

const getOperatorLabel = (op) => {
  const map = { '>=': '>=', '>': '>', '<=': '<=', '<': '<', '==': '==' }
  return map[op] || op
}

const formatThreshold = (type, value) => {
  if (type === 'cumulative_vs_plan') return Number(value).toLocaleString()
  return value
}

const formatRuleTarget = (rule) => {
  const parts = []
  if (rule.customer_name) parts.push(`客户:${rule.customer_name}`)
  if (rule.product_name) parts.push(`产品:${rule.product_name}`)
  if (rule.fab) parts.push(`Fab:${rule.fab}`)
  if (rule.bu) parts.push(`BU:${rule.bu}`)
  if (rule.mode) parts.push(`Model:${rule.mode}`)
  if (rule.material_code_52) parts.push(`52阶:${rule.material_code_52}`)
  if (rule.finished_product_code) parts.push(`成品:${rule.finished_product_code}`)
  if (parts.length === 0) parts.push('所有产品')
  return parts.join(' | ')
}

const loadRules = async () => {
  try {
    // ★ 只加载 rule_type=warning 的规则（与筛选规则完全独立）
    const response = await warningRuleApi.getList({ rule_type: 'warning' })
    rules.value = response.data.results || response.data
  } catch (error) {
    ElMessage.error('加载规则列表失败')
  }
}

const loadProducts = async () => {
  try {
    const response = await axios.get(`${API_BASE}/products/`)
    products.value = response.data.data || []
  } catch (error) { /* ignore */ }
}

const loadCustomers = async () => {
  try {
    const response = await axios.get(`${API_BASE}/customers/`)
    customers.value = response.data.data || []
  } catch (error) { /* ignore */ }
}

const openRuleForm = (rule = null) => {
  editingRule.value = rule
  if (rule) {
    Object.assign(ruleForm, {
      name: rule.name,
      customer: rule.customer,
      product: rule.product,
      fab: rule.fab || '',
      bu: rule.bu || '',
      mode: rule.mode || '',
      material_code_52: rule.material_code_52 || '',
      finished_product_code: rule.finished_product_code || '',
      condition_type: rule.condition_type,
      operator: rule.operator,
      threshold: parseFloat(rule.threshold),
      is_active: rule.is_active
    })
  } else {
    Object.assign(ruleForm, {
      name: '',
      customer: null,
      product: null,
      fab: '',
      bu: '',
      mode: '',
      material_code_52: '',
      finished_product_code: '',
      condition_type: 'cumulative_vs_plan',
      operator: '>=',
      threshold: 1000,
      is_active: true
    })
  }
  formVisible.value = true
}

const saveRule = async () => {
  // ★ 防御性校验：避免编辑模式下 id 缺失导致 URL 拼成 ".../undefined/"
  const hasId = editingRule.value && (editingRule.value.id !== undefined && editingRule.value.id !== null && editingRule.value.id !== '')
  const isEdit = !!hasId

  // 表单必填校验
  if (!ruleForm.name || !ruleForm.name.trim()) {
    ElMessage.warning('请填写规则名称')
    return
  }
  if (ruleForm.threshold === null || ruleForm.threshold === undefined || ruleForm.threshold === '') {
    ElMessage.warning('请填写阈值')
    return
  }

  // 构造 payload：把空字符串归一为 null，避免后端 unique 冲突
  const payload = {
    name: ruleForm.name.trim(),
    customer: ruleForm.customer || null,
    product: ruleForm.product || null,
    fab: (ruleForm.fab || '').trim() || null,
    bu: (ruleForm.bu || '').trim() || null,
    mode: (ruleForm.mode || '').trim() || null,
    material_code_52: (ruleForm.material_code_52 || '').trim() || null,
    finished_product_code: (ruleForm.finished_product_code || '').trim() || null,
    condition_type: ruleForm.condition_type,
    operator: ruleForm.operator,
    threshold: Number(ruleForm.threshold),
    is_active: !!ruleForm.is_active
  }

  try {
    if (isEdit) {
      await warningRuleApi.update(editingRule.value.id, payload)
      ElMessage.success('更新成功')
    } else {
      await warningRuleApi.create(payload)
      ElMessage.success('创建成功')
    }
    formVisible.value = false
    loadRules()
  } catch (error) {
    console.error('[saveRule] 失败:', error)
    const detail = error?.response?.data
    let msg = '保存失败'
    if (typeof detail === 'string') msg = `保存失败：${detail}`
    else if (detail && typeof detail === 'object') {
      const firstKey = Object.keys(detail)[0]
      const firstVal = firstKey ? detail[firstKey] : null
      msg = `保存失败：${firstKey} - ${Array.isArray(firstVal) ? firstVal.join(';') : firstVal}`
    } else if (error?.message) {
      msg = `保存失败：${error.message}`
    }
    ElMessage.error(msg)
  }
}

const toggleRule = async (rule) => {
  if (!rule || rule.id === undefined || rule.id === null) {
    ElMessage.error('规则 id 缺失，无法切换状态')
    return
  }
  try {
    await warningRuleApi.toggle(rule.id)
    rule.is_active = !rule.is_active
    ElMessage.success(rule.is_active ? '已启用' : '已停用')
  } catch (error) {
    console.error('[toggleRule] 失败:', error)
    ElMessage.error('操作失败：' + (error?.response?.data?.detail || error.message))
  }
}

const handleDelete = async (rule) => {
  if (!rule || rule.id === undefined || rule.id === null) {
    ElMessage.error('规则 id 缺失，无法删除')
    return
  }
  try {
    await ElMessageBox.confirm(`确定要删除规则"${rule.name}"吗？`, '确认删除', { type: 'warning' })
    await warningRuleApi.delete(rule.id)
    ElMessage.success('删除成功')
    loadRules()
  } catch (error) {
    if (error !== 'cancel' && error !== 'close') {
      console.error('[handleDelete] 失败:', error)
      ElMessage.error('删除失败：' + (error?.response?.data?.detail || error.message))
    }
  }
}

onMounted(() => {
  loadRules()
  loadProducts()
  loadCustomers()
})
</script>

<style lang="scss" scoped>
/* ============================================
   WarningRulesView - a.txt 科技风 + 规则配置
   ============================================ */

.warning-rules-view {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 8px;
  min-height: 0;
}

/* ── 页面标题栏 ──────────────── */
.pbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  flex-shrink: 0;
}

.pbar-left { display: flex; align-items: center; gap: 6px; }

.ptag {
  background: rgba(0, 60, 120, 0.4);
  border: 1px solid #0d3050;
  color: #5a90b8;
  font-size: 9.5px;
  font-weight: 400;
  padding: 3px 10px;
  border-radius: 4px;
  letter-spacing: 0.5px;
}

.ptitle {
  font-size: 14px;
  font-weight: 500;
  color: #c8e0f8;
  letter-spacing: 0.8px;
  margin-left: 10px;

  span { color: #00d4aa; }
}

.pright { display: flex; align-items: center; gap: 8px; }

.bsm {
  font-size: 9px;
  font-weight: 300;
  padding: 3px 10px;
  border-radius: 12px;
  cursor: pointer;
  border: 1px solid #0d3050;
  background: rgba(0, 40, 90, 0.2);
  color: #3a6070;
  transition: all 0.15s;

  &:hover { background: rgba(0, 60, 130, 0.28); color: #7098b8; }
  &.act { background: rgba(0, 70, 160, 0.28); border-color: #0050a0; color: #90c0e8; }
}

/* ── 新增规则按钮（加大版） ────────────── */
.btn-add-rule {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.6px;
  padding: 9px 18px;
  border-radius: 22px;
  cursor: pointer;
  border: 1px solid #0a7adf;
  background: linear-gradient(135deg, #0066cc 0%, #0086e8 50%, #00b4d8 100%);
  color: #ffffff;
  box-shadow: 0 4px 18px rgba(0, 130, 230, 0.45), inset 0 1px 0 rgba(255, 255, 255, 0.18);
  transition: all 0.2s;
  position: relative;
  overflow: hidden;
  min-width: 120px;
  justify-content: center;

  &:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 24px rgba(0, 150, 240, 0.7), inset 0 1px 0 rgba(255, 255, 255, 0.25);
    background: linear-gradient(135deg, #0077e0 0%, #0098f8 50%, #00c4e8 100%);
  }

  &:active {
    transform: translateY(0);
    box-shadow: 0 2px 10px rgba(0, 130, 230, 0.5);
  }

  .bar-plus {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: rgba(255, 255, 255, 0.22);
    font-size: 14px;
    font-weight: 700;
    line-height: 1;
  }
}

/* ── 帮助栏 ──────────────────── */
.help-bar {
  display: grid;
  grid-template-columns: repeat(2, 1fr);
  gap: 8px;
  flex-shrink: 0;
}

.help-item {
  background: linear-gradient(135deg, #050f1e, #071a2e);
  border: 1px solid #0d2a48;
  border-left: 2px solid #0088ff;
  border-radius: 6px;
  padding: 6px 10px;
  display: flex;
  align-items: center;
  gap: 10px;
}

.help-label {
  font-size: 10px;
  font-weight: 600;
  color: #0099cc;
  flex-shrink: 0;
}

.help-desc {
  font-size: 9.5px;
  color: #6a8aa8;
  line-height: 1.4;
}

/* ── 规则网格 ────────────────── */
.rule-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 8px;
  min-height: 0;
  overflow-y: auto;
  align-content: start;
}

.empty-state {
  grid-column: 1 / -1;
  padding: 60px 20px;
  text-align: center;
  color: #4d7d9e;
  font-size: 11px;
}

.rule-card {
  background: linear-gradient(135deg, #050f1e, #071a2e);
  border: 1px solid #0d2a48;
  border-radius: 10px;
  padding: 10px 12px;
  position: relative;
  overflow: hidden;
  transition: all 0.2s;

  &:hover {
    border-color: #1a6090;
    transform: translateY(-1px);
  }

  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 8%;
    bottom: 8%;
    width: 2px;
    background: linear-gradient(to bottom, rgba(0, 212, 170, 0.6), rgba(0, 80, 160, 0.2));
  }

  &.is-inactive {
    opacity: 0.55;

    &::before {
      background: linear-gradient(to bottom, rgba(100, 100, 100, 0.4), rgba(50, 50, 50, 0.2));
    }
  }
}

.rc-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 8px;
}

.rc-name {
  font-size: 12px;
  font-weight: 700;
  color: #c8ddf5;
  display: flex;
  align-items: center;
  gap: 6px;
  flex: 1;
  min-width: 0;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.rc-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;

  &.on {
    background: #00d4aa;
    box-shadow: 0 0 6px rgba(0, 212, 170, 0.6);
  }
  &.off { background: #3a6070; }
}

.rc-actions {
  display: flex;
  gap: 4px;
}

.rc-btn {
  width: 22px;
  height: 22px;
  border-radius: 4px;
  border: 1px solid #0d3050;
  background: rgba(0, 40, 90, 0.2);
  color: #6aa3c8;
  cursor: pointer;
  font-size: 10px;
  display: flex;
  align-items: center;
  justify-content: center;
  transition: all 0.15s;

  &:hover {
    background: rgba(0, 60, 130, 0.4);
    color: #a8d4f5;
  }

  &.danger:hover {
    background: rgba(160, 30, 30, 0.3);
    color: #ff8888;
    border-color: #882020;
  }
}

.rc-target {
  font-size: 10px;
  color: #6aa3c8;
  margin-bottom: 8px;
  padding: 4px 8px;
  background: rgba(0, 50, 110, 0.2);
  border-radius: 4px;
  line-height: 1.4;
}

.rc-target-label {
  color: #4d7d9e;
  font-weight: 500;
}

.rc-condition {
  display: grid;
  grid-template-columns: 1fr 1fr 1fr;
  gap: 6px;
  padding: 6px 0;
  border-top: 1px solid rgba(0, 80, 160, 0.15);
  border-bottom: 1px solid rgba(0, 80, 160, 0.15);
}

.rc-cond-item { text-align: center; }

.rc-cond-l {
  font-size: 8.5px;
  color: #4d7d9e;
  margin-bottom: 2px;
}

.rc-cond-v {
  font-size: 12px;
  font-weight: 600;
  color: #c8ddf5;

  &.op { color: #0099cc; }
  &.threshold { color: #00d4aa; }
}

.rc-status {
  text-align: right;
  margin-top: 6px;
}

.rc-status-text {
  font-size: 9px;
  font-weight: 500;

  &.on { color: #00d4aa; }
  &.off { color: #4d7d9e; }
}

/* ── 弹窗 ────────────────────── */
.runov {
  position: fixed;
  inset: 0;
  background: rgba(0, 5, 15, 0.7);
  backdrop-filter: blur(4px);
  z-index: 100;
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.25s;

  &.show { opacity: 1; pointer-events: all; }
}

.runbox {
  background: linear-gradient(135deg, #040e1e, #061828);
  border: 1px solid rgba(0, 100, 200, 0.3);
  border-radius: 16px;
  width: 700px;
  max-height: 85vh;
  padding: 24px 28px;
  position: relative;
  box-shadow: 0 24px 80px rgba(0, 20, 80, 0.8);
  overflow-y: auto;

  /* 自定义滚动条 - 深色科技风 */
  scrollbar-width: thin;
  scrollbar-color: rgba(0, 150, 220, 0.45) rgba(0, 20, 40, 0.5);

  &::-webkit-scrollbar {
    width: 6px;
    height: 6px;
  }

  &::-webkit-scrollbar-track {
    background: rgba(0, 20, 40, 0.5);
    border-radius: 3px;
  }

  &::-webkit-scrollbar-thumb {
    background: linear-gradient(180deg, rgba(0, 119, 204, 0.6), rgba(0, 153, 204, 0.4));
    border-radius: 3px;
    border: 1px solid rgba(0, 50, 100, 0.3);

    &:hover {
      background: linear-gradient(180deg, rgba(0, 150, 220, 0.8), rgba(0, 180, 230, 0.6));
      box-shadow: 0 0 6px rgba(0, 150, 220, 0.4);
    }
  }

  &::-webkit-scrollbar-corner {
    background: transparent;
  }
}

.runbox-close {
  position: absolute;
  top: 14px;
  right: 18px;
  font-size: 18px;
  color: #2a5070;
  cursor: pointer;

  &:hover { color: #90c0e8; }
}

.run-title {
  font-size: 18px;
  font-weight: 600;
  color: #c8e0f8;
  margin-bottom: 4px;
  letter-spacing: 0.5px;
}

.run-subtitle {
  font-size: 11px;
  font-weight: 300;
  color: #3a6080;
  margin-bottom: 16px;
}

.form-section {
  background: rgba(0, 25, 60, 0.3);
  border: 1px solid #0d3050;
  border-radius: 8px;
  padding: 12px 14px;
  margin-bottom: 12px;
}

.section-title-mini {
  font-size: 11px;
  font-weight: 600;
  color: #0099cc;
  margin-bottom: 10px;
  letter-spacing: 0.5px;
  display: flex;
  align-items: center;
  gap: 5px;

  &::before {
    content: '';
    width: 3px;
    height: 11px;
    background: #0077cc;
    border-radius: 2px;
  }
}

.form-row {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: 8px;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0 16px;
}

.form-lbl {
  font-size: 10px;
  color: #6aa3c8;
  width: 70px;
  text-align: right;
  flex-shrink: 0;
}

.form-input,
.form-select {
  flex: 1;
  background: rgba(0, 20, 40, 0.6);
  border: 1px solid #0d3050;
  border-radius: 4px;
  padding: 6px 10px;
  color: #c8ddf5;
  font-size: 11px;
  font-family: inherit;
  transition: all 0.15s;
  width: 100%;

  &:focus {
    outline: none;
    border-color: #0077cc;
    background: rgba(0, 40, 80, 0.4);
  }

  &::placeholder { color: #3a5870; }
}

.form-select {
  cursor: pointer;
  appearance: none;
  background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 12' fill='%236aa3c8'%3E%3Cpath d='M3 5l3 3 3-3z'/%3E%3C/svg%3E");
  background-repeat: no-repeat;
  background-position: right 8px center;
  background-size: 12px;
  padding-right: 28px;
}

.form-grid .form-row {
  margin-bottom: 0;
}

.switch-row {
  display: flex;
  align-items: center;
  gap: 10px;
  flex: 1;
}

.switch-label {
  font-size: 11px;
  color: #c8ddf5;
}

.tech-switch {
  position: relative;
  width: 40px;
  height: 20px;
  display: inline-block;

  input { display: none; }

  .switch-slider {
    position: absolute;
    inset: 0;
    background: #1a4060;
    border-radius: 20px;
    transition: all 0.2s;
    cursor: pointer;

    &::before {
      content: '';
      position: absolute;
      top: 2px;
      left: 2px;
      width: 16px;
      height: 16px;
      background: #4d7d9e;
      border-radius: 50%;
      transition: all 0.2s;
    }
  }

  input:checked + .switch-slider {
    background: linear-gradient(90deg, #0055aa, #00d4aa);

    &::before {
      transform: translateX(20px);
      background: #fff;
      box-shadow: 0 0 6px rgba(0, 212, 170, 0.6);
    }
  }
}

.run-btns {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin-top: 16px;
}

.run-btn {
  font-size: 13px;
  font-weight: 600;
  padding: 11px 30px;
  border-radius: 22px;
  cursor: pointer;
  border: none;
  transition: all 0.2s;

  &.primary {
    background: linear-gradient(135deg, #0055aa, #0077cc);
    color: #fff;
    box-shadow: 0 4px 16px rgba(0, 100, 200, 0.4);

    &:hover {
      box-shadow: 0 6px 24px rgba(0, 120, 240, 0.6);
    }
  }

  &.sec {
    background: rgba(0, 40, 80, 0.3);
    color: #5a90b8;
    border: 1px solid #0d3050;

    &:hover {
      background: rgba(0, 60, 120, 0.4);
    }
  }
}

.rule-grid::-webkit-scrollbar { width: 4px; }
.rule-grid::-webkit-scrollbar-track { background: transparent; }
.rule-grid::-webkit-scrollbar-thumb { background: rgba(0, 100, 200, 0.3); border-radius: 2px; }

/* ══════════════════════════════════════════════════════════════════════
   ★ 白天主题覆盖（2026-09-18）
   根因：本页原样式整套写死深色（文字 #c8ddf5 / 卡片底 linear-gradient(#050f1e,#071a2e)
   / 边框 #0d2a48 / 表单底 rgba(0,20,40,.6) / 弹窗底 linear-gradient(#040e1e,#061828)），
   且无 [data-theme="light"] 覆盖 → 切白天后浅字压浅底糊成一片。
   此处统一改「浅底 + 深字」，语义色（蓝/绿/黄/红）加深以保证白底可读。
   scoped：用 .warning-rules-view 承接 data-v；Element Plus 内部用 :deep。
   ══════════════════════════════════════════════════════════════════════ */
[data-theme="light"] .warning-rules-view {
  color: #1a4070;

  /* ── 标题栏 ── */
  .ptag { background: #dbe7f6; border-color: #bcd4ec; color: #2a5a86; }
  .ptitle { color: #0a2858; span { color: #0a8f6e; } }
  .bsm { border-color: #c0d2e4; background: var(--surface-2); color: #4a6a8a;
    &:hover { background: #cddcec; color: #24507a; }
    &.act { background: #c9ddf3; border-color: #7fb2e0; color: #14508c; } }
  .btn-add-rule { box-shadow: 0 4px 18px rgba(0,130,230,.26), inset 0 1px 0 rgba(255,255,255,.18);
    &:hover { box-shadow: 0 6px 24px rgba(0,150,240,.34), inset 0 1px 0 rgba(255,255,255,.25); }
    &:active { box-shadow: 0 2px 10px rgba(0,130,230,.28); } }

  /* ── 帮助栏 ── */
  .help-item { background: var(--surface-2); border-color: var(--line-1); border-left-color: #1f8fd8; }
  .help-label { color: #0a6fd0; }
  .help-desc { color: #5a7a9a; }

  /* ── 规则卡片 ── */
  .empty-state { color: #7a93ab; }
  .rule-card { background: var(--surface-1); border-color: var(--line-1);
    &:hover { border-color: #7fb2e0; } }
  .rc-name { color: #0a2858; }
  .rc-dot {
    &.on { background: #0a8f6e; box-shadow: 0 0 6px rgba(10,143,110,.45); }
    &.off { background: #9ab0c4; } }
  .rc-btn { border-color: #c0d2e4; background: var(--surface-2); color: #3a6a94;
    &:hover { background: #cddcec; color: #0a2858; }
    &.danger:hover { background: #fadada; color: #c0392b; border-color: #f0b8b8; } }
  .rc-target { color: #2a5a86; background: var(--surface-2); }
  .rc-target-label { color: #5a7a9a; }
  .rc-condition { border-top-color: var(--line-2); border-bottom-color: var(--line-2); }
  .rc-cond-l { color: #5a7a9a; }
  .rc-cond-v { color: #0a2858; &.op { color: #0a6fd0; } &.threshold { color: #0a8f6e; } }
  .rc-status-text { &.on { color: #0a8f6e; } &.off { color: #7a93ab; } }

  /* ── 弹窗 ── */
  .runov { background: rgba(20,45,80,.42); }
  .runbox { background: var(--surface-1); border-color: var(--line-1); box-shadow: 0 24px 80px rgba(20,60,110,.18);
    scrollbar-color: rgba(31,143,216,.45) rgba(223,234,245,.7);
    &::-webkit-scrollbar-track { background: var(--surface-2); }
    &::-webkit-scrollbar-thumb {
      background: linear-gradient(180deg, rgba(31,143,216,.5), rgba(60,160,220,.35));
      border-color: rgba(180,205,228,.6);
      &:hover { background: linear-gradient(180deg, rgba(20,130,210,.7), rgba(40,150,215,.55)); box-shadow: 0 0 6px rgba(31,143,216,.3); } } }
  .runbox-close { color: #9ab0c4; &:hover { color: #14508c; } }
  .run-title { color: #0a2858; }
  .run-subtitle { color: #93a9bd; }

  /* ── 表单 ── */
  .form-section { background: var(--surface-2); border-color: var(--line-2); }
  .section-title-mini { color: #0a6fd0;
    &::before { background: #1f8fd8; } }
  .form-lbl { color: #5a7a9a; }
  .form-input, .form-select { background: var(--field); border-color: #c0d2e4; color: #0a2858;
    &:focus { border-color: #1f8fd8; background: #dcebfa; }
    &::placeholder { color: #a8bccd; } }
  .form-select { background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 12 12' fill='%233a6a94'%3E%3Cpath d='M3 5l3 3 3-3z'/%3E%3C/svg%3E"); }
  .switch-label { color: #0a2858; }
  .tech-switch {
    .switch-slider { background: #c9daea;
      &::before { background: #ffffff; } }
    input:checked + .switch-slider { background: linear-gradient(90deg, #0a6fd0, #0a8f6e);
      &::before { box-shadow: 0 0 6px rgba(10,143,110,.45); } } }
  .run-btn.primary { background: linear-gradient(135deg, #0a5fc0, #1478d0);
    box-shadow: 0 4px 16px rgba(0,100,200,.26);
    &:hover { box-shadow: 0 6px 24px rgba(0,120,240,.34); } }
  .run-btn.sec { background: var(--well); color: #4a6a8a; border-color: #c0d2e4;
    &:hover { background: #cddcec; color: #24507a; } }

  /* ── 滚动条 ── */
  .rule-grid::-webkit-scrollbar-thumb { background: rgba(31,143,216,.32); }
  &::-webkit-scrollbar-thumb { background: rgba(31,143,216,.32); }

  /* ── Element Plus：el-input-number（阈值）── */
  :deep(.el-input-number), :deep(.el-input-number .el-input__wrapper) {
    background: var(--field) !important; border-color: #c0d2e4 !important; color: #0a2858 !important;
    box-shadow: 0 0 0 1px #c9daea inset !important; }
  :deep(.el-input-number .el-input__inner) { color: #0a2858 !important; }
  :deep(.el-input-number__decrease), :deep(.el-input-number__increase) {
    background: var(--surface-2) !important; border-color: var(--line-1) !important; color: #2a5a86 !important; }
  :deep(.el-input-number__decrease:hover), :deep(.el-input-number__increase:hover) { color: #0a8f6e !important; }
  :deep(.el-input-number.is-disabled .el-input__wrapper) { background: #f2f5f8 !important; }
}
</style>

