import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

export const warningRuleApi = {
  // 获取规则列表
  getList(params = {}) {
    return axios.get(`${API_BASE}/warning-rules/`, { params })
  },

  // 获取启用的规则
  getActiveRules() {
    return axios.get(`${API_BASE}/warning-rules/active_rules/`)
  },

  // 创建规则
  create(data) {
    return axios.post(`${API_BASE}/warning-rules/`, data)
  },

  // 更新规则
  update(id, data) {
    return axios.put(`${API_BASE}/warning-rules/${id}/`, data)
  },

  // 删除规则
  delete(id) {
    return axios.delete(`${API_BASE}/warning-rules/${id}/`)
  },

  // 切换启用状态
  toggle(id) {
    return axios.post(`${API_BASE}/warning-rules/${id}/toggle/`)
  }
}
