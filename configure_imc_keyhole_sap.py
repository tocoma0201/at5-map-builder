#!/usr/bin/env python3
"""Raster Mode SAPをKeyhole Mode用に設定し、PGW生成を補助する。"""
import argparse
import os
import sys
from pathlib import Path

from configure_imc_raster_sap import (
    MAGIC, encode_varint, encode_length_field, parse_fields, read_varint,
    replace_single_length_field, replace_single_varint_field, one_field,
)


# Raster ModeのSAPを複製し、Keyhole Mode入力KMLを設定する。
def configure_keyhole_sap(source, kml, output):
    source = Path(source).resolve()
    kml = Path(kml).resolve()
    output = Path(output).resolve()
    if source == output:
        raise ValueError("入力SAPを上書きできません")
    if not source.is_file():
        raise FileNotFoundError(f"入力SAPがありません: {source}")
    if not kml.is_file():
        raise FileNotFoundError(f"Keyhole KMLがありません: {kml}")
    if output.exists():
        raise FileExistsError(f"出力SAPが既にあります: {output}")

    raw = source.read_bytes()
    if not raw.startswith(MAGIC):
        raise ValueError("SAP signatureがGPB2ではありません")
    declared_length, body_start = read_varint(raw, len(MAGIC))
    body = raw[body_start:]
    if declared_length != len(body):
        raise ValueError("SAP長が一致しません")

    fields = parse_fields(body)
    mode = one_field(fields, 1, 0, "SAP Processing Mode")
    mode_value, end = read_varint(mode[2], 0)
    if end != len(mode[2]) or mode_value not in (1, 2):
        raise ValueError("Raster/Keyhole ModeのSAPではありません")

    body = replace_single_varint_field(body, 1, 2, "Keyhole Processing Mode")
    kml_path = str(kml).replace("\\", "/").encode("ascii")
    root_fields = parse_fields(body)
    keyhole_matches = [field for field in root_fields if field[0] == 4]
    if len(keyhole_matches) > 1:
        raise ValueError("Keyhole Mode input: root field 4 が複数あります")
    if keyhole_matches:
        keyhole_field = keyhole_matches[0]
        if keyhole_field[1] != 2:
            raise ValueError("Keyhole Mode input: root field 4 の形式が不正です")
        keyhole = keyhole_field[2]
        keyhole = replace_single_length_field(
            keyhole, 1, kml_path, "Keyhole KML path"
        )
        body = replace_single_length_field(
            body, 4, keyhole, "Keyhole Mode input"
        )
    else:
        # Sample SAPによってKeyhole入力欄が省略されている場合は追加する。
        keyhole = encode_length_field(1, kml_path)
        body += encode_length_field(4, keyhole)

    result = MAGIC + encode_varint(len(body)) + body
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.name + ".tmp")
    try:
        temp.write_bytes(result)
        temp.replace(output)
    finally:
        if temp.exists():
            temp.unlink()
    print(f"Keyhole入力KML: {kml}")
    print(f"Keyhole用SAP: {output}")


# コマンドライン引数を読み取り、Keyhole用SAPを作成する。
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sap", type=Path, help="GUIで保存したIMCプロジェクトSAP")
    parser.add_argument("kml", type=Path, help="Keyhole Modeで処理するKML")
    parser.add_argument("--out", required=True, type=Path, help="新しいSAP出力先")
    args = parser.parse_args(argv)
    configure_keyhole_sap(args.sap, args.kml, args.out)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as exc:
        print("エラー:", exc, file=sys.stderr)
        sys.exit(1)
