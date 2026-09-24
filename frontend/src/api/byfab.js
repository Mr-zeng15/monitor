import axios from 'axios'

// ============================================================
//  BY FAB 总览 · 主面板数据源（公司机器人通道，暂关闭）
// ============================================================
//  ★ 2026-09-04 决定：主面板机器人通道默认【关闭】。
//    原因：机器人工作流当前对所有查询都只返回 ABL/OOS 类折线图 JSON（echarts），
//    不返回「面板数据契约」（FD/fabList/kpiNames/PT/CAPA/OC），主面板每次请求必然 422；
//    为避免每进页面报错 + 让机器人空跑，面板改回内置静态示例（整页按真实通道暗显保护），
//    ABL 云端真实通道(cloudAbl.js)不受影响，照常点亮 ABL。
//  若后续机器人工作流按《BYFAB接入机器人数据指南.md》能返回面板契约：
//    1) 把下方 USE_BOT_API 改为 true
//    2) 机器人工作流把「面板数据契约」JSON 作为 answer 返回
//  前端只在 USE_BOT_API=true 时请求 /api/byfab/data/；请求失败 / 数据不符契约
//  自动回退到 ByFabView 内置静态示例，面板永远能渲染。
// ------------------------------------------------------------
const API_BASE = import.meta.env.VITE_API_BASE || '/api'

// ★ 主面板机器人通道总开关（false=用内置静态示例；true=请求后端机器人代理）
export const USE_BOT_API = false

// 后端代理地址（Django 同源托管前端，无跨域问题）
const BYFAB_PROXY = `${API_BASE}/byfab/data/`

// 当前月份，格式 YYYY-MM（与机器人 inputs.month 一致）
function currentMonth() {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

/**
 * 拉取 BY FAB 数据。
 * @param {string} month 形如 '2026-08'
 * @returns {Promise<object|null>}
 *   符合面板契约的对象；mock 模式或失败时返回 null（组件用内置静态数据兜底）。
 */
export async function fetchByFab(month = currentMonth()) {
  if (!USE_BOT_API) return null
  try {
    const { data } = await axios.get(BYFAB_PROXY, { params: { month } })
    if (data && data.success && data.data && data.data.FD && data.data.fabList) {
      return data.data
    }
    console.warn('[ByFab] 机器人返回数据不符合契约（缺少 FD / fabList），沿用静态示例', data)
    return null
  } catch (e) {
    const detail = e?.response?.data
    // ★ 诊断增强：422 时把后端返回的结构/前文打出来，便于核对机器人工作流输出格式
    if (e?.response?.status === 422 && detail) {
      console.warn('[ByFab] 机器人返回无法解析为面板契约(422)', {
        error: detail.error,
        shape_keys: detail.shape_keys,
        hint: detail.hint,
        raw_answer: (detail.raw_answer || '').slice(0, 400),
      })
    } else {
      console.warn('[ByFab] 机器人数据获取失败，沿用静态示例', e?.message || e)
    }
    return null
  }
}

/**
 * 面板数据契约（机器人输出应映射为此结构；字段缺失时前端用内置默认兜底）。
 * 机器人工作流把以下 JSON 作为 answer 返回即可被 ByFabView 直接渲染：
 * {
 *   "fabList": ["2A","2B","2C","2D"],
 *   "kpiNames": ["执行率","焕新行动","回复率","结案率","再发率","DPPM","ABL触发","SPC Cpk","OOC/OOS"],
 *   "fabCol4": { "2A":"#00f0b0","2B":"#60d8ff","2C":"#ffd040","2D":"#d0b0ff" },
 *   "tipCfg": {
 *     "exec": { "t":"整体执行率 — 各车间达成状况",
 *               "f":[ {f:"2A",v:"96.2%",s:"ok",b:"达标",x:"目标 ≥95%"}, ... ] },  // s: ok|bad|warn
 *     "dppm": { ... }, "abl": { ... }
 *   },
 *   "FD": {                                                       // 每 FAB 一张卡
 *     "2A": { "overall":"ok", "ot":"整体达标",
 *             "kpis":[ {n:"执行率",v:96.2,l:95.1,u:"%",tg:"≥95%"}, ... ] },          // 9 项，顺序同 kpiNames
 *     "2B": { ... }, "2C": { ... }, "2D": { ... }
 *   },
 *   "PT": { "2A": { "0":[[W1,W2,W3,W4],"单位","#颜色",目标值], ... }, ... },          // 趋势（弹窗双图）
 *   "CAPA": { "2A": { "3":[ {t:"结案流程标准化",s:"prog",m:"责任:李工 · 预计08-15",tag:"进行中"} ] }, ... },
 *   "OC": { "2A": { "0":[ {id:"OC-241",t:"执行率W3异常排查",own:"陈工",due:"2026-08-10",st:"done",pct:100} ] }, ... },
 *   "execRate": {                                                       // ★ 执行率钻取面板（点 执行率 KPI 弹出的明细）
 *     "2A": {
 *       "value":96.2,"unit":"%","last":95.1,"target":"≥95%",           // 本月值 / 上月值 / 单位 / 目标
 *       "ok":true,"trendBetter":true,"delta":1.1,"risk":"低",          // 达标 / 月度趋势改善 / 偏差量 / 风险等级
 *       "weeks":[95.0,96.2,95.8,96.2],"color":"#00f0b0","tgtLine":95,  // W1-W4 趋势 / 折线色 / 目标线
 *       "compare":{ "2A":[95.0,96.2,95.8,96.2],"2B":[...],"2C":[...],"2D":[...] },  // 四厂执行率 W1-W4
 *       "capa":[ {t:"结案流程标准化",s:"prog",m:"责任:李工 · 预计08-15",tag:"进行中"} ], // 执行率相关 CAPA
 *       "oc":[ {id:"OC-241",t:"执行率W3异常排查",own:"陈工",due:"2026-08-10",st:"done",pct:100} ]  // 执行率相关 OC
 *     }
 *   }
 * }
 * 字段说明：
 *   kpis[].tg 目标格式 '≥95%'|'≤120'|'<3%'；v=本月值；l=上月值；u=单位；
 *   该项 p:true 表示待开发(灰显)。kpiIdx 为 0~8（对应 kpiNames 下标）。
 *   PT / CAPA / OC 的 key 是 kpiIdx 字符串；s(st) 取值 open|prog|done。
 *   execRate 为「点执行率 KPI 弹出的明细面板」专用数据块；缺省时前端按 FD/PT/CAPA/OC[idx=0] 自动派生，
 *   故机器人可只返回 2A 的 execRate（其余车间自动回退派生）。ok/trendBetter 为布尔，delta 为绝对值数字。
 */

// ★ 执行率钻取面板数据契约示例（机器人 answer 的 execRate["2A"] 应映射为此形状）
//   前端默认按 FD/PT/CAPA/OC[idx=0] 派生，机器人返回后整体覆盖该 FAB 的 execRate。
export const EXEC_RATE_EXAMPLE = {
  '2A': {
    value: 96.2, unit: '%', last: 95.1, target: '≥95%',
    ok: true, trendBetter: true, delta: 1.1, risk: '低',
    weeks: [95.0, 96.2, 95.8, 96.2], color: '#00f0b0', tgtLine: 95,
    compare: {
      '2A': [95.0, 96.2, 95.8, 96.2],
      '2B': [95.5, 95.2, 94.5, 94.8],
      '2C': [93.5, 92.0, 91.8, 91.3],
      '2D': [96.5, 96.8, 97.0, 97.1]
    },
    capa: [{ t: '结案流程标准化', s: 'prog', m: '责任:李工 · 预计08-15', tag: '进行中' }],
    oc: [{ id: 'OC-241', t: '执行率W3异常排查', own: '陈工', due: '2026-08-10', st: 'done', pct: 100 }]
  }
}
