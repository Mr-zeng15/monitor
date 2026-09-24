<template>
  <header class="app-header">
    <!-- 品牌区 -->
    <div class="hbrand">
      <div class="hgem"></div>
      <div class="eng">DQAEB1</div>
      <div class="chn">QC<em>风控</em>卫士</div>
      <div class="hbline"></div>
    </div>

    <!-- 四张 KPI 卡（静态示例数据，对齐 Q.html） -->
    <div class="hgroups">
      <div v-for="card in hcards" :key="card.key" class="hcard" :class="card.key">
        <div class="hcard-title" :class="card.key">{{ card.title }}</div>
        <div class="hcard-mets">
          <template v-for="(m, i) in card.metrics" :key="i">
            <div class="hcard-met">
              <div class="hcard-mval" :class="m.cls">{{ m.val }}<span v-if="m.unit" style="font-size:.65em">{{ m.unit }}</span></div>
              <div class="hcard-mlbl">{{ m.lbl }}</div>
            </div>
            <div v-if="i < card.metrics.length - 1" class="hcard-sep"></div>
          </template>
        </div>
      </div>
    </div>

    <!-- 主题开关 -->
    <div class="theme-sw">
      <div class="ts-wrap" @click="toggleTheme">
        <span class="ts-icon moon">🌙</span>
        <span class="ts-icon sun">☀️</span>
        <div class="ts-track"><div class="ts-thumb"></div></div>
        <span class="ts-lbl">{{ themeLabel }}</span>
      </div>
    </div>

    <!-- 右侧：实时状态 + 时钟 -->
    <div class="hright">
      <div class="lbadge"><span class="ldot"></span>实时更新中</div>
      <div class="htime">
        <div class="t">{{ clockTime }}</div>
        <div class="dd">{{ clockDate }}</div>
      </div>
    </div>
  </header>
</template>

<script setup>
import { ref, onMounted, onBeforeUnmount } from 'vue'

// ★ 四张 KPI 卡（静态示例数据，沿用 Q.html 指标/自动化/人力/出勤）
const hcards = ref([
  {
    key: 'idx', title: '指 标',
    metrics: [
      { val: '91.3', unit: '%', lbl: '最低执行率', cls: 'bad' },
      { val: '84', unit: '%', lbl: '最低结案率', cls: 'warn' },
      { val: '5.8', unit: '%', lbl: '最高再发率', cls: 'bad' }
    ]
  },
  {
    key: 'auto', title: '自动化',
    metrics: [
      { val: '94.1', unit: '', lbl: '焕新行动均值', cls: 'ok' },
      { val: '93', unit: '%', lbl: '回复率均值', cls: 'ok' },
      { val: '1.45', unit: '', lbl: '整体 Cpk', cls: 'ok' }
    ]
  },
  {
    key: 'hr', title: '人 力',
    metrics: [
      { val: '186', unit: '', lbl: '在线人数', cls: 'neu' },
      { val: '92', unit: '%', lbl: '产能利用率', cls: 'ok' },
      { val: '3', unit: '', lbl: '技能缺口', cls: 'warn' }
    ]
  },
  {
    key: 'att', title: '出 勤',
    metrics: [
      { val: '98.4', unit: '%', lbl: '出勤率', cls: 'ok' },
      { val: '2', unit: '', lbl: '请假人数', cls: 'warn' },
      { val: '1', unit: '', lbl: '加班班次', cls: 'neu' }
    ]
  }
])

// ── 主题切换（dark / light）────────
// ★ 2026-09-23：选择结果写入 localStorage('qc-theme')，由 index.html 首帧脚本回读，
//   保证「白天」刷新后仍然生效（此前不持久化，刷新即回深夜）。
const THEME_KEY = 'qc-theme'
const themeLabel = ref('深夜')
function persistTheme(t) {
  try { localStorage.setItem(THEME_KEY, t) } catch (e) { /* 隐私模式忽略 */ }
}
function syncThemeFromDom() {
  const t = document.documentElement.getAttribute('data-theme') || 'dark'
  themeLabel.value = t === 'dark' ? '深夜' : '白天'
}
function toggleTheme() {
  const cur = document.documentElement.getAttribute('data-theme') || 'dark'
  const next = cur === 'dark' ? 'light' : 'dark'
  document.documentElement.setAttribute('data-theme', next)
  persistTheme(next)
  themeLabel.value = next === 'dark' ? '深夜' : '白天'
}

// ── 实时时钟 ─────────────────────
const clockTime = ref('')
const clockDate = ref('')
let timer = null
function upClock() {
  const n = new Date()
  const p = (x) => String(x).padStart(2, '0')
  clockTime.value = p(n.getHours()) + ':' + p(n.getMinutes())
  clockDate.value = n.getFullYear() + '/' + p(n.getMonth() + 1) + '/' + p(n.getDate())
}

onMounted(() => {
  syncThemeFromDom()
  upClock()
  timer = setInterval(upClock, 10000)
})
onBeforeUnmount(() => { if (timer) clearInterval(timer) })
</script>

<style lang="scss" scoped>
/* ══ HEADER（对齐 Q.html）══ */
.app-header {
  grid-area: H;
  position: relative;
  display: flex;
  align-items: stretch;
  overflow: visible;
  background: var(--bg-hd);
  border-bottom: 1px solid rgba(0, 120, 240, .24);
}

.hbrand {
  position: relative;
  z-index: 2;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 0 .9vw;
  flex-shrink: 0;
  min-width: 118px;
  gap: 4px;
}
.hbrand::after {
  content: '';
  position: absolute;
  right: 0;
  top: 12%;
  bottom: 12%;
  width: 1px;
  background: linear-gradient(to bottom, transparent, rgba(0, 160, 255, .38) 50%, transparent);
}
.hgem { width: 7px; height: 7px; background: #00d8ff; transform: rotate(45deg); margin-bottom: 3px; box-shadow: 0 0 12px rgba(0, 216, 255, .75); }
.hbrand .eng { font-size: clamp(9px, .65vw, 12px); font-weight: 300; color: var(--t3); letter-spacing: 3px; text-transform: uppercase; }
.hbrand .chn { font-size: clamp(18px, 1.7vw, 30px); font-weight: 700; color: var(--t1); letter-spacing: 2px; line-height: 1.05; }
.hbrand .chn em { color: var(--ok); font-style: normal; text-shadow: 0 0 16px rgba(0, 240, 176, .50); }
.hbline { width: 36px; height: 1px; background: linear-gradient(90deg, transparent, rgba(0, 220, 200, .45), transparent); margin-top: 4px; }

/* 四卡 */
.hgroups {
  position: relative;
  z-index: 2;
  display: flex;
  align-items: stretch;
  flex: 1;
  min-width: 0;
  padding: .4vh .4vw;
  gap: .35vw;
}
.hcard {
  flex: 1;
  min-width: 0;
  container-type: inline-size;
  background: var(--bg-card);
  border: 1.5px solid var(--bc);
  border-radius: 14px;
  box-shadow: var(--bc-g);
  padding: .35vh .5vw;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 4px;
  position: relative;
  overflow: hidden;
  transition: border-color .25s, box-shadow .25s;
}
.hcard:hover { border-color: rgba(60, 160, 255, .55); box-shadow: 0 0 0 1.5px rgba(40, 140, 255, .22), 0 5px 28px rgba(0, 120, 255, .25); }
.hcard::after { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2.5px; border-radius: 14px 14px 0 0; }
.hcard.idx::after { background: linear-gradient(90deg, transparent, rgba(100, 200, 255, .80) 40%, transparent); }
.hcard.auto::after { background: linear-gradient(90deg, transparent, rgba(0, 240, 176, .80) 40%, transparent); }
.hcard.hr::after { background: linear-gradient(90deg, transparent, rgba(255, 100, 100, .80) 40%, transparent); }
.hcard.att::after { background: linear-gradient(90deg, transparent, rgba(255, 208, 64, .80) 40%, transparent); }
.hcard-title { font-size: clamp(11px, 26cqw, 16px); font-weight: 800; letter-spacing: .3px; margin-bottom: 2px; line-height: 1; white-space: nowrap; }
.hcard-title.idx { color: #60d8ff; }
.hcard-title.auto { color: var(--ok); }
.hcard-title.hr { color: #ff9090; }
.hcard-title.att { color: var(--wn); }
[data-theme="light"] .hcard-title { text-shadow: none; }

.hcard-mets { display: flex; align-items: center; gap: 2px; }
.hcard-met { display: flex; flex-direction: column; align-items: center; flex: 1; min-width: 0; padding: 3px 3px; border-radius: 8px; background: rgba(0, 0, 0, .16); position: relative; }
[data-theme="light"] .hcard-met { background: rgba(0, 0, 0, .05); }
.hcard-mval { font-size: clamp(12px, 6cqw, 17px); font-weight: 700; line-height: 1.1; letter-spacing: -.3px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; }
.hcard-mval.ok { color: var(--ok); text-shadow: var(--ok-s); }
.hcard-mval.bad { color: var(--bd); text-shadow: var(--bd-s); }
.hcard-mval.warn { color: var(--wn); text-shadow: var(--wn-s); }
.hcard-mval.neu { color: #60d8ff; }
.hcard-mlbl { font-size: clamp(7.5px, .43vw, 9.5px); color: var(--t2); white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 100%; margin-top: 1px; font-weight: 500; }
.hcard-sep { width: 1px; height: 24px; background: rgba(30, 120, 200, .22); flex-shrink: 0; margin: 0 4px; }

/* theme switch */
.theme-sw { position: relative; z-index: 2; display: flex; align-items: center; padding: 0 .5vw; flex-shrink: 0; }
.ts-wrap { display: flex; align-items: center; gap: 7px; background: var(--bg-card); border: 1.5px solid var(--bc); border-radius: 20px; padding: 5px 10px; cursor: pointer; user-select: none; transition: all .3s; }
.ts-wrap:hover { border-color: rgba(60, 160, 255, .52); }
.ts-icon { font-size: 13px; line-height: 1; }
.ts-icon.moon { display: var(--tm-show); }
.ts-icon.sun { display: var(--ts-show); }
.ts-track { width: 32px; height: 17px; border-radius: 9px; background: rgba(0, 120, 200, .32); border: 1px solid rgba(0, 140, 220, .26); position: relative; transition: background .3s; }
[data-theme="light"] .ts-track { background: rgba(0, 140, 240, .30); }
.ts-thumb { position: absolute; top: 2px; left: 2px; width: 13px; height: 13px; border-radius: 50%; background: #00d8ff; transition: transform .3s; box-shadow: 0 1px 4px rgba(0, 0, 0, .4); }
[data-theme="light"] .ts-thumb { transform: translateX(13px); background: #ffd040; }
.ts-lbl { font-size: clamp(9px, .6vw, 10px); color: var(--t2); }

.hright { position: relative; z-index: 2; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 0 .6vw; gap: 7px; flex-shrink: 0; min-width: 92px; }
.hright::before { content: ''; position: absolute; left: 0; top: 12%; bottom: 12%; width: 1px; background: linear-gradient(to bottom, transparent, rgba(0, 160, 255, .34) 50%, transparent); }
.ldot { width: 7px; height: 7px; border-radius: 50%; background: var(--ok); animation: pulse 1.6s infinite; }
.lbadge { display: flex; align-items: center; gap: 5px; background: rgba(0, 240, 176, .08); border: 1px solid rgba(0, 240, 176, .26); border-radius: 20px; padding: 3px 8px; font-size: clamp(8px, .5vw, 9px); color: var(--ok); white-space: nowrap; font-weight: 600; }
@keyframes pulse { 0%, 100% { opacity: 1; box-shadow: 0 0 8px rgba(0, 240, 176, .60); } 50% { opacity: .3; box-shadow: none; } }
.htime { text-align: center; }
.htime .t { font-size: clamp(16px, 1.35vw, 22px); font-weight: 300; color: var(--t1); letter-spacing: 3px; }
.htime .dd { font-size: clamp(7px, .46vw, 9px); color: var(--t2); margin-top: 2px; }

/* ══ 白天主题补齐（2026-09-23）══════════════════════════════════════════
   本组件多处把「亮色」写死（青 #60d8ff / 粉 #ff9090 / 宝石 #00d8ff），
   这类低对比亮色在深底上发光好看，压到浅底卡片上直接「看不清」。
   此处按主题改回同色系深色，并去掉发光 text-shadow。 */
[data-theme="light"] {
  .hcard-title { text-shadow: none; }
  .hcard-title.idx { color: #0a6fd0; }
  .hcard-title.hr { color: #c0392b; }
  .hcard-mval { text-shadow: none; }
  .hcard-mval.neu { color: #0a6fd0; }
  .hgem { background: #1f8fd8; box-shadow: 0 0 10px rgba(31, 143, 216, .45); }
  .hbrand .chn em { text-shadow: none; }
  .hbrand::after { background: linear-gradient(to bottom, transparent, rgba(60, 140, 220, .38) 50%, transparent); }
  .hbline { background: linear-gradient(90deg, transparent, rgba(20, 150, 190, .45), transparent); }
  .hcard:hover { border-color: rgba(60, 140, 220, .55);
    box-shadow: 0 0 0 1.5px rgba(60, 140, 220, .18), 0 5px 24px rgba(60, 140, 220, .16); }
  .hcard-sep { background: rgba(90, 145, 205, .26); }
  .lbadge { background: rgba(10, 140, 110, .10); border-color: rgba(10, 140, 110, .32); }
  .hright::before { background: linear-gradient(to bottom, transparent, rgba(60, 140, 220, .32) 50%, transparent); }
}
</style>
