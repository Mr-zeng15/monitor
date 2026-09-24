// ★ ABL触发 云端数据接入（GET 后端代理；后端复用 byfab_data 的机器人通道，风格对齐）
//
//   流程：前端 GET /api/byfab/abl/ → 后端 abl_cloud_data 视图（与 byfab_data 同款）
//         向公司机器人 POST 一个问题 → 解析回覆中的 echarts JSON → 回传 {success, data}
//         → 前端从 data.data 提取所需字段（title / xAxis / series）→ 渲染 2A ABL 面板。
//   后端密钥留服务端，规避浏览器跨域。开关关时返回 null，ByFabView 沿用静态 mock。
//
// ── 配置项 ─────────────────────────────────────────────
export const USE_CLOUD_ABL = true      // ★ 总开关：true=走云端 Dify 流式；false=沿用静态 mock（离线可用）
// ─────────────────────────────────────────────────────

import axios from 'axios'
import { normalizeChart, describeShape } from '../utils/chartShape'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'
const ABL_PROXY = `${API_BASE}/byfab/abl/`   // 后端代理地址（Django 同源托管，无跨域）

// 面板固定四厂；normalizeChart 会把 series 名（'2a' / 'FAB2A' / '2A车间'）统一归一化成这四个
const ABL_FABS = ['2A', '2B', '2C', '2D']

/**
 * 从云端 JSON 中提取 ABL 面板所需字段。
 *
 * ★ 2026-09-21 起改为「形状容错」解析：机器人工作流后面挂了一层 LLM，同一问题多次提问回覆的
 *   JSON 形状会漂移 —— 标准 echarts option、原始行表（{data:[{fab,week,count_value},…],message}）、
 *   {option:{…}} / {result:{chart:{…}}} 包装层、宽表（厂别在列名）、series 写成 map、xAxis 写成
 *   逗号串……全都归一到同一份契约。图表必需的只有「x 轴 + 每厂一条数值」，其余都是附加值，
 *   所以只要这两样在就一定出图，不再因为「多了/少了别的字段」整体判失败、退回静态示例。
 *
 * @param {object} raw 云端返回的 JSON（后端 data.data）
 * @returns {{title:string, unit:string, xAxis:string[], series:Array<{name:string,data:number[]}>, wow:object|null, shape:string}|null}
 */
export function extractAblFields(raw) {
  const fields = normalizeChart(raw, { fabList: ABL_FABS })
  if (!fields) {
    // 真的没有可用轴/数值，或一条折线都对不上厂名 → 沿用静态示例（宁可不亮也不半亮）
    console.warn('[cloudAbl] 云端返回数据无法归一化为 ABL 图表，沿用静态示例', raw)
    return null
  }
  if (fields.shape !== 'echarts') {
    // 形状漂移命中（行表 / 包装层 / 宽表…）→ Console 留痕，便于判断上游是否又变了
    console.warn('[cloudAbl] 云端 JSON 形状非标准 echarts，已按容错规则归一化：' + describeShape(raw, fields))
  }
  return fields
}


/**
 * 拉取 ABL 触发云端数据（GET 后端代理；后端复用 byfab_data 的机器人通道 → 提取字段）。
 *
 * ★ 2026-09-16：后端已改为「服务端持久缓存 + 兜底种子 + 后台静默刷新」，
 *   本接口【立即】返回数据（真值 or 兜底种子），不再阻塞在机器人上。
 *   因此这里也把 meta（is_seed / fetched_at / stale / last_error）透传给调用方，
 *   便于界面显示"数据时间 / 兜底"状态。
 *
 * @param {boolean} force true=让后端同步刷新一次真值（对应界面「↻ 重新查询」）
 * @returns {Promise<{title,unit,xAxis,series,wow,_meta}|null>} 失败/未启用返回 null
 */
export async function fetchAblCloud(force = false) {
  if (!USE_CLOUD_ABL) {
    console.warn('[cloudAbl] 云端开关未开启（USE_CLOUD_ABL=false），沿用静态示例')
    return null
  }
  try {
    const { data } = await axios.get(ABL_PROXY, force ? { params: { force: 1 } } : undefined)
    if (data && data.success && data.data) {
      const fields = extractAblFields(data.data)
      if (!fields) {
        console.warn('[cloudAbl] 云端返回数据不符合 ABL 字段契约，沿用静态示例', data)
        return null
      }
      return {
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
    }
    console.warn('[cloudAbl] 云端返回异常（success=false 或缺少 data）', data)
    return null
  } catch (e) {
    console.warn('[cloudAbl] 云端获取失败，沿用静态示例', e?.message || e)
    return null
  }
}
