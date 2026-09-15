/**
 * Markdown 渲染工具
 * 基于 markdown-it + highlight.js
 */
import MarkdownIt from 'markdown-it'
import hljs from 'highlight.js'

const md = new MarkdownIt({
  html: false,         // 安全：禁止原始 HTML
  breaks: true,        // 将 \n 转为 <br>
  linkify: true,       // 自动识别链接
  typographer: true,   // 智能引号、破折号
  highlight(str, lang) {
    if (lang && hljs.getLanguage(lang)) {
      try {
        return `<pre class="hljs"><code>${hljs.highlight(str, { language: lang }).value}</code></pre>`
      } catch { /* fall through */ }
    }
    return `<pre class="hljs"><code>${md.utils.escapeHtml(str)}</code></pre>`
  },
})

/**
 * 将 Markdown 文本渲染为 HTML
 */
export function renderMarkdown(text) {
  if (!text) return ''
  return md.render(text)
}
