<template>
  <div v-if="open" class="en-mask" @click.self="close">
    <div class="en-dialog">
      <div class="en-head">
        <div class="en-title">导出命名 · {{ meta?.label }}</div>
        <button class="en-x" type="button" @click="close" aria-label="关闭">✕</button>
      </div>

      <div class="en-body">
        <p class="en-tip">自定义「{{ meta?.label }}」导出文件的命名格式。点击下方变量即可插入，留空则使用系统默认。</p>

        <div class="en-chips">
          <span class="en-chips-label">可用变量</span>
          <button v-for="v in meta?.vars" :key="v" class="en-chip" type="button" @click="insert(v)">{{ '{' + v + '}' }}</button>
        </div>

        <input
          ref="inputRef"
          class="en-input"
          v-model="local"
          placeholder="例如：预排筛选结果_{year}"
          @keydown.enter="confirm"
        />

        <div class="en-legend">
          <span><b>{year}</b> 年份</span>
          <span><b>{month}</b> 月份</span>
          <span><b>{date}</b> 日期</span>
          <span><b>{time}</b> 时间</span>
          <span><b>{label}</b> 标签</span>
          <span><b>{split}</b> 分月</span>
          <span><b>{type}</b> 类型</span>
        </div>

        <div class="en-preview">
          <span class="en-pv-label">实时预览</span>
          <code class="en-pv-name">{{ preview }}</code>
        </div>
        <p v-if="ctxHint" class="en-ctx">{{ ctxHint }}</p>
      </div>

      <div class="en-foot">
        <button class="en-btn ghost" type="button" @click="reset">恢复默认</button>
        <div class="en-foot-right">
          <button class="en-btn" type="button" @click="close">取消</button>
          <button class="en-btn primary" type="button" @click="confirm">确定</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, watch, nextTick } from 'vue'
import { NAMING_TYPES, buildNameFromTpl, getTpl, saveTpl, sampleCtx } from '../../composables/useExportNaming.js'

const props = defineProps({
  modelValue: { type: Boolean, default: false },
  type: { type: String, default: 'preplan' },
  // ★ 2026-09-20：调用方（预排筛选 / 审核决议 / 存档中心）把「当前页面筛选」传进来，
  //   预览的 {year}{month}{label}{split} 便跟随页面所选的年 / 预排月份，而不是写死的样本。
  //   不传时退回 sampleCtx（独立打开也能用，但只作兜底）。
  ctx: { type: Object, default: null },
})
const emit = defineEmits(['update:modelValue'])

const open = computed({
  get: () => props.modelValue,
  set: (v) => emit('update:modelValue', v),
})
const meta = computed(() => NAMING_TYPES[props.type])
const local = ref('')
const inputRef = ref(null)

// 上下文：优先用调用方传来的真实筛选，没有才用样本兜底
const effCtx = computed(() => props.ctx || sampleCtx(props.type))

// ★ 2026-09-20 修复：此前预览 = buildFileName(type, sampleCtx(type))
//   ①模板走 getTpl()（localStorage 里已保存的那份）→ 输入框里正在编辑的内容不参与预览，改了半天预览纹丝不动；
//   ②上下文是写死样本 → 在预排页切到别的预排月份，{month} 依然显示样本的 9 月。
//   现在模板取 local（编辑中），上下文取 effCtx（页面当前筛选），两处都实时。
const preview = computed(() => buildNameFromTpl(local.value, props.type, effCtx.value))

// 把「预览到底基于什么筛选」显式写在预览下方，避免再被误认为固定版
const ctxHint = computed(() => {
  const c = props.ctx
  if (!c) return ''
  const bits = []
  if (c.label) bits.push(String(c.label))
  else {
    if (c.year) bits.push(`${c.year}年`)
    if (c.month) bits.push(String(c.month))
  }
  if (c.splitByMonth) bits.push('按月分 Sheet')
  return bits.length ? `基于当前页面：${bits.join(' · ')}` : ''
})

watch(
  () => [props.modelValue, props.type],
  () => {
    if (props.modelValue) {
      local.value = getTpl(props.type)
      nextTick(() => inputRef.value && inputRef.value.focus())
    }
  },
  { immediate: true },
)

function insert(v) {
  local.value = (local.value || '') + `{${v}}`
  nextTick(() => inputRef.value && inputRef.value.focus())
}
function reset() {
  local.value = meta.value.defaultTpl
}
function confirm() {
  saveTpl(props.type, (local.value || '').trim())
  close()
}
function close() {
  emit('update:modelValue', false)
}
</script>

<style lang="scss" scoped>
.en-mask {
  position: fixed;
  inset: 0;
  background: rgba(2, 8, 18, 0.62);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 2000;
  backdrop-filter: blur(2px);
}

.en-dialog {
  width: 460px;
  max-width: 92vw;
  background: linear-gradient(135deg, #061525, #08203a);
  border: 1px solid #11406e;
  border-radius: 12px;
  box-shadow: 0 12px 40px rgba(0, 0, 0, 0.55), 0 0 0 1px rgba(0, 150, 255, 0.08) inset;
  overflow: hidden;
  color: #c8ddf5;
}

.en-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-bottom: 1px solid rgba(0, 90, 170, 0.22);
}
.en-title {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: 0.5px;
  color: #d8ecff;
}
.en-x {
  width: 24px;
  height: 24px;
  border-radius: 6px;
  border: 1px solid #11406e;
  background: rgba(0, 50, 110, 0.3);
  color: #7fa8c8;
  cursor: pointer;
  font-size: 12px;
  line-height: 1;
  &:hover { color: #fff; border-color: #2a7fd0; }
}

.en-body { padding: 14px 16px; display: flex; flex-direction: column; gap: 10px; }
.en-tip { font-size: 11px; color: #6aa3c8; margin: 0; line-height: 1.5; }

.en-chips { display: flex; flex-wrap: wrap; align-items: center; gap: 6px; }
.en-chips-label { font-size: 10.5px; color: #5a86a8; margin-right: 2px; }
.en-chip {
  font-size: 11px;
  font-family: 'Consolas', monospace;
  padding: 3px 8px;
  border-radius: 5px;
  border: 1px solid #11406e;
  background: rgba(0, 60, 130, 0.22);
  color: #8fd0ff;
  cursor: pointer;
  transition: all 0.15s;
  &:hover { background: rgba(0, 90, 190, 0.35); border-color: #2a7fd0; color: #d8f0ff; }
}

.en-input {
  width: 100%;
  box-sizing: border-box;
  padding: 9px 11px;
  font-size: 12px;
  font-family: 'Consolas', monospace;
  color: #d8ecff;
  background: #04101e;
  border: 1px solid #11406e;
  border-radius: 7px;
  outline: none;
  transition: border-color 0.15s;
  &::placeholder { color: #40627e; }
  &:focus { border-color: #2a9fe0; box-shadow: 0 0 0 2px rgba(0, 150, 255, 0.15); }
}

.en-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 4px 12px;
  font-size: 10px;
  color: #5a86a8;
  b { color: #8fd0ff; font-family: 'Consolas', monospace; font-weight: 600; }
}

.en-preview {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 9px 11px;
  background: rgba(0, 40, 90, 0.25);
  border: 1px dashed #1c5078;
  border-radius: 7px;
}
.en-pv-label { font-size: 10px; color: #5a86a8; flex-shrink: 0; }
.en-pv-name {
  font-size: 12px;
  font-family: 'Consolas', monospace;
  color: #38d9a9;
  word-break: break-all;
}
/* ★ 2026-09-20：预览下方说明「基于哪个页面的哪份筛选」，让联动关系可见 */
.en-ctx { font-size: 10px; color: #5a86a8; margin: 0; }

.en-foot {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 12px 16px;
  border-top: 1px solid rgba(0, 90, 170, 0.22);
}
.en-foot-right { display: flex; gap: 8px; }
.en-btn {
  font-size: 11.5px;
  padding: 6px 16px;
  border-radius: 7px;
  border: 1px solid #11406e;
  background: rgba(0, 50, 110, 0.3);
  color: #c8ddf5;
  cursor: pointer;
  transition: all 0.15s;
  &:hover { border-color: #2a7fd0; }
  &.ghost { background: transparent; color: #7fa8c8; }
  &.primary {
    background: linear-gradient(90deg, #0066cc, #00b3a4);
    border-color: #0088c0;
    color: #fff;
    &:hover { filter: brightness(1.1); }
  }
}

/* 白天主题覆盖（2026-09-24：底色改用全局 --surface-* 令牌，避免又一块纯白刺眼） */
[data-theme='light'] .en-dialog {
  background: linear-gradient(135deg, var(--surface-1), var(--surface-2));
  border-color: var(--line-1);
  color: var(--t1);
}
[data-theme='light'] .en-head { border-bottom-color: var(--line-2); }
[data-theme='light'] .en-title { color: var(--t1); }
[data-theme='light'] .en-x { background: var(--well); border-color: #c0d2e4; color: #3a5d84; &:hover { color: #14508c; border-color: #8fbce4; } }
[data-theme='light'] .en-tip, [data-theme='light'] .en-chips-label, [data-theme='light'] .en-legend { color: #3a5d84; }
[data-theme='light'] .en-chip { background: #dbe7f6; border-color: #b4cce6; color: #14568f; &:hover { background: #c9dcf3; color: #0f4a80; } }
[data-theme='light'] .en-input { background: var(--field); border-color: #c0d2e4; color: var(--t1); &::placeholder { color: #8da3bb; } &:focus { border-color: #1a63b6; } }
[data-theme='light'] .en-legend b { color: #14568f; }
[data-theme='light'] .en-preview { background: var(--surface-2); border-color: var(--line-1); }
[data-theme='light'] .en-pv-label { color: #3a5d84; }
[data-theme='light'] .en-pv-name { color: #0a6b4d; }
[data-theme='light'] .en-ctx { color: #3a5d84; }
[data-theme='light'] .en-foot { border-top-color: var(--line-2); }
[data-theme='light'] .en-btn { background: var(--well); border-color: #c0d2e4; color: var(--t1); &.ghost { background: transparent; color: #3a5d84; } &.primary { background: linear-gradient(90deg, #14568f, #0a6b4d); color: #ffffff; } }
</style>
