<template>
  <div class="byfab" :class="{ 'dim-all': !DATA_ONLINE }">
    <!-- ══ 页面标题栏（Q.html .pbar）══ -->
    <div class="pbar">
      <div style="display:flex;align-items:center;gap:6px">
        <span class="ptag">风控卫士 · V16 BY FAB</span>
        <span class="ptitle">IPQC 全指标 · <span>车间维度展开</span></span>
        <span class="pweek">最后日期：{{ queryLastWeek }}</span>
      </div>
      <div class="pright">
        <div style="display:flex;align-items:center;gap:5px;font-size:10px;color:var(--t2)">
          <span style="width:8px;height:8px;border-radius:50%;background:var(--ok);display:inline-block;box-shadow:0 0 5px rgba(0,240,176,.50)"></span>达标
          <span style="width:8px;height:8px;border-radius:50%;background:var(--wn);display:inline-block;margin-left:5px;box-shadow:0 0 5px rgba(255,208,64,.50)"></span>警告
          <span style="width:8px;height:8px;border-radius:50%;background:var(--bd);display:inline-block;margin-left:5px;box-shadow:0 0 5px rgba(255,96,96,.50)"></span>超标
        </div>
        <button class="bsm act">BY FAB</button>
        <button class="bsm">趋势总览</button>
        <button class="bsm">RAG</button>
      </div>
    </div>

    <!-- ══ 整体 KPI 横排（Q.html .ov-strip）══ -->
    <div class="ov-strip">
      <div class="ov-card e" @mouseenter="showTip($event,'exec')" @mouseleave="hideTip()">
        <div class="ov-info"><div class="ov-name">整体执行率</div><div class="ov-tgt">目标 ≥ 95%</div></div>
        <div class="ov-right"><div class="ov-num bad">2</div><div class="ov-sub">FAB 未达标</div></div>
      </div>
      <!-- ★ DPPM 卡（2026-09-21 实时化）：接入云端后取 2A/2B 本周之和。
           ★ 09-21 用户要求「DPPM 不要设置规格目标」→ 卡面不写「目标」、不判定「超出规格」；
             未接入（无真值）显示 —，不再拿静态示例数字充数（与 ABL 卡同款结构） -->
      <div class="ov-card d" @mouseenter="showTip($event,'dppm')" @mouseleave="hideTip()">
        <div class="ov-info"><div class="ov-name">DPPM</div></div>
        <div class="ov-right">
          <div class="ov-num">{{ dppmHeaderTotal === null ? '—' : fmtNum(dppmHeaderTotal) }}</div>
          <div class="ov-sub">2A/2B 本周合计</div>
        </div>
      </div>
      <div class="ov-card a" @mouseenter="showTip($event,'abl')" @mouseleave="hideTip()">
        <div class="ov-info"><div class="ov-name">ABL 件数</div><div class="ov-tgt">目标</div></div>
        <div class="ov-right"><div class="ov-num">{{ ablHeaderTotal === null ? '—' : fmtNum(ablHeaderTotal) }}</div><div class="ov-sub">2A-2D 累计 · 单位 次</div></div>
      </div>
    </div>

    <!-- ══ 主内容：4宫格 + OC侧栏（Q.html .content-area）══ -->
    <div class="content-area">
      <div class="fab-grid" id="fabgrid">
        <div v-for="fab in byfab.fabList" :key="fab" class="fab-panel" :class="{ 'no-data': !hasFabData(fab) }" :data-fab="fab">
          <div class="fab-hdr">
            <span class="fab-badge" :class="fab.slice(1)">{{ fab }}</span>
            <span class="fab-status" :class="fabStatusCls(fab)">{{ fabStatusText(fab) }}</span>
          </div>
          <div class="fab-kpis">
            <template v-for="(k, i) in byfab.FD[fab].kpis" :key="i">
              <div v-if="k.p" class="kpi-cell dev-pending">
                <div class="kpi-dot gray"></div>
                <div class="dev-tag">待开发</div>
                <div class="kpi-name">{{ k.n }}</div>
                <div class="kpi-val">—</div>
                <div class="kpi-bot"><span class="kpi-tgt">{{ k.tg }}</span><span class="kpi-delta na">—</span></div>
              </div>
              <!-- ★ 真实数据接入判定：主面板机器人数据=全真实；仅 ABL 云端接入时 ABL触发 一项真实，
                   其余指标属静态示例 → 数值用 '—' 灰显（不再"假数据一起亮"） -->
              <div v-else class="kpi-cell" :class="{ 'kpi-fake': !kpiReal(fab, k) }" @click="openPop(fab, i)" :title="kpiReal(fab, k) ? '' : '未接入真实数据（静态示例已隐藏）'">
                <div class="kpi-dot" :class="kpiView(fab, k).dot"></div>
                <div class="kpi-name">{{ k.n }}</div>
                <div class="kpi-val">{{ kpiView(fab, k).v }}</div>
                <!-- ★ ABL触发（用户 09-11）/ DPPM（用户 09-21「不要设置规格目标」）不显示左下角规格目标小字 -->
                <div class="kpi-bot"><span v-if="k.n !== 'ABL触发' && k.n !== 'DPPM'" class="kpi-tgt">{{ k.tg }}</span><span class="kpi-delta" :class="kpiView(fab, k).dc">{{ kpiView(fab, k).dt }}</span></div>
              </div>
            </template>
          </div>
        </div>
      </div>

      <div class="oc-sidebar">
        <div class="oc-hdr"><span class="oc-hdr-icon">📋</span><span class="oc-hdr-title">Ongoing Case</span><span class="oc-hdr-cnt">{{ ocTotal }} 件</span></div>
        <div class="oc-body">
          <template v-for="fab in byfab.fabList" :key="fab">
            <div v-if="ocItemsFor(fab).length" class="oc-fab-group">
              <span class="oc-fab-lbl" :class="fab.slice(1)">{{ fab }}</span>
              <div v-for="(it, idx) in ocItemsFor(fab)" :key="idx" class="oc-item">
                <div class="oc-item-hd"><span class="oc-id">{{ it.o.id }}</span><span class="oc-title">{{ it.o.t }}</span><span class="oc-st" :class="it.o.st">{{ stLbl(it.o.st) }}</span></div>
                <div class="oc-kpi">KPI: {{ it.kpi }} · 负责: {{ it.o.own }} · 到期: {{ it.o.due }}</div>
                <div class="oc-bar"><div class="oc-fill" :style="{ width: it.o.pct + '%' }"></div></div>
              </div>
            </div>
          </template>
          <div v-if="!ocTotal" class="oc-empty">暂无 Ongoing Case</div>
        </div>
      </div>
    </div>

    <!-- ══ 明细弹窗（Q.html .popov：ECharts 双图 + CAPA + OC）══ -->
    <div class="popov" :class="{ show: pop.show }" @click.self="closePop()">
      <div class="popbox">
        <span class="popclose" @click="closePop()">✕</span>
        <div class="pop-hd">
          <div class="pop-title" id="pop-title">{{ pop.title }}</div>
          <a class="pop-rag" href="#" @click="openRag($event)">🤖 RAG 深度分析 →</a>
          <button v-if="USE_CLOUD_ABL && pop.curName === 'ABL触发'" class="pop-refresh" @click="refreshAblCloud(pop.curFab)">↻ 重新查询</button>
        <button v-if="USE_CLOUD_DPPM && pop.curName === 'DPPM'" class="pop-refresh" @click="refreshDppmCloud()">↻ 重新查询</button>
        </div>
        <!-- ★ 2026-09-16（用户明确）：ABL 面板不做任何"兜底/数据时间"标注 ——
             拿到过一次真值就一直保存下来当兜底用，展示效果与正常数据完全一致。
             （后端的 is_seed/fetched_at 等元信息仍保留，但只用于内部重试节流，不上界面。） -->
        <div class="pop-stats" v-html="popStatsHtml"></div>
        <div class="pop-body">
          <div class="pop-left">
            <div class="pop-tc"><div class="pop-sec-t">本周 W 趋势</div><div class="pop-chart" ref="pc1"></div></div>
            <div class="pop-tc"><div class="pop-sec-t">四厂趋势对比</div><div class="pop-chart" ref="pc2"></div></div>
          </div>
          <div class="pop-mid">
            <div class="pop-ana"><div class="pop-sec-t">当前数据分析</div><div class="ana-grid" v-html="popAnaHtml"></div></div>
            <div class="pop-capa"><div class="pop-sec-t">问题追踪 · CAPA</div><div v-html="popCapaHtml"></div></div>
          </div>
          <div class="pop-oc"><div class="pop-sec-t oc">Ongoing Case</div><div v-html="popOcHtml"></div></div>
        </div>
      </div>
    </div>

    <!-- ══ 悬浮 tip（Q.html .htip）══ -->
    <div class="htip" :class="{ show: tip.show }" :style="{ left: tip.x + 'px', top: tip.y + 'px' }">
      <div class="htip-hd">{{ tip.title }}</div>
      <div class="htip-grid" v-html="tip.gridHtml"></div>
      <div class="htip-ft">{{ tipMonthLabel }} · 悬停查看各车间数据</div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted, onActivated, onDeactivated, onBeforeUnmount } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts/core'
import { LineChart } from 'echarts/charts'
import { GridComponent, TooltipComponent, TitleComponent, LegendComponent } from 'echarts/components'
import { CanvasRenderer } from 'echarts/renderers'
import { fetchByFab } from '../api/byfab'
import { fetchAblCloud, USE_CLOUD_ABL } from '../api/cloudAbl'
import { fetchDppmCloud, USE_CLOUD_DPPM } from '../api/cloudDppm'

// ★ title / legend 必须显式注册，否则报 "Component title is used but not imported"
echarts.use([LineChart, GridComponent, TooltipComponent, TitleComponent, LegendComponent, CanvasRenderer])

/* ★ 全局「真实数据是否已接入」开关（响应式）。
     默认 false → 整块暗显（当前均为静态假数据）。
     ★ 点亮判定 = 「任一真实通道成功」：
       - botOk：主面板通道 fetchByFab() 成功拿到 FD/fabList 契约 → true
       - ablCloudData：ABL 云端通道 loadAblCloud() 成功解析出有效 series → 非 null
     任一成立即整块点亮；各厂面板再按 hasFabData(fab) 决定自身是否点亮。 */
const botOk = ref(false)   // 主面板真实数据是否接入成功
const DATA_ONLINE = computed(() => botOk.value || !!ablCloudData.value)

/* ════════════════════════════════════════════════
   ★ 静态示例数据（严格沿用 Q.html，原样移植）—— 作为默认值 / 兜底
   ════════════════════════════════════════════════ */
const fabList = ['2A', '2B', '2C', '2D']
const kpiNames = ['执行率', '焕新行动', '回复率', '结案率', '再发率', 'DPPM', 'ABL触发', 'SPC Cpk', 'OOC/OOS']
const fabCol4 = { '2A': '#00f0b0', '2B': '#60d8ff', '2C': '#ffd040', '2D': '#d0b0ff' }

const tipCfg = {
  exec: { t: '整体执行率 — 各车间达成状况', f: [
    { f: '2A', v: '96.2%', s: 'ok', b: '达标', x: '目标 ≥95%' },
    { f: '2B', v: '94.8%', s: 'bad', b: '未达标', x: '▲0.4pp 偏差' },
    { f: '2C', v: '91.3%', s: 'bad', b: '未达标', x: '▲3.7pp 偏差' },
    { f: '2D', v: '97.1%', s: 'ok', b: '达标', x: '目标 ≥95%' }
  ] },
  // ★ DPPM 不设规格目标（用户 09-21）：静态兜底浮层也不写「目标 ≤120 / 达标 / 超标」，
  //   留空后由通用分支跳过节点渲染。s 仍保留（实时分支同款口径：较上周降低=ok绿 / 升高=bad红）。
  dppm: { t: 'DPPM — 各车间产品缺陷状况', f: [
    { f: '2A', v: '98', s: 'ok', b: '', x: '' },
    { f: '2B', v: '142', s: 'bad', b: '', x: '' },
    { f: '2C', v: '115', s: 'ok', b: '', x: '' },
    { f: '2D', v: '158', s: 'bad', b: '', x: '' }
  ] },
  abl: { t: 'ABL 件数 — 各车间触发状况', f: [
    { f: '2A', v: '2件', s: 'ok', b: '正常', x: '目标 ≤3件' },
    { f: '2B', v: '5件', s: 'bad', b: '偏多', x: '▲超出2件' },
    { f: '2C', v: '1件', s: 'ok', b: '正常', x: '目标 ≤3件' },
    { f: '2D', v: '0件', s: 'ok', b: '正常', x: '目标 ≤3件' }
  ] }
}

const FD = {
  '2A': { color: '#00f0b0', overall: 'ok', ot: '整体达标', kpis: [
    { n: '执行率', v: 96.2, l: 95.1, u: '%', tg: '≥95%' }, { n: '焕新行动', v: 94.1, l: 92.5, u: '', tg: '≥90' },
    { n: '回复率', v: 93, l: 91, u: '%', tg: '≥90%' }, { n: '结案率', v: 88, l: 89, u: '%', tg: '≥90%' },
    { n: '再发率', v: 2.1, l: 2.8, u: '%', tg: '<3%' }, { n: 'DPPM', v: 98, l: 105, u: '', tg: '' },
    { n: 'ABL触发', v: 2, l: 1, u: '件', tg: '≤3' }, { n: 'SPC Cpk', v: 1.52, l: 1.50, u: '', tg: '≥1.33', p: true }, { n: 'OOC/OOS', v: 1, l: 0, u: '件', tg: '≤5/月', p: true }] },
  '2B': { color: '#60d8ff', overall: 'bad', ot: '多项超规格', kpis: [
    { n: '执行率', v: 94.8, l: 95.2, u: '%', tg: '≥95%' }, { n: '焕新行动', v: 93.8, l: 91.2, u: '', tg: '≥90' },
    { n: '回复率', v: 91, l: 90, u: '%', tg: '≥90%' }, { n: '结案率', v: 84, l: 86, u: '%', tg: '≥90%' },
    { n: '再发率', v: 5.8, l: 5.2, u: '%', tg: '<3%' }, { n: 'DPPM', v: 142, l: 130, u: '', tg: '' },
    { n: 'ABL触发', v: 5, l: 3, u: '件', tg: '≤3' }, { n: 'SPC Cpk', v: 1.38, l: 1.37, u: '', tg: '≥1.33', p: true }, { n: 'OOC/OOS', v: 4, l: 3, u: '件', tg: '≤5/月', p: true }] },
  '2C': { color: '#ffd040', overall: 'warn', ot: '部分异常', kpis: [
    { n: '执行率', v: 91.3, l: 92.0, u: '%', tg: '≥95%' }, { n: '焕新行动', v: 88.5, l: 87.8, u: '', tg: '≥90' },
    { n: '回复率', v: 88, l: 89, u: '%', tg: '≥90%' }, { n: '结案率', v: 91, l: 90, u: '%', tg: '≥90%' },
    { n: '再发率', v: 3.5, l: 3.3, u: '%', tg: '<3%' }, { n: 'DPPM', v: 115, l: 118, u: '', tg: '' },
    { n: 'ABL触发', v: 1, l: 2, u: '件', tg: '≤3' }, { n: 'SPC Cpk', v: 1.41, l: 1.40, u: '', tg: '≥1.33', p: true }, { n: 'OOC/OOS', v: 3, l: 2, u: '件', tg: '≤5/月', p: true }] },
  '2D': { color: '#d0b0ff', overall: 'warn', ot: 'DPPM超标', kpis: [
    { n: '执行率', v: 97.1, l: 96.8, u: '%', tg: '≥95%' }, { n: '焕新行动', v: 92.8, l: 93.1, u: '', tg: '≥90' },
    { n: '回复率', v: 95, l: 93, u: '%', tg: '≥90%' }, { n: '结案率', v: 92, l: 91, u: '%', tg: '≥90%' },
    { n: '再发率', v: 2.4, l: 2.0, u: '%', tg: '<3%' }, { n: 'DPPM', v: 158, l: 140, u: '', tg: '' },
    { n: 'ABL触发', v: 0, l: 1, u: '件', tg: '≤3' }, { n: 'SPC Cpk', v: 1.49, l: 1.48, u: '', tg: '≥1.33', p: true }, { n: 'OOC/OOS', v: 4, l: 1, u: '件', tg: '≤5/月', p: true }] }
}

const PT = {
  '2A': { 0: [[95.0, 96.2, 95.8, 96.2], '%', '#00f0b0', 95], 1: [[91.2, 92.5, 93.8, 94.1], '', '#00f0b0', 90], 2: [[90.0, 91.5, 92.0, 93.0], '%', '#00f0b0', 90], 3: [[90.5, 89.2, 88.8, 88.0], '%', '#ffd040', 90], 4: [[2.5, 2.8, 2.2, 2.1], '%', '#00f0b0', 3], 5: [[108, 105, 100, 98], '', '#00f0b0', 120], 6: [[1, 1, 2, 2], '件', '#00f0b0', 3] },
  '2B': { 0: [[95.5, 95.2, 94.5, 94.8], '%', '#ff6060', 95], 1: [[91.8, 91.2, 92.5, 93.8], '', '#60d8ff', 90], 2: [[91.5, 90.0, 90.5, 91.0], '%', '#60d8ff', 90], 3: [[87.2, 86.0, 85.0, 84.0], '%', '#ff6060', 90], 4: [[4.8, 5.2, 5.5, 5.8], '%', '#ff6060', 3], 5: [[125, 130, 138, 142], '', '#ff6060', 120], 6: [[3, 3, 4, 5], '件', '#ff6060', 3] },
  '2C': { 0: [[93.5, 92.0, 91.8, 91.3], '%', '#ff6060', 95], 1: [[88.2, 87.8, 88.0, 88.5], '', '#ffd040', 90], 2: [[89.5, 89.0, 88.5, 88.0], '%', '#ffd040', 90], 3: [[90.0, 90.5, 91.0, 91.0], '%', '#00f0b0', 90], 4: [[3.2, 3.3, 3.4, 3.5], '%', '#ff6060', 3], 5: [[120, 118, 116, 115], '', '#00f0b0', 120], 6: [[2, 2, 1, 1], '件', '#00f0b0', 3] },
  '2D': { 0: [[96.5, 96.8, 97.0, 97.1], '%', '#00f0b0', 95], 1: [[93.5, 93.1, 92.8, 92.8], '', '#d0b0ff', 90], 2: [[93.0, 93.0, 94.5, 95.0], '%', '#00f0b0', 90], 3: [[91.0, 91.0, 91.5, 92.0], '%', '#00f0b0', 90], 4: [[2.0, 2.0, 2.2, 2.4], '%', '#00f0b0', 3], 5: [[138, 140, 152, 158], '', '#ff6060', 120], 6: [[1, 1, 0, 0], '件', '#00f0b0', 3] }
}

const CAPA = {
  '2A': { 3: [{ t: '结案流程标准化', s: 'prog', m: '责任:李工 · 预计08-15', tag: '进行中' }] },
  '2B': { 0: [{ t: '执行率提升专案', s: 'open', m: '责任:刘工 · 预计09-10', tag: '未启动' }, { t: '班次执行稽核', s: 'prog', m: '责任:林工 · 预计08-20', tag: '进行中' }], 4: [{ t: '再发率根因改善', s: 'open', m: '责任:王工 · 预计08-30', tag: '未启动' }], 5: [{ t: 'DPPM材料改善', s: 'prog', m: '责任:孙工 · 预计08-10', tag: '进行中' }] },
  '2C': { 0: [{ t: '执行率补强方案', s: 'prog', m: '责任:林工 · 预计08-20', tag: '进行中' }] },
  '2D': { 5: [{ t: 'DPPM=158改善', s: 'open', m: '责任:蔡工 · 预计08-31', tag: '未启动' }, { t: '薄膜均匀性改善', s: 'prog', m: '责任:许工 · 预计08-30', tag: '进行中' }] }
}

const OC = {
  '2A': { 0: [{ id: 'OC-241', t: '执行率W3异常排查', own: '陈工', due: '2026-08-10', st: 'done', pct: 100 }], 3: [{ id: 'OC-235', t: '结案SOP流程优化', own: '王工', due: '2026-08-20', st: 'open', pct: 30 }], 4: [{ id: 'OC-232', t: '再发率根因追溯', own: '张工', due: '2026-07-31', st: 'done', pct: 100 }] },
  '2B': { 0: [{ id: 'OC-250', t: '执行率持续改善计划', own: '刘工', due: '2026-09-15', st: 'open', pct: 20 }, { id: 'OC-248', t: '班次执行稽核加强', own: '林工', due: '2026-08-25', st: 'prog', pct: 55 }], 3: [{ id: 'OC-245', t: '结案流程精简专案', own: '陈工', due: '2026-08-30', st: 'open', pct: 15 }], 4: [{ id: 'OC-243', t: '再发率控制再设计', own: '王工', due: '2026-09-01', st: 'open', pct: 10 }, { id: 'OC-240', t: '参数SPC监控扩大', own: '赵工', due: '2026-08-20', st: 'prog', pct: 70 }], 5: [{ id: 'OC-237', t: 'DPPM超标材料改善', own: '孙工', due: '2026-08-15', st: 'open', pct: 25 }], 6: [{ id: 'OC-234', t: 'ABL触发原因根除', own: '吴工', due: '2026-08-31', st: 'open', pct: 35 }] },
  '2C': { 0: [{ id: 'OC-255', t: '执行率补强计划', own: '林工', due: '2026-08-20', st: 'prog', pct: 50 }], 4: [{ id: 'OC-252', t: '再发率验证方案', own: '黄工', due: '2026-08-05', st: 'prog', pct: 80 }] },
  '2D': { 4: [{ id: 'OC-260', t: '再发率波动监控', own: '胡工', due: '2026-09-01', st: 'prog', pct: 40 }], 5: [{ id: 'OC-258', t: 'DPPM=158改善专案', own: '蔡工', due: '2026-08-31', st: 'open', pct: 20 }, { id: 'OC-256', t: '薄膜均匀性改善', own: '许工', due: '2026-08-30', st: 'prog', pct: 60 }] }
}

/* ════════════════════════════════════════════════
   ★ 响应式数据源：默认内置静态示例，机器人数据到达后整体覆盖
   ════════════════════════════════════════════════ */
const byfab = reactive({
  fabList, kpiNames, fabCol4, tipCfg, FD, PT, CAPA, OC,
  execRate: null,      // ★ 执行率钻取面板专用数据块（见 byfab.js EXEC_RATE_EXAMPLE）；null=按 FD/PT/CAPA/OC 派生
  source: 'static',   // 'static' | 'bot'
  loading: false
})

// ★ 预留接口：拉取公司机器人数据（USE_BOT_API=false 时 fetchByFab 返回 null → 沿用静态示例）
onMounted(async () => {
  byfab.loading = true
  try {
    const data = await fetchByFab()
    if (data && typeof data === 'object') {
      // 顶层键整体覆盖；缺字段保留静态默认
      Object.assign(byfab, data)
      byfab.source = 'bot'
      // 执行率钻取面板：机器人返回 execRate 时整体覆盖对应 FAB（未返回则自动派生）
      if (data.execRate && typeof data.execRate === 'object') byfab.execRate = data.execRate
      // ★ 一次性查询已获取全部数值（2A/2B/2C/2D 的 W1-W4 等）→ 点亮所有面板。
      //   各厂面板再按 hasFabData(fab) 决定自身是否点亮（缺数据的厂保持置灰）。
      botOk.value = true
    }
  } catch (e) {
    console.warn('[ByFab] 机器人数据接入失败，沿用静态示例', e)
  } finally {
    byfab.loading = false
  }
  // ★ ABL触发 云端：首屏已有 localStorage 缓存数据直显（setup 已恢复），
  //   这里仅做小时级静默检查（有新数据才更新）+ 启动每小时后台轮询定时器
  loadAblCloud(false, true)
  scheduleAblHourPoll()
  // ★ DPPM 云端（2A/2B）：首屏已有 localStorage 真值直显（setup 已恢复），
  //   这里仅做静默检查（后端说新鲜就不发请求）+ 启动心跳兜底定时器
  loadDppmCloud(false, true)
  scheduleDppmPoll()
})
// ★ keep-alive：每次切回本页 → 恢复首屏缓存值 + 小时级静默检查 + 重启轮询定时器
onActivated(() => {
  loadAblCloud(false, true)
  scheduleAblHourPoll()
  loadDppmCloud(false, true)
  scheduleDppmPoll()
})
// ★ 页面停用（keep-alive 切走）→ 暂停心跳轮询 + 停掉重试链/短轮询，避免后台空跑
onDeactivated(() => {
  clearAblHourPoll()
  clearDppmPoll()
})

/* ════════════════════════════════════════════════
   ★ 执行率钻取面板（点 执行率 KPI 弹出的明细）数据接口
   ════════════════════════════════════════════════ */
// 缺省从 FD/PT/CAPA/OC（执行率 = kpiIdx 0）派生；机器人返回 execRate[fab] 时直接采用
function buildExecRate(fab) {
  const d = byfab.FD[fab]
  if (!d) return null
  const k = d.kpis[0]                                  // 执行率 = 第 0 项 KPI
  const ti = (byfab.PT[fab] && byfab.PT[fab][0]) || [[], '%', d.color, 95]
  const compare = {}
  byfab.fabList.forEach(f => {
    const t = byfab.PT[f] && byfab.PT[f][0]
    compare[f] = t ? t[0] : []
  })
  const ok = isOk(k)
  const trendBetter = getTrend(k) === 'better'
  return {
    value: k.v, unit: k.u, last: k.l, target: k.tg,
    ok, trendBetter, delta: Math.abs(k.v - k.l), risk: ok ? '低' : '高',
    weeks: ti[0], color: ti[2], tgtLine: ti[3],
    compare,
    capa: (byfab.CAPA[fab] && byfab.CAPA[fab][0]) || [],
    oc: (byfab.OC[fab] && byfab.OC[fab][0]) || []
  }
}
function getExecRate(fab) {
  if (byfab.execRate && byfab.execRate[fab]) return byfab.execRate[fab]
  return buildExecRate(fab)
}

/* ════════════════════════════════════════════════
   ★ 判定逻辑（与 Q.html 完全一致）
   ════════════════════════════════════════════════ */
function isOk(k) {
  if (k.tg.startsWith('≥')) return k.v >= parseFloat(k.tg.slice(1))
  if (k.tg.startsWith('≤')) return k.v <= parseFloat(k.tg.slice(1))
  if (k.tg.startsWith('<')) return k.v < parseFloat(k.tg.slice(1))
  return true
}
function getTrend(k) {
  return (k.tg.startsWith('≥') || k.tg.startsWith('>')) ? (k.v >= k.l ? 'better' : 'worse') : (k.v <= k.l ? 'better' : 'worse')
}

function kpiDotClass(k) {
  const ok = isOk(k)
  const bt = getTrend(k) === 'better'
  return ok ? 'ok' : (bt ? 'warn' : 'bad')
}
function kpiDeltaClass(k) {
  const bt = getTrend(k) === 'better'
  return bt ? 'dn' : 'up'
}
/* ════════════════════════════════════════════════
   ★ 真实数据接入判定（"假数据不亮"核心逻辑）：
     1) botOk（主面板机器人契约数据成功）→ 全部 KPI 真实
     2) 仅 ABL 云端接入（USE_CLOUD_ABL + ablCloudData）→ 只有「ABL触发」指标真实，
        其余 KPI 属静态示例 → 显示 —（不再整块"一起亮"）
     3) 双通道均未接入 → 示例数据整页保留，由 .dim-all 统一压暗（演示用途）
   ════════════════════════════════════════════════ */
function ablHasFab(fab) {
  const abl = ablCloudData.value
  return !!(abl && Array.isArray(abl.series) && abl.series.some(s => s.name === fab))
}
// ★ 指标是否接入真实数据（仅用于「部分接入」场景的显示开关）
function kpiReal(fab, k) {
  if (botOk.value) return true
  if (k.n === 'ABL触发') return ablHasFab(fab)
  if (k.n === 'DPPM') return dppmHasFab(fab)
  return false
}
/* ════════════════════════════════════════════════
   ★ 诊断留痕（2026-09-21 · 公司部署后「DPPM 面板不亮」排查）
     现象：后端 `GET /api/byfab/dppm/` 返回 200 且带结构，但面板既不亮也点不进去。
     链路只有一条可能断：`dppmCloudData.value` 为 null → dppmHasFab 恒 false。
     成因未定，故在浏览器 Console 打「一行结构化诊断」，不碰界面、不带任何兜底/可信度字样：
       · 拿到数据 → log 一行 fab 级摘要（seeded / 点数）
       · 拿不到   → log 后端原始响应，直接看 success / 缺哪个 fab / 缺什么字段
     排查完可整段删除（搜索 DPPM_DIAG 即可定位）。
     ════════════════════════════════════════════════ */
function dppmDiag(tag, fields, raw) {
  try {
    const serverSeedFabs = (raw && raw.seed_fabs) || []
    if (fields && fields.fabs) {
      const brief = {}
      for (const fab of ['2A', '2B']) {
        const f = fields.fabs[fab]
        brief[fab] = f ? { seeded: !!f.seeded, points: (f.values || []).length } : 'MISSING'
      }
      const fake = Object.keys(brief).filter(f => brief[f] && brief[f].seeded === true)
      console.log('[ByFab] DPPM 数据已就绪', tag, brief,
        fake.length ? ('· 仍为兜底种子的厂: ' + fake.join('/') + '（该厂这次没取到真值，界面显示的是内置样例）') : '')
      if (fake.length || serverSeedFabs.length) {
        console.warn('[ByFab] DPPM 存在未取到真值的厂（后端 seed_fabs=' + JSON.stringify(serverSeedFabs) + '）'
          + '，原因见后端 last_error：GET /api/byfab/dppm/?diag=1')
      }
    } else {
      console.warn('[ByFab] DPPM 未取到可用数据（面板将不点亮）', tag, raw)
    }
  } catch (e) { /* 诊断不影响主流程 */ }
}
// ★ 合并（DPPM_DIAG）：自控圆点不受影响，仅当「历史遗留文本恰为 DPPM」才提级
function dotIsDppm(dot) { return String(dot || '').trim().toUpperCase() === 'DPPM' }
// ★ 各 FAB 当前 DPPM 值
function dppmFabValue(fab) {
  if (!USE_CLOUD_DPPM || !dppmHasFab(fab)) return null
  const st = dppmStatsFor(fab)
  if (!st || st.cur === null || st.cur === undefined || isNaN(Number(st.cur))) return null
  return st
}
// ★ 各 FAB 当前 ABL 触发件数
function ablFabCount(fab) {
  const k = ((byfab.FD[fab] && byfab.FD[fab].kpis) || []).find(x => x.n === 'ABL触发')
  if (!k) return null
  if (USE_CLOUD_ABL && ablHasFab(fab)) {
    const st = ablStatsFor(fab)
    if (st && st.cur !== null && st.cur !== undefined && !isNaN(Number(st.cur))) return Number(st.cur)
  }
  const n = Number(k.v)
  return isNaN(n) ? null : n
}
// ★ 顶部「DPPM」卡 = 实时汇总：2A/2B 本周之和（有任何一厂真值才算，全无 → null 显示 —）
//   ★ 09-21 用户要求「DPPM 不要设置规格目标」→ 已删除 dppmHeaderTarget / dppmHeaderOver。
//     原实现里「超出规格的 FAB 数」依赖从 `tipCfg.dppm.t` 正则抓「≤ 阈值」，而该字段在 09-21
//     改版后是浮层【标题】文案（不含 ≤ 与数字）→ 恒 null，卡面副标题一直只剩「— FAB 超出规格」。
//     现在按用户口径彻底取消规格目标，不再做达标/超标判定。
const dppmHeaderTotal = computed(() => {
  let sum = 0, any = false
  byfab.fabList.forEach(fab => {
    const st = dppmFabValue(fab)
    if (st) { sum += Number(st.cur); any = true }
  })
  return any ? sum : null
})
// ★ 头部「ABL 件数」= 2A/2B/2C/2D 四板块累计总和（单位 次；目标放空不计）
const ablHeaderTotal = computed(() => {
  let sum = 0, any = false
  byfab.fabList.forEach(fab => {
    const n = ablFabCount(fab)
    if (n !== null) { sum += n; any = true }
  })
  return any ? sum : null
})
// ★ 单个 KPI 展示视图（含 ABL 云端真实值覆盖静态示例；ABL 件数单位统一为「次」）
// ★ 2026-09-21：浮点差值会把二进制误差直接显示给用户 —— 例如 760.4 - 980.2 = -219.80000000000007，
//   拼进「变化幅度/偏差量」就是 ▼219.80000000000007。统一走本函数展示：
//   按最多 2 位小数四舍五入后交给 Number 去掉末尾多余的 0 —— 只消浮点噪声，不动真实精度
//   （1180.25 原样保留、1180.5 仍是 1180.5、5200 仍是 5200）。
function fmtNum(v, digits = 2) {
  const n = Number(v)
  if (v === null || v === undefined || v === '' || isNaN(n)) return ''
  return String(Number(n.toFixed(digits)))
}
const KPI_EMPTY = { v: '—', dot: 'gray', dt: '—', dc: 'na' }
function kpiView(fab, k) {
  const partial = !!ablCloudData.value && !botOk.value   // 部分接入（仅 ABL 云端真）
  if (partial && !kpiReal(fab, k)) return KPI_EMPTY      // ★ 假数据 → 灰显 —（不"亮"）
  const u1 = t => String(t || '').replace(/次数|件/g, '次')   // ★ ABL 件数 → 单位「次」（云端 yAxis 名可能为「次数」）
  const ret = (v, dot, dt, dc) => (k.n === 'ABL触发'
    ? { v: u1(v), dot, dt: u1(dt), dc }
    : { v, dot, dt, dc })
  // ★ ABL触发 且 云端已接：数值/环比直接取云端（覆盖静态示例）
  if (k.n === 'ABL触发' && USE_CLOUD_ABL) {
    const st = ablStatsFor(fab)
    if (st && st.cur !== null && st.cur !== undefined && !isNaN(Number(st.cur))) {
      const nCur = Number(st.cur)
      const unit = u1(st.unit || k.u || '')
      // ★ 总览圆点与弹窗「达标状态/风险等级」同口径：较上周降低→绿(ok)、升高→红(bad)、无对比→灰(gray)
      //   （不再按目标阈值 ≤tgt 判定，用户 09-08 要求两侧颜色一致）
      const dotCls = (st.wow === null || st.wow === undefined || isNaN(Number(st.wow)))
        ? 'gray'
        : (Number(st.wow) <= 0 ? 'ok' : 'bad')
      if (st.wow !== null && st.wow !== undefined && !isNaN(Number(st.wow))) {
        const nWow = Number(st.wow)
        return ret(fmtNum(nCur) + unit, dotCls, (nWow <= 0 ? '▼' : '▲') + fmtNum(Math.abs(nWow)) + unit, nWow <= 0 ? 'dn' : 'up')
      }
      return ret(fmtNum(nCur) + unit, dotCls, '', 'na')
    }
  }
  // ★ DPPM 且 云端已接：数值/环比直接取云端（覆盖静态示例）；单位用云端返回的 unit
  if (k.n === 'DPPM' && USE_CLOUD_DPPM) {
    const st = dppmStatsFor(fab)
    if (st) {
      const num = v => (v === null || v === undefined || isNaN(Number(v)) ? null : Number(v))
      const nCur = num(st.cur), nWow = num(st.wow)
      // ★ 周趋势 / 风险：复用 ABL 口径「较上周降低→绿(ok) / 升高→红(bad) / 无环比→灰」
      const bt = nWow === null ? null : nWow <= 0
      const dotCls = bt === null ? 'gray' : (bt ? 'ok' : 'bad')
      // ★ 2026-09-22（用户拍板）：DPPM 不是单位 → 云端分支也不拼任何单位（不回落到 k.u）
      const unit = ''
      const vtxt = (nCur === null ? '—' : fmtNum(nCur)) + unit
      const dtxt = nWow === null ? '—' : ((nWow <= 0 ? '▼' : '▲') + fmtNum(Math.abs(nWow)) + unit)
      return ret(vtxt, dotCls, dtxt, nWow === null ? 'na' : (nWow <= 0 ? 'dn' : 'up'))
    }
  }
  // ★ DPPM 未接云端（2C/2D，或云端未启用）：同样【不按规格目标判达标】（用户 09-21），
  //   沿用「较上周」口径上色 —— 与云端 DPPM 分支 / ABL 完全同口径
  //   （较上周降低=绿 ok，升高=红 bad，无环比=灰）。
  if (k.n === 'DPPM') {
    const nWow = Number(k.v) - Number(k.l)
    const okw = isNaN(nWow) ? null : nWow <= 0
    return {
      // ★ 2026-09-22：DPPM 不是单位 → 静态分支同样不拼 k.u
      v: k.v,
      dot: okw === null ? 'gray' : (okw ? 'ok' : 'bad'),
      dt: okw === null ? '—' : ((nWow <= 0 ? '▼' : '▲') + fmtNum(Math.abs(nWow))),
      dc: okw === null ? 'na' : (okw ? 'dn' : 'up')
    }
  }
  // 静态示例 / 主面板机器人数据 的常规展示
  const bt = getTrend(k) === 'better'
  return ret(k.v + k.u, kpiDotClass(k), (bt ? '▼' : '▲') + Math.abs(k.v - k.l).toFixed(1) + k.u, kpiDeltaClass(k))
}
// ★ 面板状态文案（部分接入时不再误导性地写"整体达标"）
function fabStatusText(fab) {
  const d = byfab.FD[fab]
  if (botOk.value) return (d && d.ot) || ''
  if (ablCloudData.value) return ablHasFab(fab) ? '已接入' : '未接入'
  return (d && d.ot) || ''
}
function fabStatusCls(fab) {
  const d = byfab.FD[fab]
  if (botOk.value) return (d && d.overall) || ''
  if (ablCloudData.value) return ablHasFab(fab) ? 'ok' : ''
  return (d && d.overall) || ''
}
function stLbl(st) {
  return st === 'open' ? 'Open' : st === 'prog' ? '进行中' : 'Done'
}

/* ════════════════════════════════════════════════
   ★ Ongoing Case 侧栏
   ════════════════════════════════════════════════ */
function ocItemsFor(fab) {
  const fabItems = byfab.OC[fab]
  if (!fabItems) return []
  const out = []
  Object.keys(fabItems).forEach(idx => {
    fabItems[idx].forEach(o => out.push({ kpi: byfab.kpiNames[parseInt(idx)], o }))
  })
  return out
}
const ocTotal = computed(() => byfab.fabList.reduce((sum, fab) => sum + ocItemsFor(fab).length, 0))

/* ════════════════════════════════════════════════
   ★ 查询结果的「最后日期」默认指向本周（按 ISO 周）
   ════════════════════════════════════════════════ */
const queryLastWeek = computed(() => {
  const now = new Date()
  const d = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()))
  const dayNum = (d.getUTCDay() + 6) % 7
  d.setUTCDate(d.getUTCDate() - dayNum + 3)
  const firstThursday = new Date(Date.UTC(d.getUTCFullYear(), 0, 4))
  const week = 1 + Math.round(((d - firstThursday) / 86400000 - 3 + ((firstThursday.getUTCDay() + 6) % 7)) / 7)
  return `${now.getFullYear()}-W${String(week).padStart(2, '0')}（本周）`
})

/* ★ 未接入数据的面板（无 FD 数据块 且 无 ABL 云端数据）→ 置灰显示。
   ★ 部分接入场景（仅 ABL 云端真）：没有 ABL series 的面板视为无真实数据 → .no-data；
     双通道全未接入（纯示例）→ 一律返回 true，由 .dim-all 整页压暗。 */
function hasFabData(fab) {
  if (botOk.value) {
    const d = byfab.FD[fab]
    return !!(d && d.kpis && d.kpis.length)
  }
  const abl = ablCloudData.value
  if (abl) return ablHasFab(fab) || dppmHasFab(fab)
  return true   // ★ 纯静态示例模式：数据保留展示（dim-all 整页压暗区分真/假）
}

/* ════════════════════════════════════════════════
   ★ 悬浮 tip
   ════════════════════════════════════════════════ */
const tip = ref({ show: false, x: 0, y: 0, title: '', gridHtml: '' })
// ★ 悬浮 tip 页脚的月份标签（2026-09-15）：取当前电脑日期的「年-月」，
//   模块加载时求值一次后缓存 —— 页面停留跨月/跨年也不再变化，避免与数据口径打架
const tipMonthLabel = (() => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
})()
function showTip(e, type) {
  if (type === 'abl') {
    // ★ ABL 件数浮层：与头部 ABL 件数卡同套口径——各厂取 ABL 触发当前值（云端真实优先，回退静态示例），
    //   颜色与 ABL 弹窗「偏差量」完全一致：较上周降低→绿 / 升高→红 / 无对比=灰（用户 09-08）；
    //   弹层只保留厂名+当前数值（次），不显示「正常/偏多/目标」等文字
    tip.value.title = 'ABL 件数 — 各车间触发状况'
    tip.value.gridHtml = byfab.fabList.map(fab => {
      const st = ablStatsFor(fab)        // {cur, last, wow, unit} — 颜色统一按 wow（较上周变化）
      const cur = st ? st.cur : null
      const wow = st ? st.wow : null
      const s = wow === null ? 'na' : (wow <= 0 ? 'ok' : 'bad')
      const vc = s === 'ok' ? '#00f0b0' : (s === 'bad' ? '#ff6060' : '#ffd040')
      const vtxt = (cur === null || cur === undefined || isNaN(Number(cur))) ? '' : (fmtNum(cur) + '次')
      return '<div class="htip-card"><div class="htip-fab" style="color:' + byfab.fabCol4[fab] + '">' + fab
        + '</div><div class="htip-val" style="color:' + vc + '">' + vtxt + '</div></div>'
    }).join('')
  } else if (type === 'dppm' && ['2A', '2B'].some(f => dppmHasFab(f))) {
    // ★ DPPM 浮层（2026-09-21 改版）：版式与「ABL 件数」浮层完全同款 ——
    //   ① 列出【全部车间】2A/2B/2C/2D（不再只列 2A/2B）；
    //   ② 每格只显示「厂名 + 当前值」，【删掉「较上周」变化行】，也不写目标/达标文字；
    //   ③ 颜色仍沿用「较上周降低→绿 / 升高→红 / 无对比=灰」口径（与 DPPM 弹窗一致，只是不写文字）。
    //   ★ 2C/2D 暂无云端数据 → 数值留空占位；日后接上数据即自动显示，无需再改代码。
    //   任一厂都取不到数据时 → 落到下面通用分支，沿用静态示例浮层（不空白）。
    tip.value.title = 'DPPM — 各车间产品缺陷状况'
    tip.value.gridHtml = byfab.fabList.map(fab => {
      const st = dppmStatsFor(fab)
      const cur = st ? st.cur : null
      const nWow = (st && st.wow !== null && st.wow !== undefined && !isNaN(Number(st.wow))) ? Number(st.wow) : null
      const s = nWow === null ? 'na' : (nWow <= 0 ? 'ok' : 'bad')
      const vc = s === 'ok' ? '#00f0b0' : (s === 'bad' ? '#ff6060' : '#ffd040')
      const vtxt = (cur === null || cur === undefined || isNaN(Number(cur))) ? '' : (fmtNum(cur) + (st.unit || ''))
      return '<div class="htip-card"><div class="htip-fab" style="color:' + byfab.fabCol4[fab] + '">' + fab
        + '</div><div class="htip-val" style="color:' + vc + '">' + vtxt + '</div></div>'
    }).join('')
  } else {
    const c = byfab.tipCfg[type]
    if (!c) return
    tip.value.title = c.t
    // ★ 2026-09-21：`x`（附加说明）与 `b`（达标徽标）允许留空 → 留空则不渲染该节点。
    //   用途：DPPM 不设规格目标后，静态兜底浮层不再写「目标 ≤120 / 达标 / 超标」，
    //   又不留下空的 .htip-extra / .htip-badge 残壳。exec / abl 两项仍带值，外观不变。
    tip.value.gridHtml = c.f.map(f => {
      const vc = f.s === 'ok' ? '#00f0b0' : f.s === 'bad' ? '#ff6060' : '#ffd040'
      return '<div class="htip-card"><div class="htip-fab" style="color:' + byfab.fabCol4[f.f] + '">' + f.f + '</div><div class="htip-val" style="color:' + vc + '">' + f.v + '</div>'
        + (f.x ? '<div class="htip-extra">' + f.x + '</div>' : '')
        + (f.b ? '<span class="htip-badge ' + f.s + '">' + f.b + '</span>' : '')
        + '</div>'
    }).join('')
  }
  tip.value.show = true
  const r = e.currentTarget.getBoundingClientRect()
  let l = r.left, t = r.bottom + 8
  const tw = 280, th = 150
  if (l + tw > window.innerWidth - 10) l = window.innerWidth - tw - 10
  if (t + th > window.innerHeight - 10) t = r.top - th - 8
  tip.value.x = l
  tip.value.y = t
}
function hideTip() { tip.value.show = false }

/* ════════════════════════════════════════════════
   ★ 明细弹窗 + ECharts 双图
   ════════════════════════════════════════════════ */
const pop = ref({ show: false, title: '', curName: '', curFab: '' })
const popStatsHtml = ref('')
const popAnaHtml = ref('')
const popCapaHtml = ref('')
const popOcHtml = ref('')
const pc1 = ref(null)
const pc2 = ref(null)
let chart1 = null, chart2 = null
const RAG_URL = 'https://your-rag-chatbot.example.com'
const curCtx = ref('')

function openPop(fab, idx) {
  // ★ 执行率（kpiIdx=0）走专用钻取面板，数据来自 execRate 接口（默认派生，机器人可覆盖）
  if (idx === 0) { openExecPanel(fab); return }
  const d = byfab.FD[fab], k = d.kpis[idx]
  // ★ 部分接入场景（仅 ABL 云端真）：点击未接真实数据的示例 KPI → 提示不打开假数据弹窗
  if (!!ablCloudData.value && !botOk.value && !kpiReal(fab, k)) {
    ElMessage.warning(`${k.n}（${fab}）尚未接入真实数据，暂无法查看明细`)
    return
  }
  // ★ ABL触发：启用云端时走云端实时图表，否则沿用下方静态趋势
  if (k.n === 'ABL触发') {
    if (USE_CLOUD_ABL) { openAblCloud(fab); return }
    // 云端未启用 → 继续走下方静态 buildCharts
  }
  // ★ DPPM：2A/2B 已接云端 → 走云端实时图表；2C/2D 无 DPPM 机器人数据 → 沿用下方静态趋势
  if (k.n === 'DPPM' && USE_CLOUD_DPPM && dppmHasFab(fab)) {
    openDppmCloud(fab); return
  }
  if (k.p || !byfab.PT[fab] || !byfab.PT[fab][idx]) return
  pop.value.curName = k.n
  const ti = byfab.PT[fab][idx]
  const data = ti[0], unit = ti[1], color = ti[2], tgt = k.n === 'DPPM' ? null : ti[3]
  const ok = isOk(k), bt = getTrend(k) === 'better'
  // ★ DPPM 不设规格目标（用户 09-21）：静态弹窗同样不做「达标/超标」判定 ——
  //   达标状态留中性占位「—」，本周数值/偏差量/风险等级一律只看周趋势
  //   （较上周降低=低，与云端 DPPM 弹窗 applyDppmPop 完全同口径）；其余 KPI 维持原样。
  const isDppm = k.n === 'DPPM'
  const good = isDppm ? bt : ok
  const goodCls = good ? 'ok' : 'bad'
  curCtx.value = fab + ' · ' + k.n + ' · 本周' + k.v + k.u + (isDppm ? '' : ' 目标' + k.tg)
  pop.value.title = fab + ' · ' + k.n + ' · 详情分析'
  pop.value.show = true

  popStatsHtml.value =
    '<div class="pop-stat"><div class="pkl">本周数值</div><div class="pkv ' + (good ? 'g' : 'r') + '">' + k.v + k.u + '</div></div>' +
    '<div class="pop-stat"><div class="pkl">上周数值</div><div class="pkv">' + k.l + k.u + '</div></div>' +
    '<div class="pop-stat"><div class="pkl">变化幅度</div><div class="pkv ' + (bt ? 'g' : 'r') + '">' + (bt ? '▼' : '▲') + Math.abs(k.v - k.l).toFixed(1) + k.u + '</div></div>' +
    '<div class="pop-stat"><div class="pkl">规格目标</div><div class="pkv">' + '' + '</div></div>'

  popAnaHtml.value =
    '<div class="ana-item"><div class="ana-lbl">达标状态</div>' + (isDppm
      ? '<div class="ana-val na">—</div>'
      : '<div class="ana-val ' + (ok ? 'ok' : 'bad') + '">' + (ok ? '✓ 达标' : '✗ 偏差') + '</div>') + '</div>' +
    '<div class="ana-item"><div class="ana-lbl">周趋势</div><div class="ana-val ' + (bt ? 'ok' : 'bad') + '">' + (bt ? '▼ 改善' : '▲ 恶化') + '</div></div>' +
    '<div class="ana-item"><div class="ana-lbl">偏差量</div><div class="ana-val ' + goodCls + '">' + Math.abs(k.v - k.l).toFixed(1) + k.u + '</div></div>' +
    '<div class="ana-item"><div class="ana-lbl">风险等级</div><div class="ana-val ' + goodCls + '">' + (good ? '低' : '高') + '</div></div>'

  const cl = (byfab.CAPA[fab] && byfab.CAPA[fab][idx]) || []
  popCapaHtml.value = cl.length
    ? cl.map(c => '<div class="capa-item"><div class="capa-dot ' + c.s + '"></div><div class="capa-cnt"><div class="capa-t">' + c.t + '</div><div class="capa-m">' + c.m + '<span class="capa-tag">' + c.tag + '</span></div></div></div>').join('')
    : '<div style="font-size:10px;color:var(--t2);text-align:center;padding:8px">暂无 CAPA 条目</div>'

  const ol = (byfab.OC[fab] && byfab.OC[fab][idx]) || []
  popOcHtml.value = ol.length
    ? ol.map(o => {
      const sl = o.st === 'open' ? 'Open' : o.st === 'prog' ? '进行中' : 'Done'
      return '<div class="p-oc-item"><div class="p-oc-hd"><span class="p-oc-id">' + o.id + '</span><span class="p-oc-t">' + o.t + '</span><span class="p-oc-st ' + o.st + '">' + sl + '</span></div><div class="p-oc-meta">负责: ' + o.own + ' · 到期: ' + o.due + '</div><div class="p-oc-bar"><div class="p-oc-fill" style="width:' + o.pct + '%"></div></div></div>'
    }).join('')
    : '<div class="p-oc-empty">暂无 Ongoing Case</div>'

  // 等待 DOM（popov 从 display:none 切到 flex）后再初始化图表
  requestAnimationFrame(() => buildCharts(fab, idx, data, unit, color, tgt, k))
}

/* ════════════════════════════════════════════════
   ★ ABL触发 云端实时图表（仅 USE_CLOUD_ABL=true 时启用）
   ════════════════════════════════════════════════ */
const ablCloudData = ref(null)     // 云端返回并提取后的结构化字段 {title, unit, xAxis, series}
// ★ 2026-09-16：后端下发的数据来源元信息 {is_seed, fetched_at, last_attempt_at, stale, refreshing, last_error}
//   ★ 用户明确要求：界面不做任何"兜底/数据时间"标注，展示效果与正常数据一致。
//     这里保留 meta 仅供【内部重试节流】使用（兜底数据不占用 1 小时新鲜期，以便尽快取到真值）。
const ablMeta = ref(null)
// ★ 2026-09-16：当前【展示中】数据对应的后端版本号（后端 _meta.fetched_at）。
//   用途：区分"后端真给了新数据"与"后端把同一版旧值又给了一次（后台正在刷新）"。
//   只有版本号变了才刷新界面 —— 需求原话「保证新数据来了才刷新，在此之前一直显示旧数据」。
//   只会被【真值】写入（兜底种子不写）→ 因此它非空 ⟺ 曾经取到过真值。
const ablFetchedAt = ref('')
const ablLoading = ref(false)      // 查询中（仅手动「重新查询」且无数据时显示）
const ablError = ref(false)        // 查询失败 / 无有效数据
const ablQueried = ref(false)      // 是否已查询过（避免重复调用）
const ablHourKey = ref('')         // ★ 当前缓存所属「小时键」：YYYYMMDDHH（一小时一查）

/* ════════════════════════════════════════════════
   ★ DPPM 云端（2A / 2B）· 完整对齐 ABL 前端层（2026-09-21）
   - 后端 dppm_cloud_data 与 abl_cloud_data 同款：服务端 2h 持久缓存 + 兜底种子 + 后台静默刷新，
     接口【立即】返回缓存，绝不阻塞在机器人上。
   - 与 ABL 唯一的结构差异：DPPM 是 2A/2B 两次独立查询 → 真假必须【按厂】判断
     （每厂带 `seeded`；整份 is_seed 仅当【两厂都是种子】）。因此本层 = ABL 机制的「按厂版」：
       ① 版本号闸门——以后端 _meta.fetched_at 当版本号，只有版本号变了才刷新界面；
       ② 等真值落地——后端把同一版旧值又给一次时，每 60 秒确认一次（DPPM_REPOLL_MS）；
       ③ 拒绝降级——已有真值，后端再给种子也不接受（mergeDppmFabs 按厂执行）；
       ④ 失败指数退避——60s → 120s → … → 封顶 10 分钟，成功一次即重置；
       ⑤ stale 节流——后端说没过期（_meta.stale=false）就不发请求，只留 10 分钟心跳兜底；
       ⑥ localStorage 持久化——**只有真值落本地**，F5 / 重启服务 / 换浏览器首屏即有值；
       ⑦ 全程静默——拉取中 / 失败一律沿用旧数据（不闪 loading、不清空、不消失）。
   - 面板「只取四周」= 展示时取 values 末尾 4 个（dppmStatsFor 内 slice(-4)）。
   ════════════════════════════════════════════════ */
const dppmCloudData = ref(null)   // { fabs: { '2A':{title,unit,xAxis,values,seeded}, '2B':{...} } }
const dppmMeta = ref(null)
const dppmLoading = ref(false)
const dppmQueried = ref(false)
const dppmHourKey = ref('')       // 当前缓存所属「小时键」：YYYYMMDDHH
// ★ 版本号：当前【展示中】数据对应的后端 _meta.fetched_at。
//   只有真值会写它（兜底种子不写）→ 它非空 ⟺ 曾经取到过真值。
const dppmFetchedAt = ref('')
const dppmSavedAt = ref(0)        // 本浏览器收到这份数据的时刻（毫秒）——仅记录/排查用
let dppmInflight = null           // 并发去重（mount/激活/心跳可能同时触发）
let dppmPollTimer = null          // 心跳兜底定时器（DPPM_HEARTBEAT_MS）
let dppmRetryTimer = null         // 失败重试链（单链：一次失败只安排下一次）
let dppmRepollTimer = null        // 「等真值落地」短轮询定时器
let dppmNextAutoAt = 0            // 下一次允许「自动」尝试的时刻（手动 force 不受限）

const DPPM_CACHE_KEY = 'byfab_dppm_cache_v1'
const DPPM_RETRY_BASE_MS = 60 * 1000        // 失败后首次重试间隔：60 秒
const DPPM_RETRY_MAX_MS = 10 * 60 * 1000    // 退避上限：10 分钟
let dppmRetryDelay = DPPM_RETRY_BASE_MS     // 当前退避间隔（成功一次即重置回基准）
// ★「等真值落地」短轮询：后端缓存过期时会【立即把旧值返给你】并同时起后台线程取真值，
//   这时前端拿到的是同一版旧数据，不该当成已刷新，而是每 60 秒再看一眼（只读缓存，几乎无开销）。
//   60 秒与后端 BYFAB_BG_MIN_INTERVAL（后台刷新最小间隔）对齐，不会形成风暴。
const DPPM_REPOLL_MS = 60 * 1000
const DPPM_HEARTBEAT_MS = 10 * 60 * 1000    // 心跳兜底：10 分钟（正常由失败重试链 / 短轮询驱动）

/** DPPM 本地持久化（★ 2026-09-24 修正：种子厂也要落盘）。
 *
 *  旧实现「只把【真值】的厂写进本地缓存」→ 线上出现：
 *    · 后端给来「2A 真值 + 2B 种子」→ 本地只剩 2A；
 *    · F5 后 `dppmCloudData` 只恢复出 2A ⇒ `dppmHasFab('2B')` 恒 false
 *      ⇒ 2B 面板数值显示「—」、点击被「尚未接入真实数据」守卫拦掉（用户报"点都点不了"）；
 *    · 且因本地有版本号 + 后端 meta.stale=false，`dppmAutoBlocked()` 直接跳过自动拉取
 *      ⇒ 2B 再也回不来，只能从 2A 弹窗点「↻ 重新查询」（force）才出现（用户报"刷一下又没了"）。
 *
 *  现在：真值厂与种子厂都落盘（种子厂只用于首屏有结构可渲染，真假由 `seeded` 标记带给上层）；
 *  但**版本号只在「至少有一厂真值」时才落盘** —— 否则 F5 后会被当成"新鲜"而不再拉取真值。
 */
function writeDppmCache(fields) {
  try {
    const src = (fields && fields.fabs) || {}
    const fabs = {}
    let hasReal = false
    for (const fab of ['2A', '2B', '2C', '2D']) {
      const f = src[fab]
      if (!f) continue
      fabs[fab] = f
      if (!f.seeded) hasReal = true
    }
    if (!Object.keys(fabs).length) return        // 一个厂都没有 → 不写
    dppmSavedAt.value = Date.now()
    localStorage.setItem(DPPM_CACHE_KEY, JSON.stringify({
      savedAt: dppmSavedAt.value, hourKey: hourKeyNow(),
      fetchedAt: hasReal ? dppmFetchedAt.value : '',
      hasReal,
      meta: (fields && fields._meta) || null, fabs,
    }))
  } catch (e) { /* 存储不可用（隐私模式等）静默 */ }
}
function readDppmCache() {
  try {
    const raw = localStorage.getItem(DPPM_CACHE_KEY)
    if (!raw) return null
    const p = JSON.parse(raw)
    if (p && p.fabs && Object.keys(p.fabs).length) return p
  } catch (e) { /* 解析失败按无缓存处理 */ }
  return null
}
// ★ 立即恢复上次保存的【结构】（setup 阶段同步执行 → 首次渲染即有值，不依赖任何请求）。
//   ★ 2026-09-24：恢复的厂里可能混着种子（见 writeDppmCache），故 is_seed 按厂重算；
//     版本号按落盘规则恢复（只有含真值才非空）→ 不至于把「只有种子」的本地缓存当成新鲜数据。
const _dppmCache = readDppmCache()
if (_dppmCache) {
  const _fabs = _dppmCache.fabs || {}
  const _present = ['2A', '2B'].map(f => _fabs[f]).filter(Boolean)
  dppmCloudData.value = { fabs: _fabs }
  dppmMeta.value = { ...(_dppmCache.meta || {}), is_seed: _present.length > 0 && _present.every(f => !!f.seeded) }
  dppmFetchedAt.value = _dppmCache.fetchedAt || ''
  dppmHourKey.value = _dppmCache.hourKey || ''
  dppmSavedAt.value = _dppmCache.savedAt || Date.now()
  dppmQueried.value = true
}

// ★ 当前展示的数据里是否还有厂是兜底种子（DPPM 按厂判断真假）。
function dppmHasSeededFab() {
  const d = dppmCloudData.value
  if (!d || !d.fabs) return false
  return ['2A', '2B'].some(f => d.fabs[f] && d.fabs[f].seeded)
}
// ★ 自动路径是否被拦截（手动「重新查询」force 不受限）：
//   数据新鲜（后端 _meta.stale === false）或仍在冷却期 → 跳过本次自动尝试。
//   ★ 2026-09-24：只要还有厂是兜底种子，就**不认「新鲜」** —— 必须放行自动重试，
//     直到该厂取到真值（否则「2A 真值 + 2B 种子」会因新鲜期而再也不重问 2B）。
function dppmAutoBlocked() {
  if (!USE_CLOUD_DPPM) return true
  if (dppmHasSeededFab()) return false
  const m = dppmMeta.value
  if (dppmFetchedAt.value && m && m.stale === false) return true
  return Date.now() < dppmNextAutoAt
}
// ★ 失败后重试：指数退避（60s → 120s → 240s → 480s → 封顶 10 分钟），成功一次即重置。
//   全程旧数据一直展示（只有成功才替换）。单链防叠：每次失败只安排下一次。
function armDppmRetry() {
  clearTimeout(dppmRetryTimer)
  const delay = dppmRetryDelay
  dppmRetryDelay = Math.min(dppmRetryDelay * 2, DPPM_RETRY_MAX_MS)
  dppmRetryTimer = setTimeout(() => {
    dppmRetryTimer = null
    if (USE_CLOUD_DPPM && !dppmAutoBlocked()) loadDppmCloud(false, true)
  }, delay)
}
// ★ 这次响应是否带来了【新数据】——以后端 _meta.fetched_at 当版本号。
//   同版本 = 后端只是把旧值再给了一次（缓存已过期，接口立即返旧值 + 后台去刷新）。
function isNewDppmVersion(meta) {
  const ts = (meta && meta.fetched_at) || ''
  if (!ts) return false                 // 无版本号（兜底种子）→ 不算新数据
  return ts !== dppmFetchedAt.value
}
// ★「等真值落地」短轮询：每 60 秒只读一次服务端缓存，直到版本号变化。单链防叠。
function scheduleDppmRepoll() {
  if (dppmRepollTimer) return
  dppmRepollTimer = setTimeout(() => {
    dppmRepollTimer = null
    // bypass=true：绕过节流（数据虽"看起来新鲜"，但我们知道后端正在刷新，要盯到真值落地）
    if (USE_CLOUD_DPPM) loadDppmCloud(false, true, true)
  }, DPPM_REPOLL_MS)
}
function clearDppmRepoll() {
  if (dppmRepollTimer) { clearTimeout(dppmRepollTimer); dppmRepollTimer = null }
}
// ★「正在等新数据」的状态留痕（界面零标注）：后端把同一版旧值又给了一次时打一次。
//   用 fetched_at 去重 → 同一版数据只打印一行，60 秒轮询不会刷屏。
let _dppmLastWaitLog = ''
function logDppmWaiting(meta) {
  const state = 'wait|' + ((meta && meta.fetched_at) || '')
  if (state === _dppmLastWaitLog) return
  _dppmLastWaitLog = state
  console.info(
    '[ByFab] DPPM 正在等服务器取回新数据 —— 界面继续显示上一次的真值，不做任何变化。\n' +
    '  · 当前显示数据时间 : ' + ((meta && meta.fetched_at) || '(未知)') + '\n' +
    '  · 服务器状态       : ' + ((meta && meta.refreshing) ? '正在后台查询机器人' : '未在查询（上次尝试失败，将按退避重试）') + '\n' +
    '  · 说明             : 前端每 60 秒确认一次，一旦有新数据立即替换显示。'
  )
}

function dppmHasFab(fab) {
  const d = dppmCloudData.value
  return !!(d && d.fabs && d.fabs[fab] && Array.isArray(d.fabs[fab].values) && d.fabs[fab].values.length)
}
// ★ 取某厂 DPPM 数据，并【只取末尾 4 周】（用户要求「还是一样只取四周」）
function dppmStatsFor(fab) {
  const d = dppmCloudData.value
  if (!d || !d.fabs || !d.fabs[fab]) return null
  const f = d.fabs[fab]
  const n = 4
  const xAxis = (f.xAxis || []).slice(-n)
  const values = (f.values || []).slice(-n)
  if (!values.length) return null
  const nums = values.map(v => (v === null || v === undefined || isNaN(Number(v)) ? null : Number(v)))
  const lastIdx = nums.length - 1
  const cur = nums[lastIdx]
  const last = lastIdx >= 1 ? nums[lastIdx - 1] : null
  const wow = (cur !== null && last !== null) ? cur - last : null
  // ★ 2026-09-22（用户拍板）：**DPPM 不是单位**，面板数字 / 浮层 / 弹窗 / 图表一律不显示单位。
  //   此处刻意**无条件置空**（而不是 `f.unit || ''`）——上游形状漂移时可能把指标名塞进 unit
  //   （如 2B 回覆的 yAxis.name="DPPM"），无条件置空才能保证任何来源都改不掉。
  return { title: f.title || '', unit: '', xAxis, values: nums, cur, last, wow }
}
// ★ 按厂合并（抗降级）：DPPM 是 2A/2B 两次独立查询，必然出现「一厂真值、一厂种子」。
//   规则（与 ABL 同精神、但粒度按厂）：
//     · 新来的某厂是种子、而界面已有该厂【真值】 → 保留旧真值（拒绝降级），控制台留痕；
//     · 其余情况一律采用新值（真值升级 / 首次填充 / 该厂本来就没有真值）。
//   最后按合并结果反推 meta.is_seed：只有两厂都还是种子才算"整份是种子"。
function mergeDppmFabs(incoming) {
  // ★ 2026-09-21 修复：prev 必须按【存储形状】取 dppmCloudData.value.fabs。
  //   此前写的是 `dppmCloudData.value || {}` 再 `prev[fab]` —— 而 dppmCloudData 存的是
  //   { fabs:{…} }，于是 prev['2A'] 恒为 undefined → 「界面已有真值，拒绝降级」从未真正生效。
  const prev = (dppmCloudData.value && dppmCloudData.value.fabs) || {}
  const out = {}
  for (const fab of ['2A', '2B']) {
    const nf = incoming && incoming[fab]
    if (!nf) { if (prev[fab]) out[fab] = prev[fab]; continue }
    const pf = prev[fab]
    if (nf.seeded && pf && !pf.seeded) {
      out[fab] = pf
      console.warn('[ByFab] DPPM ' + fab + ' 仅取到兜底种子，界面已有真值，拒绝降级')
    } else {
      out[fab] = nf
    }
  }
  return out
}
// ★ 把一份数据落到界面（只在「确认是新数据」时调用）——「新数据来了才刷新」的唯一入口。
//   与 ABL 的 applyAblPayload 同款：只在内容真的变了才重绘弹窗；只有真值才 persist。
function applyDppmFields(fields, meta, hk, persist) {
  const merged = mergeDppmFabs(fields.fabs)
  // ★ 按厂容错后 fabs 可能只有一个厂（另一厂这轮没拼出来）→ 只对「存在的厂」判断是不是种子；
  //   两厂都用种子 / 只有一个厂且它是种子，才算"整份是种子"。
  const present = ['2A', '2B'].map(f => merged[f]).filter(Boolean)
  const allSeed = present.length > 0 && present.every(f => !!f.seeded)
  // ★ 2026-09-21 修复（用户报障「Console 说数据已就绪、面板还是暗的且点不进去」）：
  //   必须存回 { fabs: merged } 这层包装。此前直接把扁平 map 存进 dppmCloudData，
  //   而 dppmHasFab / dppmStatsFor / renderDppmCloudChart 全部读 `d.fabs[fab]`
  //   —— 形状对不上 → dppmHasFab() 恒 false → KPI 加 .kpi-fake 压暗、点击又被
  //   openPop 的「未接入真实数据」守卫拦掉，于是"数据明明到了却点不进去"。
  const nextFields = { fabs: merged }
  const changed = !dppmCloudData.value || JSON.stringify(nextFields) !== JSON.stringify(dppmCloudData.value)
  dppmCloudData.value = nextFields
  dppmMeta.value = { ...(meta || {}), is_seed: allSeed }
  dppmHourKey.value = hk
  if (persist) {
    // ★ 只有真值才认版本号 / 才落本地缓存（兜底种子不写，否则会挡住后续真值的落地判断）
    dppmFetchedAt.value = (meta && meta.fetched_at) || ''
    dppmSavedAt.value = Date.now()
    writeDppmCache({ fabs: merged, _meta: meta })
  }
  if (changed && pop.value.show && pop.value.curName === 'DPPM') {
    applyDppmPop(pop.value.curFab)             // 弹窗开着 → 旧图立即换新数据重绘
    try { renderDppmCloudChart(pop.value.curFab) } catch (e) {}
  }
}
// ★ 拉取 DPPM 云端数据（对齐 ABL 的 loadAblCloud）：
//   - silent=true（默认自动路径）：后台静默拉取 —— 不显示 loading，
//     成功拿到新数据才替换显示并写回 localStorage；失败/无数据期间沿用旧数据；
//   - force=true（点「↻ 重新查询」）：忽略节流强制拉取，并让后端同步刷一次真值；
//   - bypass=true（「等真值落地」短轮询）：只绕过节流，不当成强制刷新。
async function loadDppmCloud(force = false, silent = false, bypass = false) {
  if (!USE_CLOUD_DPPM) return
  const hk = hourKeyNow()
  // 自动路径节流（手动 force 与 bypass 不受限）：数据新鲜（后端 stale=false）或冷却期内 → 跳过
  if (!force && !bypass && dppmAutoBlocked()) return
  // 并发去重：同一次拉取只发一个请求
  if (dppmInflight) return dppmInflight
  const task = (async () => {
    if (!silent && !dppmCloudData.value) dppmLoading.value = true
    try {
      // ★ force 透传给后端 —— true 时后端同步刷新一次真值（短超时），否则立即返回服务端持久缓存
      const fields = await fetchDppmCloud(force)
      dppmQueried.value = true
      dppmDiag('load', fields, fields && fields._raw)   // ★ DPPM_DIAG（控制台留痕，界面零标注）
      const meta = fields ? (fields._meta || null) : null
      const present = (fields && fields.fabs) ? ['2A', '2B'].map(f => fields.fabs[f]).filter(Boolean) : []
      const allSeed = present.length > 0 && present.every(f => !!f.seeded)
      const hasReal = !!dppmFetchedAt.value      // 非空 ⟺ 曾经取到过真值（兜底种子不写版本号）

      if (!fields) {
        // ① 拿不到任何结构（503 / 形状拼不出）→ 保留旧数据，按退避重试
        if (dppmCloudData.value) dppmHourKey.value = hk
        if (!force) { dppmNextAutoAt = 0; armDppmRetry() }
      } else if (allSeed && hasReal) {
        // ② 已有真值 → 【拒绝降级成兜底数据】。界面保持旧真值不动，稍后按退避再试真值。
        if (!force) { dppmNextAutoAt = 0; armDppmRetry() }
      } else if (allSeed) {
        // ③ 从未取到过真值 → 展示兜底种子（保证面板有结构、不空白），同时去取真值
        applyDppmFields(fields, meta, hk, false)   // persist=false：兜底不写本地缓存
        dppmRetryDelay = DPPM_RETRY_BASE_MS
        if (!force) {
          dppmNextAutoAt = 0
          // 后端正在后台取（种子恒为 stale，每次请求都会触发）→ 60 秒后确认一次，真值一到就换；
          // 后端没在取（通常是上次失败了）→ 转指数退避，避免连不上机器人时空转。
          // ★ 2026-09-24：`meta.stale` 也进短轮询 —— 后端对「还有厂是种子」的缓存恒判 stale，
          //   即使这次没抢到刷新租约（refreshing=false）也值得 60 秒后再看，而不是退避。
          if (meta && (meta.refreshing || meta.stale)) scheduleDppmRepoll()
          else armDppmRetry()
        }
      } else if (isNewDppmVersion(meta)) {
        // ④ 真·新数据（或首次取到真值，含「一厂真一厂种子」的部分真值）→ 刷新界面 + 写回本地缓存
        applyDppmFields(fields, meta, hk, true)
        dppmRetryDelay = DPPM_RETRY_BASE_MS           // 成功一次 → 退避间隔重置回基准
        dppmNextAutoAt = 0                           // 新鲜与否交给后端的 _meta.stale 判定
      } else {
        // ⑤ 后端返回的还是【同一版】旧数据 → 界面不动，也不给新鲜期。
        //    · refreshing=true（后端正在后台取真值）→ 60 秒后再看一眼，直到版本号变化；
        //    · refreshing=false（后台没在取，通常是上一次取失败了）→ 转回指数退避重试。
        //    这正是"服务器开机后用上次真值兜底、等真值查询到了再更新"的落点。
        dppmHourKey.value = hk
        logDppmWaiting(meta)
        // ★ 2026-09-24：`meta.stale`（后端说"还没拿到完整真值"）同样进短轮询 ——
        //   典型场景：2A 已有真值、2B 还是种子 → 版本号暂时不变，但后端会持续重问 2B，
        //   前端必须 60 秒盯一次，而不是转成指数退避（退避会让 2B 长期停在假数据）。
        if (meta && (meta.refreshing || meta.stale)) {
          scheduleDppmRepoll()
        } else {
          dppmRetryDelay = DPPM_RETRY_BASE_MS
          if (!force) { dppmNextAutoAt = 0; armDppmRetry() }
        }
      }
    } catch (e) {
      // ★ 异常 → 沿用已缓存数据（持续显示），按退避间隔再试
      console.warn('[ByFab] DPPM 云端查询失败，沿用已缓存数据，将按退避间隔重试', e)
      dppmQueried.value = true
      if (dppmCloudData.value) dppmHourKey.value = hk
      if (!force) { dppmNextAutoAt = 0; armDppmRetry() }
    } finally {
      dppmLoading.value = false
      dppmInflight = null
    }
  })()
  dppmInflight = task
  return task
}
// ★ 手动「↻ 重新查询」：走 force 路径（后端同步刷一次真值）
async function refreshDppmCloud() {
  if (!USE_CLOUD_DPPM) return
  await loadDppmCloud(true, false)
}
// ★ 低频心跳兜底：每 10 分钟看一眼，未被拦截才静默拉新（页面刚打开等场景的保险）
function scheduleDppmPoll() {
  clearDppmPoll()
  dppmPollTimer = setInterval(() => {
    if (!dppmAutoBlocked()) loadDppmCloud(false, true)
  }, DPPM_HEARTBEAT_MS)
}
function clearDppmPoll() {
  if (dppmPollTimer) { clearInterval(dppmPollTimer); dppmPollTimer = null }
  if (dppmRetryTimer) { clearTimeout(dppmRetryTimer); dppmRetryTimer = null }   // 页停用/卸载同时停掉重试链
  clearDppmRepoll()                                                            // 以及「等真值落地」短轮询
}

// ★ 打开 DPPM 明细弹窗（云端数据驱动；2A=DPPM、2B=抽检量）
function openDppmCloud(fab) {
  // ★ 首屏直显：弹窗立即用「已保存数据」（localStorage/内存缓存）渲染，绝不阻塞等待；
  //   后台静默拉新，成功取到新数据后 applyDppmFields 内联动重绘。
  if (USE_CLOUD_DPPM) loadDppmCloud(false, true)
  pop.value.title = fab + ' · DPPM · 详情分析'
  pop.value.curName = 'DPPM'
  pop.value.curFab = fab
  pop.value.show = true
  applyDppmPop(fab)
  requestAnimationFrame(() => renderDppmCloudChart(fab))
}

// ★ 用当前 dppmCloudData 刷新弹窗统计/分析区（打开弹窗 & 后台取到新数据时共用）
function applyDppmPop(fab) {
  const st = dppmStatsFor(fab)
  const has = v => v !== null && v !== undefined && !isNaN(Number(v))
  const num = v => (v === null || v === undefined || v === '' || isNaN(Number(v)) ? null : Number(v))
  const cur = st ? st.cur : null
  const last = st ? st.last : null
  const wow = st ? st.wow : null
  const unit = (st && st.unit) || ''
  const nWow = num(wow)
  // ★ 周趋势 / 风险等级：复用 ABL 口径「较上周降低→绿(ok) / 升高→红(bad) / 无环比→灰」
  const bt = nWow === null ? null : nWow <= 0
  const btCls = bt === null ? null : (bt ? 'ok' : 'bad')
  const curCls = btCls === 'ok' ? 'g' : (btCls === 'bad' ? 'r' : '')
  const withU = (v, u) => (has(v) ? fmtNum(v) + (u || '') : '')
  curCtx.value = fab + ' · DPPM · 本周' + withU(cur, unit) + (st && st.title ? '（' + st.title + '）' : '')

  popStatsHtml.value =
    '<div class="pop-stat"><div class="pkl">本周数值</div><div class="pkv ' + curCls + '">' + withU(cur, unit) + '</div></div>' +
    '<div class="pop-stat"><div class="pkl">上周数值</div><div class="pkv">' + withU(last, unit) + '</div></div>' +
    '<div class="pop-stat"><div class="pkl">变化幅度</div><div class="pkv ' + (btCls === null ? '' : (btCls === 'ok' ? 'g' : 'r')) + '">' + (bt === null ? '' : ((bt ? '▼' : '▲') + fmtNum(Math.abs(nWow)))) + '</div></div>' +
    '<div class="pop-stat"><div class="pkl">规格目标</div><div class="pkv"></div></div>'

  // ★ 达标状态：用户要求先放空（不给出达标/未达标判定）→ 显示中性占位「—」，不渲染红绿圆点
  popAnaHtml.value =
    '<div class="ana-item"><div class="ana-lbl">达标状态</div><div class="ana-val na">—</div></div>' +
    '<div class="ana-item"><div class="ana-lbl">周趋势</div><div class="ana-val ' + (btCls || '') + '">' + (bt === null ? '' : (bt ? '▼ 改善' : '▲ 恶化')) + '</div></div>' +
    '<div class="ana-item"><div class="ana-lbl">偏差量</div><div class="ana-val ' + (btCls || '') + '">' + (nWow === null ? '' : fmtNum(Math.abs(nWow)) + unit) + '</div></div>' +
    '<div class="ana-item"><div class="ana-lbl">风险等级</div><div class="ana-val ' + (btCls || '') + '">' + (bt === null ? '' : (bt ? '低' : '高')) + '</div></div>'

  popCapaHtml.value = '<div style="font-size:10px;color:var(--t2);text-align:center;padding:8px">AI 云端分析</div>'
  popOcHtml.value = '<div class="p-oc-empty">暂无 Ongoing Case</div>'
}

// 渲染 DPPM 云端图表：pc1 = 当前厂 4 周趋势，pc2 = 2A/2B 对比
function renderDppmCloudChart(fab) {
  if (!pc1.value || !pc2.value) return
  if (chart1) { try { chart1.dispose() } catch (e) {} chart1 = null }
  if (chart2) { try { chart2.dispose() } catch (e) {} chart2 = null }
  const dk = document.documentElement.getAttribute('data-theme') === 'dark'
  const axC = dk ? '#5a7a9a' : '#6a9aba'
  const spC = dk ? '#0a2050' : '#c8daf0'
  const colorOf = name => byfab.fabCol4[name] || '#60d8ff'

  const d = dppmCloudData.value
  if (!d || !d.fabs || !d.fabs[fab]) {
    pc1.value.innerHTML = dppmLoading.value
      ? '<div class="abl-state">⏳ 查询云端中…</div>'
      : '<div class="abl-state no-data">未接入数据</div>'
    pc2.value.innerHTML = ''
    return
  }
  const st = dppmStatsFor(fab)
  if (!st) {
    pc1.value.innerHTML = dppmLoading.value
      ? '<div class="abl-state">⏳ 查询云端中…</div>'
      : '<div class="abl-state no-data">未接入数据</div>'
    pc2.value.innerHTML = ''
    return
  }
  const xLabels = st.xAxis
  const unit = st.unit
  const base = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', backgroundColor: dk ? '#08162a' : '#f0f6fc', textStyle: { color: dk ? '#d8e8f8' : '#0a2858', fontSize: 11 } },
    xAxis: {
      type: 'category', name: '周别', nameTextStyle: { color: axC, fontSize: 10 }, data: xLabels,
      axisLabel: { color: axC, fontSize: 11, interval: 0, rotate: xLabels.length > 6 ? 30 : 0, margin: 10 },
      axisLine: { lineStyle: { color: axC } }, splitLine: { show: false }
    },
    yAxis: {
      type: 'value', name: unit, nameTextStyle: { color: axC, fontSize: 10 },
      splitNumber: 4, minInterval: 1,
      axisLabel: { color: axC, fontSize: 10 }, splitLine: { lineStyle: { color: spC, type: 'dashed' } }
    },
    grid: { top: 44, right: 24, bottom: 36, left: 58 }
  }
  // 图1 · 当前厂 4 周趋势（只取四周：dppmStatsFor 已 slice(-4)）
  pc1.value.innerHTML = ''
  resetReveal()
  chart1 = echarts.init(pc1.value)
  chart1.setOption(Object.assign({}, base, {
    title: { text: (st.title || 'DPPM') + ' · ' + fab, left: 'center', top: 2, textStyle: { color: dk ? '#d8e8f8' : '#0a2858', fontSize: 13 } },
    series: [{
      name: fab, type: 'line', smooth: true, data: st.values,
      lineStyle: { color: colorOf(fab), width: 2 }, itemStyle: { color: colorOf(fab) },
      symbol: 'circle', symbolSize: 6,
      label: { show: true, position: 'top', color: dk ? '#d8e8f8' : '#0a2858', fontSize: 10 },
      areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: colorOf(fab) + '42' }, { offset: 1, color: colorOf(fab) + '08' }] } }
    }]
  }))
  // 图2 · 2A/2B 对比（各自取末尾 4 周，2A/2B 周别已对齐到 W2636~W2639）
  pc2.value.innerHTML = ''
  chart2 = echarts.init(pc2.value)
  const allFabs = ['2A', '2B'].filter(fb => dppmHasFab(fb))
  chart2.setOption(Object.assign({}, base, {
    legend: { data: allFabs, top: 4, textStyle: { color: axC, fontSize: 10 }, itemWidth: 12, itemHeight: 10 },
    series: allFabs.map(fb => {
      const s2 = dppmStatsFor(fb)
      return {
        name: fb, type: 'line', smooth: true, data: s2 ? s2.values : [],
        lineStyle: { color: colorOf(fb), width: 2 }, itemStyle: { color: colorOf(fb) },
        symbol: 'circle', symbolSize: 5
      }
    })
  }))
  deferFitCharts()
  revealLineCharts()
}

// ★ 当前小时键（跨整点后自动变化）
function hourKeyNow() {
  const d = new Date()
  const p = n => String(n).padStart(2, '0')
  return `${d.getFullYear()}${p(d.getMonth() + 1)}${p(d.getDate())}${p(d.getHours())}`
}

/* ════════════════════════════════════════════════
   ★ ABL 持久化缓存（localStorage）+ 低频静默轮询：2026-09-07
   - F5 / 关闭重进：直接恢复上次保存的数据 → 首屏即有值，不出现「查询云端中」；
   ★ 2026-09-16 起：**刷新的节奏归后端**（`backend/core/services/bot_refresh.py` 每 2 小时主动拉一次，
     与有没有人打开页面无关）。前端不再自己算 1 小时 TTL，只认后端下发的 `_meta.stale`：
       ① 后端说没过期（stale=false）→ 不发任何请求，直接用缓存；
       ② 后端说过期、正在刷新、或我们还没有真值 → 才去问；问回来据此决策；
       ③ 心跳每 10 分钟醒一次做检查（真正的请求仍受 ① 拦着，所以通常不产生流量）；
       ④ 全程静默：只有成功取到新数据才替换显示并写回缓存；
       ⑤ 拉取中 / 失败 → 旧数据一直保留展示（不闪 loading、不清空、不消失）。
   ★ 2026-09-16 口径补充（用户明确：「把上次拿到的真值当成兜底的缓存，假如服务器关机开机
     就用这个来，并且要保证新数据来了才刷新，在此之前一直显示旧数据」）：
       ⑥ **只有真值才写本地缓存** —— 兜底种子不落本地，避免它在真值到达前污染首屏；
       ⑦ **版本号判新**：以后端 `_meta.fetched_at` 当版本号，**只有版本号变了才刷新界面**。
          后端把同一版旧值又给一次（缓存过期、它已在后台刷新）时 → 界面纹丝不动、也不给新鲜期，
          改为每 60 秒确认一次（`ABL_REPOLL_MS`），直到新数据落地（`scheduleAblRepoll`）；
       ⑧ **拒绝降级**：一旦取到过真值，后端再给兜底种子也不接受，继续显示旧真值。
   ════════════════════════════════════════════════ */
const ABL_CACHE_KEY = 'byfab_abl_cache_v1'
// ★ 2026-09-16：删掉了前端自己的 1 小时 TTL —— 改由【后端拥有节奏】。
//   服务器现在每 2 小时定时主动刷新（backend/core/services/bot_refresh.py，与有没有人访问无关），
//   并把"这份数据过没过期"通过 _meta.stale 下发。前端只认这个标志，前后端只有一套口径，
//   也不受浏览器时钟误差影响。前端职责退化为："后端说没过期就别打扰；说过期了、或正在刷新，就盯着。"
// ★ 2026-09-16：失败重试由「固定 1.5 秒、重到拿到为止」改为【指数退避】。
//   原实现配合后端"每请求现场打一次 680 秒超时的机器人查询"，会在服务器侧形成重试风暴
//   （deploy 到服务器后表现为 ERR_CONNECTION_RESET + 大量 500）。现在后端已改为
//   立即返回缓存 + 后台静默刷新，前端也就不需要高频重试了。
const ABL_RETRY_BASE_MS = 60 * 1000       // 失败后首次重试间隔：60 秒
const ABL_RETRY_MAX_MS = 10 * 60 * 1000   // 退避上限：10 分钟
let ablRetryDelay = ABL_RETRY_BASE_MS     // 当前退避间隔（成功一次即重置回基准值）
// ★ 2026-09-16：「等真值落地」的短轮询间隔。
//   场景：后端缓存已过期，接口会【立即把旧值返给你】并同时起后台线程去取真值。
//   这时前端拿到的是"同一版旧数据"，不该把界面当成已刷新、更不该锁 1 小时，
//   而是每 60 秒再去看一眼（只读服务端缓存，几乎无开销），直到版本号变化为止。
//   60 秒与后端 `BYFAB_BG_MIN_INTERVAL`（后台刷新最小间隔）对齐，不会形成风暴。
const ABL_REPOLL_MS = 60 * 1000
const ABL_HEARTBEAT_MS = 10 * 60 * 1000 // 心跳检测周期：10 分钟（兜底；正常由「失败重试链」驱动）
const ABL_SAVED_AT_FALLBACK = Date.now() // 老缓存无 savedAt 时的兜底（视为刚保存，不立即重查）

function readAblCache() {
  try {
    const raw = localStorage.getItem(ABL_CACHE_KEY)
    if (!raw) return null
    const p = JSON.parse(raw)
    if (p && p.fields && Array.isArray(p.fields.series) && p.fields.series.length) return p
  } catch (e) { /* 解析失败按无缓存处理 */ }
  return null
}
const ablSavedAt = ref(0)              // 本浏览器收到这份数据的时刻（毫秒）—— 仅作记录/排查用，
                                       // ★ 2026-09-16 起不再用它判断新鲜度（改由后端 _meta.stale 判定）
// ★ 2026-09-16：只持久化【真值】。原因见用户需求「把上次拿到的真值当成兜底的缓存，
//   服务器关机开机就用这个来」—— 真值存在服务端与本地，重启/换浏览器首屏即显。
//   兜底种子【不写本地】：它本就是"从未取到真值"时的占位，写进去反而会在真值到达前误导首屏。
function writeAblCache(fields, fetchedAtStr) {
  const t = Date.now()
  ablSavedAt.value = t
  try {
    localStorage.setItem(ABL_CACHE_KEY, JSON.stringify({
      savedAt: t, hourKey: hourKeyNow(), fetchedAt: fetchedAtStr || '', fields,
    }))
  } catch (e) { /* 存储不可用（隐私模式等）静默 */ }
}
// ★ 立即恢复上次保存的数据（setup 阶段同步执行 → 首次渲染即有值，不依赖任何请求）
const _ablCache = readAblCache()
if (_ablCache) {
  ablCloudData.value = _ablCache.fields
  ablMeta.value = _ablCache.fields?._meta || null   // ★ 同步恢复数据来源/时间
  const _cSeed = !!(ablMeta.value && ablMeta.value.is_seed)
  // 只有真值才认版本号；兜底种子一律视为"还没有真值"（否则会挡住后续真值的落地判断）
  ablFetchedAt.value = _cSeed ? '' : (_ablCache.fetchedAt || (ablMeta.value && ablMeta.value.fetched_at) || '')
  ablHourKey.value = _ablCache.hourKey || ''
  ablQueried.value = true
  ablSavedAt.value = _ablCache.savedAt || ABL_SAVED_AT_FALLBACK
}
let ablInflight = null          // 并发去重（mount/激活/心跳可能同时触发）
let ablNextAutoAt = 0           // 下一次允许「自动」尝试的时刻（成功=+1h；失败置 0 → 允许立即重试；手动刷新不设）
let ablRetryTimer = null        // 失败重试链定时器（单链：一次失败只安排下一次）
let ablRepollTimer = null       // 「等真值落地」短轮询定时器（见 ABL_REPOLL_MS）
let ablHourTimer = null

// ★ 自动路径是否被拦截（手动「重新查询」force 不受限）：
//   ★ 2026-09-16：「新鲜」的判据【以后端为准】—— `_meta.stale === false` 即后端认为没过期
//   （后端 TTL 现在是 2 小时，与它的定时刷新周期同源）。这样：
//     · 数据没过期 → 拦下（不发请求，省钱省事）；
//     · 后端说过期 / 从未取到真值 / 有失败冷却 → 放行，前端才去问。
//   兜底种子与"后端只把同一版旧值又给一次"都不算新鲜 → 才能继续把真值盯到手。
function ablAutoBlocked() {
  if (!USE_CLOUD_ABL) return true
  const m = ablMeta.value
  if (ablFetchedAt.value && m && m.stale === false) return true
  return Date.now() < ablNextAutoAt
}

// ★ 失败后重试：指数退避（60s → 120s → 240s → 480s → 封顶 10 分钟），成功一次即重置。
//   全程旧数据一直展示（只有成功才替换）。单链防叠：每次失败只安排下一次。
//   ★ 不再"1.5 秒重到拿到为止"——那会在服务器侧形成重试风暴（见上方常量注释）。
function armAblRetry() {
  clearTimeout(ablRetryTimer)
  const delay = ablRetryDelay
  ablRetryDelay = Math.min(ablRetryDelay * 2, ABL_RETRY_MAX_MS)
  ablRetryTimer = setTimeout(() => {
    ablRetryTimer = null
    if (USE_CLOUD_ABL && !ablAutoBlocked()) loadAblCloud(false, true)
  }, delay)
}

// ★ 2026-09-16：这次响应是否带来了【新数据】—— 以后端 _meta.fetched_at 当版本号。
//   同版本 = 后端只是把旧值再给了一次（典型：缓存已过期，接口立即返回旧值 + 后台线程去刷新），
//   此时【界面不动、不给 1 小时新鲜期】，改为 60 秒后再看一眼，真值落地才刷新。
function isNewAblVersion(meta) {
  const ts = (meta && meta.fetched_at) || ''
  if (!ts) return false                 // 无版本号（兜底种子）→ 不算新数据
  return ts !== ablFetchedAt.value
}

// ★ 「等真值落地」短轮询：每 60 秒只读一次服务端缓存，直到版本号变化。单链防叠。
function scheduleAblRepoll() {
  if (ablRepollTimer) return
  ablRepollTimer = setTimeout(() => {
    ablRepollTimer = null
    // bypass=true：绕过节流（数据虽"看起来新鲜"，但我们知道后端正在刷新，要盯到真值落地）
    if (USE_CLOUD_ABL) loadAblCloud(false, true, true)
  }, ABL_REPOLL_MS)
}
function clearAblRepoll() {
  if (ablRepollTimer) { clearTimeout(ablRepollTimer); ablRepollTimer = null }
}

// ★ 把一份数据落到界面（只在"确认是新数据"时调用）——「新数据来了才刷新」的唯一入口。
//   persist=true 才写本地缓存（只有真值 persist，兜底种子不写，见 writeAblCache 注释）。
function applyAblPayload(fields, meta, hk, persist) {
  const changed = !ablCloudData.value || JSON.stringify(fields) !== JSON.stringify(ablCloudData.value)
  ablCloudData.value = fields
  ablMeta.value = meta
  ablHourKey.value = hk
  ablError.value = false
  if (persist) {
    ablFetchedAt.value = (meta && meta.fetched_at) || ''
    writeAblCache(fields, ablFetchedAt.value)
  }
  logAblSource(meta)
  if (changed && pop.value.show && pop.value.curName === 'ABL触发') {
    applyAblPop(pop.value.curFab)             // 弹窗开着 → 旧图立即换新数据重绘
    try { renderAblCloudChart(pop.value.curFab) } catch (e) {}
  }
}

// ★ 低频心跳兜底：每 10 分钟看一眼，未被拦截才静默拉新（页面刚打开等场景的保险）
function scheduleAblHourPoll() {
  clearAblHourPoll()
  ablHourTimer = setInterval(() => {
    if (!ablAutoBlocked()) loadAblCloud(false, true)
  }, ABL_HEARTBEAT_MS)
}
function clearAblHourPoll() {
  if (ablHourTimer) { clearInterval(ablHourTimer); ablHourTimer = null }
  if (ablRetryTimer) { clearTimeout(ablRetryTimer); ablRetryTimer = null }   // 页停用/卸载同时停掉重试链
  clearAblRepoll()                                                          // 以及「等真值落地」短轮询
}

// ★ 2026-09-16：ABL 数据来源只在【控制台】留痕 —— 界面不加任何标注（用户明确要求"就和正常一样"）。
//   目的：① 上线期间便于排查（F12 一眼看出是真值还是兜底、失败原因是什么）
//         ② 机器人接通后可当场向领导证明"数据是真的"
//   状态没变化就不重复打印，避免退避重试时刷屏。
let _ablLastLogState = ''
function logAblSource(meta) {
  const isSeed = !!(meta && meta.is_seed)
  const state = isSeed ? `seed|${(meta && meta.last_error) || ''}` : `real|${(meta && meta.fetched_at) || ''}`
  if (state === _ablLastLogState) return
  _ablLastLogState = state
  if (isSeed) {
    console.warn(
      '[ByFab] ABL 尚未取到真实数据 —— 当前显示的是兜底占位值（样例数值，仅保证图表结构不空白）。\n' +
      '  · 最近失败原因 : ' + ((meta && meta.last_error) || '(无记录)') + '\n' +
      '  · 最近尝试时间 : ' + ((meta && meta.last_attempt_at) || '(从未尝试)') + '\n' +
      '  · 排查入口     : 浏览器打开 /api/byfab/abl/?diag=1 可看机器人 TCP 可达性与缓存状态\n' +
      '  · 说明         : 服务器一旦能连上机器人，会自动取到真值并【永久保存】为兜底，无需手动操作；\n' +
      '                   界面不会有任何变化（按要求不加标注），想确认是否已接真值请看本行是否变成 info 级别。'
    )
  } else {
    console.info(
      '[ByFab] ABL 已取到真实数据 ✓\n' +
      '  · 数据时间 : ' + ((meta && meta.fetched_at) || '(未知)') + '\n' +
      '  · 该数据已持久化到服务器：重启服务 / 换浏览器都直接显示，无需重新查询。'
    )
  }
}

// ★ 「正在等新数据」的状态留痕（界面同样零标注）：后端把同一版旧值又给了一次时打一次。
//   用 fetched_at 去重 → 同一版数据只打印一行，60 秒轮询不会刷屏。
function logAblWaiting(meta) {
  const state = `wait|${(meta && meta.fetched_at) || ''}`
  if (state === _ablLastLogState) return
  _ablLastLogState = state
  console.info(
    '[ByFab] ABL 正在等服务器取回新数据 —— 界面继续显示上一次的真值，不做任何变化。\n' +
    '  · 当前显示数据时间 : ' + ((meta && meta.fetched_at) || '(未知)') + '\n' +
    '  · 服务器状态       : ' + ((meta && meta.refreshing) ? '正在后台查询机器人' : '未在查询（上次尝试失败，将按退避重试）') + '\n' +
    '  · 说明             : 前端每 60 秒确认一次，一旦有新数据立即替换显示。'
  )
}

// ★ 拉取云端 ABL 数据（每小时缓存 + 首屏旧值直显）：
//   - silent=true（默认自动路径）：后台静默拉取 —— 不显示「查询云端中」，
//     成功拿到新数据才替换显示并写回 localStorage；失败/无数据期间沿用旧数据；
//   - force=true（点「重新查询」）：忽略小时缓存强制拉取，允许 loading（仅在无数据时出现）。
async function loadAblCloud(force = false, silent = false, bypass = false) {
  if (!USE_CLOUD_ABL) return
  const hk = hourKeyNow()
  // ★ 自动路径节流（手动「重新查询」force 不受限；「等真值落地」短轮询 bypass 也不受限）：
  //   数据新鲜（<1h）或冷却期（成功+1h / 失败按退避时长）内 → 跳过本次自动尝试
  if (!force && !bypass && ablAutoBlocked()) return
  // 并发去重：同一次拉取只发一个请求
  if (ablInflight) return ablInflight
  const task = (async () => {
    ablError.value = false
    if (!silent && !ablCloudData.value) ablLoading.value = true
    try {
      // ★ 2026-09-16：把 force 透传给后端 —— true 时后端会同步刷新一次真值（短超时），
      //   否则后端直接返回服务端持久缓存（真值 or 兜底种子），立即响应。
      const fields = await fetchAblCloud(force)
      ablQueried.value = true
      const meta = fields ? (fields._meta || null) : null
      const isSeed = !!(meta && meta.is_seed)
      const hasReal = !!ablFetchedAt.value     // 非空 ⟺ 曾经取到过真值（兜底种子不写版本号）

      if (!fields) {
        // ① 拿不到任何结构（如 503）→ 保留旧数据，按退避重试
        if (ablCloudData.value) ablHourKey.value = hk
        else ablError.value = true
        if (!force) { ablNextAutoAt = 0; armAblRetry() }
      } else if (isSeed && hasReal) {
        // ② 已有真值 → 【拒绝降级成兜底数据】。界面保持旧真值不动，稍后按退避再试真值。
        //    （用户需求：「上次拿到的真值当成兜底」「保证新数据来了才刷新，在此之前一直显示旧数据」）
        if (!force) { ablNextAutoAt = 0; armAblRetry() }
      } else if (isSeed) {
        // ③ 从未取到过真值 → 展示兜底种子（保证面板有结构、不空白），同时去取真值
        applyAblPayload(fields, meta, hk, false)   // persist=false：兜底不写本地缓存
        ablRetryDelay = ABL_RETRY_BASE_MS
        if (!force) {
          ablNextAutoAt = 0
          // 后端正在后台取（种子恒为 stale，每次请求都会触发）→ 60 秒后确认一次，真值一到就换；
          // 后端没在取（通常是上次失败了）→ 转指数退避，避免连不上机器人时空转。
          if (meta && meta.refreshing) scheduleAblRepoll()
          else armAblRetry()
        }
      } else if (isNewAblVersion(meta)) {
        // ④ 真·新数据（或首次取到真值）→ 刷新界面 + 写回本地缓存
        applyAblPayload(fields, meta, hk, true)
        ablRetryDelay = ABL_RETRY_BASE_MS           // 成功一次 → 退避间隔重置回基准
        ablNextAutoAt = 0                           // 新鲜与否交给后端的 _meta.stale 判定
      } else {
        // ⑤ 后端返回的还是【同一版】旧数据 → 界面不动，也不给新鲜期。
        //    · 后端 refreshing=true（它正在后台取真值）→ 60 秒后再看一眼，直到版本号变化；
        //    · refreshing=false（后台没在取，通常是上一次取失败了）→ 转回指数退避重试。
        //    这正是"服务器开机后用上次真值兜底、等真值查询到了再更新"的落点。
        ablHourKey.value = hk
        logAblWaiting(meta)
        if (meta && meta.refreshing) {
          scheduleAblRepoll()
        } else {
          ablRetryDelay = ABL_RETRY_BASE_MS
          if (!force) { ablNextAutoAt = 0; armAblRetry() }
        }
      }
    } catch (e) {
      // ★ 异常 → 沿用已缓存数据（持续显示），按退避间隔再试
      console.warn('[ByFab] ABL 云端查询失败，沿用已缓存数据，将按退避间隔重试', e)
      ablQueried.value = true
      if (ablCloudData.value) ablHourKey.value = hk
      else ablError.value = true
      if (!force) { ablNextAutoAt = 0; armAblRetry() }
    } finally {
      ablLoading.value = false
      ablInflight = null
    }
  })()
  ablInflight = task
  return task
}

/* ── 从云端 series 取指定 FAB 的 本周 / 上周 / 变化幅度(WoW) ──
   实际 JSON 固定带 WoW 列（已由 cloudAbl.extractAblFields 剥离，周数据必然充足），
   此处直接本地计算：变化幅度 = 本周 − 上周。 */
function ablStatsFor(fab) {
  const d = ablCloudData.value
  if (!d) return null
  const s = (d.series || []).find(x => x.name === fab)
  if (!s || !Array.isArray(s.data) || !s.data.length) return null
  const vals = s.data
  const cur = vals[vals.length - 1]
  const last = vals.length >= 2 ? vals[vals.length - 2] : null
  // ★ 变化幅度（WoW）= 本周 − 上周（用户指定逻辑；数据点不足时返回 null，面板显示 —）
  const wow = (!isNaN(Number(cur)) && !isNaN(Number(last))) ? Number(cur) - Number(last) : null
  return { cur, last, wow, unit: d.unit || '' }
}

function openAblCloud(fab) {
  // ★ 首屏直显：弹窗立即用「已保存数据」（localStorage/内存缓存）渲染，绝不阻塞等待；
  //   后台静默拉新（每小时一次），成功取到新数据后 applyAblPop 自动重绘（loadAblCloud 内联动）。
  if (USE_CLOUD_ABL) loadAblCloud(false, true)
  pop.value.title = fab + ' · ABL触发 · 详情分析'
  pop.value.curName = 'ABL触发'
  pop.value.curFab = fab
  pop.value.show = true
  applyAblPop(fab)
  requestAnimationFrame(() => renderAblCloudChart(fab))
}

// ★ 用当前 ablCloudData 刷新弹窗统计/分析区（打开弹窗 & 后台取到新数据时共用）
function applyAblPop(fab) {
  const k = ((byfab.FD[fab] && byfab.FD[fab].kpis) || []).find(x => x.n === 'ABL触发') || {}
  const st = ablStatsFor(fab)
  const cur = st ? st.cur : null
  const last = st ? st.last : null
  const wow = st ? st.wow : null
  const unit = (st && st.unit) || k.u || ''
  const num = v => (v === null || v === undefined || v === '' || isNaN(Number(v)) ? null : Number(v))
  const nWow = num(wow)
  const bt = nWow === null ? null : nWow <= 0          // 周趋势（WoW ≤ 0 = 较上周降低/改善）
  const btCls = bt === null ? null : (bt ? 'ok' : 'bad') // 颜色：较上周降低→绿(ok)，升高→红(bad)
  // ★ 单位统一「次」；无数据显示空（不出现"—件"这类占位）
  const unitShow = String((st && st.unit) || k.u || '').replace(/次数|件/g, '次')   // ★ 单位统一「次」（云端返回可能为「次数/件」）
  const hasVal = v => v !== null && v !== undefined && !isNaN(Number(v))
  const withU = (v, u) => (hasVal(v) ? fmtNum(v) + (u || '') : '')
  // ★ 状态圆点（2026-09-09 用户语义）：达标状态 按【本周数值 0=达标】——
  //   本周数值为 0 → 绿点(达标)；其它（>0 或暂无数据）→ 灰点
  const curVal = hasVal(cur) ? Number(cur) : null
  const dotCls = curVal === 0 ? 'ok' : 'na'
  const dotTip = curVal === null
    ? '暂无本周数据'
    : (curVal === 0 ? '达标（本周 0 次）' : '待关注（本周 ' + fmtNum(curVal) + ' 次）')
  // ★ 风险等级圆点（2026-09-11 用户语义）：与「变化幅度」同口径【较上周变化】——
  //   较上周降低 → 绿点(风险下降)；升高 → 红点(风险上升)；无环比 → 灰点
  const riskCls = btCls === null ? 'na' : btCls
  const riskTip = btCls === null
    ? '暂无环比数据'
    : (btCls === 'ok'
      ? '风险下降（较上周 ▼' + fmtNum(Math.abs(nWow)) + '）'
      : '风险上升（较上周 ▲' + fmtNum(Math.abs(nWow)) + '）')
  const dot = (st, tip) => '<i class="st-dot ' + st + '" title="' + tip + '"></i>'

  curCtx.value = fab + ' · ABL触发 · 本周' + (hasVal(cur) ? fmtNum(cur) + unitShow : '') + ' 目标' + (k.tg || '')

  // ★ 统计框：数值为空时不显示"—"，ABL 单位统一「次」；
  //   ★ 本周数值颜色跟随「达标状态/风险等级」同一判定（较上周变化）：降低→绿(g)、升高→红(r)、无对比→默认
  const curCls = btCls === 'ok' ? 'g' : (btCls === 'bad' ? 'r' : '')
  popStatsHtml.value =
    '<div class="pop-stat"><div class="pkl">本周数值</div><div class="pkv ' + curCls + '">' + withU(cur, unitShow) + '</div></div>' +
    '<div class="pop-stat"><div class="pkl">上周数值</div><div class="pkv">' + withU(last, unitShow) + '</div></div>' +
    '<div class="pop-stat"><div class="pkl">变化幅度</div><div class="pkv ' + (btCls === null ? '' : (btCls === 'ok' ? 'g' : 'r')) + '">' + (bt === null ? '' : ((bt ? '▼' : '▲') + fmtNum(Math.abs(nWow)))) + '</div></div>' +
    '<div class="pop-stat"><div class="pkl">规格目标</div><div class="pkv">' + '' + '</div></div>'

  // ★ 当前数据分析：达标状态=圆点(本周 0→绿 达标 / 其它→灰)；
  //   风险等级=圆点(与变化幅度同口径，较上周降→绿 升→红 无环比→灰)；周趋势/偏差量仍按周变化上色
  popAnaHtml.value =
    '<div class="ana-item"><div class="ana-lbl">达标状态</div><div class="ana-val">' + dot(dotCls, dotTip) + '</div></div>' +
    '<div class="ana-item"><div class="ana-lbl">周趋势</div><div class="ana-val ' + (btCls || '') + '">' + (bt === null ? '' : (bt ? '▼ 改善' : '▲ 恶化')) + '</div></div>' +
    '<div class="ana-item"><div class="ana-lbl">偏差量</div><div class="ana-val ' + (btCls || '') + '">' + (nWow === null ? '' : fmtNum(Math.abs(nWow)) + unitShow) + '</div></div>' +
    '<div class="ana-item"><div class="ana-lbl">风险等级</div><div class="ana-val">' + dot(riskCls, riskTip) + '</div></div>'

  popCapaHtml.value = '<div style="font-size:10px;color:var(--t2);text-align:center;padding:8px">AI 云端分析</div>'
  popOcHtml.value = '<div class="p-oc-empty">暂无 Ongoing Case</div>'
}

// 渲染云端图表：pc1 = 本周 W 趋势（当前 FAB），pc2 = 四厂趋势对比
function renderAblCloudChart(fab) {
  if (!pc1.value || !pc2.value) return
  if (chart1) { try { chart1.dispose() } catch (e) {} chart1 = null }
  if (chart2) { try { chart2.dispose() } catch (e) {} chart2 = null }
  const dk = document.documentElement.getAttribute('data-theme') === 'dark'
  const axC = dk ? '#5a7a9a' : '#6a9aba'
  const spC = dk ? '#0a2050' : '#c8daf0'
  const colorOf = name => byfab.fabCol4[name] || '#60d8ff'

  if (!USE_CLOUD_ABL) {
    pc1.value.innerHTML = '<div class="abl-state">云端未启用（USE_CLOUD_ABL=false）</div>'
    pc2.value.innerHTML = ''
    return
  }
  // ★ 有缓存数据 → 立即绘制（后台轮询/手动刷新期间也持续显示旧数据，不闪「查询云端中」）
  if (!ablCloudData.value) {
    pc1.value.innerHTML = ablLoading.value
      ? '<div class="abl-state">⏳ 查询云端中…</div>'
      : '<div class="abl-state no-data">未接入数据</div>'
    pc2.value.innerHTML = ''
    return
  }
  const d = ablCloudData.value
  // ★ 横坐标直接用机器人 API 返回的原始编号（如 W2637 / WK202633…），不缩写、不简化前缀；
  //   类别轴默认居中显示，仅当编号过多时才旋转避免重叠
  const xLabels = Array.isArray(d.xAxis) ? d.xAxis.map(w => String(w)) : []
  const base = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', backgroundColor: dk ? '#08162a' : '#f0f6fc', textStyle: { color: dk ? '#d8e8f8' : '#0a2858', fontSize: 11 } },
    xAxis: {
      type: 'category', name: '周别', nameTextStyle: { color: axC, fontSize: 10 }, data: xLabels,
      axisLabel: { color: axC, fontSize: 11, interval: 0, rotate: xLabels.length > 6 ? 30 : 0, margin: 10 },
      axisLine: { lineStyle: { color: axC } }, splitLine: { show: false }
    },
    // ★ 限制分割段数与最小间隔，避免 y 轴刻度过密
    yAxis: {
      type: 'value', name: d.unit || '', nameTextStyle: { color: axC, fontSize: 10 },
      splitNumber: 4, minInterval: 1,
      axisLabel: { color: axC, fontSize: 10 }, splitLine: { lineStyle: { color: spC, type: 'dashed' } }
    },
    grid: { top: 44, right: 24, bottom: 36, left: 58 }
  }
  // 图1 · 本周 W 趋势
  pc1.value.innerHTML = ''
  resetReveal()
  chart1 = echarts.init(pc1.value)
  const one = (d.series || []).find(s => s.name === fab)
  chart1.setOption(Object.assign({}, base, {
    title: { text: (d.title || 'ABL 触发') + ' · ' + fab, left: 'center', top: 2, textStyle: { color: dk ? '#d8e8f8' : '#0a2858', fontSize: 13 } },
    series: [{
      name: fab, type: 'line', smooth: true, data: one ? one.data : [],
      lineStyle: { color: colorOf(fab), width: 2 }, itemStyle: { color: colorOf(fab) },
      symbol: 'circle', symbolSize: 6,
      label: { show: true, position: 'top', color: dk ? '#d8e8f8' : '#0a2858', fontSize: 10 },
      areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: colorOf(fab) + '42' }, { offset: 1, color: colorOf(fab) + '08' }] } }
    }]
  }))
  // 图2 · 四厂趋势对比
  pc2.value.innerHTML = ''
  chart2 = echarts.init(pc2.value)
  chart2.setOption(Object.assign({}, base, {
    legend: { data: d.series.map(s => s.name), top: 4, textStyle: { color: axC, fontSize: 10 }, itemWidth: 12, itemHeight: 10 },
    series: d.series.map(s => ({
      name: s.name, type: 'line', smooth: true, data: s.data,
      lineStyle: { color: colorOf(s.name), width: 2 }, itemStyle: { color: colorOf(s.name) },
      symbol: 'circle', symbolSize: 5
    }))
  }))
  // ★ 图表完整渲染后，从左到右匀速“揭开”（GPU 合成，无点出现卡顿）
  deferFitCharts()
  revealLineCharts()
}

/* ★ 弹窗图表尺寸统一适配：弹出动画/布局稳定后延迟两次 resize，
   保证「ABL 云端图」与「其余 KPI 静态图」显示行为完全一致 */
function deferFitCharts() {
  [80, 240].forEach(t => setTimeout(() => {
    try { chart1 && chart1.resize() } catch (e) {}
    try { chart2 && chart2.resize() } catch (e) {}
  }, t))
}

/* ════════════════════════════════════════════════
   ★ 折线「匀速丝滑绘制」动画（用户需求，v3 方案）
   - 原理：图表一次性完整渲染，再用 CSS clip-path「从左到右匀速揭开」——
     可见区域像画笔一样向右扩展，视觉=线条被匀速画出来；
     全程走 GPU 合成（linear transition），无逐点 setOption、无点出现的卡顿；
   - 每次打开弹窗 / 点「重新查询」都会重新触发（重建后重新播放一次）；
   - 结束时清除 clipPath，不影响后续 hover/tooltip 与窗口 resize。
   ════════════════════════════════════════════════ */
const revealCleanup = new WeakMap()
function resetReveal() {
  ;[pc1.value, pc2.value].forEach(el => {
    if (!el) return
    const h = revealCleanup.get(el)
    if (h) { el.removeEventListener('transitionend', h); revealCleanup.delete(el) }
    el.style.transition = 'none'
    el.style.clipPath = ''
  })
}
// durationMs：全程时长（毫秒），linear 匀速
function revealLineCharts(durationMs = 900) {
  ;[pc1.value, pc2.value].forEach(el => {
    if (!el) return
    const h = revealCleanup.get(el)
    if (h) { el.removeEventListener('transitionend', h) }
    // 隐藏 → 强制回流 → 线性展开
    el.style.transition = 'none'
    el.style.clipPath = 'inset(0 100% 0 0)'
    void el.offsetWidth
    el.style.transition = `clip-path ${durationMs}ms linear`
    el.style.clipPath = 'inset(0 0% 0 0)'
    const done = () => {
      revealCleanup.delete(el)
      el.style.transition = 'none'
      el.style.clipPath = ''
    }
    el.addEventListener('transitionend', done, { once: true })
    revealCleanup.set(el, done)
  })
}

// 「重新查询」按钮：忽略小时缓存强制刷新（已有数据期间不闪 loading；
//   成功后由 loadAblCloud 联动：弹窗开着 → applyAblPop + renderAblCloudChart 自动重绘）
async function refreshAblCloud(fab) {
  await loadAblCloud(true, false)
}

/* ════════════════════════════════════════════════
   ★ 执行率钻取面板：数据来自 execRate（getExecRate → 机器人覆盖 / 自动派生）
   ════════════════════════════════════════════════ */
function openExecPanel(fab) {
  // ★ 部分接入（仅 ABL 云端真）：执行率尚无真实数据 → 不打开静态示例钻取
  if (!!ablCloudData.value && !botOk.value) {
    ElMessage.warning(`执行率（${fab}）尚未接入真实数据，暂无法查看明细`)
    return
  }
  const er = getExecRate(fab)
  if (!er) return
  const ok = er.ok, bt = er.trendBetter
  curCtx.value = fab + ' · 执行率 · 本周' + er.value + er.unit + ' 目标' + er.target
  pop.value.title = fab + ' · 执行率 · 详情分析'
  pop.value.curName = '执行率'
  pop.value.show = true

  popStatsHtml.value =
    '<div class="pop-stat"><div class="pkl">本周数值</div><div class="pkv ' + (ok ? 'g' : 'r') + '">' + er.value + er.unit + '</div></div>' +
    '<div class="pop-stat"><div class="pkl">上周数值</div><div class="pkv">' + er.last + er.unit + '</div></div>' +
    '<div class="pop-stat"><div class="pkl">变化幅度</div><div class="pkv ' + (bt ? 'g' : 'r') + '">' + (bt ? '▼' : '▲') + er.delta.toFixed(1) + er.unit + '</div></div>' +
    '<div class="pop-stat"><div class="pkl">规格目标</div><div class="pkv">' + '' + '</div></div>'

  popAnaHtml.value =
    '<div class="ana-item"><div class="ana-lbl">达标状态</div><div class="ana-val ' + (ok ? 'ok' : 'bad') + '">' + (ok ? '✓ 达标' : '✗ 偏差') + '</div></div>' +
    '<div class="ana-item"><div class="ana-lbl">周趋势</div><div class="ana-val ' + (bt ? 'ok' : 'bad') + '">' + (bt ? '▼ 改善' : '▲ 恶化') + '</div></div>' +
    '<div class="ana-item"><div class="ana-lbl">偏差量</div><div class="ana-val ' + (ok ? 'ok' : 'bad') + '">' + er.delta.toFixed(1) + er.unit + '</div></div>' +
    '<div class="ana-item"><div class="ana-lbl">风险等级</div><div class="ana-val ' + (ok ? 'ok' : (bt ? 'warn' : 'bad')) + '">' + er.risk + '</div></div>'

  popCapaHtml.value = er.capa && er.capa.length
    ? er.capa.map(c => '<div class="capa-item"><div class="capa-dot ' + c.s + '"></div><div class="capa-cnt"><div class="capa-t">' + c.t + '</div><div class="capa-m">' + c.m + '<span class="capa-tag">' + c.tag + '</span></div></div></div>').join('')
    : '<div style="font-size:10px;color:var(--t2);text-align:center;padding:8px">暂无 CAPA 条目</div>'

  popOcHtml.value = er.oc && er.oc.length
    ? er.oc.map(o => {
      const sl = o.st === 'open' ? 'Open' : o.st === 'prog' ? '进行中' : 'Done'
      return '<div class="p-oc-item"><div class="p-oc-hd"><span class="p-oc-id">' + o.id + '</span><span class="p-oc-t">' + o.t + '</span><span class="p-oc-st ' + o.st + '">' + sl + '</span></div><div class="p-oc-meta">负责: ' + o.own + ' · 到期: ' + o.due + '</div><div class="p-oc-bar"><div class="p-oc-fill" style="width:' + o.pct + '%"></div></div></div>'
    }).join('')
    : '<div class="p-oc-empty">暂无 Ongoing Case</div>'

  // 等待 DOM（popov 从 display:none 切到 flex）后再初始化图表
  requestAnimationFrame(() => buildExecCharts(fab, er))
}

function buildExecCharts(fab, er) {
  if (!pc1.value || !pc2.value) return
  const dk = document.documentElement.getAttribute('data-theme') === 'dark'
  const axC = dk ? '#5a7a9a' : '#6a9aba'
  const spC = dk ? '#0a2050' : '#c8daf0'
  const base = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', backgroundColor: dk ? '#08162a' : '#f0f6fc', textStyle: { color: dk ? '#d8e8f8' : '#0a2858', fontSize: 10 } },
    grid: { top: 22, right: 14, bottom: 22, left: 42 },
    xAxis: { type: 'category', data: er.weeks.map((_, i) => 'W' + (i + 1)), axisLabel: { color: axC, fontSize: 10 }, axisLine: { lineStyle: { color: axC } }, splitLine: { show: false } },
    yAxis: { type: 'value', axisLabel: { color: axC, fontSize: 9 }, splitLine: { lineStyle: { color: spC, type: 'dashed' } } }
  }
  if (chart1) { try { chart1.dispose() } catch (e) {} }
  resetReveal()
  chart1 = echarts.init(pc1.value)
  chart1.setOption(Object.assign({}, base, {
    series: [
      { name: '执行率', type: 'line', smooth: true, data: er.weeks, lineStyle: { color: er.color, width: 2 }, itemStyle: { color: er.color }, symbol: 'circle', symbolSize: 6, label: { show: true, position: 'top', color: dk ? '#d8e8f8' : '#0a2858', fontSize: 10, formatter: p => p.value + er.unit }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: er.color + '42' }, { offset: 1, color: er.color + '08' }] } } },
      { name: '目标', type: 'line', data: [er.tgtLine, er.tgtLine, er.tgtLine, er.tgtLine], lineStyle: { color: '#ff6060', type: 'dashed', width: 1.5 }, symbol: 'none' }
    ]
  }))
  if (chart2) { try { chart2.dispose() } catch (e) {} }
  chart2 = echarts.init(pc2.value)
  const s4 = byfab.fabList.map(f => {
    const d2 = er.compare && er.compare[f] ? er.compare[f] : []
    return { name: f, type: 'line', smooth: true, data: d2, lineStyle: { color: byfab.fabCol4[f], width: 2 }, itemStyle: { color: byfab.fabCol4[f] }, symbol: 'circle', symbolSize: 5 }
  })
  chart2.setOption(Object.assign({}, base, {
    legend: { data: byfab.fabList, top: 0, textStyle: { color: axC, fontSize: 9 }, itemWidth: 10, itemHeight: 10 },
    grid: { top: 28, right: 14, bottom: 22, left: 42 },
    series: s4
  }))
  deferFitCharts()
  revealLineCharts()
}

function buildCharts(fab, idx, data, unit, color, tgt, k) {
  if (!pc1.value || !pc2.value) return
  const dk = document.documentElement.getAttribute('data-theme') === 'dark'
  const axC = dk ? '#5a7a9a' : '#6a9aba'
  const spC = dk ? '#0a2050' : '#c8daf0'
  const base = {
    backgroundColor: 'transparent',
    tooltip: { trigger: 'axis', backgroundColor: dk ? '#08162a' : '#f0f6fc', textStyle: { color: dk ? '#d8e8f8' : '#0a2858', fontSize: 10 } },
    grid: { top: 22, right: 14, bottom: 22, left: 42 },
    xAxis: { type: 'category', data: data.map((_, i) => 'W' + (i + 1)), axisLabel: { color: axC, fontSize: 10 }, axisLine: { lineStyle: { color: axC } }, splitLine: { show: false } },
    yAxis: { type: 'value', axisLabel: { color: axC, fontSize: 9 }, splitLine: { lineStyle: { color: spC, type: 'dashed' } } }
  }
  if (chart1) { try { chart1.dispose() } catch (e) {} }
  resetReveal()
  chart1 = echarts.init(pc1.value)
  // ★ 目标线仅在 tgt 有效时绘制（用户 09-21：DPPM 不设规格目标 → openPop 传 null → 不画线不显示图例）
  const series1 = [
    { name: k.n, type: 'line', smooth: true, data, lineStyle: { color, width: 2 }, itemStyle: { color }, symbol: 'circle', symbolSize: 6, label: { show: true, position: 'top', color: dk ? '#d8e8f8' : '#0a2858', fontSize: 10, formatter: p => p.value + unit }, areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1, colorStops: [{ offset: 0, color: color + '42' }, { offset: 1, color: color + '08' }] } } }
  ]
  if (tgt !== null && tgt !== undefined && tgt !== '' && !isNaN(Number(tgt))) {
    series1.push({ name: '目标', type: 'line', data: [Number(tgt), Number(tgt), Number(tgt), Number(tgt)], lineStyle: { color: '#ff6060', type: 'dashed', width: 1.5 }, symbol: 'none' })
  }
  chart1.setOption(Object.assign({}, base, { series: series1 }))
  if (chart2) { try { chart2.dispose() } catch (e) {} }
  chart2 = echarts.init(pc2.value)
  const s4 = byfab.fabList.map(f => {
    const d2 = (byfab.PT[f] && byfab.PT[f][idx]) ? byfab.PT[f][idx][0] : data
    return { name: f, type: 'line', smooth: true, data: d2, lineStyle: { color: byfab.fabCol4[f], width: 2 }, itemStyle: { color: byfab.fabCol4[f] }, symbol: 'circle', symbolSize: 5 }
  })
  chart2.setOption(Object.assign({}, base, {
    legend: { data: byfab.fabList, top: 0, textStyle: { color: axC, fontSize: 9 }, itemWidth: 10, itemHeight: 10 },
    grid: { top: 28, right: 14, bottom: 22, left: 42 },
    series: s4
  }))
  deferFitCharts()
  revealLineCharts()
}

function closePop() {
  pop.value.show = false
  resetReveal()
  if (chart1) { try { chart1.dispose() } catch (e) {} chart1 = null }
  if (chart2) { try { chart2.dispose() } catch (e) {} chart2 = null }
}
function openRag(e) {
  e.preventDefault()
  window.open(RAG_URL + '?ctx=' + encodeURIComponent(curCtx.value), '_blank')
}

onBeforeUnmount(() => {
  clearAblHourPoll()
  clearDppmPoll()
  resetReveal()
  if (chart1) { try { chart1.dispose() } catch (e) {} }
  if (chart2) { try { chart2.dispose() } catch (e) {} }
})
</script>

<style lang="scss" scoped>
/* ════════════════════════════════════════════════
   BY FAB 总览 · 严格对齐 Q.html（类名 / 结构 / 样式）
   ════════════════════════════════════════════════ */
.byfab { flex: 1; display: flex; flex-direction: column; gap: .5vh; min-height: 0; background: var(--bg-main); }
/* ★ 假数据暗显（DATA_ONLINE=false 时）：
   - 主面板数据（byfab_data 机器人）尚未接入 → 数据区整体压暗，区分「假数据/真数据」
   - 标题栏 pbar 与明细弹窗 popov（根节点直接子节点，在数据区外）保持常亮可点
   - 真实数据接入成功（fetchByFab 返回 FD/fabList 契约）→ DATA_ONLINE=true 自动点亮
   - 不叠加任何 per-面板额外暗化，弹窗内 ABL 云端图表不受影响 */
.byfab.dim-all .ov-strip,
.byfab.dim-all .content-area { filter: grayscale(.72) brightness(.62); opacity: .62; transition: filter .35s, opacity .35s; }
.byfab:not(.dim-all) .ov-strip,
.byfab:not(.dim-all) .content-area { filter: none; opacity: 1; transition: filter .35s, opacity .35s; }

/* Hover Tip */
.htip { display: none; position: fixed; z-index: 500; background: var(--bg-pop); border: 1.5px solid var(--bpop); border-radius: 14px; padding: 14px 16px; width: min(380px, 25vw); box-shadow: var(--bpop-g); pointer-events: none; }
.htip.show { display: block; }
.htip-hd { font-size: 11px; font-weight: 700; color: var(--t1); margin-bottom: 10px; display: flex; align-items: center; gap: 6px; }
.htip-hd::before { content: ''; width: 3px; height: 13px; background: var(--ac); border-radius: 2px; display: inline-block; box-shadow: 0 0 6px rgba(0, 216, 255, .40); }
.htip-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 8px; }
.htip-card { background: rgba(10, 30, 70, .55); border: 1px solid rgba(50, 140, 255, .30); border-radius: 10px; padding: 8px 10px; }
.htip-fab { font-size: 10px; font-weight: 700; margin-bottom: 4px; }
.htip-val { font-size: 18px; font-weight: 700; line-height: 1.1; }
.htip-extra { font-size: 9px; color: var(--t2); margin-top: 2px; }
.htip-badge { display: inline-block; font-size: 8px; padding: 1px 5px; border-radius: 5px; margin-top: 3px; font-weight: 600; }
.htip-badge.ok { background: var(--okg); color: var(--ok); border: 1px solid rgba(0, 240, 176, .36); }
.htip-badge.bad { background: var(--bdg); color: var(--bd); border: 1px solid rgba(255, 96, 96, .36); }
.htip-badge.warn { background: var(--wng); color: var(--wn); border: 1px solid rgba(255, 208, 64, .36); }
.htip-ft { font-size: 9px; color: var(--t2); text-align: center; margin-top: 5px; border-top: 1px solid rgba(0, 100, 200, .20); padding-top: 5px; }

/* ══ 标题栏 ══ */
.pbar { display: flex; align-items: center; justify-content: space-between; flex-shrink: 0; margin-bottom: 1px; }
.ptag { background: var(--bg-card); border: 1px solid var(--bc); color: var(--t2); font-size: clamp(8px, .58vw, 10px); padding: 2px 8px; border-radius: 6px; }
.ptitle { font-size: clamp(11px, .8vw, 14px); font-weight: 500; color: var(--t1); letter-spacing: .8px; margin-left: .5vw; }
.ptitle span { color: var(--ok); }
.pweek { margin-left: .6vw; font-size: clamp(9px, .62vw, 11px); color: var(--t2); background: rgba(0, 120, 220, .14); border: 1px solid rgba(60, 160, 255, .38); padding: 2px 9px; border-radius: 10px; white-space: nowrap; }
.pright { display: flex; align-items: center; gap: .5vw; }
.bsm { background: var(--bg-card); border: 1px solid var(--bc); color: var(--tn); font-size: clamp(9px, .62vw, 11px); padding: 3px 10px; border-radius: 6px; cursor: pointer; transition: all .18s; }
.bsm:hover, .bsm.act { background: rgba(0, 120, 220, .28); border-color: rgba(60, 160, 255, .52); color: var(--tna); }

/* ══ KPI 横排卡 ══ */
.ov-strip { display: flex; gap: .6vw; flex-shrink: 0; }
.ov-card { flex: 1; background: var(--bg-card); border: 1.5px solid var(--bc); border-radius: 12px; box-shadow: var(--bc-g); padding: .36vh .8vw; display: flex; align-items: center; gap: .7vw; position: relative; overflow: hidden; cursor: pointer; transition: border-color .25s, box-shadow .25s; }
/* 顶部类型色线（静态）：e=青 / d=红 / a=绿 */
.ov-card::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px; border-radius: 12px 12px 0 0; }
.ov-card.e::before { background: linear-gradient(90deg, transparent, rgba(100, 200, 255, .75) 40%, transparent); }
.ov-card.d::before { background: linear-gradient(90deg, transparent, rgba(255, 100, 100, .75) 40%, transparent); }
.ov-card.a::before { background: linear-gradient(90deg, transparent, rgba(0, 240, 176, .75) 40%, transparent); }
.ov-card:hover { border-color: rgba(60, 160, 255, .55); box-shadow: 0 0 0 1.5px rgba(40, 140, 255, .20), 0 5px 28px rgba(0, 120, 255, .20); }
.ov-info { flex: 1; min-width: 0; }
.ov-name { font-size: clamp(10px, .7vw, 13px); font-weight: 600; color: var(--t2); }
.ov-tgt { font-size: clamp(7.5px, .45vw, 9px); color: var(--t3); font-weight: 500; }
.ov-right { text-align: right; }
.ov-num { font-size: clamp(20px, 1.8vw, 32px); font-weight: 700; line-height: 1; }
.ov-num.ok { color: var(--ok); text-shadow: var(--ok-s); }
.ov-num.bad { color: var(--bd); text-shadow: var(--bd-s); }
.ov-num.warn { color: var(--wn); text-shadow: var(--wn-s); }
.ov-sub { font-size: clamp(8px, .48vw, 9px); color: var(--t3); }

/* ══ content area ══ */
.content-area { display: grid; grid-template-columns: 1fr 260px; gap: .6vw; flex: 1; overflow: hidden; min-height: 0; }

/* ══ FAB 2×2 ══ */
.fab-grid { display: grid; grid-template-columns: repeat(2, 1fr); grid-template-rows: repeat(2, 1fr); gap: .55vw; overflow: hidden; }
.fab-panel { background: var(--bg-panel); border: 2px solid var(--bf); border-radius: 14px; box-shadow: var(--bf-g); display: flex; flex-direction: column; overflow: hidden; position: relative; transition: border-color .25s; }
/* 顶部类型色线（静态）：2A 绿 / 2B 蓝 / 2C 黄 / 2D 紫 */
.fab-panel::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2.5px; border-radius: 14px 14px 0 0; }
.fab-panel[data-fab="2A"]::before { background: linear-gradient(90deg, transparent, rgba(0, 240, 176, .80) 40%, transparent); }
.fab-panel[data-fab="2B"]::before { background: linear-gradient(90deg, transparent, rgba(60, 200, 255, .80) 40%, transparent); }
.fab-panel[data-fab="2C"]::before { background: linear-gradient(90deg, transparent, rgba(255, 208, 64, .80) 40%, transparent); }
.fab-panel[data-fab="2D"]::before { background: linear-gradient(90deg, transparent, rgba(180, 140, 255, .80) 40%, transparent); }
/* ★ 该 FAB 无数据块时：仅轻量提示（虚线边框 + 轻微降透明），不破坏原始配色 */
.fab-panel.no-data { border-style: dashed; border-color: rgba(90, 110, 140, .45); opacity: .82; }
.fab-panel.no-data .fab-status { color: var(--t3); }
.fab-hdr { display: flex; align-items: center; padding: .42vh .8vw; border-bottom: 1.5px solid rgba(50, 150, 255, .30); gap: .5vw; flex-shrink: 0; background: var(--bg-fab-hdr); }
.fab-badge { font-size: clamp(20px, 1.62vw, 27px); font-weight: 800; letter-spacing: 2px; padding: 2px 9px; border-radius: 8px; line-height: 1.1; }
.fab-badge.A { background: rgba(0, 240, 176, .12); color: #00f0b0; border: 1px solid rgba(0, 240, 176, .32); box-shadow: 0 0 10px rgba(0, 240, 176, .20); }
.fab-badge.B { background: rgba(60, 200, 255, .12); color: #60d8ff; border: 1px solid rgba(60, 200, 255, .32); box-shadow: 0 0 10px rgba(60, 200, 255, .20); }
.fab-badge.C { background: rgba(255, 208, 64, .12); color: #ffd040; border: 1px solid rgba(255, 208, 64, .32); box-shadow: 0 0 10px rgba(255, 208, 64, .20); }
.fab-badge.D { background: rgba(180, 140, 255, .12); color: #d0b0ff; border: 1px solid rgba(180, 140, 255, .32); box-shadow: 0 0 10px rgba(180, 140, 255, .20); }
.fab-status { font-size: clamp(9px, .62vw, 12px); padding: 2px 8px; border-radius: 20px; font-weight: 600; }
.fab-status.ok { background: var(--okg); color: var(--ok); border: 1px solid rgba(0, 240, 176, .28); }
.fab-status.bad { background: var(--bdg); color: var(--bd); border: 1px solid rgba(255, 96, 96, .28); }
.fab-status.warn { background: var(--wng); color: var(--wn); border: 1px solid rgba(255, 208, 64, .28); }
/* KPI cell */
.fab-kpis { display: grid; grid-template-columns: repeat(3, 1fr); gap: 3px; padding: .36vh .42vw; flex: 1; overflow: hidden; }
.kpi-cell { background: var(--bf-cell-bg); border: 1.2px solid var(--bcell); border-radius: 10px; padding: .4vh .52vw .32vh; display: flex; flex-direction: column; justify-content: space-between; cursor: pointer; transition: background .18s, border-color .18s, box-shadow .18s; position: relative; }
.kpi-cell:hover { background: var(--bf-cell-bg-h); border-color: var(--bcell-h); box-shadow: 0 0 0 1px rgba(40, 130, 220, .18), 0 2px 12px rgba(0, 100, 200, .16); }
/* ★ 未接入真实数据的示例 KPI：整体压暗 + 虚线边框 + 不可点击（不再"假数据一起亮"） */
.kpi-cell.kpi-fake { opacity: .42; filter: grayscale(.85); cursor: default; pointer-events: auto; border-style: dashed; border-color: rgba(100, 120, 150, .5); }
.kpi-cell.kpi-fake:hover { background: var(--bf-cell-bg); border-color: rgba(100, 120, 150, .5); box-shadow: none; }
.kpi-cell.kpi-fake .kpi-val { color: var(--t4); }
.kpi-cell.kpi-fake .kpi-delta { color: var(--t4); }
.kpi-name { font-size: clamp(10.5px, .75vw, 13px); font-weight: 600; color: var(--tkn); padding-right: 20px; line-height: 1.2; }
.kpi-cell.dev-pending .kpi-name { color: var(--t4); }
.kpi-val { font-size: clamp(14px, 1.08vw, 18px); font-weight: 700; color: var(--t1); line-height: 1.15; letter-spacing: -.2px; }
.kpi-cell.dev-pending .kpi-val { color: var(--t4); }
.kpi-bot { display: flex; align-items: center; gap: 4px; }
.kpi-tgt { font-size: clamp(8px, .48vw, 10px); color: var(--tkt); font-weight: 600; }
.kpi-delta { font-size: clamp(8px, .5vw, 10px); font-weight: 700; margin-left: auto; }
.kpi-delta.up { color: var(--bd); } .kpi-delta.dn { color: var(--ok); } .kpi-delta.na { color: var(--t4); }
.kpi-dot { position: absolute; top: 7px; right: 8px; width: 12px; height: 12px; border-radius: 50%; transition: box-shadow .3s; }
/* 红/绿状态点：呼吸光晕（dotBreath 定义于 global.scss，光晕色随变体） */
.kpi-dot.ok { background: var(--ok); --dot-glow: rgba(0, 240, 176, .72); animation: dotBreath 1.8s ease-in-out infinite; }
.kpi-dot.warn { background: var(--wn); box-shadow: var(--wn-s); }
.kpi-dot.bad { background: var(--bd); --dot-glow: rgba(255, 96, 96, .72); animation: dotBreath 1.8s ease-in-out infinite; }
.kpi-dot.gray { background: #3a4a5a; box-shadow: none; }
.kpi-cell.dev-pending { opacity: .32; cursor: default; pointer-events: none; }
.dev-tag { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(30, 50, 80, .95); color: var(--t3); font-size: 9px; padding: 2px 6px; border-radius: 4px; border: 1px solid rgba(30, 120, 200, .32); white-space: nowrap; z-index: 2; }
[data-theme="light"] .dev-tag { background: rgba(210, 230, 250, .95); color: #5a8aaa; border-color: #90c0d8; }

/* ══ OC 侧栏 ══ */
.oc-sidebar { background: var(--bg-panel); border: 1.5px solid var(--boc); border-radius: 14px; box-shadow: var(--boc-g); display: flex; flex-direction: column; overflow: hidden; position: relative; }
.oc-sidebar::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2.5px; border-radius: 14px 14px 0 0; background: linear-gradient(90deg, transparent, rgba(180, 140, 255, .78) 30%, rgba(80, 200, 255, .78) 70%, transparent); }
.oc-hdr { display: flex; align-items: center; gap: 8px; padding: .48vh .9vw; border-bottom: 1.5px solid rgba(120, 100, 255, .28); flex-shrink: 0; background: rgba(140, 80, 255, .07); }
.oc-hdr-icon { font-size: 14px; }
.oc-hdr-title { font-size: clamp(12px, .88vw, 15px); font-weight: 800; color: #d0c0f8; letter-spacing: 1px; }
.oc-hdr-cnt { margin-left: auto; background: rgba(140, 80, 255, .18); color: var(--bf-text-soft); font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 12px; border: 1px solid rgba(140, 80, 255, .32); }
.oc-body { flex: 1; overflow-y: auto; padding: 8px; }
.oc-body::-webkit-scrollbar { width: 3px; } .oc-body::-webkit-scrollbar-thumb { background: rgba(120, 100, 255, .28); }
.oc-fab-group { margin-bottom: 8px; }
.oc-fab-lbl { font-size: 9px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; padding: 2px 6px; border-radius: 5px; margin-bottom: 5px; display: inline-block; }
.oc-fab-lbl.A { color: #00f0b0; background: rgba(0, 240, 176, .10); border: 1px solid rgba(0, 240, 176, .24); }
.oc-fab-lbl.B { color: #60d8ff; background: rgba(60, 200, 255, .10); border: 1px solid rgba(60, 200, 255, .24); }
.oc-fab-lbl.C { color: #ffd040; background: rgba(255, 208, 64, .10); border: 1px solid rgba(255, 208, 64, .24); }
.oc-fab-lbl.D { color: #d0b0ff; background: rgba(180, 140, 255, .10); border: 1px solid rgba(180, 140, 255, .24); }
.oc-item { background: rgba(100, 60, 200, .07); border: 1.2px solid rgba(140, 100, 255, .22); border-radius: 8px; padding: 7px 9px; margin-bottom: 4px; transition: background .15s, border-color .15s; }
[data-theme="light"] .oc-item { background: rgba(80, 40, 180, .04); border-color: rgba(100, 60, 200, .18); }
.oc-item:hover { background: rgba(140, 80, 255, .12); border-color: rgba(140, 100, 255, .36); }
.oc-item-hd { display: flex; align-items: center; gap: 5px; margin-bottom: 3px; }
.oc-id { font-size: 8px; font-weight: 700; color: #d0b0ff; background: rgba(140, 80, 255, .16); padding: 1px 5px; border-radius: 4px; flex-shrink: 0; }
.oc-title { font-size: 10px; font-weight: 600; color: var(--t1); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.oc-st { font-size: 8px; padding: 1px 5px; border-radius: 8px; font-weight: 600; flex-shrink: 0; }
.oc-st.open { background: var(--bdg); color: var(--bd); } .oc-st.prog { background: var(--wng); color: var(--wn); } .oc-st.done { background: var(--okg); color: var(--ok); }
.oc-kpi { font-size: 8px; color: var(--t2); margin-bottom: 3px; font-weight: 500; }
.oc-bar { height: 2px; border-radius: 2px; background: var(--trk); overflow: hidden; }
.oc-fill { height: 100%; border-radius: 2px; background: linear-gradient(90deg, rgba(180, 140, 255, .85), rgba(80, 200, 255, .85)); }
.oc-empty { font-size: 11px; color: var(--t2); text-align: center; padding: 20px 10px; }

/* ══ POPOVER ══ */
.popov { display: none; position: fixed; inset: 0; z-index: 300; background: rgba(0, 0, 0, .65); backdrop-filter: blur(5px); align-items: center; justify-content: center; }
.popov.show { display: flex; }
.popbox { background: var(--bg-pop); border: 2px solid var(--bpop); border-radius: 16px; box-shadow: var(--bpop-g); width: min(1180px, 94vw); max-width: 97vw; max-height: 94vh; overflow-y: auto; padding: 18px 22px; position: relative; display: flex; flex-direction: column; gap: 12px; }
.popbox::before { content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2.5px; border-radius: 16px 16px 0 0; background: linear-gradient(90deg, transparent, rgba(0, 216, 255, .78) 30%, rgba(0, 240, 176, .78) 70%, transparent); }
.popclose { position: absolute; top: 14px; right: 16px; cursor: pointer; color: var(--t2); font-size: 18px; transition: color .15s; font-weight: 700; }
.popclose:hover { color: var(--bd); }
.pop-hd { display: flex; align-items: center; justify-content: space-between; }
.pop-title { font-size: clamp(13px, .95vw, 16px); font-weight: 700; color: var(--t1); }
.pop-rag { display: inline-flex; align-items: center; gap: 5px; background: rgba(0, 100, 200, .30); border: 1.5px solid rgba(60, 160, 255, .44); color: var(--ac); font-size: clamp(9px, .68vw, 11px); padding: 5px 12px; border-radius: 8px; cursor: pointer; text-decoration: none; transition: all .2s; font-weight: 600; margin-right: 34px; }
.pop-rag:hover { background: rgba(0, 120, 240, .42); border-color: rgba(80, 180, 255, .52); color: var(--bf-text-bright); }
/* ABL触发 云端：重新查询按钮 + 数据来源提示 + 状态占位 */
.pop-refresh { margin-left: auto; margin-right: 44px; background: rgba(0, 120, 220, .28); border: 1.5px solid rgba(60, 160, 255, .52); color: var(--tna); font-size: clamp(9px, .68vw, 11px); padding: 5px 12px; border-radius: 8px; cursor: pointer; font-weight: 600; transition: all .2s; }
.pop-refresh:hover { background: rgba(0, 130, 240, .42); border-color: rgba(80, 180, 255, .6); color: var(--bf-text-bright); }
.pop-note { grid-column: 1 / -1; background: rgba(0, 110, 200, .16); border: 1.2px solid rgba(60, 160, 255, .34); border-radius: 10px; padding: 9px 12px; font-size: 11px; color: var(--t1); letter-spacing: .5px; }
.abl-state { display: flex; align-items: center; justify-content: center; height: 210px; font-size: 12px; color: var(--t3); text-align: center; background: var(--bf-state-bg); border: 1px dashed rgba(90, 110, 140, .35); border-radius: 8px; letter-spacing: .4px; }
.abl-state.no-data { color: var(--t4); background: var(--bf-state-bg2); border-color: rgba(80, 100, 130, .3); }
/* ABL触发 卡片：与其余 KPI 卡片完全一致，不再额外压暗 */
/* 弹窗 4格摘要 */
.pop-stats { display: grid; grid-template-columns: repeat(4, 1fr); gap: 8px; }
.pop-stat { background: var(--bf-stat-bg); border: 1.2px solid rgba(50, 150, 255, .28); border-radius: 10px; padding: 9px 12px; }
.pop-stat .pkl { font-size: 9px; color: var(--t2); margin-bottom: 3px; font-weight: 600; letter-spacing: .5px; }
.pop-stat .pkv { font-size: clamp(15px, 1.2vw, 20px); font-weight: 700; color: var(--t1); }
.pop-stat .pkv.g { color: var(--ok); text-shadow: var(--ok-s); } .pop-stat .pkv.r { color: var(--bd); text-shadow: var(--bd-s); } .pop-stat .pkv.y { color: var(--wn); text-shadow: var(--wn-s); }
/* 3栏主体 */
.pop-body { display: grid; grid-template-columns: 1.4fr 1fr 1fr; gap: 10px; min-height: 0; }
.pop-sec-t { font-size: 10px; font-weight: 700; color: var(--t2); letter-spacing: 1px; text-transform: uppercase; margin-bottom: 5px; display: flex; align-items: center; gap: 6px; }
.pop-sec-t::before { content: ''; width: 3px; height: 10px; background: var(--ac); border-radius: 2px; display: inline-block; box-shadow: 0 0 7px rgba(0, 216, 255, .50); }
.pop-left { display: flex; flex-direction: column; gap: 8px; }
.pop-tc { background: var(--bf-tc-bg); border: 1.2px solid rgba(50, 150, 255, .24); border-radius: 11px; padding: 9px 11px; }
/* ★ 图表整体放大拉高：原 100px 在真实数据下会塌缩、刻度拥挤 */
.pop-chart { height: 210px; width: 100%; }
.pop-mid { display: flex; flex-direction: column; gap: 8px; }
.pop-ana { background: var(--bf-tc-bg); border: 1.2px solid rgba(50, 150, 255, .24); border-radius: 11px; padding: 11px 12px; }
.ana-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 5px; margin-top: 5px; }
.ana-item { background: var(--bf-ana-bg); border: 1px solid rgba(40, 130, 220, .20); border-radius: 8px; padding: 7px 10px; }
[data-theme="light"] .ana-item { background: var(--bf-ana-bg); }
.ana-lbl { font-size: 9px; color: var(--t2); margin-bottom: 3px; font-weight: 600; }
.ana-val { font-size: 13px; font-weight: 700; color: var(--t1); }
.ana-val.ok { color: var(--ok); } .ana-val.bad { color: var(--bd); } .ana-val.warn { color: var(--wn); }
.st-dot{ display:inline-block; width:11px; height:11px; border-radius:50%; margin-right:6px; vertical-align:-1px; }
.st-dot.ok{ background:var(--ok); box-shadow:0 0 6px rgba(0,212,170,.55); }
.st-dot.bad{ background:var(--bd); box-shadow:0 0 6px rgba(255,95,109,.55); }
.st-dot.na{ background:#6a7a8c; }
.st-txt{ font-size:11px; color:var(--t2); font-weight:600; margin-left:2px; }
.pop-capa { background: var(--bf-capa-bg); border: 1.2px solid rgba(50, 150, 255, .24); border-radius: 11px; padding: 10px 12px; flex: 1; overflow-y: auto; max-height: 175px; display: flex; flex-direction: column; gap: 5px; }
.pop-capa::-webkit-scrollbar { width: 2px; } .pop-capa::-webkit-scrollbar-thumb { background: var(--scr); }
.capa-item { display: flex; align-items: flex-start; gap: 7px; padding: 6px 8px; border-radius: 7px; background: var(--bf-capa-bg); border: 1px solid rgba(40, 130, 220, .18); transition: background .15s; }
[data-theme="light"] .capa-item { background: var(--bf-capa-bg); }
.capa-item:hover { background: rgba(20, 50, 100, .62); }
.capa-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; margin-top: 3px; }
.capa-dot.open { background: var(--bd); box-shadow: var(--bd-s); }
.capa-dot.prog { background: var(--wn); box-shadow: var(--wn-s); }
.capa-dot.done { background: var(--ok); box-shadow: var(--ok-s); }
.capa-cnt { flex: 1; min-width: 0; }
.capa-t { font-size: 11px; font-weight: 600; color: var(--t1); line-height: 1.3; }
.capa-m { font-size: 9px; color: var(--t2); margin-top: 2px; display: flex; gap: 8px; flex-wrap: wrap; }
.capa-tag { padding: 1px 5px; border-radius: 4px; background: var(--acg); color: var(--ac); font-size: 8px; font-weight: 700; }
/* pop OC栏 */
.pop-oc { background: var(--bf-oc-bg); border: 1.2px solid rgba(120, 100, 255, .28); border-radius: 11px; padding: 10px 12px; display: flex; flex-direction: column; gap: 5px; overflow-y: auto; }
.pop-oc::-webkit-scrollbar { width: 2px; } .pop-oc::-webkit-scrollbar-thumb { background: var(--scr); }
.pop-sec-t.oc::before { background: linear-gradient(180deg, #d0b0ff, #60d8ff); box-shadow: 0 0 7px rgba(140, 80, 255, .50); }
.p-oc-item { background: var(--bf-item-bg); border: 1.2px solid rgba(140, 100, 255, .26); border-radius: 7px; padding: 7px 9px; transition: background .15s; }
.p-oc-item:hover { background: var(--bf-item-bg-h); }
.p-oc-hd { display: flex; align-items: center; gap: 5px; margin-bottom: 3px; }
.p-oc-id { font-size: 9px; font-weight: 700; color: var(--bf-text-soft); background: rgba(140, 80, 255, .16); padding: 1px 5px; border-radius: 4px; flex-shrink: 0; }
.p-oc-t { font-size: 11px; font-weight: 600; color: var(--t1); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.p-oc-st { font-size: 8px; padding: 1px 5px; border-radius: 8px; font-weight: 600; flex-shrink: 0; }
.p-oc-st.open { background: var(--bdg); color: var(--bd); } .p-oc-st.prog { background: var(--wng); color: var(--wn); } .p-oc-st.done { background: var(--okg); color: var(--ok); }
.p-oc-meta { font-size: 9px; color: var(--t2); display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 4px; font-weight: 500; }
.p-oc-bar { height: 2px; border-radius: 2px; background: var(--trk); overflow: hidden; }
.p-oc-fill { height: 100%; border-radius: 2px; background: linear-gradient(90deg, #d0b0ff, #60d8ff); }
.p-oc-empty { font-size: 10px; color: var(--t2); text-align: center; padding: 10px 0; }

/* 窄屏降级（与外壳一致） */
@media (max-width: 1100px) {
  .content-area { grid-template-columns: minmax(0, 1fr); }
  .oc-sidebar { display: none; }
}

</style>

<!-- ════════════════════════════════════════════════════════════════
 弹窗内 v-html / innerHTML 注入内容的样式（★ 必须是非 scoped 全局块）
 ────────────────────────────────────────────────────────────────────
 根因：上方 scoped 块中的 .pop-stat/.ana-item/.capa-*/.p-oc-* 等选择器
 编译后会带 [data-v-xxx] 属性限定，而「本周数值/上周数值」等统计框是通过
 v-html 注入的，注入节点不带 scoped 属性 → 边框与颜色从未生效。
 本块以 .byfab 命名空间前缀全局复刻 Q.html 的样式（.pop-stat 边框
 1.2px rgba(50,150,255,.28) 圆角10px、.pkv 颜色 var(--t1)、字重700 等），
 覆盖全部 KPI 菜单（openPop / openExec / openAblCloud 共用同一容器结构）。
 ════════════════════════════════════════════════════════════════ -->
<style lang="scss">
/* ── 数值摘要框（本周数值 / 上周数值 / 变化幅度 / 规格目标）—— 逐项复刻 Q.html .pop-stat ── */
.byfab .pop-stat { background: var(--bf-stat-bg); border: 1.2px solid rgba(50, 150, 255, .28); border-radius: 10px; padding: 9px 12px; }
.byfab .pop-stat .pkl { font-size: 9px; color: var(--t2); margin-bottom: 3px; font-weight: 600; letter-spacing: .5px; }
.byfab .pop-stat .pkv { font-size: clamp(15px, 1.2vw, 20px); font-weight: 700; color: var(--t1); }
.byfab .pop-stat .pkv.g { color: var(--ok); text-shadow: var(--ok-s); }
.byfab .pop-stat .pkv.r { color: var(--bd); text-shadow: var(--bd-s); }
.byfab .pop-stat .pkv.y { color: var(--wn); text-shadow: var(--wn-s); }

/* ── 当前数据分析（达标状态/周趋势/偏差量/风险等级）── */
.byfab .ana-item { background: var(--bf-ana-bg); border: 1px solid rgba(40, 130, 220, .20); border-radius: 8px; padding: 7px 10px; }
[data-theme="light"] .byfab .ana-item { background: var(--bf-ana-bg); }
.byfab .ana-lbl { font-size: 9px; color: var(--t2); margin-bottom: 3px; font-weight: 600; }
.byfab .ana-val { font-size: 13px; font-weight: 700; color: var(--t1); }
.byfab .ana-val.ok { color: var(--ok); } .byfab .ana-val.bad { color: var(--bd); } .byfab .ana-val.warn { color: var(--wn); }
/* ★ 达标状态/风险等级 圆点（v-html 注入，必须放在非 scoped 全局块才会生效；
     曾只写在 scoped 块导致圆点注入但不可见） */
.byfab .st-dot { display: inline-block; width: 11px; height: 11px; border-radius: 50%; margin-right: 6px; vertical-align: -1px; flex-shrink: 0; }
.byfab .st-dot.ok { background: var(--ok); --dot-glow: rgba(0, 240, 176, .70); animation: dotBreath 1.8s ease-in-out infinite; }
.byfab .st-dot.bad { background: var(--bd); --dot-glow: rgba(255, 95, 109, .70); animation: dotBreath 1.8s ease-in-out infinite; }
.byfab .st-dot.na { background: #6a7a8c; }

/* ── CAPA 列表 ── */
.byfab .capa-item { display: flex; align-items: flex-start; gap: 7px; padding: 6px 8px; border-radius: 7px; background: var(--bf-capa-bg); border: 1px solid rgba(40, 130, 220, .18); transition: background .15s; }
[data-theme="light"] .byfab .capa-item { background: var(--bf-capa-bg); }
.byfab .capa-item:hover { background: rgba(20, 50, 100, .62); }
.byfab .capa-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; margin-top: 3px; }
.byfab .capa-dot.open { background: var(--bd); --dot-glow: rgba(255, 96, 96, .70); animation: dotBreath 1.8s ease-in-out infinite; }
.byfab .capa-dot.prog { background: var(--wn); box-shadow: var(--wn-s); }
.byfab .capa-dot.done { background: var(--ok); --dot-glow: rgba(0, 240, 176, .70); animation: dotBreath 1.8s ease-in-out infinite; }
.byfab .capa-cnt { flex: 1; min-width: 0; }
.byfab .capa-t { font-size: 11px; font-weight: 600; color: var(--t1); line-height: 1.3; }
.byfab .capa-m { font-size: 9px; color: var(--t2); margin-top: 2px; display: flex; gap: 8px; flex-wrap: wrap; }
.byfab .capa-tag { padding: 1px 5px; border-radius: 4px; background: var(--acg); color: var(--ac); font-size: 8px; font-weight: 700; }

/* ── Ongoing Case 列表 ── */
.byfab .p-oc-item { background: var(--bf-item-bg); border: 1.2px solid rgba(140, 100, 255, .26); border-radius: 7px; padding: 7px 9px; transition: background .15s; }
.byfab .p-oc-item:hover { background: var(--bf-item-bg-h); }
.byfab .p-oc-hd { display: flex; align-items: center; gap: 5px; margin-bottom: 3px; }
.byfab .p-oc-id { font-size: 9px; font-weight: 700; color: var(--bf-text-soft); background: rgba(140, 80, 255, .16); padding: 1px 5px; border-radius: 4px; flex-shrink: 0; }
.byfab .p-oc-t { font-size: 11px; font-weight: 600; color: var(--t1); flex: 1; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.byfab .p-oc-st { font-size: 8px; padding: 1px 5px; border-radius: 8px; font-weight: 600; flex-shrink: 0; }
.byfab .p-oc-st.open { background: var(--bdg); color: var(--bd); } .byfab .p-oc-st.prog { background: var(--wng); color: var(--wn); } .byfab .p-oc-st.done { background: var(--okg); color: var(--ok); }
.byfab .p-oc-meta { font-size: 9px; color: var(--t2); display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 4px; font-weight: 500; }
.byfab .p-oc-bar { height: 2px; border-radius: 2px; background: var(--trk); overflow: hidden; }
.byfab .p-oc-fill { height: 100%; border-radius: 2px; background: linear-gradient(90deg, #d0b0ff, #60d8ff); }
.byfab .p-oc-empty { font-size: 10px; color: var(--t2); text-align: center; padding: 10px 0; }

/* ── ABL 云端占位态（查询中 / 未启用 / 未接入数据）── */
.byfab .abl-state { display: flex; align-items: center; justify-content: center; height: 210px; font-size: 12px; color: var(--t3); text-align: center; background: var(--bf-state-bg); border: 1px dashed rgba(90, 110, 140, .35); border-radius: 8px; letter-spacing: .4px; }
.byfab .abl-state.no-data { color: var(--t4); background: var(--bf-state-bg2); border-color: rgba(80, 100, 130, .3); }
</style>
