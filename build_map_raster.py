#!/usr/bin/env python3
"""指定した範囲の地図タイルから、IMC用の分割PNG＋KMLを作成する。"""
import argparse
import json
import math
import sys
from pathlib import Path
from xml.sax.saxutils import escape

from map_raster_source import (
    TILE_SIZE, fetch_tile, inverse_world_pixel, make_plan,
)

# 初回表示用の例。範囲はUIで自由に変更できます。
DEFAULT_BBOX = (35.140, 139.130, 35.330, 139.590)
DEFAULT_ZOOM = 15
DEFAULT_CHUNK_TILES = 8

# タイル範囲をIMCの最大画像サイズに合わせて分割する。
def make_chunks(bbox, zoom, chunk_tiles):
    """地図のXYZタイル範囲を重複・隙間なく分割する（外縁はタイル端）。"""
    if not 1 <= chunk_tiles <= 8:
        raise ValueError("--chunk-tiles は1〜8で指定してください（画像1辺最大2048px）")
    coverage = make_plan(bbox, zoom)
    x1, y1 = coverage["tile_start"]
    x2, y2 = coverage["tile_end"]
    chunks = []
    for y in range(y1, y2 + 1, chunk_tiles):
        for x in range(x1, x2 + 1, chunk_tiles):
            end_x = min(x + chunk_tiles - 1, x2)
            end_y = min(y + chunk_tiles - 1, y2)
            west, north = inverse_world_pixel(x * TILE_SIZE, y * TILE_SIZE, zoom)
            east, south = inverse_world_pixel((end_x + 1) * TILE_SIZE,
                                              (end_y + 1) * TILE_SIZE, zoom)
            name = f"map_z{zoom}_x{x}_y{y}"
            chunks.append({
                "name": name,
                "png": f"{name}.png",
                "start": [x, y],
                "end": [end_x, end_y],
                "tiles": (end_x - x + 1) * (end_y - y + 1),
                "pixels": [(end_x - x + 1) * TILE_SIZE,
                           (end_y - y + 1) * TILE_SIZE],
                "bounds": {"west": west, "east": east,
                           "north": north, "south": south},
            })
    assert sum(c["tiles"] for c in chunks) == coverage["tile_count"]
    return coverage, chunks


# 画像ピクセルと緯度経度を対応付けるPGWを書き出す。
def write_world_file(input_dir, chunk):
    """GroundOverlayのLatLonBoxと同じ範囲をPGWに記録する。"""
    bounds = chunk["bounds"]
    width, height = chunk["pixels"]
    pixel_x = (bounds["east"] - bounds["west"]) / width
    pixel_y = -(bounds["north"] - bounds["south"]) / height
    center_x = bounds["west"] + pixel_x / 2
    center_y = bounds["north"] + pixel_y / 2
    content = "\n".join((
        f"{pixel_x:.17g}", "0", "0", f"{pixel_y:.17g}",
        f"{center_x:.17g}", f"{center_y:.17g}", ""
    ))
    path = input_dir / (Path(chunk["png"]).stem + ".pgw")
    temp = path.with_name(path.name + ".tmp")
    try:
        temp.write_text(content, encoding="ascii")
        temp.replace(path)
    finally:
        if temp.exists():
            temp.unlink()


# 分割画像を地理座標上に配置するGroundOverlay KMLを作る。
def overlays_kml(chunks):
    """IMC Keyhole Modeでファイル指定するKML。PNGを同じフォルダに配置。"""
    parts = ['<?xml version="1.0" encoding="UTF-8"?>',
             '<kml xmlns="http://www.opengis.net/kml/2.2">',
             '  <Document>',
             '    <name>AT5 Map Builder raster</name>']
    for chunk in chunks:
        bounds = chunk["bounds"]
        parts.extend([
            '    <GroundOverlay>',
            f'      <name>{escape(chunk["name"])}</name>',
            f'      <Icon><href>{escape(chunk["png"])}</href></Icon>',
            '      <LatLonBox>',
            f'        <north>{bounds["north"]:.12f}</north>',
            f'        <south>{bounds["south"]:.12f}</south>',
            f'        <east>{bounds["east"]:.12f}</east>',
            f'        <west>{bounds["west"]:.12f}</west>',
            '        <rotation>0</rotation>',
            '      </LatLonBox>',
            '    </GroundOverlay>',
        ])
    parts.extend(['  </Document>', '</kml>', ''])
    return '\n'.join(parts)


# 緯度に応じた経度補正を行い、指定海里分だけ範囲を広げる。
def expand_bbox_nm(bbox, margin_nm):
    """指定した海里分だけ範囲を全周へ広げる（緯度経度近似）。"""
    if margin_nm < 0:
        raise ValueError("--margin-nm は0以上で指定してください")
    south, west, north, east = bbox
    lat_pad = margin_nm / 60.0
    mid_lat = (south + north) / 2.0
    lon_pad = margin_nm / (60.0 * math.cos(math.radians(mid_lat)))
    return south - lat_pad, west - lon_pad, north + lat_pad, east + lon_pad


# 地図ソースとズーム範囲を確認し、取得内容をマニフェストに記録する。
def plan_data(bbox, zoom, chunk_tiles, base_map="standard", lake_contours=False):
    from map_raster_source import TILE_SOURCES

    if base_map not in ("standard", "aerial", "usgs_imagery"):
        raise ValueError("--base-map は standard、aerial、usgs_imagery のいずれかを指定してください")
    min_zoom = 14 if base_map == "aerial" else 10
    max_zoom = 16 if base_map == "usgs_imagery" else 18
    if not min_zoom <= zoom <= max_zoom:
        raise ValueError(
            f"{base_map} のズームレベルは {min_zoom}～{max_zoom} で指定してください"
        )
    if lake_contours and not 11 <= zoom <= 17:
        raise ValueError("湖沼図（等深線）のズームレベルは11～17です")

    coverage, chunks = make_chunks(bbox, zoom, chunk_tiles)
    base_source = TILE_SOURCES[base_map]
    overlay_source = TILE_SOURCES["lake_contours"] if lake_contours else None
    return {
        "schema_version": 2,
        "preset": "custom",
        "base_map": base_map,
        "lake_contours": lake_contours,
        "zoom": zoom,
        "requested_bbox": list(bbox),
        "chunk_tiles": chunk_tiles,
        "tile_count": coverage["tile_count"],
        "tile_range": {"start": coverage["tile_start"],
                       "end": coverage["tile_end"]},
        "chunk_count": len(chunks),
        "chunks": chunks,
        "attribution": base_source.get("attribution", "国土地理院（地理院タイル）"),
        "base_source_url": base_source["url"],
        "overlay_source_url": overlay_source["url"] if overlay_source else None,
    }


# 既存マニフェストが今回の生成条件と一致するか比較する。
def is_same_plan(saved, expected):
    fields = ("schema_version", "preset", "base_map", "lake_contours",
              "zoom", "requested_bbox", "chunk_tiles", "tile_count",
              "tile_range", "chunk_count", "chunks", "base_source_url",
              "overlay_source_url")
    return all(saved.get(field) == expected.get(field) for field in fields)


# 既存フォルダーの内容を調べ、安全に再利用できるか確認する。
def validate_output_directory(out, plan):
    """既存の平塚パイロットや異なる設定の出力を上書きしない。"""
    out = out.resolve()
    input_dir = out / "imc-input"
    manifest_path = out / "source-metadata.json"
    if manifest_path.exists():
        saved = json.loads(manifest_path.read_text(encoding="utf-8"))
        if not is_same_plan(saved, plan):
            raise ValueError("既存の出力と設定が異なります。別の --out を指定してください")
    elif input_dir.exists() and any(input_dir.iterdir()):
        raise ValueError("出力先に既存のIMC入力があります。別の --out を指定してください")
    expected = {c["png"] for c in plan["chunks"]}
    expected.add("map_overlays.kml")
    expected.update(c["png"][:-4] + ".kml" for c in plan["chunks"])
    expected.update(c["png"][:-4] + ".pgw" for c in plan["chunks"])
    if input_dir.exists():
        unknown = [p.name for p in input_dir.iterdir() if p.name not in expected]
        if unknown:
            raise ValueError(f"出力先に想定外のファイルがあります: {unknown[:5]}")


# タイルを取得して分割PNGを作り、完了後にKMLとメタデータを保存する。
def generate_images(out, plan, refresh=False, tile_loader=fetch_tile):
    """出力を前回と同じ条件で再開できる。完了前の生成物はIMCに渡さない。"""
    try:
        from PIL import Image
    except ImportError as exc:
        raise RuntimeError("Pillowが必要: py -m pip install pillow") from exc

    validate_output_directory(out, plan)
    input_dir = out / "imc-input"
    input_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = out / "_tile_cache"
    metadata_path = out / "source-metadata.json"
    metadata_path.write_text(json.dumps({**plan, "complete": False},
                                        ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    for i, chunk in enumerate(plan["chunks"], 1):
        png = input_dir / chunk["png"]
        # 途中で停止しても、完成したPNGは再利用できる。--refreshは再取得する。
        if png.is_file() and not refresh:
            try:
                with Image.open(png) as check:
                    check.verify()
                with Image.open(png) as check:
                    if check.size == tuple(chunk["pixels"]):
                        print(f"[{i}/{plan['chunk_count']}] 既存PNGを再利用: {png.name}")
                        continue
            except OSError:
                print("不完全なPNGを再生成:", png.name)
        x1, y1 = chunk["start"]
        x2, y2 = chunk["end"]
        image = Image.new("RGBA", tuple(chunk["pixels"]))
        for y in range(y1, y2 + 1):
            for x in range(x1, x2 + 1):
                offset = ((x - x1) * TILE_SIZE, (y - y1) * TILE_SIZE)
                base_tile = tile_loader(
                    plan["zoom"], x, y, cache_dir, refresh,
                    source=plan["base_map"],
                )
                image.alpha_composite(base_tile.convert("RGBA"), dest=offset)
                if plan["lake_contours"]:
                    contour_tile = tile_loader(
                        plan["zoom"], x, y, cache_dir, refresh,
                        source="lake_contours", optional=True,
                    )
                    image.alpha_composite(contour_tile.convert("RGBA"), dest=offset)
        temp = input_dir / (png.stem + ".tmp")
        try:
            image.convert("RGB").save(temp, format="PNG", optimize=True)
            temp.replace(png)
        finally:
            if temp.exists():
                temp.unlink()
        print(f"[{i}/{plan['chunk_count']}] 完成: {png.name}")

    # PNGと同じLatLonBoxからPGWを生成し、Keyhole Modeの手作業を省く。
    # PGWはWGS84緯度経度で、KML GroundOverlayの外枠に一致させる。
    for chunk in plan["chunks"]:
        write_world_file(input_dir, chunk)

    # すべてのPNGが完成した場合だけKMLを出力。
    (input_dir / "map_overlays.kml").write_text(
        overlays_kml(plan["chunks"]), encoding="utf-8")
    # 複数GroundOverlayをIMCで一括処理できない場合のフォールバック。
    for chunk in plan["chunks"]:
        (input_dir / (chunk["name"] + ".kml")).write_text(
            overlays_kml([chunk]), encoding="utf-8")
    metadata_path.write_text(json.dumps({**plan, "complete": True},
                                        ensure_ascii=False, indent=2) + "\n",
                             encoding="utf-8")
    print("KML:", (input_dir / "map_overlays.kml").resolve())
    print("PGW: PNGごとに同じLatLonBoxから自動生成済み")
    map_names = {"standard": "標準地図", "aerial": "国土地理院航空写真",
                 "usgs_imagery": "USGS航空写真"}
    print(f"地図: {map_names[plan['base_map']]}"
          + (" ＋ 湖沼図（等深線）" if plan["lake_contours"] else ""))
    print("IMC Raster Mode: imc-input をSource Folder、出力フォルダー内のimc-outputをWork Directoryに指定")
    print("このツールはAT5化・SDカードへの書き込みを行いません")


# 引数を検証し、タイル取得計画と画像生成を実行する。
def main(argv=None):
    parser = argparse.ArgumentParser(description="指定範囲の分割ラスターIMC入力データを作成")
    parser.add_argument("--bbox", nargs=4, type=float, default=DEFAULT_BBOX,
                        metavar=("SOUTH", "WEST", "NORTH", "EAST"))
    parser.add_argument("--zoom", type=int, default=DEFAULT_ZOOM)
    parser.add_argument("--base-map", choices=("standard", "aerial", "usgs_imagery"), default="standard",
                        help="背景地図の種類（standard: 標準地図、aerial: 国土地理院航空写真、usgs_imagery: USGS航空写真）")
    parser.add_argument("--lake-contours", action="store_true",
                        help="湖沼図（等深線）を背景地図に重ねる")
    parser.add_argument("--chunk-tiles", type=int, default=DEFAULT_CHUNK_TILES)
    parser.add_argument("--out", type=Path, help="別のズーム・設定には別の出力先を使用")
    parser.add_argument("--max-tiles", type=int, default=1000,
                        help="警告を出す目安タイル数（超過しても処理を続行。標準1000）")
    parser.add_argument("--margin-nm", type=float, default=0,
                        help="地図範囲の四辺に加える余白（海里）")
    parser.add_argument("--dry-run", action="store_true", help="ダウンロードや書込みなし")
    parser.add_argument("--refresh", action="store_true", help="キャッシュと出力PNGを再取得")
    args = parser.parse_args(argv)
    base_bbox = tuple(args.bbox)
    bbox = expand_bbox_nm(base_bbox, args.margin_nm)
    zoom = args.zoom
    chunk_tiles = args.chunk_tiles
    plan = plan_data(bbox, zoom, chunk_tiles, args.base_map, args.lake_contours)
    if args.margin_nm:
        plan["margin_nm"] = args.margin_nm
        plan["base_bbox"] = list(base_bbox)
    bbox_tag = "-".join(("m" if v < 0 else "p") + f"{round(abs(v)*1_000_000):09d}" for v in bbox)
    map_tag = "aerial" if args.base_map == "aerial" else "standard"
    if args.lake_contours:
        map_tag += "-lake"
    default_out = Path("builds") / f"map-{map_tag}-z{zoom}-{bbox_tag}"
    if args.margin_nm:
        default_out = Path(f"{default_out}-margin-{args.margin_nm:g}nm")
    out = args.out or default_out
    print(f"範囲: {bbox} / ZL{zoom}" + (f"（元範囲から各辺{args.margin_nm:g}海里拡張）" if args.margin_nm else ""))
    print(f"取得タイル: {plan['tile_count']} 枚 / PNG: {plan['chunk_count']} 枚")
    print(f"保存先: {out.resolve()}")
    print("出典: 国土地理院（地理院タイル："
          + ("全国最新写真（シームレス）" if plan["base_map"] == "aerial" else "標準地図")
          + ("、湖沼図" if plan["lake_contours"] else "") + "）")
    for chunk in plan["chunks"]:
        print(f"  {chunk['png']}: {chunk['pixels'][0]}x{chunk['pixels'][1]} px ({chunk['tiles']}タイル)")
    if args.max_tiles < 1:
        raise ValueError("--max-tiles は1以上で指定してください")
    if plan["tile_count"] > args.max_tiles:
        print(
            f"警告: タイル数 {plan['tile_count']} 枚が目安 {args.max_tiles} 枚を超えています。"
            "処理を続行します。",
            file=sys.stderr,
        )
    if args.dry_run:
        print("ドライラン完了：ネットワーク通信・ファイル作成は行いませんでした")
        return
    generate_images(out, plan, refresh=args.refresh)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError, KeyboardInterrupt) as exc:
        print("エラー:", exc, file=sys.stderr)
        sys.exit(1)
