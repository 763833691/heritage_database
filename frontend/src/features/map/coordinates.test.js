import { describe, expect, it } from 'vitest'
import { gcj02ToWgs84, wgs84ToGcj02 } from './coordinates'

describe('map coordinate conversion', () => {
  it('round-trips a WGS84 point through GCJ-02 without visible drift', () => {
    const original = [116.397389, 39.908722]
    const gcj02 = wgs84ToGcj02(...original)
    const restored = gcj02ToWgs84(...gcj02)

    expect(restored[0]).toBeCloseTo(original[0], 6)
    expect(restored[1]).toBeCloseTo(original[1], 6)
  })

  it('leaves coordinates outside China unchanged', () => {
    expect(gcj02ToWgs84(2.3522, 48.8566)).toEqual([2.3522, 48.8566])
  })
})
