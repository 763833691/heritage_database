export const portalNavigation = [
  { label: '首页', path: '/', match: ['/'] },
  { label: '研究数据', path: '/research-data', match: ['/research-data'] },
  { label: '遗址公园', path: '/parks', match: ['/parks'] },
  { label: '地图浏览', path: '/map', match: ['/map'] },
  { label: '对比分析', path: '/compare', match: ['/compare', '/comparison'] },
  { label: '知识图谱', path: '/knowledge-graph', match: ['/knowledge-graph'] },
  { label: '文件库', path: '/kg/vault', match: ['/kg/vault'] },
  { label: '处理流程', path: '/kg/processing', match: ['/kg/processing'] },
  { label: 'AI助手', path: '/assistant', match: ['/assistant', '/chat'] },
  { label: '知识库', path: '/library', match: ['/library', '/knowledge-base'] },
  { label: '文献计量', path: '/bibliometrics', match: ['/bibliometrics'] },
  { label: '关于我们', path: '/about', match: ['/about'] },
]

export function isNavigationActive(item, currentPath) {
  return item.match.some((path) => path === '/'
    ? currentPath === '/'
    : currentPath === path || currentPath.startsWith(`${path}/`))
}
