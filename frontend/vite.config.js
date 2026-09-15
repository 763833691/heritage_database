import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import { resolve } from 'path'

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')
  const backendPort = env.VITE_BACKEND_PORT || '8001'
  const backendUrl = `http://localhost:${backendPort}`

  return {
  plugins: [vue()],
  resolve: {
    alias: {
      '@': resolve(__dirname, 'src'),
    },
  },
  server: {
    port: 3000,
    host: '0.0.0.0',
    allowedHosts: ['localhost', '127.0.0.1'],
    proxy: {
      '/api': {
        target: backendUrl,
        changeOrigin: true,
        timeout: 600000,  // 10分钟超时（知识库上传需要LLM解析）
        configure: (proxy) => {
          proxy.on('proxyReq', (proxyReq, req) => {
            if (req.url.includes('/chat/stream') || req.url.includes('/upload/report') || req.url.includes('/knowledge/upload')) {
              proxyReq.setHeader('Connection', 'keep-alive')
            }
          })
          proxy.on('proxyRes', (proxyRes, req) => {
            if (req.url.includes('/chat/stream')) {
              proxyRes.headers['cache-control'] = 'no-cache'
              proxyRes.headers['x-accel-buffering'] = 'no'
            }
          })
        },
      },
    },
  },
  test: {
    include: ['src/**/*.test.js'],
    exclude: ['tests/e2e/**', 'node_modules/**'],
  },
  build: {
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules/echarts') || id.includes('node_modules/zrender')) return 'charts'
          if (id.includes('node_modules/element-plus') || id.includes('node_modules/@element-plus')) return 'ui'
          if (id.includes('node_modules/vue') || id.includes('node_modules/pinia')) return 'vue-vendor'
        },
      },
    },
  },
}
})
