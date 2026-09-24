// ★ 2026-09-16：QC_AI_TEAM · AI Agent 专案登记（前后端版）
//
//   原版是单文件纯前端页，台账存在浏览器 localStorage（qcat_p4 / qcat_c4）。
//   现改为走后端 /api/qc-ai/...，数据持久化在服务端，换电脑/换浏览器都能看到。
//   ★ 所有写接口都返回「最新全量状态」{projects, cats}，前端直接整体替换即可，
//     不做增量合并 —— 保证界面与服务端永远一致（与原版 saveProjects 后整体 refresh 同语义）。
import axios from 'axios'

const API = import.meta.env.VITE_API_BASE || '/api'
const BASE = `${API}/qc-ai`

async function get(path, params) {
  const { data } = await axios.get(BASE + path, params ? { params } : undefined)
  return data
}
async function post(path, payload) {
  const { data } = await axios.post(BASE + path, payload || {})
  return data
}

/** 一次取回：projects + cats + prefix_map + builtins + statuses + btypes */
export const qcBootstrap = () => get('/bootstrap/')

/** 流水码自动分配：同 群组+子类型 下的最小未用号，与工作后缀无关（废除的保留、不重分配） */
export const qcNextSeq = (group, subtype, work, excludeId) =>
  get('/next-seq/', { group, subtype, work, exclude_id: excludeId || '' })

/** 新增/修改专案（id 为空=新增）。名称由服务端按命名规则生成。 */
export const qcSaveProject = (payload) => post('/projects/save/', payload)

/** 改状态：废除 / 恢复 */
export const qcSetStatus = (id, status) => post('/projects/status/', { id, status })

/** 永久删除 */
export const qcDeleteProject = (id) => post('/projects/delete/', { id })

/** 分类项增删（内建项不可删） */
export const qcCatAdd = (kind, name) => post('/cats/add/', { kind, name })
export const qcCatRemove = (kind, name) => post('/cats/remove/', { kind, name })

/** 备份 JSON（结构与原版 exportJSON 完全一致，可双向互导） */
export const qcExport = () => get('/export/')

/** 汇入 JSON（覆盖现有数据） */
export const qcImport = (backup) => post('/import/', backup)
