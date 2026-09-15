const PI = Math.PI
const A = 6378245
const EE = 0.006693421622965943

function outOfChina(longitude, latitude) {
  return longitude < 72.004 || longitude > 137.8347 || latitude < 0.8293 || latitude > 55.8271
}

function transformLatitude(x, y) {
  let result = -100 + 2 * x + 3 * y + .2 * y * y + .1 * x * y + .2 * Math.sqrt(Math.abs(x))
  result += (20 * Math.sin(6 * x * PI) + 20 * Math.sin(2 * x * PI)) * 2 / 3
  result += (20 * Math.sin(y * PI) + 40 * Math.sin(y / 3 * PI)) * 2 / 3
  result += (160 * Math.sin(y / 12 * PI) + 320 * Math.sin(y * PI / 30)) * 2 / 3
  return result
}

function transformLongitude(x, y) {
  let result = 300 + x + 2 * y + .1 * x * x + .1 * x * y + .1 * Math.sqrt(Math.abs(x))
  result += (20 * Math.sin(6 * x * PI) + 20 * Math.sin(2 * x * PI)) * 2 / 3
  result += (20 * Math.sin(x * PI) + 40 * Math.sin(x / 3 * PI)) * 2 / 3
  result += (150 * Math.sin(x / 12 * PI) + 300 * Math.sin(x / 30 * PI)) * 2 / 3
  return result
}

export function wgs84ToGcj02(longitude, latitude) {
  if (!Number.isFinite(longitude) || !Number.isFinite(latitude) || outOfChina(longitude, latitude)) {
    return [longitude, latitude]
  }
  let dLatitude = transformLatitude(longitude - 105, latitude - 35)
  let dLongitude = transformLongitude(longitude - 105, latitude - 35)
  const radLatitude = latitude / 180 * PI
  let magic = Math.sin(radLatitude)
  magic = 1 - EE * magic * magic
  const sqrtMagic = Math.sqrt(magic)
  dLatitude = (dLatitude * 180) / ((A * (1 - EE)) / (magic * sqrtMagic) * PI)
  dLongitude = (dLongitude * 180) / (A / sqrtMagic * Math.cos(radLatitude) * PI)
  return [longitude + dLongitude, latitude + dLatitude]
}

export function gcj02ToWgs84(longitude, latitude) {
  if (!Number.isFinite(longitude) || !Number.isFinite(latitude) || outOfChina(longitude, latitude)) {
    return [longitude, latitude]
  }

  // Iteratively remove the GCJ-02 offset so a clicked AMap position can be
  // persisted in the WGS84 coordinate system used by the park API.
  let wgsLongitude = longitude
  let wgsLatitude = latitude
  for (let index = 0; index < 5; index += 1) {
    const [gcjLongitude, gcjLatitude] = wgs84ToGcj02(wgsLongitude, wgsLatitude)
    wgsLongitude -= gcjLongitude - longitude
    wgsLatitude -= gcjLatitude - latitude
  }
  return [wgsLongitude, wgsLatitude]
}

export function toGcj02(point) {
  if (point.coordinateSystem === 'GCJ02') return [point.longitude, point.latitude]
  return wgs84ToGcj02(point.longitude, point.latitude)
}
