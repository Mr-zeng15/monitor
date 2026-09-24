// ★ 2026-09-24 Excel 处理测试 · 前端 API
//   上传走 multipart（等价预排导入的 axios + FormData 写法）；
//   下载是浏览器直接跳转的 GET（后端 FileResponse 带 attachment），不走 axios。
import axios from 'axios'

const API = import.meta.env.VITE_API_BASE || '/api'
const BASE = `${API}/excel-flow`

/** 上传 Excel，返回 {success, task}；后端忙时 HTTP 409 {success:false, error} */
export function excelFlowUpload(file) {
  const fd = new FormData()
  fd.append('file', file)
  return axios.post(`${BASE}/upload/`, fd, { headers: { 'Content-Type': 'multipart/form-data' } })
    .then(r => r.data)
}

/** 当前/最后任务状态（2s 轮询） */
export const excelFlowStatus = () => axios.get(`${BASE}/status/`).then(r => r.data)

/** 结果下载地址（浏览器直接访问，Content-Disposition 触发下载） */
export const EXCEL_FLOW_DOWNLOAD_URL = `${BASE}/download/`
