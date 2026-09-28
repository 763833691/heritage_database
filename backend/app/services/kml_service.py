"""两步路（TwoNav / 两步路户外助手）KML 解析。

仅使用标准库 ``xml.etree.ElementTree``，不引入第三方 KML 库。
命名空间采用「本地名匹配」的通配策略，兼容 ``gx:Track`` 与普通 ``LineString``。

解析产出：
- ``TrackPoint``：轨迹点（时间 / 经纬度 / 海拔）；
- ``PhotoPoint``：照片标注点（经纬度 / 海拔 / 拍摄时间 / 速度 / 定位精度 / 照片 URL / 原始文件名）。
"""
from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

# 两步路 gx:when 为 UTC，而 ExtendedData/文件名时间多为北京时间；统一换算到本地时区
LOCAL_TIMEZONE = ZoneInfo("Asia/Shanghai")

_PHOTO_EXT_RE = re.compile(r"https?://[^\s\"'<>]+?\.(?:jpg|jpeg|png|webp|heic)(?:\?[^\s\"'<>]*)?", re.I)
_ANY_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.I)
_IMG_SRC_RE = re.compile(r"""<img[^>]+src=["']([^"']+)["']""", re.I)

_TIME_FORMATS = (
    "%Y-%m-%dT%H:%M:%SZ",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%Y-%m-%d %H:%M",
    "%Y/%m/%d %H:%M",
)


def local_name(tag: str) -> str:
    """去掉命名空间前缀，返回元素/属性的本地名。"""
    if not isinstance(tag, str):
        return ""
    return tag.rsplit("}", 1)[-1] if "}" in tag else tag


def parse_datetime(value: object) -> datetime | None:
    """解析常见的 KML / 两步路时间字符串。"""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    # 两步路 ExtendedData 的 Time 为毫秒 epoch（13 位数字）
    if text.isdigit() and len(text) >= 12:
        try:
            return datetime.fromtimestamp(int(text) / 1000, LOCAL_TIMEZONE).replace(tzinfo=None)
        except (ValueError, OSError, OverflowError):
            return None
    text = text.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(text)
        if parsed.tzinfo is not None:
            # 带时区的值（如 gx:when 的 Z）换算到本地时区后再去掉 tzinfo
            return parsed.astimezone(LOCAL_TIMEZONE).replace(tzinfo=None)
        return parsed
    except ValueError:
        pass
    for fmt in _TIME_FORMATS:
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def parse_float(value: object) -> float | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    match = re.search(r"-?\d+(?:\.\d+)?", text)
    if not match:
        return None
    try:
        return float(match.group(0))
    except ValueError:
        return None


def _iter_local(root: ET.Element, name: str):
    for element in root.iter():
        if local_name(element.tag) == name:
            yield element


def _find_local(root: ET.Element, name: str) -> ET.Element | None:
    for element in root.iter():
        if local_name(element.tag) == name:
            return element
    return None


def _collect_extended_data(placemark: ET.Element) -> dict[str, str]:
    """把 ExtendedData 中的 Data / SimpleData / 直接子元素汇总为 name -> value。"""
    data: dict[str, str] = {}
    for container in placemark.iter():
        if local_name(container.tag) != "ExtendedData":
            continue
        for child in container.iter():
            name = local_name(child.tag)
            if name in ("ExtendedData",):
                continue
            if name in ("Data", "SimpleData"):
                key = child.get("name") or ""
                value_el = None
                for sub in child:
                    if local_name(sub.tag) == "value":
                        value_el = sub
                        break
                value = (value_el.text if value_el is not None else child.text) or ""
                if key:
                    data[key] = value.strip()
            elif name == "value":
                continue
            else:
                if child.text and child.text.strip() and name not in data:
                    data[name] = child.text.strip()
    return data


def _match(data: dict[str, str], keywords: tuple[str, ...]) -> str | None:
    for key, value in data.items():
        lowered = key.lower()
        if any(keyword in lowered for keyword in keywords) and value:
            return value
    return None


def _parse_coordinates(text: str) -> list[tuple[float, float, float | None]]:
    """解析 KML ``<coordinates>``：``lon,lat[,alt]`` 三元组，空白分隔。"""
    points: list[tuple[float, float, float | None]] = []
    if not text:
        return points
    for token in re.split(r"\s+", text.strip()):
        if not token:
            continue
        parts = token.split(",")
        if len(parts) < 2:
            continue
        try:
            lon = float(parts[0])
            lat = float(parts[1])
        except ValueError:
            continue
        alt = None
        if len(parts) > 2:
            try:
                alt = float(parts[2])
            except ValueError:
                alt = None
        points.append((lon, lat, alt))
    return points


def _parse_gx_coord(text: str) -> tuple[float, float, float | None] | None:
    """解析 ``gx:coord``：``lon lat alt``，空格分隔。"""
    parts = (text or "").split()
    if len(parts) < 2:
        return None
    try:
        lon = float(parts[0])
        lat = float(parts[1])
    except ValueError:
        return None
    alt = None
    if len(parts) > 2:
        try:
            alt = float(parts[2])
        except ValueError:
            alt = None
    return (lon, lat, alt)


@dataclass
class TrackPoint:
    time: datetime | None
    longitude: float
    latitude: float
    altitude: float | None = None


@dataclass
class PhotoPoint:
    longitude: float
    latitude: float
    altitude: float | None = None
    shot_time: datetime | None = None
    speed: float | None = None
    accuracy: float | None = None
    url: str | None = None
    file_name: str | None = None
    name: str | None = None


@dataclass
class KmlParseResult:
    name: str = ""
    points: list[TrackPoint] = field(default_factory=list)
    photos: list[PhotoPoint] = field(default_factory=list)


def _parse_gx_tracks(root: ET.Element) -> list[TrackPoint]:
    points: list[TrackPoint] = []
    for track in _iter_local(root, "Track"):
        whens: list[datetime | None] = []
        coords: list[tuple[float, float, float | None]] = []
        for child in track:
            tag = local_name(child.tag)
            if tag == "when":
                whens.append(parse_datetime(child.text))
            elif tag == "coord":
                parsed = _parse_gx_coord(child.text or "")
                if parsed:
                    coords.append(parsed)
        for index, coord in enumerate(coords):
            shot = whens[index] if index < len(whens) else None
            points.append(TrackPoint(shot, coord[0], coord[1], coord[2]))
    return points


def _parse_linestrings(root: ET.Element) -> list[TrackPoint]:
    points: list[TrackPoint] = []
    for line in _iter_local(root, "LineString"):
        coord_el = None
        for child in line.iter():
            if local_name(child.tag) == "coordinates":
                coord_el = child
                break
        if coord_el is None:
            continue
        for lon, lat, alt in _parse_coordinates(coord_el.text or ""):
            points.append(TrackPoint(None, lon, lat, alt))
    return points


def _placemark_point(placemark: ET.Element) -> tuple[float, float, float | None] | None:
    for point in placemark.iter():
        if local_name(point.tag) != "Point":
            continue
        for child in point.iter():
            if local_name(child.tag) == "coordinates":
                parsed = _parse_coordinates(child.text or "")
                if parsed:
                    return parsed[0]
    return None


_DESC_FIELD_RE = {
    "lon": re.compile(r"经度[：:]\s*(-?\d+(?:\.\d+)?)"),
    "lat": re.compile(r"纬度[：:]\s*(-?\d+(?:\.\d+)?)"),
    "alt": re.compile(r"海拔[：:]\s*(-?\d+(?:\.\d+)?)"),
    "time": re.compile(r"时间[：:]\s*([\d\-/: ]{8,25})"),
}


def _placemark_description(placemark: ET.Element) -> str:
    text = ""
    for child in placemark.iter():
        if local_name(child.tag) == "description" and child.text:
            text += child.text
    return text


def _description_coord(description: str) -> tuple[float, float, float | None] | None:
    """旧版两步路格式：坐标写在 description 的「经度：…纬度：…」div 中。"""
    lon_m = _DESC_FIELD_RE["lon"].search(description)
    lat_m = _DESC_FIELD_RE["lat"].search(description)
    if not lon_m or not lat_m:
        return None
    alt_m = _DESC_FIELD_RE["alt"].search(description)
    return (float(lon_m.group(1)), float(lat_m.group(1)),
            float(alt_m.group(1)) if alt_m else None)


def _extended_data_coord(data: dict[str, str]) -> tuple[float, float, float | None] | None:
    """旧版两步路格式：坐标写在 ExtendedData（经度键名为 Longtitude 拼写变体）。"""
    lon = lat = alt = None
    for key, value in data.items():
        lowered = key.lower()
        if lowered.startswith(("long", "lng")) or "经度" in key:
            lon = parse_float(value)
        elif lowered.startswith("lat") or "纬度" in key:
            lat = parse_float(value)
        elif lowered.startswith(("alt", "elev")) or "海拔" in key:
            alt = parse_float(value)
    if lon is None or lat is None:
        return None
    return (lon, lat, alt)


def _placemark_timestamp(placemark: ET.Element) -> datetime | None:
    """新版两步路格式：Placemark 下的 TimeStamp/when（UTC）。"""
    for child in placemark:
        if local_name(child.tag) != "TimeStamp":
            continue
        for sub in child.iter():
            if local_name(sub.tag) == "when" and sub.text:
                return parse_datetime(sub.text)
    return None


def _extract_photo_url(placemark: ET.Element, data: dict[str, str]) -> str | None:
    for value in data.values():
        match = _PHOTO_EXT_RE.search(value or "")
        if match:
            return match.group(0)
    description = ""
    for child in placemark.iter():
        if local_name(child.tag) == "description" and child.text:
            description += child.text
    match = _IMG_SRC_RE.search(description)
    if match:
        return match.group(1).strip()
    for value in data.values():
        match = _ANY_URL_RE.search(value or "")
        if match:
            return match.group(0)
    match = _ANY_URL_RE.search(description)
    if match:
        return match.group(0)
    return None


def _parse_photo_placemarks(root: ET.Element) -> list[PhotoPoint]:
    photos: list[PhotoPoint] = []
    for placemark in _iter_local(root, "Placemark"):
        if any(local_name(node.tag) in ("Track", "LineString") for node in placemark.iter()):
            continue
        data = _collect_extended_data(placemark)
        description = _placemark_description(placemark)
        # 坐标三级回退：Point 元素 → ExtendedData（旧版）→ description div（旧版）
        coord = _placemark_point(placemark)
        if coord is None:
            coord = _extended_data_coord(data)
        if coord is None:
            coord = _description_coord(description)
        if coord is None:
            continue
        lon, lat, alt = coord
        url = _extract_photo_url(placemark, data)
        if url is None:
            # 起点/终点/纯文字标注点不计入照片点
            continue

        name_el = None
        for child in placemark:
            if local_name(child.tag) == "name":
                name_el = child
                break
        place_name = (name_el.text or "").strip() if name_el is not None and name_el.text else None

        # 时间三级回退：description「时间：」（旧版）→ TimeStamp/when（新版）→ ExtendedData
        desc_time_m = _DESC_FIELD_RE["time"].search(description)
        time_raw = (
            (desc_time_m.group(1).strip() if desc_time_m else None)
            or _match(data, ("time", "when", "date", "拍摄", "时间"))
            or data.get("when")
        )
        shot_time = parse_datetime(time_raw) or _placemark_timestamp(placemark)
        speed_raw = _match(data, ("speed", "速度", "velocity"))
        accuracy_raw = _match(data, ("accuracy", "precision", "acc", "精度"))
        altitude_raw = _match(data, ("altitude", "elevation", "海拔", "高度"))
        file_raw = _match(data, ("filename", "file_name", "file", "名称", "title")) or place_name

        photos.append(
            PhotoPoint(
                longitude=lon,
                latitude=lat,
                altitude=parse_float(altitude_raw) if altitude_raw is not None else alt,
                shot_time=shot_time,
                speed=parse_float(speed_raw),
                accuracy=parse_float(accuracy_raw),
                url=url,
                file_name=file_raw,
                name=place_name,
            )
        )
    return photos


def parse_kml_bytes(data: bytes) -> KmlParseResult:
    """解析 KML 字节流，返回轨迹点与照片标注点。"""
    root = ET.fromstring(data)
    name = ""
    doc_name = _find_local(root, "name")
    if doc_name is not None and doc_name.text:
        name = doc_name.text.strip()

    points = _parse_gx_tracks(root)
    if not points:
        points = _parse_linestrings(root)

    return KmlParseResult(name=name, points=points, photos=_parse_photo_placemarks(root))


def parse_kml_file(path: str | Path) -> KmlParseResult:
    return parse_kml_bytes(Path(path).read_bytes())
