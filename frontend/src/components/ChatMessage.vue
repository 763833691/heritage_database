<template>
  <div :class="['message', msg.role]">
    <div class="message-avatar">
      <el-avatar :size="36" :icon="msg.role === 'user' ? 'UserFilled' : 'ChatDotRound'" />
    </div>
    <div class="message-body">
      <div class="message-content">
        <div
          v-if="msg.content"
          class="chat-markdown"
          :class="{ 'streaming-cursor': msg.isStreaming }"
          v-html="renderedContent"
        ></div>
        <div v-if="msg.isStreaming && !msg.content" class="typing-indicator">
          <span></span><span></span><span></span>
        </div>
        <div v-if="msg.error" class="message-error">
          <el-icon><WarningFilled /></el-icon>
          {{ msg.error }}
          <el-button size="small" text @click="$emit('retry')">重试</el-button>
        </div>
      </div>
      <div v-if="msg.chart" class="message-chart">
        <div :ref="el => setChartRef(el)" style="height:300px;width:100%"></div>
      </div>
      <div v-if="msg.sources?.length && !msg.isStreaming" class="message-sources">
        <el-tag v-for="s in msg.sources" :key="s" size="small" type="info">{{ s }}</el-tag>
      </div>
      <div v-if="!msg.isStreaming && msg.role === 'assistant'" class="message-actions">
        <el-button size="small" text @click="copyContent">
          <el-icon><CopyDocument /></el-icon>
        </el-button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, ref, nextTick, watch } from 'vue'
import { ElMessage } from 'element-plus'
import * as echarts from 'echarts'
import { renderMarkdown } from '@/utils/markdown'

const props = defineProps({
  msg: { type: Object, required: true },
})

defineEmits(['retry'])

const chartRef = ref(null)
let chartInstance = null

const renderedContent = computed(() => renderMarkdown(props.msg.content || ''))

function setChartRef(el) {
  chartRef.value = el
}

watch(() => props.msg.chart, async (chartData) => {
  if (chartData && chartRef.value) {
    await nextTick()
    renderChart(chartData)
  }
}, { immediate: true })

function renderChart(chartData) {
  if (!chartRef.value || !chartData) return
  if (chartInstance) chartInstance.dispose()
  chartInstance = echarts.init(chartRef.value)

  if (chartData.type === 'radar') {
    const indicators = []
    const seriesData = []

    chartData.data.forEach(park => {
      const keys = Object.keys(park.values)
      if (indicators.length === 0) {
        keys.forEach(k => indicators.push({ name: k, max: 100 }))
      }
      seriesData.push({
        name: park.name,
        value: keys.map(k => park.values[k]),
      })
    })

    chartInstance.setOption({
      tooltip: {},
      legend: { data: seriesData.map(d => d.name), bottom: 0 },
      radar: { indicator: indicators, radius: '60%' },
      series: [{ type: 'radar', data: seriesData }],
    })
  }
}

async function copyContent() {
  try {
    await navigator.clipboard.writeText(props.msg.content)
    ElMessage.success('已复制')
  } catch {
    ElMessage.error('复制失败')
  }
}
</script>

<style scoped>
.message {
  display: flex;
  gap: 12px;
  margin-bottom: 20px;
}

.message.user {
  flex-direction: row-reverse;
}

.message.user .message-content {
  background: #409eff;
  color: #fff;
  border-radius: 12px 4px 12px 12px;
}

.message.user .chat-markdown {
  color: #fff;
}

.message.user .chat-markdown :deep(code) {
  background: rgba(255,255,255,0.2);
  color: #fff;
}

.message.user .chat-markdown :deep(blockquote) {
  border-left-color: rgba(255,255,255,0.5);
  background: rgba(255,255,255,0.1);
  color: rgba(255,255,255,0.9);
}

.message.user .chat-markdown :deep(a) {
  color: #fff;
}

.message.assistant .message-content {
  background: #f5f5f5;
  color: #333;
  border-radius: 4px 12px 12px 12px;
}

.message-body {
  max-width: 75%;
  min-width: 80px;
}

.message-content {
  padding: 12px 16px;
  line-height: 1.7;
}

.message-error {
  color: #f56c6c;
  display: flex;
  align-items: center;
  gap: 8px;
  margin-top: 8px;
}

.message-chart {
  margin-top: 12px;
  background: #fff;
  border-radius: 8px;
  padding: 8px;
  border: 1px solid #eee;
}

.message-sources {
  margin-top: 8px;
  display: flex;
  gap: 6px;
  flex-wrap: wrap;
}

.message-actions {
  margin-top: 4px;
  opacity: 0;
  transition: opacity 0.2s;
}

.message:hover .message-actions {
  opacity: 1;
}

.typing-indicator {
  display: flex;
  gap: 4px;
  padding: 4px 0;
}

.typing-indicator span {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: #999;
  animation: typing 1.4s infinite ease-in-out;
}

.typing-indicator span:nth-child(2) { animation-delay: 0.2s; }
.typing-indicator span:nth-child(3) { animation-delay: 0.4s; }

@keyframes typing {
  0%, 60%, 100% { transform: translateY(0); }
  30% { transform: translateY(-8px); }
}
</style>
