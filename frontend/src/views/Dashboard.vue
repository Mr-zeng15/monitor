<template>
  <div class="dashboard">
    <!-- 页面标题栏 -->
    <div class="pbar">
      <div class="pbar-left">
        <div class="ptag">QC</div>
        <div class="ptitle">QC 风控卫士 · <span>产量预警自动化</span></div>
      </div>
      <div class="pright">
        <div class="bsm act">全部</div>
        <div class="bsm">运行中</div>
        <div class="bsm">告警</div>
      </div>
    </div>

    <!-- 4×4 卡片网格 -->
    <div class="auto-grid">
      <div
        v-for="(item, index) in procs"
        :key="index"
        class="ac"
        @click="openRun(index)"
      >
        <div class="ac-num">#{{ String(index + 1).padStart(2, '0') }}</div>
        <div class="ac-info">
          <div class="ac-name">{{ item.name }}</div>
          <div class="ac-sub">{{ item.sub }}</div>
          <div class="ac-meta">
            <div class="ac-status" :class="item.run ? 'on' : 'off'">
              <div class="ac-status-dot"></div>
              {{ item.run ? '运行中' : '待机中' }}
            </div>
            <div class="ac-chip">{{ item.count }}次</div>
            <div class="ac-chip">{{ item.rate }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 弹窗 -->
    <div class="runov" :class="{ show: runovShow }" @click.self="closeRun">
      <div class="runbox">
        <div class="runbox-close" @click="closeRun">✕</div>
        <div class="run-title">{{ runData.name }}</div>
        <div class="run-subtitle">{{ runData.sub }}</div>
        <div class="run-status-row">
          <div class="run-stat">
            <div class="sl">执行次数</div>
            <div class="sv g">{{ runData.count }}</div>
          </div>
          <div class="run-stat">
            <div class="sl">成功率</div>
            <div class="sv g">{{ runData.rate }}</div>
          </div>
          <div class="run-stat">
            <div class="sl">平均耗时</div>
            <div class="sv y">{{ runData.time }}</div>
          </div>
          <div class="run-stat">
            <div class="sl">上次执行</div>
            <div class="sv">{{ runData.last }}</div>
          </div>
        </div>
        <div class="run-progress">
          <div class="run-progress-lbl">
            <span>当前进度</span>
            <span>{{ runData.run ? runData.pct + '%' : '待启动' }}</span>
          </div>
          <div class="run-bar">
            <div
              class="run-bar-fill"
              :style="{ width: runData.run ? runData.pct + '%' : '0%' }"
            ></div>
          </div>
        </div>
        <div class="run-logs">
          <div
            v-for="(log, i) in runData.logs"
            :key="i"
            :class="getLogClass(log)"
          >
            {{ log }}
          </div>
        </div>
        <div class="run-btns">
          <button class="run-btn primary" @click="closeRun">立即执行</button>
          <button class="run-btn sec" @click="closeRun">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'

const router = useRouter()
const runovShow = ref(false)
const runData = ref({})

// 16 个自动化流程卡片
const procs = ref([
  {
    name: 'SPC\n数据撷取',
    sub: '2A/2B/2C/2D · 每 5 分钟',
    run: true, count: '14,832', rate: '99.4%', time: '3.2s', last: '2分钟前', pct: 72,
    logs: [
      '✅ 08:12 2A SPC 数据撷取成功（批号 A0419-01）',
      '✅ 08:17 2B SPC 数据撷取成功',
      '⚠️ 08:22 2C 数据延迟 1.2s，已补偿',
      '✅ 08:27 2D SPC 数据撷取成功'
    ]
  },
  {
    name: '再发异常\n自动通报',
    sub: 'Yield 異常 → 即时 Email/Line',
    run: true, count: '1,204', rate: '100%', time: '1.1s', last: '1小时前', pct: 88,
    logs: [
      '✅ 07:44 2B 再发率超标 → 已通报 PM+QE',
      '✅ 06:30 2B DPPM 超标通报完成'
    ]
  },
  {
    name: 'Cpk 计算\n排程',
    sub: '每班结束自动计算',
    run: true, count: '8,456', rate: '98.7%', time: '8.4s', last: '3小时前', pct: 55,
    logs: [
      '✅ 05:00 Day Shift Cpk 批量计算完成',
      '⚠️ 2B Cpk=1.29 低于目标，已标记'
    ]
  },
  {
    name: '预警规则\n实时匹配',
    sub: '每 5 秒自动检测',
    run: true, count: '5,612', rate: '100%', time: '0.4s', last: '刚才', pct: 95,
    route: '/warning',
    logs: [
      '✅ 当前已启用 3 条预警规则',
      '✅ 实时监控 5 个产品产量',
      '⚠️ 检测到 2 个产品触发预警'
    ]
  },
  {
    name: 'MES 工单\n同步',
    sub: '每 10 分钟拉单',
    run: true, count: '22,401', rate: '99.8%', time: '1.8s', last: '8分钟前', pct: 61,
    logs: [
      '✅ 08:20 工单同步完成（批次 B-0419）',
      '✅ 08:10 工单同步完成'
    ]
  },
  {
    name: 'OQC 报告\n自动生成',
    sub: '每日 18:00',
    run: false, count: '428', rate: '97.9%', time: '2m18s', last: '昨天 18:02', pct: 0,
    logs: [
      '✅ 昨天 OQC 日报生成完成 → 已发送至品管主管'
    ]
  },
  {
    name: '设备稼动\n监控',
    sub: '每 1 分钟心跳',
    run: true, count: '61,023', rate: '99.9%', time: '0.4s', last: '刚才', pct: 95,
    logs: [
      '✅ 08:28 设备稼动率 94.3%，正常',
      '✅ 08:27 设备稼动率 94.1%，正常'
    ]
  },
  {
    name: '产量数据\n自动抓取',
    sub: '每 5 秒抓取后台DB',
    run: true, count: '88,401', rate: '99.99%', time: '0.1s', last: '刚才', pct: 99,
    route: '/warning',
    logs: [
      '✅ 全部产品心跳正常',
      '✅ 抓取速度：0.1s',
      '✅ 累计抓取 88,401 次'
    ]
  },
  {
    name: 'SPC 管制\n预警',
    sub: '超出 ±2σ 即时告警',
    run: true, count: '5,612', rate: '100%', time: '0.9s', last: '22分钟前', pct: 78,
    logs: [
      '⚠️ 08:06 2B 制程均值偏移 +1.8σ，已推送',
      '✅ 07:55 2A/2C/2D 管制内，正常'
    ]
  },
  {
    name: '客诉根因\n AI 分析',
    sub: '新客诉单触发 Agent',
    run: false, count: '89', rate: '94.4%', time: '1m42s', last: '3天前', pct: 0,
    logs: [
      '✅ 04/16 客诉 CMP-0416 根因报告完成（置信度 87%）'
    ]
  },
  {
    name: '首件确认\n通知',
    sub: 'Line Leader 签核提醒',
    run: true, count: '9,201', rate: '99.7%', time: '2.1s', last: '15分钟前', pct: 50,
    logs: [
      '✅ 08:13 2A Line 首件确认通知已送出',
      '✅ 08:01 2C Line 首件确认完成'
    ]
  },
  {
    name: '预警规则\n配置管理',
    sub: '多维度组合筛选',
    run: true, count: '1,247', rate: '100%', time: '0.3s', last: '1小时前', pct: 70,
    route: '/warning-rules',
    logs: [
      '✅ 已配置 4 条多维预警规则',
      '✅ 支持客户/Fab/BU/Model筛选',
      '✅ 多规则组合匹配'
    ]
  },
  {
    name: '不良品\n隔离通报',
    sub: 'QC 判退后自动锁单',
    run: true, count: '2,187', rate: '99.5%', time: '1.4s', last: '2小时前', pct: 33,
    logs: [
      '✅ 06:18 批号 A0418-07 判退，已隔离锁单',
      '✅ 05:50 批号 A0418-05 判退处理完成'
    ]
  },
  {
    name: '良率周报\n自动发送',
    sub: '每周五 17:30',
    run: false, count: '52', rate: '98.1%', time: '3m05s', last: '04/11', pct: 0,
    logs: [
      '✅ 04/11 良率周报已发送至总监 + 课长（共 8 人）'
    ]
  },
  {
    name: 'RPA 健康\n自监控',
    sub: '每 30 秒自检',
    run: true, count: '88,401', rate: '99.99%', time: '0.1s', last: '刚才', pct: 99,
    logs: [
      '✅ 全部 15 支机器人心跳正常',
      '✅ 系统资源：CPU 12% / RAM 34%'
    ]
  }
])

const openRun = (i) => {
  const item = procs.value[i]
  // 如果有路由跳转，跳转过去
  if (item.route) {
    router.push(item.route)
    return
  }
  runData.value = item
  runovShow.value = true
}

const closeRun = () => {
  runovShow.value = false
}

const getLogClass = (log) => {
  if (log.includes('✅')) return 'run-log-g'
  if (log.includes('⚠️')) return 'run-log-y'
  if (log.includes('❌')) return 'run-log-r'
  return ''
}
</script>

<style lang="scss" scoped>
/* ============================================
   Dashboard - 还原 a.txt 4×4 卡片网格
   ============================================ */

.dashboard {
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

.pbar-left {
  display: flex;
  align-items: center;
  gap: 6px;
}

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

  span {
    color: #00d4aa;
  }
}

.pright {
  display: flex;
  align-items: center;
  gap: 8px;
}

.bsm {
  font-size: 10.5px;
  font-weight: 400;
  padding: 5px 13px;
  border-radius: 13px;
  cursor: pointer;
  border: 1px solid #0d3050;
  background: rgba(0, 40, 90, 0.2);
  color: #3a6070;
  transition: all 0.15s;

  &:hover {
    background: rgba(0, 60, 130, 0.28);
    color: #7098b8;
  }

  &.act {
    background: rgba(0, 70, 160, 0.28);
    border-color: #0050a0;
    color: #90c0e8;
  }
}

/* ── 4×N 卡片网格（响应式）───────── */
.auto-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  grid-auto-rows: minmax(110px, 1fr);
  gap: 8px;
  min-height: 0;
}

@media (min-width: 1600px) {
  .auto-grid { grid-template-columns: repeat(4, 1fr); }
}
@media (min-width: 1200px) and (max-width: 1599px) {
  .auto-grid { grid-template-columns: repeat(3, 1fr); }
}
@media (max-width: 1199px) {
  .auto-grid { grid-template-columns: repeat(2, 1fr); }
}

.ac {
  background: linear-gradient(135deg, #050f1e, #071a2e);
  border: 1px solid #0d2a48;
  border-radius: 10px;
  display: flex;
  flex-direction: column;
  cursor: pointer;
  position: relative;
  overflow: hidden;
  transition: border-color 0.22s, transform 0.12s, box-shadow 0.22s;
  padding: 12px;

  &:hover {
    border-color: #1a6090;
    transform: translateY(-2px) scale(1.01);
    box-shadow: 0 8px 30px rgba(0, 100, 200, 0.4);
  }

  &::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    border-radius: 10px 10px 0 0;
    background: linear-gradient(90deg, rgba(0, 140, 255, 0), #0088ff 30%, rgba(0, 200, 255, 0.6) 60%, rgba(0, 140, 255, 0));
  }

  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 8%;
    bottom: 8%;
    width: 2px;
    border-radius: 2px;
    background: linear-gradient(to bottom, rgba(0, 160, 255, 0.6), rgba(0, 80, 160, 0.2));
  }
}

.ac-num {
  position: absolute;
  top: 5px;
  right: 8px;
  font-size: 9px;
  font-weight: 600;
  color: #1a4060;
  background: rgba(0, 80, 160, 0.25);
  border-radius: 3px;
  padding: 1px 5px;
  z-index: 2;
}

.ac-info {
  flex: 1;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 6px;
  min-width: 0;
  padding-left: 6px;
}

.ac-name {
  font-size: 13px;
  font-weight: 600;
  color: #c0d8f0;
  white-space: pre-wrap;
  line-height: 1.3;
}

.ac-sub {
  font-size: 10px;
  font-weight: 300;
  color: #2a5070;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.ac-meta {
  display: flex;
  align-items: center;
  gap: 6px;
  flex-wrap: wrap;
  margin-top: 4px;
}

.ac-status {
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 10px;
  font-weight: 500;

  &.on { color: #00d4aa; }
  &.off { color: #3a6070; }
}

.ac-status-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: currentColor;
  flex-shrink: 0;
}

.ac-status.on .ac-status-dot {
  animation: pulse 1.6s infinite;
}

.ac-chip {
  font-size: 9px;
  font-weight: 300;
  color: #1e4060;
  background: rgba(0, 40, 80, 0.3);
  border-radius: 3px;
  padding: 1px 5px;
}

@keyframes pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.3; }
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

  &.show {
    opacity: 1;
    pointer-events: all;
  }
}

.runbox {
  background: linear-gradient(135deg, #040e1e, #061828);
  border: 1px solid rgba(0, 100, 200, 0.3);
  border-radius: 16px;
  width: 640px;
  padding: 28px 32px;
  position: relative;
  box-shadow: 0 24px 80px rgba(0, 20, 80, 0.8);
}

.runbox-close {
  position: absolute;
  top: 14px;
  right: 18px;
  font-size: 18px;
  color: #2a5070;
  cursor: pointer;
  transition: color 0.15s;

  &:hover { color: #90c0e8; }
}

.run-title {
  font-size: 18px;
  font-weight: 600;
  color: #c8e0f8;
  margin-bottom: 6px;
  letter-spacing: 0.5px;
  white-space: pre-wrap;
}

.run-subtitle {
  font-size: 11px;
  font-weight: 300;
  color: #3a6080;
  margin-bottom: 16px;
}

.run-status-row {
  display: flex;
  justify-content: center;
  gap: 14px;
  margin-bottom: 16px;
}

.run-stat {
  background: rgba(0, 25, 60, 0.45);
  border: 1px solid #0d3050;
  border-radius: 8px;
  padding: 10px 18px;
  text-align: center;

  .sl {
    font-size: 9px;
    font-weight: 300;
    color: #2a5070;
    margin-bottom: 4px;
  }

  .sv {
    font-size: 20px;
    font-weight: 600;

    &.g { color: #00d4aa; }
    &.y { color: #e8b838; }
    &.r { color: #e85858; }
  }
}

.run-progress {
  margin-bottom: 16px;
}

.run-progress-lbl {
  font-size: 9px;
  font-weight: 300;
  color: #2a5070;
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
}

.run-bar {
  height: 6px;
  background: rgba(0, 40, 80, 0.4);
  border-radius: 3px;
  overflow: hidden;
}

.run-bar-fill {
  height: 100%;
  border-radius: 3px;
  background: linear-gradient(90deg, #0055aa, #00d4aa);
  transition: width 1.2s ease-out;
}

.run-logs {
  text-align: left;
  background: rgba(0, 10, 24, 0.5);
  border: 1px solid #0a2030;
  border-radius: 8px;
  padding: 10px 12px;
  max-height: 80px;
  overflow-y: auto;
  font-size: 9px;
  font-weight: 300;
  color: #3a6070;
  line-height: 1.6;
  margin-bottom: 14px;
}

.run-log-g { color: #00a880; }
.run-log-y { color: #b09020; }
.run-log-r { color: #b04040; }

.run-btns {
  display: flex;
  gap: 10px;
  justify-content: center;
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

/* ══════════════════════════════════════════════════════════════════════
   ★ 白天主题覆盖（2026-09-18）
   根因：本页原样式整套写死深色（标题 #c8e0f8 / 卡片底 linear-gradient(#050f1e,#071a2e) /
   卡片副标题 #2a5070 / 弹窗底 #040e1e→#061828 / 日志区 rgba(0,10,24,.5)），
   且无 [data-theme="light"] 覆盖，切白天后浅字压浅底 → 读不清。
   此处统一改为「浅底 + 深字」，语义色加深以保证白底可读。
   scoped：用 .dashboard 承接 data-v。
   ══════════════════════════════════════════════════════════════════════ */
[data-theme="light"] .dashboard {
  color: #1a4070;

  .ptag { background: #dbe7f6; border-color: #bcd4ec; color: #2a5a86; }
  .ptitle { color: #0a2858; span { color: #0a8f6e; } }
  .bsm { border-color: #c0d2e4; background: var(--surface-2); color: #4a6a8a;
    &:hover { background: #cddcec; color: #24507a; }
    &.act { background: #c9ddf3; border-color: #7fb2e0; color: #14508c; } }

  /* 卡片：白底深字，顶部/左侧强调条保留（浅底上仍清晰） */
  .ac { background: var(--surface-1); border-color: var(--line-1);
    &:hover { border-color: #7fb2e0; box-shadow: 0 8px 30px rgba(31,143,216,.18); } }
  .ac-num { color: #4a6a8a; background: #dbe7f6; }
  .ac-name { color: #0a2858; }
  .ac-sub { color: #5a7a9a; }
  .ac-status {
    &.on { color: #0a8f6e; }
    &.off { color: #5a7a9a; } }
  .ac-chip { color: #4a6a8a; background: var(--surface-2); }

  /* 弹窗 */
  .runov { background: rgba(20, 45, 80, .42); }
  .runbox { background: var(--surface-1); border-color: var(--line-1); box-shadow: 0 24px 80px rgba(20,60,110,.18); }
  .runbox-close { color: #9ab0c4; &:hover { color: #14508c; } }
  .run-title { color: #0a2858; }
  .run-subtitle { color: #5a7a9a; }
  .run-stat { background: var(--surface-2); border-color: var(--line-2);
    .sl { color: #5a7a9a; }
    .sv { &.g { color: #0a8f6e; } &.y { color: #b07800; } &.r { color: #d02828; } } }
  .run-progress-lbl { color: #5a7a9a; }
  .run-bar { background: #e6edf4; }
  .run-logs { background: var(--surface-2); border-color: var(--line-2); color: #5a7a9a; }
  .run-log-g { color: #0a8f6e; }
  .run-log-y { color: #b07800; }
  .run-log-r { color: #d02828; }
  .run-btn.sec { background: var(--well); color: #4a6a8a; border-color: #c0d2e4;
    &:hover { background: #cddcec; color: #24507a; } }
}
</style>
