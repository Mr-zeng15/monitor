<template>
  <button class="nav-toggle" :class="{ collapsed: navCollapsed }" @click="toggleNav">❮</button>

  <nav class="app-nav">
    <div class="nav-inner">
      <div class="nlb">
        <div class="nbadge">DQAEB1</div>
        <div class="ntxt">QC 风控 · 生产卫士</div>
      </div>
      <div class="ndiv"></div>

      <!-- 分组（可折叠） -->
      <template v-for="g in groups" :key="g.id">
        <div class="ngrp-hd" :class="{ collapsed: collapsed[g.id] }" @click="toggleGrp(g.id)">
          <span>{{ g.title }}</span><span class="narr">▾</span>
        </div>
        <div class="ngrp-bd" :class="{ collapsed: collapsed[g.id] }">
          <template v-for="(it, i) in g.items" :key="i">
            <!-- 子标签 -->
            <div v-if="it.type === 'label'" class="nslbl">{{ it.text }}</div>
            <!-- 真实业务入口 -->
            <div v-else-if="it.to"
                 class="ni"
                 :class="{ act: isActive(it.to) }"
                 @click="go(it.to)">
              <span class="nks">{{ it.icon }}</span>{{ it.text }}
              <span v-if="it.badge" class="nbdg">{{ it.badge }}</span>
            </div>
            <!-- 待开发（置灰） -->
            <div v-else class="ni dev-pending" :class="{ 'nki-pend': it.ksub }">
              <span class="nks">{{ it.icon }}</span>{{ it.text }}
              <span class="dev-tag">待开发</span>
            </div>
          </template>
        </div>
        <div class="ndiv"></div>
      </template>

      <!-- 底部：系统 -->
      <div class="nbot">
        <div v-for="(b, i) in bottom" :key="i"
             class="nbi"
             :class="{ 'nbi-link': b.to, 'dev-pending': b.dev }"
             @click="b.to && go(b.to)">
          <span class="nks">{{ b.icon }}</span>{{ b.text }}
        </div>
      </div>
    </div>
  </nav>
</template>

<script setup>
import { ref } from 'vue'
import { useRoute, useRouter } from 'vue-router'

const route = useRoute()
const router = useRouter()

// ★ 分组：真实业务入口可点击；示例菜单 dev-pending 置灰
const groups = ref([
  {
    id: 'risk', title: '🛡 风控卫士', open: true, items: [
      { type: 'label', text: 'IPQC 管理' },
      { to: '/by-fab', icon: '📊', text: 'BY FAB 总览' },
      { dev: true, icon: '📈', text: '指标趋势' },
      { dev: true, icon: '🔍', text: 'CAPA 追踪' },
      { dev: true, icon: '📋', text: 'Ongoing Case', badge: '13' },
      { type: 'label', text: '产量预警 · 预排' },
      { to: '/warning', icon: '🔔', text: '实时预警监控' },     // ★ 预警功能入口（Q.html 风格整合）
      { to: '/preplan', icon: '📥', text: '预排筛选导入' },
      { to: '/entry-table', icon: '📖', text: '基础资料表' },
      { to: '/decision-review', icon: '⚖️', text: '审核决议中心' },
      { to: '/history', icon: '🗄️', text: '存档中心' }
    ]
  },
  {
    id: 'hr', title: '👥 人事管理', open: false, items: [
      { dev: true, icon: '🗓', text: '出勤看板' },
      { dev: true, icon: '🧑🔧', text: '技能管理' },
      { dev: true, icon: '⚡', text: '产能规划' }
    ]
  },
  {
    id: 'auto', title: '⚡ 流程自动化', open: false, items: [
      { to: '/robot-automation', icon: '🤖', text: '16项自动化机器人' },
      { to: '/excel-flow', icon: '🧪', text: 'Excel 处理测试' },
      { dev: true, icon: '📧', text: '邮件自动化' },
      { dev: true, icon: '📊', text: '定时报表推送' }
    ]
  },
  {
    id: 'rag', title: '🤖 智能 · RAG', open: true, items: [
      // ★ 2026-09-16：真实业务入口 —— QC_AI_TEAM（AI Agent 专案登记，前后端版）
      { to: '/qc-ai-team', icon: '🧠', text: 'AI Agent 专案登记' },
      { dev: true, icon: '💬', text: '历史真因问答', ksub: true },
      { dev: true, icon: '📋', text: '改善案例检索' },
      { dev: true, icon: '📖', text: 'SOP 知识库' }
    ]
  }
])

const bottom = ref([
  { to: '/settings', icon: '⚙️', text: '系统设置' },
  { to: '/dashboard', icon: '🖥', text: '主控看板' },
  { dev: true, icon: '📤', text: '导出报表' },
  { dev: true, icon: '❓', text: '使用说明' }
])

const collapsed = ref({})
groups.value.forEach(g => { collapsed.value[g.id] = !g.open })

function toggleGrp(id) { collapsed.value[id] = !collapsed.value[id] }
function isActive(to) { return route.path === to }
function go(to) { router.push(to) }

// ★ 导航折叠（对齐 Q.html body.nav-collapsed）
const navCollapsed = ref(false)
function toggleNav() {
  navCollapsed.value = !navCollapsed.value
  document.body.classList.toggle('nav-collapsed', navCollapsed.value)
}
</script>

<style lang="scss" scoped>
/* ══ NAV（对齐 Q.html）══ */
.app-nav {
  grid-area: N;
  width: var(--nav-w);
  min-width: 0;
  background: var(--bg-nav);
  border-right: 1px solid var(--bn);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  transition: width .28s ease;
}

.nav-toggle {
  position: fixed;
  left: calc(var(--nav-w));
  top: 50%;
  transform: translateY(-50%);
  z-index: 100;
  width: 15px;
  height: 38px;
  background: var(--bg-card);
  border: 1px solid rgba(40, 130, 220, .40);
  border-left: none;
  border-radius: 0 7px 7px 0;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: var(--t2);
  transition: left .28s ease, background .2s, color .2s;
  user-select: none;
}
.nav-toggle:hover { background: rgba(0, 100, 200, .35); color: var(--tna); }
.nav-toggle.collapsed { left: 0; }

.nav-inner {
  flex: 1;
  overflow-y: auto;
  overflow-x: hidden;
  padding: 6px 0;
}
.nav-inner::-webkit-scrollbar { width: 2px; }
.nav-inner::-webkit-scrollbar-thumb { background: rgba(30, 120, 200, .32); }

.nlb { padding: 8px 12px; border-bottom: 1px solid rgba(30, 110, 200, .18); flex-shrink: 0; white-space: nowrap; }
.nbadge { display: inline-block; background: rgba(0, 100, 180, .28); border: 1px solid rgba(0, 140, 220, .28); color: var(--ac); font-size: 9px; font-weight: 700; padding: 2px 7px; border-radius: 6px; letter-spacing: 1px; margin-bottom: 4px; }
.ntxt { font-size: clamp(9px, .65vw, 10px); color: var(--t2); font-weight: 500; }

.ngrp-hd {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 5px 12px;
  font-size: 9px;
  font-weight: 700;
  color: var(--t2);
  letter-spacing: 2px;
  text-transform: uppercase;
  cursor: pointer;
  user-select: none;
  white-space: nowrap;
  transition: color .15s;
}
.ngrp-hd:hover { color: var(--tn); }
.narr { font-size: 10px; transition: transform .25s; display: inline-block; flex-shrink: 0; }
.ngrp-hd.collapsed .narr { transform: rotate(-90deg); }
.ngrp-bd { overflow: hidden; transition: max-height .3s ease; max-height: 800px; }
.ngrp-bd.collapsed { max-height: 0; }

.ndiv { height: 1px; background: rgba(30, 110, 200, .16); margin: 4px 10px; }
.nslbl { padding: 3px 12px; font-size: 8px; font-weight: 700; color: var(--t2); letter-spacing: 2px; text-transform: uppercase; white-space: nowrap; }

.ni {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  cursor: pointer;
  font-size: clamp(11px, .74vw, 13px);
  color: var(--tn);
  border-radius: 8px;
  margin: 1px 5px;
  transition: all .15s;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  position: relative;
}
.ni:hover { background: rgba(0, 100, 200, .16); color: var(--tna); }
.ni.act { background: rgba(0, 120, 220, .24); color: var(--tna); }
.ni.act::before { content: ''; position: absolute; left: 0; top: 18%; bottom: 18%; width: 2px; background: var(--ac); border-radius: 0 2px 2px 0; box-shadow: 0 0 8px rgba(0, 216, 255, .50); }
.nks { padding-left: 2px; }

.nbdg { margin-left: auto; background: var(--bdg); color: var(--bd); font-size: 9px; font-weight: 700; padding: 1px 5px; border-radius: 8px; border: 1px solid rgba(255, 96, 96, .36); flex-shrink: 0; }

/* 待开发：置灰、不可点击 */
.ni.dev-pending {
  color: var(--t4);
  opacity: .55;
  pointer-events: none;
  cursor: default;
}
.ni.dev-pending .dev-tag {
  margin-left: auto;
  background: rgba(30, 50, 80, .95);
  color: var(--t3);
  font-size: 8px;
  padding: 1px 5px;
  border-radius: 4px;
  border: 1px solid rgba(30, 120, 200, .32);
  flex-shrink: 0;
}
[data-theme="light"] .ni.dev-pending .dev-tag { background: rgba(210, 230, 250, .95); color: #5a8aaa; border-color: #90c0d8; }

.nbot { border-top: 1px solid rgba(30, 110, 200, .16); padding: 7px 10px; flex-shrink: 0; }
.nbi {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 5px 8px;
  font-size: clamp(10px, .68vw, 11px);
  color: var(--t2);
  cursor: default;
  border-radius: 6px;
  transition: all .15s;
  white-space: nowrap;
}
.nbi.nbi-link { cursor: pointer; }
.nbi.nbi-link:hover { background: rgba(0, 100, 200, .12); color: var(--tn); }
.nbi.dev-pending { color: var(--t4); opacity: .55; }
.nbi.dev-pending .dev-tag { margin-left: auto; }

/* ══ 白天主题补齐（2026-09-23）══════════════════════════════════════════
   侧栏原本只有一条 `[data-theme="light"] .ni.dev-pending .dev-tag` 覆盖，
   其余靠变量。变量已换成更深的文字色，这里再显式钉一版：保证
   ① 真实业务入口（含「🧠 AI Agent 专案登记」/qc-ai-team）文字清晰；
   ② 当前项 active 底 + 左侧亮条在浅底上依然可辨；
   ③ nbadge / 分隔线 / 滚动条不再是深色残留。 */
[data-theme="light"] {
  .app-nav { border-right-color: rgba(90, 150, 220, .28); }
  .nlb { border-bottom-color: rgba(90, 145, 205, .22); }
  .ntxt { color: #2a5a86; }
  .nbadge { background: #dbe7f6; border-color: #bcd4ec; color: #0a6fd0; }
  .ngrp-hd { color: #2a5a86; }
  .ngrp-hd:hover { color: #14508c; }
  .narr { color: #4a6a8a; }
  .nslbl { color: #5a7a9a; }
  .ndiv { background: rgba(90, 145, 205, .22); }

  .ni { color: #245080; }
  .ni:hover { background: rgba(40, 120, 210, .12); color: #0b2a52; }
  .ni.act { background: rgba(40, 120, 210, .18); color: #0b2a52; font-weight: 600; }
  .ni.act::before { background: #1f8fd8; box-shadow: none; }
  .ni.dev-pending { color: #7d99b8; }
  .nks { filter: none; }

  .nav-inner::-webkit-scrollbar-thumb { background: rgba(120, 165, 215, .45); }
  .nav-toggle { border-color: #bcd4ec; color: #2a5a86; }
  .nav-toggle:hover { background: #cddcec; color: #0b2a52; }

  .nbot { border-top-color: rgba(90, 145, 205, .22); }
  .nbi { color: #2a5a86; }
  .nbi.nbi-link:hover { background: rgba(40, 120, 210, .10); color: #14508c; }
  .nbi.dev-pending { color: #7d99b8; }
}
</style>
