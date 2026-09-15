import { BACKEND_URL } from '@/config/app'

/**
 * SSE 流式聊天客户端
 * 使用 fetch + ReadableStream 解析 SSE 事件（支持 POST）
 * 注意：SSE 流式请求绕过 Vite 代理直连后端，避免代理缓冲导致卡住
 */

function getStreamUrl() {
  // 开发模式直连后端，避免代理缓冲导致卡住
  if (window.location.port === '3000' || window.location.port === '5173') {
    return `${BACKEND_URL}/api/chat/stream`
  }
  return '/api/chat/stream'
}

/**
 * 流式发送聊天消息
 */
export async function* streamChat(message, conversationId, signal) {
  const token = localStorage.getItem('token')
  const response = await fetch(getStreamUrl(), {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'Authorization': `Bearer ${token}`,
    },
    body: JSON.stringify({
      message,
      conversation_id: conversationId || undefined,
    }),
    signal,
  })

  if (!response.ok) {
    const error = await response.json().catch(() => ({}))
    throw new Error(error.detail || `请求失败 (${response.status})`)
  }

  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ''
  let currentEvent = 'message'

  while (true) {
    const { done, value } = await reader.read()
    if (done) break

    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split('\n')
    buffer = lines.pop() || ''

    for (const line of lines) {
      if (line.startsWith('event: ')) {
        currentEvent = line.slice(7).trim()
      } else if (line.startsWith('data: ')) {
        const jsonStr = line.slice(6)
        try {
          const data = JSON.parse(jsonStr)
          yield { event: currentEvent, data }
        } catch {
          // 跳过无法解析的行
        }
      }
    }
  }
}
