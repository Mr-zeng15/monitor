import axios from 'axios'

const API_BASE = import.meta.env.VITE_API_BASE || '/api'

// 客户相关 API
export const customerApi = {
  // 获取客户列表
  getList(params = {}) {
    return axios.get(`${API_BASE}/customers/`, { params })
  },

  // 获取客户详情
  getById(id) {
    return axios.get(`${API_BASE}/customers/${id}/`)
  },

  // 创建客户
  create(data) {
    return axios.post(`${API_BASE}/customers/`, data)
  },

  // 更新客户
  update(id, data) {
    return axios.put(`${API_BASE}/customers/${id}/`, data)
  },

  // 删除客户
  delete(id) {
    return axios.delete(`${API_BASE}/customers/${id}/`)
  },

  // 获取简化列表（用于下拉选择）
  getSimpleList() {
    return axios.get(`${API_BASE}/customers/simple_list/`)
  }
}

// 产品相关 API
export const productApi = {
  // 获取产品列表
  getList(params = {}) {
    return axios.get(`${API_BASE}/products/`, { params })
  },

  // 获取产品详情
  getById(id) {
    return axios.get(`${API_BASE}/products/${id}/`)
  },

  // 创建产品
  create(data) {
    return axios.post(`${API_BASE}/products/`, data)
  },

  // 更新产品
  update(id, data) {
    return axios.put(`${API_BASE}/products/${id}/`, data)
  },

  // 删除产品
  delete(id) {
    return axios.delete(`${API_BASE}/products/${id}/`)
  },

  // 获取简化列表（用于下拉选择）
  getSimpleList() {
    return axios.get(`${API_BASE}/products/simple_list/`)
  }
}
