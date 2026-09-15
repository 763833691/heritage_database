// 登录开关：设为 false 跳过登录页，true 恢复登录验证
export const AUTH_ENABLED = false

// 本地开发后端端口（与 start.bat / .env 保持一致）
export const BACKEND_PORT = import.meta.env.VITE_BACKEND_PORT || '8001'
export const BACKEND_URL = `http://localhost:${BACKEND_PORT}`
