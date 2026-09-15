<template>
  <div ref="container" class="kg-scene" :class="`kg-scene--${theme}`">
    <div class="kg-scene__hint" v-if="webglFailed">
      当前浏览器不支持 WebGL，无法渲染 3D 图谱，请更换浏览器或开启硬件加速。
    </div>
    <div class="kg-scene__hint" v-else-if="!hasNodes">
      <slot name="empty">暂无图谱数据，请先完成文件处理。</slot>
    </div>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import {
  AdditiveBlending,
  AmbientLight,
  BufferGeometry,
  Color,
  DirectionalLight,
  Float32BufferAttribute,
  GridHelper,
  Group,
  Line,
  LineBasicMaterial,
  Mesh,
  MeshBasicMaterial,
  MeshStandardMaterial,
  PerspectiveCamera,
  PointLight,
  Points,
  PointsMaterial,
  Raycaster,
  Scene,
  SphereGeometry,
  Vector2,
  Vector3,
  WebGLRenderer,
} from 'three'
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js'
import { CSS2DObject, CSS2DRenderer } from 'three/examples/jsm/renderers/CSS2DRenderer.js'
import { EffectComposer } from 'three/examples/jsm/postprocessing/EffectComposer.js'
import { RenderPass } from 'three/examples/jsm/postprocessing/RenderPass.js'
import { UnrealBloomPass } from 'three/examples/jsm/postprocessing/UnrealBloomPass.js'
import { getNodeTypeStyle } from './graphStyleConfig'

const props = defineProps({
  graph: { type: Object, default: null },
  selectedNodeId: { type: String, default: null },
  hoveredNodeId: { type: String, default: null },
  highlightedNodeIds: { type: Object, default: () => new Set() },
  highlightedLinkIds: { type: Object, default: () => new Set() },
  graphViewMode: { type: String, default: 'overview' },
  sourceClusterMode: { type: String, default: 'unified' },
  clusterBounds: { type: Array, default: () => [] },
  cameraController: { type: Object, required: true },
  cameraMinDistance: { type: Number, default: 6 },
  cameraMaxDistance: { type: Number, default: 120 },
})

const emit = defineEmits(['select', 'hover', 'background-click', 'enter-planet'])

const container = ref(null)
const webglFailed = ref(false)
const hasNodes = computed(() => Boolean(props.graph?.nodes?.length))
const theme = computed(() => props.graph?.styles?.theme || 'jspace')

let renderer = null
let labelRenderer = null
let scene = null
let camera = null
let controls = null
let composer = null
let bloomPass = null
let nodeGroup = null
let edgeGroup = null
let labelGroup = null
let hitGroup = null
let gridHelper = null
let particleGroup = null
let resizeObserver = null
let frameId = null
let disposed = false

const nodeObjects = new Map()
const edgeObjects = []
let nodeGeometry = null
let hitGeometry = null
const raycaster = new Raycaster()
const pointer = new Vector2()
let lastHoveredId = null
const clock = { elapsed: 0 }

function styles() {
  return props.graph?.styles || {}
}

function nodeRadius(node) {
  const style = styles()
  const base = node.size * (style.nodeSizeScale || 0.07) * (style.nodeSizeMultiplier ?? 1) * 6
  const overviewScale = props.graphViewMode === 'overview' ? 0.55 : 1
  return Math.max(0.2, base * overviewScale)
}

function createNodeMaterial(node) {
  if (theme.value === 'jspace') {
    return new MeshBasicMaterial({ color: new Color(node.color), transparent: true, opacity: 1 })
  }
  return new MeshStandardMaterial({
    color: new Color(node.color),
    emissive: new Color(node.emissive || node.color),
    emissiveIntensity: 0.65,
    roughness: 0.35,
    metalness: 0.12,
    transparent: true,
    opacity: 1,
  })
}

function clearGroup(group) {
  if (!group) return
  while (group.children.length) {
    const child = group.children.pop()
    group.remove(child)
    disposeObject(child)
  }
}

function disposeObject(object) {
  if (object?.geometry && object.geometry !== nodeGeometry && object.geometry !== hitGeometry) {
    object.geometry.dispose()
  }
  if (object?.material) {
    const materials = Array.isArray(object.material) ? object.material : [object.material]
    materials.forEach((material) => material?.dispose?.())
  }
  if (object?.element?.remove) object.element.remove()
}

function disposeShared() {
  nodeGeometry?.dispose()
  nodeGeometry = null
  hitGeometry?.dispose()
  hitGeometry = null
}

function buildNodes() {
  const graph = props.graph
  if (!graph) return
  nodeGeometry = new SphereGeometry(1, 18, 18)
  nodeObjects.clear()

  graph.nodes.forEach((node) => {
    const radius = nodeRadius(node)
    const material = createNodeMaterial(node)
    const mesh = new Mesh(nodeGeometry, material)
    mesh.position.set(node.x, node.y, node.z)
    mesh.scale.setScalar(radius)
    mesh.userData.node = node
    mesh.userData.baseRadius = radius
    nodeGroup.add(mesh)
    nodeObjects.set(node.id, mesh)
  })
}

function buildEdges() {
  const graph = props.graph
  if (!graph) return
  edgeObjects.length = 0
  const style = styles()
  graph.links.forEach((link) => {
    const source = nodeObjects.get(link.source)
    const target = nodeObjects.get(link.target)
    if (!source || !target) return
    const geometry = new BufferGeometry().setFromPoints([source.position.clone(), target.position.clone()])
    const material = new LineBasicMaterial({
      color: new Color(style.edgeColor || '#cbd5e1'),
      transparent: true,
      opacity: 0.55,
    })
    const line = new Line(geometry, material)
    line.userData.link = link
    edgeGroup.add(line)
    edgeObjects.push(line)
  })
}

function makeLabelElement(text, options = {}) {
  const element = document.createElement('div')
  element.className = `kg-label ${options.className || ''}`.trim()
  element.textContent = text
  if (options.color) element.style.color = options.color
  if (options.background) element.style.background = options.background
  if (options.clickable) {
    element.style.pointerEvents = 'auto'
    element.style.cursor = 'pointer'
  }
  return element
}

/** 当前可见图的整体半径，用于让标签偏移量随图规模自适应。 */
function graphSpread() {
  const nodes = props.graph?.nodes || []
  if (!nodes.length) return 10
  let cx = 0
  let cy = 0
  let cz = 0
  nodes.forEach((node) => {
    cx += node.x
    cy += node.y
    cz += node.z
  })
  cx /= nodes.length
  cy /= nodes.length
  cz /= nodes.length
  let maxRadius = 0
  nodes.forEach((node) => {
    maxRadius = Math.max(maxRadius, Math.hypot(node.x - cx, node.y - cy, node.z - cz))
  })
  return Math.max(maxRadius, 1)
}

function buildLabels() {
  const graph = props.graph
  if (!graph) return
  const style = styles()
  const spread = graphSpread()
  const bounds = props.clusterBounds
  const showSourceLabels = props.graphViewMode === 'overview' && props.sourceClusterMode === 'by_source' && bounds.length > 1

  if (showSourceLabels) {
    bounds.forEach((bound) => {
      const element = makeLabelElement(bound.label, {
        className: 'kg-label--cluster',
        background: 'rgba(37, 99, 235, 0.9)',
        color: '#ffffff',
        clickable: true,
      })
      element.addEventListener('click', (event) => {
        event.stopPropagation()
        emit('enter-planet', bound.id)
      })
      const object = new CSS2DObject(element)
      object.position.set(bound.x, bound.y + bound.radius * 0.6 + spread * 0.12, bound.z)
      labelGroup.add(object)
    })
  } else {
    const groups = new Map()
    graph.nodes.forEach((node) => {
      if (!groups.has(node.type)) groups.set(node.type, [])
      groups.get(node.type).push(node)
    })
    groups.forEach((nodes, type) => {
      if (nodes.length < 3) return
      const typeStyle = getNodeTypeStyle(type, style)
      const center = nodes.reduce(
        (acc, node) => ({ x: acc.x + node.x / nodes.length, y: acc.y + node.y / nodes.length, z: acc.z + node.z / nodes.length }),
        { x: 0, y: 0, z: 0 }
      )
      const element = makeLabelElement(typeStyle.label, { className: 'kg-label--cluster', background: 'rgba(255,255,255,0.86)' })
      const object = new CSS2DObject(element)
      object.position.set(center.x, center.y + spread * 0.42, center.z)
      labelGroup.add(object)
    })
  }

  const limit = graph.nodes.length <= 60 ? 10 : props.graphViewMode === 'planet' ? 24 : 6
  const prominent = [...graph.nodes]
    .sort((a, b) => (b.metadata?.connection_count || 0) - (a.metadata?.connection_count || 0))
    .slice(0, limit)
  prominent.forEach((node) => {
    const typeStyle = getNodeTypeStyle(node.type, style)
    const element = makeLabelElement(node.label, { className: 'kg-label--node', color: typeStyle.color })
    const object = new CSS2DObject(element)
    object.position.set(node.x, node.y - nodeRadius(node) - spread * 0.05, node.z)
    labelGroup.add(object)
  })
}

function buildHitSpheres() {
  clearGroup(hitGroup)
  hitGeometry?.dispose()
  hitGeometry = null
  if (!props.clusterBounds.length) return
  hitGeometry = new SphereGeometry(1, 12, 12)
  props.clusterBounds.forEach((bound) => {
    const material = new MeshBasicMaterial({ transparent: true, opacity: 0, depthWrite: false })
    const mesh = new Mesh(hitGeometry, material)
    mesh.position.set(bound.x, bound.y, bound.z)
    mesh.scale.setScalar(Math.max(bound.radius * 1.15, 6))
    mesh.userData.clusterId = bound.id
    hitGroup.add(mesh)
  })
}

function buildParticles() {
  const count = 280
  const positions = []
  for (let index = 0; index < count; index += 1) {
    const radius = 40 + Math.random() * 40
    const theta = Math.random() * Math.PI * 2
    const phi = Math.acos(2 * Math.random() - 1)
    positions.push(
      radius * Math.sin(phi) * Math.cos(theta),
      radius * Math.cos(phi) * 0.6,
      radius * Math.sin(phi) * Math.sin(theta)
    )
  }
  const geometry = new BufferGeometry()
  geometry.setAttribute('position', new Float32BufferAttribute(positions, 3))
  const material = new PointsMaterial({
    color: new Color('#60a5fa'),
    size: 0.35,
    transparent: true,
    opacity: 0.7,
    blending: AdditiveBlending,
    depthWrite: false,
  })
  particleGroup = new Points(geometry, material)
  scene.add(particleGroup)
}

function rebuild() {
  if (!scene) return
  clearGroup(nodeGroup)
  clearGroup(edgeGroup)
  clearGroup(labelGroup)
  clearGroup(hitGroup)
  disposeShared()

  const style = styles()
  scene.background = new Color(style.background || '#f8f9fb')
  if (gridHelper) gridHelper.visible = Boolean(style.showGrid)
  if (particleGroup) particleGroup.visible = Boolean(style.showParticles)
  if (bloomPass) bloomPass.enabled = Boolean(style.enableBloom)

  if (!props.graph?.nodes?.length) {
    applyEmphasis()
    return
  }
  buildNodes()
  buildEdges()
  buildLabels()
  buildHitSpheres()
  applyEmphasis()
}

function applyEmphasis() {
  const selectedId = props.selectedNodeId
  const hoveredId = props.hoveredNodeId
  const highlightedNodes = props.highlightedNodeIds || new Set()
  const highlightedLinks = props.highlightedLinkIds || new Set()
  const style = styles()
  const connecting = new Set()
  if (hoveredId) {
    connecting.add(hoveredId)
    edgeObjects.forEach((line) => {
      const link = line.userData.link
      if (link.source === hoveredId || link.target === hoveredId) {
        connecting.add(link.source)
        connecting.add(link.target)
      }
    })
  }

  nodeObjects.forEach((mesh, id) => {
    const baseRadius = mesh.userData.baseRadius || 1
    const isSelected = id === selectedId
    const isHovered = id === hoveredId
    const emphasized = selectedId ? highlightedNodes.has(id) : connecting.has(id) || !hoveredId
    mesh.material.opacity = selectedId && !highlightedNodes.has(id) ? 0.24 : 1
    mesh.material.transparent = mesh.material.opacity < 1
    mesh.scale.setScalar(baseRadius * (isSelected ? 1.45 : isHovered ? 1.2 : 1))
    if (mesh.material.emissiveIntensity !== undefined) {
      mesh.material.emissiveIntensity = isSelected ? 1.5 : emphasized ? 0.65 : 0.25
    }
  })

  const showEdges = Boolean(style.showEdges) || (style.showEdgesOnSelect && Boolean(selectedId))
  edgeObjects.forEach((line) => {
    const link = line.userData.link
    line.visible = showEdges
    if (!showEdges) return
    const isHighlighted = highlightedLinks.has(link.id)
    const isHoverRelated = hoveredId && (link.source === hoveredId || link.target === hoveredId)
    if (isHighlighted || isHoverRelated) {
      line.material.color = new Color(style.edgeHighlightColor || '#374151')
      line.material.opacity = 0.95
    } else if (selectedId || hoveredId) {
      line.material.color = new Color(style.edgeColor || '#cbd5e1')
      line.material.opacity = 0.05
    } else {
      line.material.color = new Color(style.edgeColor || '#cbd5e1')
      line.material.opacity = 0.5
    }
  })
}

function updatePointer(event) {
  const rect = renderer.domElement.getBoundingClientRect()
  pointer.x = ((event.clientX - rect.left) / rect.width) * 2 - 1
  pointer.y = -((event.clientY - rect.top) / rect.height) * 2 + 1
}

function pickNode() {
  raycaster.setFromCamera(pointer, camera)
  const meshes = [...nodeObjects.values()]
  const hits = raycaster.intersectObjects(meshes, false)
  return hits.length ? hits[0].object.userData.node : null
}

function pickCluster() {
  if (!hitGroup?.children.length) return null
  raycaster.setFromCamera(pointer, camera)
  const hits = raycaster.intersectObjects(hitGroup.children, false)
  return hits.length ? hits[0].object.userData.clusterId : null
}

function onPointerMove(event) {
  if (!renderer) return
  updatePointer(event)
  const node = pickNode()
  const nodeId = node?.id ?? null
  if (nodeId !== lastHoveredId) {
    lastHoveredId = nodeId
    emit('hover', nodeId)
  }
  renderer.domElement.style.cursor = nodeId ? 'pointer' : pickCluster() ? 'zoom-in' : 'grab'
}

function onPointerLeave() {
  lastHoveredId = null
  emit('hover', null)
}

function onClick(event) {
  if (!renderer) return
  updatePointer(event)
  const node = pickNode()
  if (node) {
    emit('select', node)
    return
  }
  const clusterId = pickCluster()
  if (clusterId) {
    emit('enter-planet', clusterId)
    return
  }
  emit('background-click')
}

function onResize() {
  if (!renderer || !container.value) return
  const width = container.value.clientWidth || 1
  const height = container.value.clientHeight || 1
  camera.aspect = width / height
  camera.updateProjectionMatrix()
  renderer.setSize(width, height)
  labelRenderer.setSize(width, height)
  composer?.setSize(width, height)
  bloomPass?.setSize(width, height)
}

function animate() {
  if (disposed) return
  frameId = requestAnimationFrame(animate)
  clock.elapsed += 0.005

  const controller = props.cameraController
  if (controller?.state?.active) {
    camera.position.lerp(controller.state.position, 0.08)
    controls.target.lerp(controller.state.lookAt, 0.1)
    if (camera.position.distanceTo(controller.state.position) < 0.5) controller.stop()
  }

  if (particleGroup?.visible) {
    particleGroup.rotation.y += 0.0006
    particleGroup.rotation.x = Math.sin(clock.elapsed * 0.3) * 0.05
  }

  controls.update()
  if (composer && bloomPass?.enabled) composer.render()
  else renderer.render(scene, camera)
  labelRenderer.render(scene, camera)
}

function initScene() {
  try {
    renderer = new WebGLRenderer({ antialias: true, powerPreference: 'high-performance' })
  } catch (error) {
    console.warn('[kg] WebGL 初始化失败，跳过 3D 渲染', error)
    webglFailed.value = true
    return
  }
  const style = styles()
  scene = new Scene()
  scene.background = new Color(style.background || '#f8f9fb')

  camera = new PerspectiveCamera(theme.value === 'jspace' ? 38 : 46, 1, 0.1, 500)
  const initial = theme.value === 'jspace' ? new Vector3(0, 2, 36) : new Vector3(0, 10, 52)
  camera.position.copy(initial)

  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.75))
  container.value.appendChild(renderer.domElement)
  renderer.domElement.addEventListener('pointermove', onPointerMove)
  renderer.domElement.addEventListener('pointerleave', onPointerLeave)
  renderer.domElement.addEventListener('click', onClick)

  labelRenderer = new CSS2DRenderer()
  labelRenderer.domElement.style.position = 'absolute'
  labelRenderer.domElement.style.top = '0'
  labelRenderer.domElement.style.left = '0'
  labelRenderer.domElement.style.pointerEvents = 'none'
  container.value.appendChild(labelRenderer.domElement)

  controls = new OrbitControls(camera, renderer.domElement)
  controls.enableDamping = true
  controls.dampingFactor = 0.08
  controls.maxPolarAngle = Math.PI * 0.85
  controls.minDistance = props.cameraMinDistance
  controls.maxDistance = props.cameraMaxDistance

  scene.add(new AmbientLight(0xffffff, theme.value === 'jspace' ? 1 : 0.55))
  const directional = new DirectionalLight(0xffffff, theme.value === 'jspace' ? 0.6 : 0.9)
  directional.position.set(8, 14, 10)
  scene.add(directional)
  const point = new PointLight(new Color('#60a5fa'), 1.2, 200)
  point.position.set(-16, 20, -14)
  scene.add(point)

  gridHelper = new GridHelper(120, 24, new Color(style.gridColor || '#e5e7eb'), new Color(style.gridColor || '#e5e7eb'))
  gridHelper.visible = Boolean(style.showGrid)
  scene.add(gridHelper)

  composer = new EffectComposer(renderer)
  composer.addPass(new RenderPass(scene, camera))
  bloomPass = new UnrealBloomPass(new Vector2(1, 1), 1.15, 0.85, 0.15)
  bloomPass.enabled = Boolean(style.enableBloom)
  composer.addPass(bloomPass)

  nodeGroup = new Group()
  edgeGroup = new Group()
  labelGroup = new Group()
  hitGroup = new Group()
  scene.add(nodeGroup, edgeGroup, labelGroup, hitGroup)

  buildParticles()

  resizeObserver = new ResizeObserver(onResize)
  resizeObserver.observe(container.value)
  onResize()
  rebuild()
  animate()
}

watch(
  () => props.graph,
  () => rebuild()
)

watch(
  () => theme.value,
  () => rebuild()
)

watch(
  () => props.clusterBounds,
  () => {
    if (!scene) return
    buildHitSpheres()
    clearGroup(labelGroup)
    buildLabels()
  }
)

watch(
  () => [props.selectedNodeId, props.hoveredNodeId, props.highlightedNodeIds, props.highlightedLinkIds],
  () => applyEmphasis()
)

watch(
  () => [props.cameraMinDistance, props.cameraMaxDistance],
  ([min, max]) => {
    if (!controls) return
    controls.minDistance = min
    controls.maxDistance = max
  }
)

onMounted(initScene)

onBeforeUnmount(() => {
  disposed = true
  if (frameId) cancelAnimationFrame(frameId)
  resizeObserver?.disconnect()
  const canvas = renderer?.domElement
  if (canvas) {
    canvas.removeEventListener('pointermove', onPointerMove)
    canvas.removeEventListener('pointerleave', onPointerLeave)
    canvas.removeEventListener('click', onClick)
  }
  clearGroup(nodeGroup)
  clearGroup(edgeGroup)
  clearGroup(labelGroup)
  clearGroup(hitGroup)
  disposeShared()
  composer?.dispose?.()
  controls?.dispose?.()
  renderer?.dispose?.()
  renderer?.domElement?.remove()
  labelRenderer?.domElement?.remove()
  renderer = null
  scene = null
})
</script>

<style scoped>
.kg-scene {
  position: relative;
  width: 100%;
  height: 100%;
  overflow: hidden;
}

.kg-scene__hint {
  position: absolute;
  inset: 0;
  display: grid;
  place-items: center;
  color: var(--text-tertiary);
  font-size: 13px;
  pointer-events: none;
}

.kg-scene--jspace {
  background: #f8f9fb;
}

.kg-scene--jarvis {
  background: #050814;
}

:deep(.kg-label) {
  padding: 2px 7px;
  border-radius: 999px;
  font-size: 11px;
  line-height: 1.4;
  white-space: nowrap;
  color: var(--text-secondary);
  background: rgba(255, 255, 255, 0.72);
  pointer-events: none;
  user-select: none;
}

:deep(.kg-label--cluster) {
  font-size: 12px;
  font-weight: 600;
  box-shadow: 0 4px 12px rgba(15, 23, 42, 0.14);
}

:deep(.kg-scene--jarvis .kg-label) {
  background: rgba(2, 6, 23, 0.72);
  color: #cbd5f5;
}
</style>
