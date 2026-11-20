#!/usr/bin/env python3
"""IMC Raster Filter Boundary用のWGS84矩形ポリゴンSHPを生成する。

source-metadata.json の全チャンク外縁または単一画像のKML境界を使って出力する。
これはラスター画像をピクセル単位で切り抜く処理ではなく、IMCの比較試験用入力。
"""
import argparse
import json
import struct
from pathlib import Path


SHAPE_POLYGON = 5
WGS84_PRJ = (
    'GEOGCS["GCS_WGS_1984",DATUM["D_WGS_1984",'
    'SPHEROID["WGS_1984",6378137.0,298.257223563]],'
    'PRIMEM["Greenwich",0.0],UNIT["Degree",0.0174532925199433]]'
)


# 矩形境界をSHP、SHX、DBFのバイナリレコードへ変換する。
def make_shapefile_records(west, south, east, north):
    """SHP/SHX/DBFの最小構成を返す。外周は時計回り、WGS84経緯度。"""
    if not (-180 <= west < east <= 180 and -90 <= south < north <= 90):
        raise ValueError("不正なWGS84境界です")

    # ESRI Shapefileの外周リングの規約に従い、頂点を時計回りに並べる。
    points = [
        (west, south), (west, north), (east, north),
        (east, south), (west, south),
    ]
    content = struct.pack("<i4d2i", SHAPE_POLYGON, west, south, east, north, 1, len(points))
    content += struct.pack("<i", 0)
    content += b"".join(struct.pack("<2d", x, y) for x, y in points)

    # SHPには100バイトのヘッダーと1件のレコードを格納し、長さと位置は16ビットワードで記録する。
    shp_length_words = (100 + 8 + len(content)) // 2
    shp_header = struct.pack(">7i", 9994, 0, 0, 0, 0, 0, shp_length_words)
    shp_header += struct.pack("<2i4d", 1000, SHAPE_POLYGON, west, south, east, north) + b"\0" * 32
    shp = shp_header + struct.pack(">2i", 1, len(content) // 2) + content

    # SHXには同じヘッダーと、SHPレコードを指す索引を1件記録する。
    shx_length_words = (100 + 8) // 2
    shx_header = struct.pack(">7i", 9994, 0, 0, 0, 0, 0, shx_length_words)
    shx_header += struct.pack("<2i4d", 1000, SHAPE_POLYGON, west, south, east, north) + b"\0" * 32
    shx = shx_header + struct.pack(">2i", 50, len(content) // 2)

    # DBFは数値ID欄1つとデータ1件だけの最小構成にする。
    field = b"ID" + b"\0" * 9 + b"N" + b"\0" * 4 + struct.pack("<2B", 4, 0) + b"\0" * 14
    header_length = 32 + len(field) + 1
    record_length = 1 + 4
    dbf_header = bytearray(32)
    dbf_header[0:4] = bytes((3, 126, 1, 1))
    struct.pack_into("<I", dbf_header, 4, 1)
    struct.pack_into("<H", dbf_header, 8, header_length)
    struct.pack_into("<H", dbf_header, 10, record_length)
    dbf = bytes(dbf_header) + field + b"\r" + b" " + b"   1" + b"\x1a"
    return shp, shx, dbf


# メタデータから全画像チャンクを含む外接範囲を求める。
def bounds_from_metadata(metadata_path):
    data = json.loads(metadata_path.read_text(encoding="utf-8"))
    if data.get("complete") is True:
        chunks = data.get("chunks")
        if not chunks:
            raise ValueError("チャンク情報がありません")
        bounds = [chunk["bounds"] for chunk in chunks]
        west = min(b["west"] for b in bounds)
        east = max(b["east"] for b in bounds)
        south = min(b["south"] for b in bounds)
        north = max(b["north"] for b in bounds)
    elif isinstance(data.get("kml_bounds"), dict):
        bounds = data["kml_bounds"]
        west, south, east, north = (
            bounds.get("west"), bounds.get("south"),
            bounds.get("east"), bounds.get("north"),
        )
    else:
        raise ValueError(
            "メタデータにcomplete/chunksまたはkml_boundsがありません"
        )
    if not all(isinstance(v, (int, float)) for v in (west, south, east, north)):
        raise ValueError("メタデータの境界値が数値ではありません")
    return west, south, east, north


# 指定範囲からRaster Filter用の最小構成Shapefileを作る。
def write_filter_shapefile(metadata_path, output_path, inset_percent=0.0):
    if not 0 <= inset_percent < 50:
        raise ValueError("inset-percentは0以上50未満にしてください")
    west, south, east, north = bounds_from_metadata(metadata_path)
    dx = (east - west) * inset_percent / 100.0
    dy = (north - south) * inset_percent / 100.0
    west, south, east, north = west + dx, south + dy, east - dx, north - dy
    output_path = output_path.with_suffix("")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shp, shx, dbf = make_shapefile_records(west, south, east, north)
    output_path.with_suffix(".shp").write_bytes(shp)
    output_path.with_suffix(".shx").write_bytes(shx)
    output_path.with_suffix(".dbf").write_bytes(dbf)
    output_path.with_suffix(".prj").write_text(WGS84_PRJ + "\n", encoding="ascii")
    print(f"境界: W={west:.12f}, S={south:.12f}, E={east:.12f}, N={north:.12f}")
    print("出力:", output_path.with_suffix(".shp").resolve())
    print("IMCのRaster Filter Shapefileに指定する場合は、Raster Projectionも同じWGS84に合わせてください。")
    print(f"各辺の内側余白: {inset_percent:g}%")
    print("この境界は比較試験用です。SHP単独で黒枠を消す・画像を透明化する機能ではありません。")


# メタデータと出力先を受け取り、境界Shapefileを作成する。
def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("metadata", type=Path, help="生成済み source-metadata.json")
    parser.add_argument("--out", type=Path, default=Path("imc-raster-filter-boundary.shp"))
    parser.add_argument("--inset-percent", type=float, default=0.0,
                        help="境界を各辺から内側へ縮める割合（0以上50未満、比較試験用）")
    args = parser.parse_args()
    write_filter_shapefile(args.metadata, args.out, args.inset_percent)


if __name__ == "__main__":
    main()
