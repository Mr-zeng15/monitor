<template>
  <div class="settings-view">
    <!-- 页面标题栏 -->
    <div class="pbar">
      <div class="pbar-left">
        <div class="ptag">SETTINGS</div>
        <div class="ptitle">系统设置 · <span>阈值、规则与参数</span></div>
      </div>
      <div class="pright">
        <div class="bsm act">全部</div>
        <div class="bsm">系统</div>
        <div class="bsm">通知</div>
        <div class="bsm">数据源</div>
      </div>
    </div>

    <!-- 设置卡片网格 -->
    <div class="settings-grid">
      <!-- 预警阈值 -->
      <div class="setting-card">
        <div class="card-header">
          <div class="card-icon">⚠️</div>
          <div class="card-title">预警阈值</div>
        </div>
        <div class="card-body">
          <div class="setting-row">
            <span class="row-l">默认阈值</span>
            <span class="row-v">1000</span>
          </div>
          <div class="setting-row">
            <span class="row-l">预警刷新频率</span>
            <span class="row-v">5 秒</span>
          </div>
          <div class="setting-row">
            <span class="row-l">产量增长模拟</span>
            <span class="row-v">10 ~ 50 / 次</span>
          </div>
          <div class="setting-row">
            <span class="row-l">预警停止阈值</span>
            <span class="row-v">计划 × 120%</span>
          </div>
        </div>
      </div>

      <!-- 通知设置 -->
      <div class="setting-card">
        <div class="card-header">
          <div class="card-icon">🔔</div>
          <div class="card-title">通知设置</div>
        </div>
        <div class="card-body">
          <div class="setting-row">
            <span class="row-l">站内通知</span>
            <label class="tech-switch on">
              <input type="checkbox" checked />
              <span class="switch-slider"></span>
            </label>
          </div>
          <div class="setting-row">
            <span class="row-l">邮件通知</span>
            <label class="tech-switch">
              <input type="checkbox" />
              <span class="switch-slider"></span>
            </label>
          </div>
          <div class="setting-row">
            <span class="row-l">企业微信</span>
            <label class="tech-switch">
              <input type="checkbox" />
              <span class="switch-slider"></span>
            </label>
          </div>
          <div class="setting-row">
            <span class="row-l">短信告警</span>
            <label class="tech-switch">
              <input type="checkbox" />
              <span class="switch-slider"></span>
            </label>
          </div>
        </div>
      </div>

      <!-- 数据源 -->
      <div class="setting-card">
        <div class="card-header">
          <div class="card-icon">💾</div>
          <div class="card-title">数据源</div>
        </div>
        <div class="card-body">
          <div class="setting-row">
            <span class="row-l">数据库类型</span>
            <span class="row-v">SQLite</span>
          </div>
          <div class="setting-row">
            <span class="row-l">数据库路径</span>
            <span class="row-v">db.sqlite3</span>
          </div>
          <div class="setting-row">
            <span class="row-l">连接状态</span>
            <span class="row-v status-ok">● 已连接</span>
          </div>
          <div class="setting-row">
            <span class="row-l">记录总数</span>
            <span class="row-v">9 条</span>
          </div>
        </div>
      </div>

      <!-- 主题外观 -->
      <div class="setting-card">
        <div class="card-header">
          <div class="card-icon">🎨</div>
          <div class="card-title">主题外观</div>
        </div>
        <div class="card-body">
          <div class="setting-row">
            <span class="row-l">主题模式</span>
            <span class="row-v">深色科技风</span>
          </div>
          <div class="setting-row">
            <span class="row-l">主色调</span>
            <span class="row-v color-dot">
              <span class="dot" style="background: #00d4aa"></span>
              青色 #00d4aa
            </span>
          </div>
          <div class="setting-row">
            <span class="row-l">告警色</span>
            <span class="row-v color-dot">
              <span class="dot" style="background: #e85858"></span>
              红色 #e85858
            </span>
          </div>
          <div class="setting-row">
            <span class="row-l">字号</span>
            <span class="row-v">11px / 默认</span>
          </div>
        </div>
      </div>

      <!-- 系统信息 -->
      <div class="setting-card">
        <div class="card-header">
          <div class="card-icon">ℹ️</div>
          <div class="card-title">系统信息</div>
        </div>
        <div class="card-body">
          <div class="setting-row">
            <span class="row-l">系统版本</span>
            <span class="row-v">v1.0.0</span>
          </div>
          <div class="setting-row">
            <span class="row-l">前端框架</span>
            <span class="row-v">Vue 3 + Vite</span>
          </div>
          <div class="setting-row">
            <span class="row-l">后端框架</span>
            <span class="row-v">Django 4.2 + DRF</span>
          </div>
          <div class="setting-row">
            <span class="row-l">部署时间</span>
            <span class="row-v">2026-07-30</span>
          </div>
        </div>
      </div>

      <!-- 操作日志 -->
      <div class="setting-card">
        <div class="card-header">
          <div class="card-icon">📋</div>
          <div class="card-title">最近操作</div>
        </div>
        <div class="card-body">
          <div class="log-list">
            <div class="log-item">
              <span class="log-time">11:25:17</span>
              <span class="log-msg">Excel 导入成功 · 5 条记录</span>
            </div>
            <div class="log-item">
              <span class="log-time">11:24:03</span>
              <span class="log-msg">新增预警规则：客户A专属规则</span>
            </div>
            <div class="log-item">
              <span class="log-time">11:20:45</span>
              <span class="log-msg">产量数据重置 → 50%</span>
            </div>
            <div class="log-item">
              <span class="log-time">11:18:22</span>
              <span class="log-msg">实时监控启动 · 5秒自动刷新</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
</script>

<style lang="scss" scoped>
/* ============================================
   SettingsView - a.txt 科技风
   ============================================ */

.settings-view {
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

/* ── 设置网格 ────────────────── */
.settings-grid {
  flex: 1;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  grid-auto-rows: 1fr;
  gap: 8px;
  min-height: 0;
  overflow-y: auto;
  align-content: start;
}

.setting-card {
  background: linear-gradient(135deg, #050f1e, #071a2e);
  border: 1px solid #0d2a48;
  border-radius: 10px;
  padding: 10px 12px;
  position: relative;
  overflow: hidden;
  transition: all 0.2s;

  &:hover { border-color: #1a6090; }

  &::before {
    content: '';
    position: absolute;
    left: 0;
    top: 8%;
    bottom: 8%;
    width: 2px;
    background: linear-gradient(to bottom, rgba(0, 212, 170, 0.6), rgba(0, 80, 160, 0.2));
  }

  &::after {
    content: '';
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    height: 2px;
    background: linear-gradient(90deg, transparent, #0088ff 30%, rgba(0, 200, 255, 0.6) 60%, transparent);
  }
}

.card-header {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 10px;
  padding-bottom: 8px;
  border-bottom: 1px solid rgba(0, 80, 160, 0.15);
}

.card-icon {
  font-size: 18px;
  width: 32px;
  height: 32px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(0, 50, 110, 0.3);
  border: 1px solid #0d3050;
  border-radius: 6px;
}

.card-title {
  font-size: 12px;
  font-weight: 600;
  color: #c8e0f8;
  letter-spacing: 0.5px;
}

.card-body {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.setting-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  font-size: 10.5px;
  padding: 4px 0;
}

.row-l {
  color: #6aa3c8;
}

.row-v {
  color: #c8ddf5;
  font-weight: 500;
  display: flex;
  align-items: center;
  gap: 5px;
}

.status-ok { color: #00d4aa; }

.color-dot {
  .dot {
    width: 10px;
    height: 10px;
    border-radius: 50%;
    display: inline-block;
  }
}

/* ── Switch 开关 ────────────── */
.tech-switch {
  position: relative;
  width: 32px;
  height: 16px;
  display: inline-block;

  input { display: none; }

  .switch-slider {
    position: absolute;
    inset: 0;
    background: #1a4060;
    border-radius: 16px;
    transition: all 0.2s;
    cursor: pointer;

    &::before {
      content: '';
      position: absolute;
      top: 2px;
      left: 2px;
      width: 12px;
      height: 12px;
      background: #4d7d9e;
      border-radius: 50%;
      transition: all 0.2s;
    }
  }

  &.on .switch-slider {
    background: linear-gradient(90deg, #0055aa, #00d4aa);

    &::before {
      transform: translateX(16px);
      background: #fff;
      box-shadow: 0 0 6px rgba(0, 212, 170, 0.6);
    }
  }
}

/* ── 日志列表 ────────────────── */
.log-list {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.log-item {
  display: flex;
  gap: 8px;
  font-size: 10px;
  padding: 3px 0;
  border-bottom: 1px dashed rgba(0, 80, 160, 0.1);

  &:last-child { border-bottom: none; }
}

.log-time {
  color: #4d7d9e;
  font-family: 'Consolas', monospace;
  flex-shrink: 0;
}

.log-msg {
  color: #c8ddf5;
}

.settings-grid::-webkit-scrollbar { width: 4px; }
.settings-grid::-webkit-scrollbar-track { background: transparent; }
.settings-grid::-webkit-scrollbar-thumb { background: rgba(0, 100, 200, 0.3); border-radius: 2px; }

/* ══════════════════════════════════════════════════════════════════════
   ★ 白天主题覆盖（2026-09-18）
   根因：本页原样式整写死深色（卡片底 linear-gradient(#050f1e,#071a2e)、
   文字 #c8e0f8 / #c8ddf5、边框 #0d2a48、开关底 #1a4060），无 [data-theme="light"]
   覆盖，切白天后浅字压浅底 → 读不清。统一改「浅底 + 深字」，语义色加深。
   scoped：用 .settings-view 承接 data-v；本页无 Element Plus 组件。
   ══════════════════════════════════════════════════════════════════════ */
[data-theme="light"] .settings-view {
  color: #1a4070;

  .ptag { background: #dbe7f6; border-color: #bcd4ec; color: #2a5a86; }
  .ptitle { color: #0a2858; span { color: #0a8f6e; } }
  .bsm { border-color: #c0d2e4; background: var(--surface-2); color: #4a6a8a;
    &:hover { background: #cddcec; color: #24507a; }
    &.act { background: #c9ddf3; border-color: #7fb2e0; color: #14508c; } }

  .setting-card { background: linear-gradient(135deg,var(--surface-1),var(--surface-2)); border-color: var(--line-1);
    &:hover { border-color: #7fb2e0; } }
  .card-header { border-bottom-color: #e2ebf5; }
  .card-icon { background: var(--surface-2); border-color: var(--line-2); }
  .card-title { color: #0a2858; }

  .row-l { color: #5a7a9a; }
  .row-v { color: #0a2858; }
  .status-ok { color: #0a8f6e; }

  .tech-switch {
    .switch-slider { background: #c9daea;
      &::before { background: #ffffff; box-shadow: 0 1px 2px rgba(20,60,110,.25); } }
    &.on .switch-slider { background: linear-gradient(90deg,#0a6fd0,#0a8f6e); }
  }

  .log-item { border-bottom-color: #e2ebf5; }
  .log-time { color: #5a7a9a; }
  .log-msg { color: #0a2858; }

  .settings-grid::-webkit-scrollbar-thumb { background: #a8c4dd; }
}
</style>
