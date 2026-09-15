import axios from 'axios'
import { ElMessage } from 'element-plus'
import { AUTH_ENABLED } from '@/config/app'

const api = axios.create({
  baseURL: '/api',
  timeout: 30000,
})

let authRedirectPending = false
let lastNotice = { key: '', time: 0 }

function showMessageOnce(message, type = 'error') {
  const key = `${type}:${message}`
  const now = Date.now()
  if (lastNotice.key === key && now - lastNotice.time < 2500) return
  lastNotice = { key, time: now }
  ElMessage({ message, type })
}

// 请求拦截器
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => Promise.reject(error)
)

// 响应拦截器
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error.response?.status
    const silent = error.config?.silent === true
    if (status === 401 && AUTH_ENABLED) {
      localStorage.removeItem('token')
      localStorage.removeItem('user')
      if (!authRedirectPending) {
        authRedirectPending = true
        showMessageOnce('登录状态已失效，请重新登录')
        const redirect = encodeURIComponent(`${window.location.pathname}${window.location.search}`)
        window.location.assign(`/login?redirect=${redirect}`)
      }
    } else if (!silent && status === 403) {
      showMessageOnce('当前账号没有执行此操作的权限')
    } else if (!silent) {
      const message = error.response?.data?.detail || (error.request ? '网络连接失败，请稍后重试' : '请求失败')
      showMessageOnce(message)
    }
    return Promise.reject(error)
  }
)

export default api
