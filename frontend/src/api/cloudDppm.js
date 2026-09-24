// ★ DPPM 云端（2A / 2B）数据接入（GET 后端代理；后端复用 byfab_data 的机器人通道，风格对齐 ABL）
//
//   流程：前端 GET /api/byfab/dppm/ → 后端 dppm_cloud_data 视图（与 byfab_data / abl_cloud_data 同款）
//         向公司机器人（DPPM 专用 key）分别 POST 2A(DPPM) / 2B(抽检量) 两个问题 →
//         解析回覆中的 echarts JSON → 合并为 { fabs: { "2A":{...}, "2B":{...} } } → 回传。
//   后端密钥留服务端，规避浏览器跨域。开关关时返回 null，ByFabView 沿用静态 mock。
//
//   与 ABL 的差异：
//     · ABL 机器人一次返回四厂（series 带 name）；DPPM 机器人【按厂分别返回】（series 不带 name，
//       只有一条 data 折线），后端按提问厂别打标签后再合并；
//     · 面板「只取四周」= **后端解析时已裁到最近 4 周**（`DPPM_RECENT_WEEKS`，见 byfab_views
//       `_extract_dppm_fab`）。上游 4 周 / 6 周都可能给，裁周统一在后端做，两个厂因此天然同构；
//       前端 `dppmStatsFor` 里保留的 `slice(-4)` 只是**幂等兜底**（重复裁无副作用）。
// ── 配置项 ─────────────────────────────────────────────
export const USE_CLOUD_DPPM = true     // ★ 总开关：true=走云端 Dify 流式；false=沿用静态 mock（离线可用）
// ─────────────────────────────────────────────────────

import axios from 'axios'
import { normalizeChart, describeShape, toNum } from '../utils/chartShape'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'
const DPPM_PROXY = `${API_BASE}/byfab/dppm/`   // 后端代理地址（Django 同源托管，无跨域）

const DPPM_FABS = ['2A', '2B']

/** 单厂 values 归一化：数组化 + 转数字 + 与 xAxis 对齐。
 *
 *  ★ 2026-09-24：与后端 `_normalize_chart` 改成同一口径 —— **按尾部对齐**
 *    （最新的标签 ↔ 最新的数值），且**绝不编造 'W1'…'Wn' 假周别**。
 *    旧实现是「轴不够就用 'W' + 序号补齐」，一旦上游漂移成「4 个周标签 + 6 个数」，
 *    面板 slice(-4) 就会显示出 `W5 / W6` 这种**不存在的周别**。
 *    正常路径下后端已给标准 xAxis（2A 4 周 / 2B 6 周），这里只做防御性对齐。
 */
function buildFab(entry, axis, fallbackTitle, fallbackUnit, seeded) {
  const values = (entry.values || []).map(toNum)
  let xs = Array.isArray(entry.xAxis) ? entry.xAxis.map(v => String(v)) : []
  if (xs.length > values.length) xs = xs.slice(-values.length)
  else if (xs.length && xs.length < values.length) xs = new Array(values.length - xs.length).fill('').concat(xs)
  return {
    title: entry.title || fallbackTitle || '',
    unit: entry.unit || fallbackUnit || '',
    xAxis: xs,
    values,
    seeded: !!seeded,
  }
}

/** 从归一化结果里挑出属于某厂的折线：名字精确匹配 → 名字包含 → 只有一条则直接采用 */
function pickFabSeries(norm, fab) {
  if (!norm || !norm.series.length) return null
  const exact = norm.series.find(s => s.name === fab)
  if (exact) return exact
  const loose = norm.series.find(s => s.name && s.name.toUpperCase().includes(fab))
  if (loose) return loose
  return norm.series.length === 1 ? norm.series[0] : null
}

/**
 * 校验后端返回的 DPPM 字段结构，并归一化为可渲染形态。
 *
 * 后端「标准契约」：{ fabs: { "2A": {title, unit, xAxis, values, seeded}, "2B": {...} }, seed_fabs:[...] }
 *   - values 允许含 null（机器人某周缺值）；这里统一转成 number | null。
 *   - `seeded`（★ 内部标记，不上界面）：该厂这一份是不是兜底种子。
 *     DPPM 按厂分别查询、单厂失败只回退该厂，所以必须**按厂**判断真假，
 *     前端据此做「按厂抗降级」（已有真值的那一厂绝不退回种子）。
 *
 * ★ 2026-09-21 两处放宽（都是被线上问题逼出来的）：
 *   ① **形状容错**：机器人后面挂了 LLM，回覆形状会漂移 —— 可能是原始行表
 *      （{data:[{fab,week,count_value},…]}）、{option:{…}} 包装层、宽表、series 写成 map……
 *      统一交给 chartShape.normalizeChart 归一化；图表必需的只有「x 轴 + 数值」两样。
 *   ② **按厂容错**：原实现要求 **2A 和 2B 都有非空 values，否则整体 return null** →
 *      `dppmCloudData` 恒 null → 面板不亮且点不进去。但后端 `_refresh_dppm` 是刻意做成
 *      「单厂独立失败」的（单厂坏只回退该厂，另一厂照常真值），两边契约打架。
 *      现在改成：能拼出哪个厂就返回哪个厂，**一个厂都拼不出才 return null**。
 *
 * @param {object} raw 后端返回的 data.data
 * @returns {{fabs:object}|null}
 */
export function extractDppmFields(raw) {
  if (!raw || typeof raw !== 'object') return null
  const rawFabs = (raw.fabs && typeof raw.fabs === 'object') ? raw.fabs : null

  // 一次归一化，2A/2B 共用（后端可能直接给 fabs 结构，也可能给原始行表 / 任意包装层）
  const norm = normalizeChart(raw, { fabList: null, defaultName: '' })

  const out = {}
  for (const fab of DPPM_FABS) {
    // ① 后端已归一化的标准结构（优先，保留 seeded 标记）
    const f = rawFabs && rawFabs[fab]
    if (f && Array.isArray(f.values) && f.values.length) {
      const built = buildFab(f, norm ? norm.xAxis : [], norm ? norm.title : '', norm ? norm.unit : '', f.seeded)
      if (built.values.some(v => v !== null)) { out[fab] = built; continue }
    }
    // ② 形状容错：从整体 JSON 里找该厂折线（含行表 / 包装层 / 无名单折线）
    const s = pickFabSeries(norm, fab)
    if (s && s.data.some(v => v !== null)) {
      out[fab] = buildFab(
        { values: s.data, xAxis: norm.xAxis, title: norm.title, unit: norm.unit },
        norm.xAxis, norm.title, norm.unit, false
      )
    }
  }

  if (!Object.keys(out).length) {
    console.warn('[cloudDppm] 云端返回数据无法归一化为 DPPM 图表（2A/2B 都拼不出），沿用静态示例', raw)
    return null
  }
  if (Object.keys(out).length < DPPM_FABS.length || (norm && norm.shape !== 'echarts' && !rawFabs)) {
    // 走到这里说明至少有一个厂可用；本条只是留痕：部分可用 / 形状非标准（便于发现上游又变了）
    console.warn('[cloudDppm] DPPM 数据已按容错规则处理：'
      + (norm ? describeShape(raw, norm) : '后端标准 fabs 结构')
      + ' → 可用厂 [' + Object.keys(out).join('/') + ']')
  }
  return { fabs: out }
}


/**
 * 拉取 DPPM 云端数据（GET 后端代理）。
 * 后端已做「服务端持久缓存 + 兜底种子 + 后台静默刷新」，本接口【立即】返回数据，不阻塞。
 * @param {boolean} force true=让后端同步刷新一次真值（对应界面「↻ 重新查询」）
 * @returns {Promise<{fabs:object,_meta:object}|null>} 失败/未启用返回 null
 */
export async function fetchDppmCloud(force = false) {
  if (!USE_CLOUD_DPPM) {
    console.warn('[cloudDppm] 云端开关未开启（USE_CLOUD_DPPM=false），沿用静态示例')
    return null
  }
  try {
    const { data } = await axios.get(DPPM_PROXY, force ? { params: { force: 1 } } : undefined)
    // ★ DPPM_DIAG：把后端原始响应挂到返回值上（不可序列化进界面，仅供 Console 排查）
    let raw = data
    if (data && data.success && data.data) {
      const fields = extractDppmFields(data.data)
      if (!fields) {
        // 形状容错已经尽力（echarts / 行表 / 包装层 / 宽表 / series-map 都试过）仍拼不出来
        console.warn('[cloudDppm] DPPM 云端数据无法归一化为图表，沿用静态示例', data)
        return null
      }
      const out = {
        ...fields,
        _meta: {
          is_seed: !!data.is_seed,
          fetched_at: data.fetched_at || '',
          last_attempt_at: data.last_attempt_at || '',
          stale: !!data.stale,
          refreshing: !!data.refreshing,
          last_error: data.last_error || '',
        },
      }
      out._raw = raw                  // ★ DPPM_DIAG
      return out
    }
    console.warn('[cloudDppm] 云端返回异常（success=false 或缺少 data）', data)
    return { _raw: raw }              // ★ DPPM_DIAG：带着原始响应返回，供上层留痕
  } catch (e) {
    console.warn('[cloudDppm] 云端获取失败，沿用静态示例', e?.message || e)
    return null
  }
}
