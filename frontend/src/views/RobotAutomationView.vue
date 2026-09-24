<template>
  <div class="robot-view">
    <!-- 页面标题栏（对齐 PreplanView 风格） -->
    <div class="pbar">
      <div style="display:flex;align-items:center">
        <span class="ptag">流程自动化</span>
        <span class="ptitle">作业自动化机器人 <span>· 16项流程</span></span>
        <span class="ptip">点击机器人 → 查看运行状态</span>
      </div>
      <div class="pright">
        <span class="runinfo">运行中 {{ runningCount }} · 待机 {{ standbyCount }}</span>
        <button class="bsm" :class="{act: filter==='all'}" @click="filter='all'">全部机器人</button>
        <button class="bsm" :class="{act: filter==='on'}" @click="filter='on'">运行中</button>
        <button class="bsm" :class="{act: filter==='off'}" @click="filter='off'">待机</button>
      </div>
    </div>

    <!-- 16 机器人 4×4 网格 -->
    <div class="auto-grid">
      <div v-for="(p,i) in filtered" :key="i" class="ac" @click="openRun(i)">
        <!-- 左：图片区（★ 2026-09-22 去掉 CSS 手绘机器人 → 改为「一张照片 ×16」）
             所有卡片共用 ROBOT_IMG 这一张图（base64 优先，见 src/assets/robotBase64.js）；
             图没放/加载失败时自动隐藏，不留破图。 -->
        <div class="ac-robot-zone">
          <div class="ac-num">{{ String(p.o).padStart(2,'0') }}</div>
          <img v-if="!imgFailed" class="ac-img" :src="ROBOT_IMG" alt="" @error="imgFailed = true">
        </div>
        <!-- 右：信息区 -->
        <div class="ac-info">
          <div class="ac-name">{{ p.name }}</div>
          <div class="ac-sub">{{ p.sub }}</div>
          <div class="ac-meta">
            <div class="ac-status" :class="p.run?'on':'off'">
              <div class="ac-status-dot"></div>{{ p.run?'运行中':'待机中' }}
            </div>
            <div class="ac-chip">执行 {{ p.count }}次</div>
            <div class="ac-chip">成功率 {{ p.rate }}</div>
          </div>
        </div>
      </div>
    </div>

    <!-- 运行弹窗 -->
    <div class="runov" :class="{show: showRun}" @click="onOvClick">
      <div class="runbox">
        <span class="runbox-close" @click="closeRun">✕</span>
        <!-- ★ 2026-09-24：弹窗大机器人由 CSS 手绘改为图片，与卡片共用同一个 ROBOT_IMG
             （base64 见 src/assets/robotBase64.js，换图只改那一个文件，两处同时生效） -->
        <div class="run-robot">
          <img v-if="!imgFailed" class="rr-img" :src="ROBOT_IMG" alt="" @error="imgFailed = true">
        </div>
        <div class="run-title">{{ run.title }}</div>
        <div class="run-subtitle">{{ run.sub }}</div>
        <div class="run-status-row">
          <div class="run-stat"><div class="sl">本月执行次数</div><div class="sv g">{{ run.count }}</div></div>
          <div class="run-stat"><div class="sl">成功率</div><div class="sv g">{{ run.rate }}</div></div>
          <div class="run-stat"><div class="sl">平均耗时</div><div class="sv y">{{ run.time }}</div></div>
          <div class="run-stat"><div class="sl">最近运行</div><div class="sv g">{{ run.last }}</div></div>
        </div>
        <div class="run-progress">
          <div class="run-progress-lbl"><span>当前进度</span><span>{{ run.pctText }}</span></div>
          <div class="run-bar"><div class="run-bar-fill" :style="{width: run.pctWidth}"></div></div>
        </div>
        <div class="run-logs">
          <div v-for="(l,i) in run.logs" :key="i" :class="logClass(l)">{{ l }}</div>
        </div>
        <div class="run-btns">
          <button class="run-btn primary" @click="closeRun">立即执行</button>
          <button class="run-btn sec" @click="closeRun">查看日志</button>
          <button class="run-btn sec" @click="closeRun">关闭</button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, nextTick } from 'vue'
// ★ 2026-09-23：机器人图片改为支持 base64 内联（串太长，单独放在 src/assets/robotBase64.js，
//   那边只维护一行 export default 'data:image/png;base64,....'；留空则回退 public/assets/robot.png）。
import ROBOT_BASE64 from '../assets/robotBase64.js'

// ★ 16 项自动化机器人（数据源自 newpage.html 的 procs 定义，保持与甲方面板一致）
const procs = [
  { name:'AN单\n开立', sub:'自动识别异常触发 AN 单建立', run:true, count:248,rate:'98.4%',time:'2.3分',last:'今天 18:52',pct:76,
    logs:['[18:52:01] ✅ 读取数据源，共 32 笔待处理','[18:52:03] ✅ 数据验证通过','[18:52:08] ✅ 成功开立 AN 单 28 笔','[18:52:10] ⚠️ 4 笔缺必填栏位，已告警','[18:52:12] ✅ 流程完成'] },
  { name:'AN单\n周月管理', sub:'定期汇总 AN 单状态推送报表', run:true, count:32, rate:'100%', time:'5.1分',last:'今天 08:00',pct:100,
    logs:['[08:00:01] ✅ 读取本周 AN 单数据 156 笔','[08:00:05] ✅ 生成周汇总报表','[08:00:08] ✅ 邮件推送完成（12位）','[08:00:09] ✅ 月报 Excel 更新至 SharePoint'] },
  { name:'AN单\n结案时效', sub:'监控逾期未结案自动催办', run:true, count:190,rate:'97.2%',time:'1.8分',last:'今天 17:30',pct:88,
    logs:['[17:30:02] ✅ 扫描逾期 AN 单，共 5 笔超时','[17:30:04] ✅ 自动发送催办邮件','[17:30:06] ✅ 更新逾期状态看板','[17:30:08] ⚠️ 1 笔逾期超 15 天，升级通知 Mgr'] },
  { name:'客户稽核系统\nChecklist 收集', sub:'自动汇整客户稽核条目', run:true, count:48, rate:'100%', time:'8.4分',last:'昨天 16:00',pct:100,
    logs:['[16:00:01] ✅ 读取客户稽核系统数据','[16:00:05] ✅ Check list 汇整 86 项','[16:00:09] ✅ 发送给 QE 团队','[16:00:11] ✅ 归档至 SharePoint'] },
  { name:'E-report\nChecklist 收集', sub:'E-report 检查项自动收集汇总', run:true, count:156,rate:'99.1%',time:'3.2分',last:'今天 09:15',pct:95,
    logs:['[09:15:00] ✅ 连接 E-report 系统成功','[09:15:03] ✅ 收集 Check list 共 234 项','[09:15:06] ✅ 异常项目 8 笔已标记红旗','[09:15:09] ✅ 汇总报表推送完成'] },
  { name:'SPC\nKPI 管理', sub:'自动计算 Cpk 并生成 KPI 报表', run:true, count:320,rate:'98.8%',time:'4.5分',last:'今天 06:00',pct:100,
    logs:['[06:00:01] ✅ 读取 SPC 数据，128 个参数','[06:00:08] ✅ 计算 Cpk，均值 1.45','[06:00:12] ✅ 3 个参数告警已标记','[06:00:15] ✅ KPI 月报更新至看板'] },
  { name:'Sample\n点检提醒', sub:'定时推送样品点检任务通知', run:true, count:480,rate:'100%', time:'0.5分',last:'今天 19:00',pct:100,
    logs:['[19:00:00] ✅ 读取今日点检排程 24 站','[19:00:01] ✅ 推送 LINE/Email 提醒','[19:00:02] ✅ 12/24 站已回报完成','[19:00:02] ⚠️ 12 站待完成，已二次提醒'] },
  { name:'出货\n检验报告', sub:'自动产出 OQC 出货检验报告', run:false,count:88, rate:'96.5%',time:'6.8分',last:'今天 14:20',pct:0,
    logs:['[14:20:01] ✅ 读取当日出货清单 32 批','[14:20:05] ✅ 检验数据匹配，28 批合格','[14:20:08] ⚠️ 4 批 DPPM 超标阻挡出货','[14:20:12] ✅ 出货报告 PDF 发送客户'] },
  { name:'自动\n建Chart', sub:'异常数据自动生成分析图表', run:true, count:210,rate:'99.5%',time:'2.1分',last:'今天 18:00',pct:82,
    logs:['[18:00:01] ✅ 侦测 12 笔异常数据触发','[18:00:03] ✅ 自动绘制 Pareto/趋势图','[18:00:05] ✅ 图表嵌入 PowerPoint 模板','[18:00:07] ✅ 发送至相关工程师信箱'] },
  { name:'Q工单管理\n自动开立&关闭', sub:'品质工单全流程自动化监控', run:true, count:165,rate:'97.6%',time:'3.8分',last:'今天 17:45',pct:70,
    logs:['[17:45:00] ✅ 侦测异常，工单开立条件触发','[17:45:02] ✅ 自动开立 Q 工单 8 笔','[17:45:06] ✅ 逾期工单 3 笔已催办','[17:45:09] ⚠️ 1 笔逾期升级通知主管'] },
  { name:'SPL/MRB Code\n自动申请&建档', sub:'特殊放行码自动化管理', run:false,count:42, rate:'98.0%',time:'5.5分',last:'昨天 15:00',pct:0,
    logs:['[15:00:01] ✅ 读取待申请 SPL 清单 8 笔','[15:00:04] ✅ 自动填写申请表单','[15:00:08] ✅ MRB Code 建档完成','[15:00:10] ✅ 关联数据更新完成'] },
  { name:'SQC 自动\n库存报表', sub:'水位/进出/锁帐/EDA 自动上抛', run:true, count:60, rate:'100%', time:'4.2分',last:'今天 07:00',pct:100,
    logs:['[07:00:01] ✅ 读取 SQC 库存水位数据','[07:00:03] ✅ 进出料明细汇总完成','[07:00:06] ✅ 锁帐影响分析报告生成','[07:00:09] ✅ EDA 自动上抛完成'] },
  { name:'WHMS Report\n系统自动维护', sub:'仓库管理系统报表自动更新', run:true, count:120,rate:'99.2%',time:'3.6分',last:'今天 06:30',pct:100,
    logs:['[06:30:01] ✅ 连接 WHMS 系统成功','[06:30:03] ✅ 读取昨日收发货数据','[06:30:07] ✅ 报表更新至 SharePoint','[06:30:09] ✅ 自动发送 Report 至管理层'] },
  { name:'Training &\n回训一览表', sub:'培训计划进度自动追踪汇整', run:false,count:28, rate:'100%', time:'2.8分',last:'昨天 17:00',pct:0,
    logs:['[17:00:01] ✅ 读取培训系统数据','[17:00:03] ✅ 汇整本月培训完成状况','[17:00:05] ⚠️ 3 人回训逾期，已发提醒','[17:00:07] ✅ 一览表 Excel 已更新'] },
  { name:'出货限制式\n确认', sub:'出货前自动核查所有限制条件', run:true, count:310,rate:'97.9%',time:'1.5分',last:'今天 18:30',pct:90,
    logs:['[18:30:00] ✅ 读取出货清单 48 批','[18:30:02] ✅ 核查品质限制条件','[18:30:04] ✅ 44 批通过可正常出货','[18:30:05] ⚠️ 4 批存在限制，通知 QE'] },
  { name:'假勤\n管理', sub:'员工出勤异常自动侦测与预警', run:true, count:96, rate:'100%', time:'1.2分',last:'今天 18:00',pct:100,
    logs:['[18:00:00] ✅ 读取刷卡系统数据','[18:00:01] ✅ 今日出勤率 96.8%','[18:00:02] ⚠️ 2 人未刷卡，已发 LINE 提醒','[18:00:03] ✅ 假勤报表更新至 HR 系统'] }
]
// 保留原始序号（用于卡片左上角编号）
procs.forEach((p,i)=>{ p.o = i+1 })

/* ★ 2026-09-23：卡片左侧「一张照片 × 16」—— 16 张卡片共用下面这一个常量。
   图片来源优先级：
     ① frontend/src/assets/robotBase64.js 里的 base64 串（长串放那儿，本项目首选，无需外部文件）
     ② 回退：frontend/public/assets/robot.png（文件方案，见 机器人图片替换指南.md）
   填 base64 的步骤：打开 src/assets/robotBase64.js → 把整串粘进 export default '' 的引号里（一行到底）→
                     重新 build + 同步产物 → F5。Vue 这边不用再改任何东西。
   为什么留 /assets/robot.png 这条回退：base64 串一旦被清空/写坏，页面还有图可显，不至于开天窗。 */
const ROBOT_IMG = (typeof ROBOT_BASE64 === 'string' && ROBOT_BASE64.trim())
  ? ROBOT_BASE64.trim()
  : '/assets/robot.png'
// 图片缺失/加载失败 → 置 true 隐藏 <img>（16 张共用同一 src，同生同死，一个标志即可）
const imgFailed = ref(false)

const filter = ref('all')
const filtered = computed(()=>{
  if(filter.value==='on') return procs.filter(p=>p.run)
  if(filter.value==='off') return procs.filter(p=>!p.run)
  return procs
})
const runningCount = computed(()=>procs.filter(p=>p.run).length)
const standbyCount = computed(()=>procs.filter(p=>!p.run).length)

const showRun = ref(false)
const run = ref({ title:'', sub:'', count:'—', rate:'—', time:'—', last:'—', pctText:'—', pctWidth:'0%', logs:[] })

function openRun(i){
  const p = filtered.value[i]
  if(!p) return
  run.value = {
    title: p.name.replace(/\n/g,' ') + ' 机器人',
    sub: p.sub,
    count: p.count,
    rate: p.rate,
    time: p.time,
    last: p.last,
    pctText: p.run ? p.pct + '%' : '待启动',
    pctWidth: '0%',
    logs: p.logs
  }
  showRun.value = true
  // 进度条动画
  nextTick(()=>{
    setTimeout(()=>{ run.value.pctWidth = p.run ? p.pct + '%' : '0%' }, 80)
  })
}
function closeRun(){ showRun.value = false }
function onOvClick(e){ if(e.target === e.currentTarget) closeRun() }
function logClass(l){
  if(l.includes('✅')) return 'run-log-g'
  if(l.includes('⚠️')) return 'run-log-y'
  return 'run-log-r'
}
</script>

<style lang="scss" scoped>
.robot-view{ height:100%; display:flex; flex-direction:column; gap:8px; min-height:0; padding:2px; }

.pbar{ display:flex; align-items:center; justify-content:space-between; flex-shrink:0; }
.ptag{ background:rgba(0,60,120,.4); border:1px solid #0d3050; color:#5a90b8; font-size:9.5px; font-weight:400; padding:3px 10px; border-radius:4px; letter-spacing:.5px; }
.ptitle{ font-size:14px; font-weight:500; color:#c8e0f8; letter-spacing:.8px; margin-left:10px; }
.ptitle span{ color:#00d4aa; }
.ptip{ font-size:8.5px; font-weight:300; color:#c8a020; background:rgba(200,160,32,.06); border:1px solid rgba(200,160,32,.18); padding:2px 7px; border-radius:10px; margin-left:8px; }
.pright{ display:flex; align-items:center; gap:8px; }
.runinfo{ font-size:8.5px; color:#1a3a50; }
.bsm{ font-size:9px; font-weight:300; padding:3px 10px; border-radius:12px; cursor:pointer; border:1px solid #0d3050; background:rgba(0,40,90,.2); color:#3a6070; transition:all .15s; }
.bsm:hover{ background:rgba(0,60,130,.28); color:#7098b8; }
.bsm.act{ background:rgba(0,70,160,.28); border-color:#0050a0; color:#90c0e8; }

/* ════ 横向卡片 4×4 ════ */
.auto-grid{ flex:1; display:grid; grid-template-columns:repeat(4,1fr); grid-template-rows:repeat(4,1fr); gap:8px; min-height:0; overflow:auto; }

/* 横向长方体卡片 */
.ac{
 background:linear-gradient(135deg,#050f1e,#071a2e);
 border:1px solid #0d2a48;border-radius:10px;
 display:flex;flex-direction:row;align-items:stretch;
 cursor:pointer;position:relative;overflow:hidden;
 transition:border-color .22s,transform .12s,box-shadow .22s;
}
.ac:hover{
 border-color:#1a6090;
 transform:translateY(-2px) scale(1.01);
 box-shadow:0 8px 30px rgba(0,100,200,.4);
}
/* 顶部彩线 */
.ac::after{content:'';position:absolute;top:0;left:0;right:0;height:2px;border-radius:10px 10px 0 0;
 background:linear-gradient(90deg,rgba(0,140,255,0),#0088ff 30%,rgba(0,200,255,.6) 60%,rgba(0,140,255,0));}
/* 左侧竖线 */
.ac::before{content:'';position:absolute;left:0;top:8%;bottom:8%;width:2px;border-radius:2px;
 background:linear-gradient(to bottom,rgba(0,160,255,.6),rgba(0,80,160,.2));}

/* 左侧：机器人区域 */
.ac-robot-zone{
 flex-shrink:0;width:110px;
 display:flex;align-items:center;justify-content:center;
 background:linear-gradient(135deg,rgba(0,30,70,.4),rgba(0,15,40,.6));
 border-right:1px solid rgba(0,80,160,.15);
 position:relative;overflow:hidden;
}
/* 发光背景 */
.ac-robot-zone::after{
 content:'';position:absolute;inset:0;
 background:radial-gradient(ellipse at 50% 60%,rgba(0,140,255,.12),transparent 70%);
 pointer-events:none;
}
/* 序号 */
.ac-num{
 position:absolute;top:5px;left:8px;
 font-size:9px;font-weight:600;color:#1a4060;
 background:rgba(0,60,140,.25);border-radius:3px;padding:1px 5px;
 z-index:2;
}

/* ── 卡片照片（★ 2026-09-22：原 CSS 手绘机器人已移除，改为「一张照片 ×16」）
     图片来源见 <script> 的 ROBOT_IMG：优先 src/assets/robotBase64.js 的 base64，其次 public/assets/robot.png。 ── */
.ac-img{
 width:72px;height:80px;object-fit:contain;
 transition:transform .3s;z-index:1;
 filter:drop-shadow(0 4px 12px rgba(0,120,255,.35));
}
.ac:hover .ac-img{transform:scale(1.08) translateY(-3px);}
/* 注：@keyframes blink / antPulse 原供弹窗手绘机器人（.rr-*）使用，2026-09-24 手绘移除后一并删除 */

/* 右侧：信息区 */
.ac-info{
 flex:1;display:flex;flex-direction:column;justify-content:center;
 padding:10px 14px 10px 12px;gap:5px;min-width:0;
}
/* 大字机器人名称 */
.ac-name{
 font-size:15px;font-weight:700;color:#c8e0f8;
 letter-spacing:.3px;line-height:1.3;
 white-space:pre-line;
}
/* 副标题 */
.ac-sub{font-size:9px;font-weight:300;color:#2a5070;letter-spacing:.3px;line-height:1.4;}
/* 状态 + 快速数据行 */
.ac-meta{display:flex;align-items:center;gap:8px;margin-top:2px;flex-wrap:wrap;}
.ac-status{display:flex;align-items:center;gap:4px;font-size:9px;font-weight:400;padding:2px 8px;border-radius:8px;flex-shrink:0;}
.ac-status.on{background:rgba(0,212,170,.08);color:#00d4aa;border:1px solid rgba(0,212,170,.2);}
.ac-status.off{background:rgba(232,184,56,.08);color:#e8b838;border:1px solid rgba(232,184,56,.2);}
.ac-status-dot{width:5px;height:5px;border-radius:50%;}
.ac-status.on .ac-status-dot{background:#00d4aa;box-shadow:0 0 4px #00d4aa;animation:pulse 1.5s infinite;}
.ac-status.off .ac-status-dot{background:#e8b838;}
.ac-chip{font-size:8.5px;font-weight:300;color:#1e3a50;padding:1px 6px;border-radius:6px;background:rgba(0,40,90,.3);border:1px solid rgba(0,60,120,.2);}

/* ════ 运行弹窗 ════ */
.runov{display:none;position:fixed;inset:0;z-index:300;background:rgba(0,5,15,.85);backdrop-filter:blur(8px);}
.runov.show{display:flex;align-items:center;justify-content:center;}
.runbox{background:linear-gradient(135deg,#040e20,#071828);border:1px solid #1050a0;border-radius:16px;padding:28px 32px;width:680px;max-width:92vw;box-shadow:0 0 60px rgba(0,100,220,.4),0 24px 80px rgba(0,20,80,.8);position:relative;text-align:center;}
.runbox-close{position:absolute;top:14px;right:16px;font-size:18px;color:#1a4060;cursor:pointer;}
.runbox-close:hover{color:#90c0e0;}
/* 大机器人 */
/* 运行弹窗大机器人：图片版（与卡片共用 ROBOT_IMG，来源见 <script> 注释） */
.run-robot{width:140px;height:150px;margin:0 auto 16px;}
.rr-img{width:100%;height:100%;object-fit:contain;display:block;}
/* 弹窗内容 */
.run-title{font-size:18px;font-weight:600;color:#c8e0f8;margin-bottom:6px;letter-spacing:.5px;}
.run-subtitle{font-size:11px;font-weight:300;color:#3a6080;margin-bottom:16px;}
.run-status-row{display:flex;justify-content:center;gap:14px;margin-bottom:16px;}
.run-stat{background:rgba(0,25,60,.45);border:1px solid #0d3050;border-radius:8px;padding:10px 18px;text-align:center;}
.run-stat .sl{font-size:9px;font-weight:300;color:#2a5070;margin-bottom:4px;}
.run-stat .sv{font-size:20px;font-weight:600;}
.run-stat .sv.g{color:#00d4aa;}.run-stat .sv.y{color:#e8b838;}.run-stat .sv.r{color:#e85858;}
.run-progress{margin-bottom:16px;}
.run-progress-lbl{font-size:9px;font-weight:300;color:#2a5070;display:flex;justify-content:space-between;margin-bottom:6px;}
.run-bar{height:6px;background:rgba(0,40,80,.4);border-radius:3px;overflow:hidden;}
.run-bar-fill{height:100%;border-radius:3px;background:linear-gradient(90deg,#0055aa,#00d4aa);transition:width 1.2s ease-out;}
.run-logs{text-align:left;background:rgba(0,10,24,.5);border:1px solid #0a2030;border-radius:8px;padding:10px 12px;max-height:80px;overflow-y:auto;font-size:9px;font-weight:300;color:#3a6070;line-height:1.6;margin-bottom:14px;}
.run-log-g{color:#00a880;}.run-log-y{color:#b09020;}.run-log-r{color:#b04040;}
.run-btns{display:flex;gap:10px;justify-content:center;}
.run-btn{font-size:11px;font-weight:500;padding:8px 22px;border-radius:20px;cursor:pointer;border:none;transition:all .2s;}
.run-btn.primary{background:linear-gradient(135deg,#0055aa,#0077cc);color:#fff;box-shadow:0 4px 16px rgba(0,100,200,.4);}
.run-btn.primary:hover{box-shadow:0 6px 24px rgba(0,120,240,.6);}
.run-btn.sec{background:rgba(0,40,80,.3);color:#5a90b8;border:1px solid #0d3050;}
.run-btn.sec:hover{background:rgba(0,60,120,.4);}

@keyframes pulse{0%,100%{opacity:1;box-shadow:0 0 6px rgba(0,212,170,.6)}50%{opacity:.3;box-shadow:none}}

/* ══════════════════════════════════════════════════════════════════════
   ★ 白天主题覆盖（2026-09-18）
   根因：本页原样式整套写死深色（文字 #c8e0f8 / 卡片底 linear-gradient(#050f1e,#071a2e)
   / 弹窗底 #040e20 / 面板底 rgba(0,25,60,.45) 与 rgba(0,10,24,.5) / 边框 #0d2a48、
   #0d3050），无 [data-theme="light"] 覆盖，切白天后浅字压浅底 → 读不清。
   此处统一改「浅底 + 深字」，语义色（红/黄/绿）加深保证白底可读。
   scoped：用 .robot-view 承接 data-v；本页无 Element Plus 组件。
   卡片与运行弹窗机器人为同一张图片（.ac-img / .rr-img，来源见 <script> 的 ROBOT_IMG），
   照片本体自带颜色，深浅主题均无需覆盖。
   ══════════════════════════════════════════════════════════════════════ */
[data-theme="light"] .robot-view {
  color: #1a4070;

  .ptag { background: #dbe7f6; border-color: #bcd4ec; color: #2a5a86; }
  .ptitle { color: #0a2858; span { color: #0a8f6e; } }
  .ptip { color: #b07800; background: rgba(176,120,0,.08); border-color: rgba(176,120,0,.28); }
  .runinfo { color: #5a7a9a; }
  .bsm { border-color: #c0d2e4; background: var(--surface-2); color: #4a6a8a;
    &:hover { background: #cddcec; color: #24507a; }
    &.act { background: #c9ddf3; border-color: #7fb2e0; color: #14508c; } }

  /* ── 机器人卡片 ── */
  .ac { background: linear-gradient(135deg,var(--surface-1),var(--surface-2)); border-color: var(--line-1); }
  .ac:hover { border-color: #7fb2e0; box-shadow: 0 8px 30px rgba(30,100,200,.18); }
  .ac-robot-zone { background: linear-gradient(135deg,#f4f9ff,#e8f2fc); border-right-color: var(--line-2); }
  .ac-num { color: #2a5a86; background: #dbe7f6; }
  .ac-name { color: #0a2858; }
  .ac-sub { color: #5a7a9a; }
  .ac-status.on { background: rgba(10,143,110,.10); color: #0a8f6e; border-color: rgba(10,143,110,.35); }
  .ac-status.off { background: rgba(176,120,0,.10); color: #b07800; border-color: rgba(176,120,0,.32); }
  .ac-status.on .ac-status-dot { background: #0a8f6e; }
  .ac-status.off .ac-status-dot { background: #b07800; }
  .ac-chip { color: #1a4070; background: var(--surface-2); border-color: #c0d2e4; }

  /* ── 运行弹窗 ── */
  .runov { background: rgba(20,45,80,.42); }
  .runbox { background: var(--surface-1); border-color: var(--line-1); box-shadow: 0 24px 80px rgba(20,60,110,.18); }
  .runbox-close { color: #9ab0c4; &:hover { color: #14508c; } }
  .run-title { color: #0a2858; }
  .run-subtitle { color: #5a7a9a; }
  .run-stat { background: var(--surface-2); border-color: var(--line-2); }
  .run-stat .sl { color: #5a7a9a; }
  .run-stat .sv.g { color: #0a8f6e; }
  .run-stat .sv.y { color: #b07800; }
  .run-stat .sv.r { color: #d02828; }
  .run-progress-lbl { color: #5a7a9a; }
  .run-bar { background: #dbe6f0; }
  .run-bar-fill { background: linear-gradient(90deg,#0a6fd0,#0a8f6e); }
  .run-logs { background: var(--surface-2); border-color: var(--line-2); color: #5a7a9a; }
  .run-log-g { color: #0a8f6e; }
  .run-log-y { color: #b07800; }
  .run-log-r { color: #d02828; }
  .run-btn.sec { background: var(--well); color: #4a6a8a; border-color: #c0d2e4;
    &:hover { background: #cddcec; color: #24507a; } }
}
</style>
