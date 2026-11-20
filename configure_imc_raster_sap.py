#!/usr/bin/env python3
"""IMC 0.7.4 Raster ModeのSAPへ出力先とRaster Filter SHPを設定する。

SAPの未知フィールドは保持し、Raster modeのWork DirectoryとRaster Filter Shapefileだけを更新する。
"""
import argparse
import hashlib
import os
import struct
import sys
import zipfile
from pathlib import Path


MAGIC = b"GPB2"


def read_varint(data, pos):
    value = 0
    shift = 0
    while pos < len(data):
        byte = data[pos]
        pos += 1
        value |= (byte & 0x7F) << shift
        if byte < 0x80:
            return value, pos
        shift += 7
        if shift >= 70:
            raise ValueError("varintが長すぎます")
    raise ValueError("varintが途中で終わっています")


def encode_varint(value):
    if value < 0:
        raise ValueError("varintは非負整数である必要があります")
    out = bytearray()
    while value >= 0x80:
        out.append((value & 0x7F) | 0x80)
        value >>= 7
    out.append(value)
    return bytes(out)


def parse_fields(data):
    """Protobuf wire fieldsを解析し、未知フィールドを含む順序を保持する。"""
    fields = []
    pos = 0
    while pos < len(data):
        start = pos
        key, pos = read_varint(data, pos)
        number, wire = key >> 3, key & 7
        if number == 0:
            raise ValueError("不正なProtobuf field number 0")
        if wire == 0:
            value_start = pos
            _, pos = read_varint(data, pos)
            value = data[value_start:pos]
        elif wire == 1:
            end = pos + 8
            if end > len(data):
                raise ValueError("fixed64が途中で終わっています")
            value = data[pos:end]
            pos = end
        elif wire == 2:
            length, pos = read_varint(data, pos)
            end = pos + length
            if end > len(data):
                raise ValueError("length-delimited fieldが途中で終わっています")
            value = data[pos:end]
            pos = end
        elif wire == 5:
            end = pos + 4
            if end > len(data):
                raise ValueError("fixed32が途中で終わっています")
            value = data[pos:end]
            pos = end
        else:
            raise ValueError(f"未対応のProtobuf wire type: {wire}")
        fields.append((number, wire, value, data[start:pos]))
    return fields


def encode_length_field(number, value):
    return encode_varint((number << 3) | 2) + encode_varint(len(value)) + value


def replace_single_length_field(message, number, new_value, label):
    fields = parse_fields(message)
    matches = [i for i, field in enumerate(fields)
               if field[0] == number and field[1] == 2]
    if len(matches) != 1:
        raise ValueError(f"{label}: field {number} が一つに特定できません")
    index = matches[0]
    replacement = (number, 2, new_value, encode_length_field(number, new_value))
    fields[index] = replacement
    return b"".join(field[3] for field in fields)


def set_length_field(message, number, new_value, label):
    """既存のlength-delimited fieldを置換し、なければ追加する。"""
    fields = parse_fields(message)
    matches = [i for i, field in enumerate(fields) if field[0] == number]
    if len(matches) > 1:
        raise ValueError(f"{label}: field {number} が複数あります")
    if matches:
        index = matches[0]
        field = fields[index]
        if field[1] != 2:
            raise ValueError(f"{label}: field {number} のwire typeが不正です")
        fields[index] = (
            number, 2, new_value, encode_length_field(number, new_value)
        )
        return b"".join(field[3] for field in fields)
    return message + encode_length_field(number, new_value)



def replace_single_varint_field(message, number, new_value, label):
    if new_value < 0:
        raise ValueError(f"{label}: 値は0以上にしてください")
    fields = parse_fields(message)
    matches = [i for i, field in enumerate(fields)
               if field[0] == number and field[1] == 0]
    if len(matches) != 1:
        raise ValueError(f"{label}: field {number} が一つに特定できません")
    index = matches[0]
    encoded = encode_varint((number << 3) | 0) + encode_varint(new_value)
    fields[index] = (number, 0, encode_varint(new_value), encoded)
    return b"".join(field[3] for field in fields)

def replace_single_fixed32_field(message, number, new_value, label):
    fields = parse_fields(message)
    matches = [i for i, field in enumerate(fields)
               if field[0] == number and field[1] == 5]
    if len(matches) != 1:
        raise ValueError(f"{label}: fixed32 field {number} が一つに特定できません")
    index = matches[0]
    value = struct.pack("<f", float(new_value))
    encoded = encode_varint((number << 3) | 5) + value
    fields[index] = (number, 5, value, encoded)
    return b"".join(field[3] for field in fields)

def one_field(fields, number, wire, label):
    matches = [f for f in fields if f[0] == number and f[1] == wire]
    if len(matches) != 1:
        raise ValueError(f"{label}: field {number} が一つに特定できません")
    return matches[0]


def normalize_imc_path(path, directory=False):
    value = str(Path(path).resolve()).replace("\\", "/")
    if directory:
        value = value.rstrip("/") + "/"
    return value


def _is_raster_template_bytes(raw):
    """バイト列がIMC Raster Mode設定か確認する。"""
    try:
        if not raw.startswith(MAGIC):
            return False
        declared_length, body_start = read_varint(raw, len(MAGIC))
        body = raw[body_start:]
        if declared_length != len(body):
            return False
        fields = parse_fields(body)
        mode = one_field(fields, 1, 0, "SAP Processing Mode")
        mode_value, end = read_varint(mode[2], 0)
        if end != len(mode[2]) or mode_value != 1:
            return False
        raster = one_field(fields, 3, 2, "Raster Mode")[2]
        raster_fields = parse_fields(raster)
        one_field(raster_fields, 1, 2, "Raster Source Folder")
        one_field(raster_fields, 2, 2, "Raster Work Directory")
        one_field(raster_fields, 3, 5, "Raster Min Resolution")
        one_field(raster_fields, 4, 5, "Raster Max Resolution")
        one_field(fields, 4, 2, "Keyhole Mode input")
        options = one_field(fields, 9, 2, "Raster Options")[2]
        options_fields = parse_fields(options)
        one_field(options_fields, 2, 2, "Raster Filter Shapefile")
        one_field(options_fields, 6, 0, "Raster Filter Alpha")
        return True
    except (ValueError, IndexError):
        return False


def is_raster_template(path):
    """ファイルが判別可能なIMC Raster Mode設定か確認する。"""
    try:
        return _is_raster_template_bytes(Path(path).read_bytes())
    except OSError:
        return False


def find_raster_template(imc_exe):
    """IMC配布物のサンプルからRaster Mode設定を探す。ZIPは展開せずに読み取る。"""
    exe_dir = Path(imc_exe).resolve().parent
    bases = (exe_dir, *list(exe_dir.parents)[:2])
    roots = []
    for base in bases:
        roots.extend((base / "IMC_Sample" / "Raster", base / "IMC_Sample"))

    candidates = []
    seen = set()
    for root in roots:
        if not root.is_dir():
            continue
        try:
            for path in root.rglob("*.sap"):
                resolved = path.resolve()
                if resolved not in seen:
                    seen.add(resolved)
                    candidates.append(resolved)
        except OSError:
            continue
    for path in sorted(candidates, key=lambda item: (item.name.lower(), str(item).lower())):
        if is_raster_template(path):
            return path

    sample_archives = []
    for base in bases:
        if not base.is_dir():
            continue
        try:
            sample_archives.extend(
                path for path in base.iterdir()
                if path.is_file() and "sample" in path.name.casefold()
                and path.suffix.casefold() == ".zip"
            )
        except OSError:
            continue

    cache_root = Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "AT5MapBuilder" / "imc-template-cache"
    for archive in sorted(set(sample_archives), key=lambda item: item.name.casefold()):
        try:
            with zipfile.ZipFile(archive) as bundle:
                members = sorted(
                    (info for info in bundle.infolist()
                     if not info.is_dir() and info.filename.casefold().endswith(".sap")),
                    key=lambda info: info.filename.casefold(),
                )
                for info in members:
                    raw = bundle.read(info)
                    if not _is_raster_template_bytes(raw):
                        continue
                    digest = hashlib.sha256(
                        str(archive.resolve()).encode("utf-8") + b"\0"
                        + info.filename.encode("utf-8") + b"\0" + raw
                    ).hexdigest()[:16]
                    cached = cache_root / f"{archive.stem}-{digest}-{Path(info.filename).name}"
                    if not cached.is_file():
                        cache_root.mkdir(parents=True, exist_ok=True)
                        cached.write_bytes(raw)
                    return cached
        except (OSError, zipfile.BadZipFile, RuntimeError):
            continue

    raise FileNotFoundError(
        "Raster Mode設定が見つかりません。IMC_Application_x64の近くに"
        "IMC_Sampleフォルダー、または名前にSampleを含むZIPがあるか確認してください。"
    )


def configure_sap(source, output, work_dir, raster_filter,
                  source_folder=None, min_resolution=None, max_resolution=None,
                  filter_alpha=None, filter_image_boundary=None,
                  atlas_description=None):
    if os.name != "nt":
        raise RuntimeError("IMC用SAPのパス設定はWindows上で実行してください")
    source = Path(source).resolve()
    output = Path(output).resolve()
    work_dir = Path(work_dir).resolve()
    raster_filter = Path(raster_filter).resolve() if raster_filter is not None else None
    source_folder = Path(source_folder).resolve() if source_folder is not None else None
    if (min_resolution is None) != (max_resolution is None):
        raise ValueError("Min/Max Resolutionは両方指定してください")
    if min_resolution is not None and (min_resolution < 1 or max_resolution < min_resolution):
        raise ValueError("Resolutionは1以上で、MaxはMin以上にしてください")
    if filter_alpha is not None and not 0 <= filter_alpha <= 255:
        raise ValueError("Filter Alphaは0〜255で指定してください")
    if atlas_description is not None:
        if (not atlas_description or not atlas_description.isascii()
                or any(ord(char) < 32 or ord(char) > 126 for char in atlas_description)):
            raise ValueError("Atlas Descriptionは空でない半角ASCII文字で指定してください")
        if len(atlas_description) > 64:
            raise ValueError("Atlas Descriptionは64文字以内で指定してください")

    if source == output:
        raise ValueError("入力SAPを上書きできません")
    if not source.is_file():
        raise FileNotFoundError(f"入力SAPがありません: {source}")
    if output.exists():
        raise FileExistsError(f"出力SAPが既にあります: {output}")
    if work_dir.exists() and any(work_dir.iterdir()):
        raise FileExistsError(f"Work Directoryが空ではありません: {work_dir}")
    if source_folder is not None and not source_folder.is_dir():
        raise FileNotFoundError(f"Source Folderがありません: {source_folder}")
    if raster_filter is not None:
        for suffix in (".shp", ".shx", ".dbf", ".prj"):
            component = raster_filter.with_suffix(suffix)
            if not component.is_file():
                raise FileNotFoundError(f"Raster Filter shapefile一式が不足しています: {component}")

    raw = source.read_bytes()
    if not raw.startswith(MAGIC):
        raise ValueError("SAP signatureがGPB2ではありません")
    declared_length, body_start = read_varint(raw, len(MAGIC))
    body = raw[body_start:]
    if declared_length != len(body):
        raise ValueError(
            f"SAP長が一致しません: header={declared_length}, actual={len(body)}"
        )

    root_fields = parse_fields(body)
    mode = one_field(root_fields, 1, 0, "SAP")
    mode_value, mode_end = read_varint(mode[2], 0)
    if mode_end != len(mode[2]) or mode_value != 1:
        raise ValueError("このSAPはRaster Modeではありません")

    raster = one_field(root_fields, 3, 2, "SAP")[2]
    raster_fields = parse_fields(raster)
    source_field = one_field(raster_fields, 1, 2, "Raster Mode")
    if not source_field[2]:
        raise ValueError("Source Folderが空です")
    work_value = normalize_imc_path(work_dir, directory=True).encode("ascii")
    raster_updated = replace_single_length_field(
        raster, 2, work_value, "Raster Mode Work Directory"
    )
    if source_folder is not None:
        source_value = normalize_imc_path(source_folder, directory=True).encode("ascii")
        raster_updated = replace_single_length_field(
            raster_updated, 1, source_value, "Raster Mode Source Folder"
        )
    if min_resolution is not None:
        raster_updated = replace_single_fixed32_field(
            raster_updated, 3, min_resolution, "Raster Mode Min Resolution"
        )
        raster_updated = replace_single_fixed32_field(
            raster_updated, 4, max_resolution, "Raster Mode Max Resolution"
        )
    body_updated = replace_single_length_field(
        body, 3, raster_updated, "Raster Mode"
    )

    # Root field 4 keeps the KML selected in Keyhole Mode. When changing the
    # raster folder, move that project reference to the matching KML there too.
    if source_folder is not None:
        root_fields = parse_fields(body_updated)
        source_ref = one_field(root_fields, 4, 2, "Keyhole Mode input")
        source_ref_fields = parse_fields(source_ref[2])
        source_path = one_field(source_ref_fields, 1, 2, "Keyhole input path")
        old_path = source_path[2].decode("ascii")
        source_name = old_path.replace("\\", "/").rsplit("/", 1)[-1]
        keyhole_path = normalize_imc_path(source_folder / source_name).encode("ascii")
        source_ref_updated = replace_single_length_field(
            source_ref[2], 1, keyhole_path, "Keyhole input path"
        )
        body_updated = replace_single_length_field(
            body_updated, 4, source_ref_updated, "Keyhole Mode input"
        )

    # Root field 9 is Raster Options; subfield 2 is Raster Filter Shapefile.
    root_fields = parse_fields(body_updated)
    options = one_field(root_fields, 9, 2, "SAP Raster Options")[2]
    filter_value = (
        normalize_imc_path(raster_filter).encode("ascii")
        if raster_filter is not None else b""
    )
    options_updated = replace_single_length_field(
        options, 2, filter_value, "Raster Filter Shapefile"
    )
    if filter_alpha is not None:
        options_updated = replace_single_varint_field(
            options_updated, 6, filter_alpha, "Raster Filter Alpha"
        )
    body_updated = replace_single_length_field(
        body_updated, 9, options_updated, "SAP Raster Options"
    )
    if filter_image_boundary is not None:
        # Root field 17 is IMC's Filter Image Boundary checkbox (0/1).
        root_fields = parse_fields(body_updated)
        matches = [f for f in root_fields if f[0] == 17 and f[1] == 0]
        if len(matches) > 1:
            raise ValueError("Filter Image Boundary: root field 17 が複数あります")
        encoded = encode_varint((17 << 3) | 0) + encode_varint(int(filter_image_boundary))
        if matches:
            body_updated = replace_single_varint_field(
                body_updated, 17, int(filter_image_boundary), "Filter Image Boundary"
            )
        else:
            body_updated += encoded

    if atlas_description is not None:
        # Root field 7 is Atlas Options; nested field 3 is its Description.
        root_fields = parse_fields(body_updated)
        atlas_matches = [f for f in root_fields if f[0] == 7]
        if len(atlas_matches) > 1:
            raise ValueError("Atlas Options: root field 7 が複数あります")
        if atlas_matches and atlas_matches[0][1] != 2:
            raise ValueError("Atlas Options: root field 7 のwire typeが不正です")
        atlas_options = atlas_matches[0][2] if atlas_matches else b""
        atlas_options = set_length_field(
            atlas_options, 3, atlas_description.encode("ascii"),
            "Atlas Description"
        )
        body_updated = set_length_field(body_updated, 7, atlas_options, "Atlas Options")

    result = MAGIC + encode_varint(len(body_updated)) + body_updated
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.name + ".tmp")
    try:
        temp.write_bytes(result)
        temp.replace(output)
    finally:
        if temp.exists():
            temp.unlink()
    print(f"入力SAP: {source}")
    print("Raster Filter:", raster_filter if raster_filter is not None else "(なし)")
    if source_folder is not None:
        print(f"Source Folder: {source_folder}")
        print(f"Keyhole Input: {source_folder / source_name}")
    if min_resolution is not None:
        print(f"Resolution: Min={min_resolution}, Max={max_resolution}")
    if filter_alpha is not None:
        print(f"Filter Alpha: {filter_alpha}")
    if filter_image_boundary is not None:
        print(f"Filter Image Boundary: {'ON' if filter_image_boundary else 'OFF'}")
    if atlas_description is not None:
        print(f"Atlas Description: {atlas_description}")
    print(f"Work Directory: {work_dir}")
    print(f"出力SAP: {output}")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("sap", type=Path, help="元のRaster Mode SAP（変更しません）")
    filter_group = parser.add_mutually_exclusive_group(required=True)
    filter_group.add_argument("--raster-filter", type=Path,
                              help="Raster Filter Shapefile（.shp）")
    filter_group.add_argument("--no-raster-filter", action="store_true",
                              help="Raster Filterを空にして対照用SAPを生成")
    parser.add_argument("--work-dir", required=True, type=Path,
                        help="空または未作成の新規Work Directory")
    parser.add_argument("--source-folder", type=Path,
                        help="Raster ModeのSource Folderを変更")
    parser.add_argument("--min-resolution", type=float,
                        help="Raster ModeのMin Resolution（Maxと同時指定）")
    parser.add_argument("--max-resolution", type=float,
                        help="Raster ModeのMax Resolution（Minと同時指定）")
    parser.add_argument("--filter-alpha", type=int,
                        help="Raster OptionsのFilter Alpha（0〜255）")
    parser.add_argument("--atlas-description",
                        help="Atlas OptionsのDescription（例: M=Map01）")
    boundary = parser.add_mutually_exclusive_group()
    boundary.add_argument("--filter-image-boundary", dest="filter_image_boundary",
                          action="store_true", help="黒い画像境界をフィルター")
    boundary.add_argument("--no-filter-image-boundary", dest="filter_image_boundary",
                          action="store_false", help="画像境界フィルターを無効化")
    parser.set_defaults(filter_image_boundary=None)
    parser.add_argument("--out", required=True, type=Path,
                        help="新しいSAPの出力パス")
    args = parser.parse_args(argv)
    raster_filter = None if args.no_raster_filter else args.raster_filter
    configure_sap(
        args.sap, args.out, args.work_dir, raster_filter,
        args.source_folder, args.min_resolution, args.max_resolution,
        args.filter_alpha, args.filter_image_boundary, args.atlas_description
    )


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as exc:
        print("エラー:", exc, file=sys.stderr)
        sys.exit(1)
