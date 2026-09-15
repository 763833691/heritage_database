import { Vector3 } from 'three'

/**
 * 相机聚焦控制器（非响应式，逐帧读取）。
 * 场景每帧把相机位置与观察点向 focus 目标插值，逼近后自动停止。
 */
export function createGraphCameraController() {
  const state = {
    active: false,
    position: new Vector3(),
    lookAt: new Vector3(),
  }

  function getFocusDistance(nodeSize, override) {
    if (override) return override
    return Math.max(7, Math.min(70, 6 + Math.sqrt(Math.max(nodeSize || 0.1, 0.1)) * 5.5))
  }

  function focusOnNode(node, override) {
    if (!node) return
    const distance = getFocusDistance(node.size, override)
    state.position.set(node.x, node.y + distance * 0.16, node.z + distance)
    state.lookAt.set(node.x, node.y, node.z)
    state.active = true
  }

  function focusOnCluster(center, radius, mode = 'planet') {
    const distance = mode === 'overview' ? Math.max(radius * 2.2, 26) : Math.max(radius * 2.4, 14)
    state.position.set(center.x, center.y + radius * 0.45, center.z + distance)
    state.lookAt.set(center.x, center.y, center.z)
    state.active = true
  }

  function focusOnOverview(bounds) {
    if (!bounds?.length) {
      state.position.set(0, 6, 26)
      state.lookAt.set(0, 0, 0)
      state.active = true
      return
    }
    // 用各簇的外接球整体取景，避免镜头退得过远导致节点变成小点
    let span = 0
    let cx = 0
    let cy = 0
    let cz = 0
    bounds.forEach((item) => {
      cx += item.x
      cy += item.y
      cz += item.z
    })
    const count = bounds.length
    const center = { x: cx / count, y: cy / count, z: cz / count }
    bounds.forEach((item) => {
      span = Math.max(span, Math.hypot(item.x - center.x, item.y - center.y, item.z - center.z) + item.radius)
    })
    const radius = Math.max(span, 2)
    const distance = Math.max(radius * 2.3, 7)
    state.position.set(center.x, center.y + radius * 0.35, center.z + distance)
    state.lookAt.set(center.x, center.y, center.z)
    state.active = true
  }

  function stop() {
    state.active = false
  }

  return { state, getFocusDistance, focusOnNode, focusOnCluster, focusOnOverview, stop }
}
