import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

// 基础资料表（EntryTable）：P/N 主数据，预排导入时按 P/N 自动带出 52阶料号/满箱量/客户
export const entryTableApi = {
  // 列表（可带搜索/分页参数）
  list(params = {}) {
    return axios.get(`${API_BASE}/entry-table/`, { params })
  },

  // 新增
  create(data) {
    return axios.post(`${API_BASE}/entry-table/`, data)
  },

  // 更新
  update(id, data) {
    return axios.put(`${API_BASE}/entry-table/${id}/`, data)
  },

  // 删除
  remove(id) {
    return axios.delete(`${API_BASE}/entry-table/${id}/`)
  }
}
