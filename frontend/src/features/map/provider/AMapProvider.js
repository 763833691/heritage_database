import AMapLoader from '@amap/amap-jsapi-loader'
import { toGcj02 } from '../coordinates'

export class AMapProvider {
  constructor(options = {}) {
    this.key = options.key
    this.securityCode = options.securityCode
    this.mapStyle = options.mapStyle
    this.map = null
    this.AMap = null
    this.loca = null
    this.pointLayer = null
    this.selectedHalo = null
    this.cluster = null
    this.markers = []
    this.points = []
    this.pointClickHandlers = new Set()
    this.mapClickHandlers = new Set()
    this.viewportHandlers = new Set()
    this.selectedPointId = null
    this.draftPoint = null
    this.pickingMode = false
  }

  async mount(container) {
    if (!this.key) throw new Error('MISSING_AMAP_KEY')
    if (this.securityCode) window._AMapSecurityConfig = { securityJsCode: this.securityCode }
    this.AMap = await AMapLoader.load({
      key: this.key,
      version: '2.0',
      plugins: ['AMap.Scale', 'AMap.MarkerCluster'],
      Loca: { version: '2.0.0' },
    })
    const style = this.mapStyle
      ? (this.mapStyle.startsWith('amap://') ? this.mapStyle : `amap://styles/${this.mapStyle}`)
      : 'amap://styles/whitesmoke'
    this.map = new this.AMap.Map(container, {
      viewMode: '2D',
      center: [104.2, 35.8],
      zoom: 4.6,
      mapStyle: style,
      showLabel: true,
      features: ['bg', 'road', 'building', 'point'],
    })
    this.map.addControl(new this.AMap.Scale({ position: 'LB' }))
    this.map.on('zoomend', () => this.emitViewport())
    this.map.on('moveend', () => this.emitViewport())
    this.map.on('click', (event) => {
      const position = event?.lnglat
      if (!position) return
      this.mapClickHandlers.forEach((handler) => handler({
        longitude: position.lng,
        latitude: position.lat,
        coordinateSystem: 'GCJ02',
      }))
    })
    if (window.Loca) this.loca = new window.Loca.Container({ map: this.map })
  }

  destroy() {
    this.pointLayer?.destroy?.()
    this.selectedHalo?.setMap?.(null)
    this.draftPoint?.setMap?.(null)
    this.cluster?.setMap?.(null)
    this.cluster?.clearMarkers?.()
    this.markers.forEach((marker) => marker.off('click'))
    this.loca?.destroy?.()
    this.map?.destroy()
    this.pointLayer = null
    this.selectedHalo = null
    this.draftPoint = null
    this.cluster = null
    this.markers = []
    this.loca = null
    this.map = null
  }

  setView(view) {
    if (!this.map) return
    if (view.center) this.map.setCenter(view.center)
    if (view.zoom) this.map.setZoom(view.zoom)
  }

  fitBounds(bounds) {
    if (!this.map || !bounds?.length) return
    this.map.setFitView(bounds, false, [70, 70, 70, 70])
  }

  setPoints(points = []) {
    if (!this.map || !this.AMap) return
    this.points = points.filter((point) => Number.isFinite(point.longitude) && Number.isFinite(point.latitude))
    this.cluster?.setMap?.(null)
    this.markers.forEach((marker) => marker.off('click'))
    this.markers = this.points.map((point) => {
      const position = toGcj02(point)
      const marker = new this.AMap.Marker({ position, title: point.name, extData: point })
      marker.on('click', () => this.pointClickHandlers.forEach((handler) => handler(point)))
      return marker
    })
    if (this.markers.length) {
      this.cluster = new this.AMap.MarkerCluster(this.map, this.markers, {
        gridSize: 64,
        averageCenter: true,
        maxZoom: 12,
      })
    }
    this.renderLocaPoints()
  }

  renderLocaPoints() {
    if (!this.loca || !window.Loca || !this.points.length) return
    this.pointLayer?.destroy?.()
    const features = this.points.map((point) => ({ type: 'Feature', properties: point, geometry: { type: 'Point', coordinates: toGcj02(point) } }))
    const source = new window.Loca.GeoJSONSource({ data: { type: 'FeatureCollection', features } })
    this.pointLayer = new window.Loca.PointLayer({ zIndex: 121, blend: 'normal' })
    this.pointLayer.setSource(source)
    this.pointLayer.setStyle({ radius: 6, color: '#2563EB', borderWidth: 2, borderColor: '#FFFFFF', opacity: .9 })
    this.loca.add(this.pointLayer)
    this.loca.render()
  }

  setSelectedPoint(id) {
    this.selectedPointId = id
    this.selectedHalo?.setMap?.(null)
    this.selectedHalo = null
    const point = this.points.find((item) => String(item.id) === String(id))
    if (point && this.map) {
      const position = toGcj02(point)
      this.selectedHalo = new this.AMap.CircleMarker({
        center: position,
        radius: 16,
        strokeColor: '#7C3AED',
        strokeWeight: 3,
        strokeOpacity: .82,
        fillColor: '#7C3AED',
        fillOpacity: .12,
        zIndex: 140,
      })
      this.selectedHalo.setMap(this.map)
      const zoom = Math.max(this.map.getZoom(), 11)
      this.map.setZoomAndCenter(zoom, position, false, 280)
    }
  }

  setPickingMode(active) {
    this.pickingMode = Boolean(active)
    this.map?.setDefaultCursor?.(this.pickingMode ? 'crosshair' : 'default')
  }

  setDraftPoint(point) {
    this.clearDraftPoint()
    if (!this.map || !this.AMap || !point) return
    this.draftPoint = new this.AMap.CircleMarker({
      center: toGcj02(point),
      radius: 10,
      strokeColor: '#FFFFFF',
      strokeWeight: 3,
      strokeOpacity: 1,
      fillColor: '#EF4444',
      fillOpacity: 1,
      zIndex: 160,
    })
    this.draftPoint.setMap(this.map)
  }

  clearDraftPoint() {
    this.draftPoint?.setMap?.(null)
    this.draftPoint = null
  }

  setFilters() {}

  onPointClick(handler) {
    this.pointClickHandlers.add(handler)
    return () => this.pointClickHandlers.delete(handler)
  }

  onMapClick(handler) {
    this.mapClickHandlers.add(handler)
    return () => this.mapClickHandlers.delete(handler)
  }

  onViewportChange(handler) {
    this.viewportHandlers.add(handler)
    return () => this.viewportHandlers.delete(handler)
  }

  emitViewport() {
    if (!this.map) return
    const center = this.map.getCenter()
    const view = { center: [center.lng, center.lat], zoom: this.map.getZoom() }
    this.viewportHandlers.forEach((handler) => handler(view))
  }

  resize() { this.map?.resize?.() }
}
