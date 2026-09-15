export function parkToMapPoint(park) {
  return {
    id: String(park.id),
    name: park.short_name || park.name,
    longitude: Number(park.longitude),
    latitude: Number(park.latitude),
    coordinateSystem: 'WGS84',
    province: park.province,
    city: park.city,
    district: park.district,
    parkType: park.park_type,
    batch: park.batch ? `第${park.batch}批` : undefined,
    protectionLevel: park.world_heritage ? '世界遗产相关' : undefined,
    score: averageScore(park.scores),
    coverImage: null,
    summary: park.description,
    metrics: Object.fromEntries((park.scores || []).map((score) => [score.indicator_name, score.score])),
    raw: park,
  }
}

function averageScore(scores = []) {
  const values = scores.map((score) => Number(score.score)).filter(Number.isFinite)
  return values.length ? Number((values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(1)) : null
}
