#!/usr/bin/env python3
"""地理院XYZタイルの取得と座標計算に使う共通関数。"""
import argparse
import io
import json
import math
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from xml.sax.saxutils import escape

TILE_SIZE = 256
BASE_URL = "https://cyberjapandata.gsi.go.jp/xyz/std/{z}/{x}/{y}.png"


def world_pixel(lon, lat, zoom):
    lat = max(-85.05112878, min(85.05112878, lat))
    n = TILE_SIZE * (2 ** zoom)
    x = (lon + 180.0) / 360.0 * n
    rad = math.radians(lat)
    y = (1.0 - math.asinh(math.tan(rad)) / math.pi) / 2.0 * n
    return x, y


def inverse_world_pixel(x, y, zoom):
    n = TILE_SIZE * (2 ** zoom)
    lon = 360.0 * x / n - 180.0
    lat = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    return lon, lat


def make_plan(bbox, zoom):
    south, west, north, east = bbox
    if not (-85 < south < north < 85 and -180 < west < east < 180):
        raise ValueError("bboxには SOUTH WEST NORTH EAST の順で正しい座標を指定してください")
    if not 10 <= zoom <= 18:
        raise ValueError("この試験版はズーム10～18に限定しています")
    left, bottom = world_pixel(west, south, zoom)
    right, top = world_pixel(east, north, zoom)
    x1, y1 = math.floor(left / 256), math.floor(top / 256)
    x2, y2 = math.ceil(right / 256) - 1, math.ceil(bottom / 256) - 1
    crop_left, crop_top = math.floor(left), math.floor(top)
    crop_right, crop_bottom = math.ceil(right), math.ceil(bottom)
    west2, north2 = inverse_world_pixel(crop_left, crop_top, zoom)
    east2, south2 = inverse_world_pixel(crop_right, crop_bottom, zoom)
    return {
        "bbox": bbox, "zoom": zoom,
        "tile_start": [x1, y1], "tile_end": [x2, y2],
        "tile_count": (x2 - x1 + 1) * (y2 - y1 + 1),
        "pixels": [crop_right - crop_left, crop_bottom - crop_top],
        "crop_global": [crop_left, crop_top, crop_right, crop_bottom],
        "kml_bounds": {"west": west2, "east": east2, "north": north2, "south": south2},
        "tile_source": "国土地理院 標準地図",
        "attribution": "国土地理院（地理院タイル）",
    }


def fetch_tile(z, x, y, cache_dir, refresh=False):
    from PIL import Image  # Pillowはダウンロード処理実行時だけ必要

    tile = cache_dir / str(z) / str(x) / f"{y}.png"
    if tile.is_file() and not refresh:
        try:
            with Image.open(tile) as img:
                img.load()
                if img.size == (TILE_SIZE, TILE_SIZE):
                    return img.convert("RGB")
        except (OSError, ValueError):
            print("キャッシュを再取得:", tile)
    url = BASE_URL.format(z=z, x=x, y=y)
    req = urllib.request.Request(
        url, headers={
            "User-Agent": "AT5MapBuilder/1.0",
            "Accept": "image/png,image/*;q=0.8",
        }
    )
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                data = response.read()
            with Image.open(io.BytesIO(data)) as img:
                img.load()
                if img.size != (TILE_SIZE, TILE_SIZE):
                    raise ValueError(f"画像サイズが不正: {img.size}")
                result = img.convert("RGB")
            tile.parent.mkdir(parents=True, exist_ok=True)
            tile.write_bytes(data)
            time.sleep(0.15)  # 連続アクセスを抑える
            return result
        except (OSError, ValueError, urllib.error.URLError) as exc:
            if attempt:
                raise RuntimeError(f"地理院タイルの取得に失敗: {url} ({exc})") from exc
            time.sleep(1.5)




