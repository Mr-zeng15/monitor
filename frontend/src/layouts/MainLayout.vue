<template>
  <div class="app-root">
    <!-- 顶部 Header（grid-area H） -->
    <AppHeader />

    <!-- 告警跑马灯（grid-area A，沿用 Q.html .astrip 风格） -->
    <div class="alert-strip">
      <div class="albl">
        <span class="albl-dot"></span>⚠ 告警
      </div>
      <div class="ascroll-wrap">
        <span class="ascroll">{{ marqueeText }}</span>
      </div>
    </div>

    <!-- 左侧导航（grid-area N） -->
    <AppSidebar />

    <!-- 主内容（grid-area M） -->
    <main class="main-area">
      <router-view v-slot="{ Component }">
        <keep-alive :include="['PreplanView', 'EntryTableView', 'WarningView', 'DecisionReviewView', 'HistoryView', 'ByFabView', 'RobotAutomationView', 'QcAiTeamView']">
          <component :is="Component" />
        </keep-alive>
      </router-view>
    </main>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import AppHeader from '../components/common/AppHeader.vue'
import AppSidebar from '../components/common/AppSidebar.vue'

const alerts = ref([
  '🔴【执行率未达标】2B 94.8%、2C 91.3% 低于目标 95%',
  '🔴【DPPM超标】2B=142、2D=158 超出目标 120',
  '🟡【ABL偏多】2B 本月 5件超目标 3件',
  '🟡【再发率超标】2B=5.8%、2C=3.5% 超目标 3%',
  '🟢【整体Cpk】1.45，制程稳定',
  '🔴【预警】S13 计划中 3 项触发 ORT 预警，待回填 Type'
])

// 跑马灯文本：重复一份以实现无缝滚动
const marqueeText = ref([...alerts.value, ...alerts.value].join('        '))

// ★ 性能优化：进入主布局后空闲时预加载重量级页面代码(chunk)，避免首次点击菜单跳转卡顿
onMounted(() => {
  const preload = () => {
    import('../views/PreplanView.vue')
    import('../views/DecisionReviewView.vue')
    import('../views/WarningView.vue')
    import('../views/EntryTableView.vue')
    import('../views/HistoryView.vue')
    import('../views/ByFabView.vue')
    import('../views/RobotAutomationView.vue')
  }
  if (typeof requestIdleCallback === 'function') {
    requestIdleCallback(preload, { timeout: 2000 })
  } else {
    setTimeout(preload, 800)
  }
})
</script>

<style lang="scss" scoped>
/* ============================================
   MainLayout - 对齐 Q.html 网格：11vh / 4vh / 1fr
   grid-template-areas: "H H" / "A A" / "N M"
   ============================================ */

.app-root {
  width: 100%;
  height: 100vh;
  height: 100dvh;
  min-height: 0;
  overflow: hidden;
  font-family: "Microsoft JhengHei", "PingFang SC", sans-serif;
  background: var(--bg-root);
  color: var(--t2);
  display: grid;
  grid-template-rows: 11vh 4vh minmax(0, 1fr);
  grid-template-columns: var(--nav-w) minmax(0, 1fr);
  grid-template-areas:
    "H H"
    "A A"
    "N M";
  transition: grid-template-columns .28s ease;
}

/* ── 告警跑马灯（Q.html .astrip）─────────────── */
.alert-strip {
  grid-area: A;
  display: flex;
  align-items: center;
  overflow: hidden;
  background: var(--astrip);
  border-top: 1px solid rgba(0, 120, 240, .20);
  border-bottom: 1px solid rgba(0, 120, 240, .20);
}

.albl {
  display: flex;
  align-items: center;
  gap: 8px;
  background: linear-gradient(90deg, #8a1010, #aa2020);
  color: #ffd0d0;
  font-size: clamp(11px, .85vw, 14px);
  font-weight: 700;
  padding: 0 1.2vw;
  height: 100%;
  flex-shrink: 0;
  letter-spacing: 1.5px;
}

.albl-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  background: #ff9090;
  animation: adot 1.2s ease-in-out infinite;
}

@keyframes adot {
  0%, 100% { opacity: 1; transform: scale(1); }
  50% { opacity: .3; transform: scale(.6); }
}

.ascroll-wrap {
  flex: 1;
  overflow: hidden;
}

.ascroll {
  display: inline-block;
  white-space: nowrap;
  font-size: clamp(11px, .85vw, 14px);
  color: #e0d070;
  padding-left: 24px;
  letter-spacing: .3px;
  animation: sl 40s linear infinite;
}

[data-theme="light"] .ascroll { color: #9a7010; }

@keyframes sl {
  0% { transform: translateX(0); }
  100% { transform: translateX(-50%); }
}

/* ── 主体区域 ───────────────────────── */
.main-area {
  grid-area: M;
  display: flex;
  flex-direction: column;
  padding: .7vh .9vw;
  gap: .5vh;
  overflow: hidden;
  background: var(--bg-main);
  min-width: 0;
  min-height: 0;
  transition: background .35s;
}
</style>
