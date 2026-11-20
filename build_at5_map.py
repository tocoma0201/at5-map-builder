#!/usr/bin/env python3
"""選択範囲の地理院タイルをAT5へ変換し、指定先に出力する。"""
import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from configure_imc_keyhole_sap import configure_keyhole_sap
from configure_imc_raster_sap import configure_sap, find_raster_template


# 既存の成果物と重ならない連番の作業名を決める。
def next_run_number(output_dir, resolution_label):
    number = 1
    while True:
        suffix = f"batch-{number:02d}"
        sap = output_dir / f"raster-{resolution_label}-{suffix}.sap"
        work = output_dir / f"imc-output-{resolution_label}-{suffix}"
        keyhole_sap = output_dir / f"keyhole-{suffix}.sap"
        if not sap.exists() and not work.exists() and not keyhole_sap.exists():
            return suffix, sap, work, keyhole_sap
        number += 1


# 外部コマンドを表示して実行し、失敗時は処理を中断する。
def run(command, *, cwd=None):
    print("+", subprocess.list2cmdline([str(part) for part in command]), flush=True)
    result = subprocess.run(command, cwd=cwd)
    if result.returncode:
        raise RuntimeError(f"コマンド失敗 (exit={result.returncode})")
    return result


# IMCをバッチモードで起動し、ログから完了を確認する。
def run_imc(imc_exe, sap_path, log_path):
    try:
        result = subprocess.run(
            [str(imc_exe), "-b", str(sap_path), str(log_path)],
            cwd=imc_exe.parent,
        )
    except OSError as exc:
        raise RuntimeError(f"IMCを起動できません: {exc}") from exc
    if result.returncode:
        log_tail(log_path)
        raise RuntimeError(f"IMC CLIが終了コード {result.returncode} で終了しました")
    if not log_path.is_file():
        raise RuntimeError(f"IMCログが作成されませんでした: {log_path}")
    log_text = log_path.read_text(encoding="utf-8", errors="replace")
    if "Process Complete!" not in log_text:
        log_tail(log_path)
        raise RuntimeError("IMCログにProcess Complete!がありません")
    return log_text


# IMCログの末尾をエラー調査用に表示する。
def log_tail(path, lines=50):
    if not path.is_file():
        print(f"IMCログがありません: {path}", file=sys.stderr)
        return
    text = path.read_text(encoding="utf-8", errors="replace").splitlines()
    print("\n".join(text[-lines:]), file=sys.stderr)


# PGWが未回転の6行形式で出力されたことを確認する。
def validate_pgw(path):
    values = [float(line.strip()) for line in path.read_text(encoding="ascii").splitlines()]
    if len(values) != 6 or not all(map(lambda value: abs(value) < float("inf"), values)):
        raise ValueError(f"Keyhole Modeが有効なPGWを出力していません: {path}")
    if values[1] != 0 or values[2] != 0:
        raise ValueError(f"未回転PGWではありません: {path}")


# KMLをKeyhole Modeで処理し、各画像に対応するPGWを生成する。
def make_keyhole_pgws(imc_exe, template_sap, source_folder, output_dir, run_tag, chunks):
    kml_path = source_folder / "map_overlays.kml"
    keyhole_sap = output_dir / f"keyhole-highres-{run_tag}.sap"
    keyhole_log = output_dir / f"keyhole-highres-{run_tag}.log"
    configure_keyhole_sap(template_sap, kml_path, keyhole_sap)

    pgw_paths = [source_folder / (Path(chunk["png"]).stem + ".pgw") for chunk in chunks]
    # 前回の試行で作られたPGWを退避し、Keyhole Modeが今回出力したことを確認する。
    previous = {path: path.read_bytes() if path.exists() else None for path in pgw_paths}
    for path in pgw_paths:
        path.unlink(missing_ok=True)
    try:
        run_imc(imc_exe, keyhole_sap, keyhole_log)
        for path in pgw_paths:
            if not path.is_file():
                raise RuntimeError(f"Keyhole ModeがPGWを生成しませんでした: {path.name}")
            validate_pgw(path)
    except Exception:
        log_tail(keyhole_log)
        for path, data in previous.items():
            path.unlink(missing_ok=True)
            if data is not None:
                path.write_bytes(data)
        raise
    print(f"Keyhole ModeでPGW {len(pgw_paths)}枚を生成しました")


# 画像取得からIMC変換、AT5検証、指定先へのコピーまでを制御する。
def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bbox", nargs=4, type=float,
                        metavar=("SOUTH", "WEST", "NORTH", "EAST"),
                        help="任意の範囲を指定（南 緯度、西 経度、北 緯度、東 経度）")
    parser.add_argument("--output-dir", type=Path,
                        help="広域画像の生成先（既存PNGは再利用）")
    parser.add_argument("--margin-nm", type=float, default=0,
                        help="地図範囲の四辺に加える余白（海里、標準0＝現行範囲）")
    parser.add_argument("--template-sap", type=Path,
                        default=None,
                        help="上級者向け: IMC付属設定の自動検出に代えて設定ファイルを指定")
    parser.add_argument("--imc-exe", type=Path,
                        default=None, help="InsightMapCreator.exeの場所（必須）")
    parser.add_argument("--max-tiles", type=int, default=1000,
                        help="タイル数超過時に警告する目安（超過しても処理を続行。標準1000）")
    parser.add_argument("--min-resolution", type=float, default=1)
    parser.add_argument("--max-resolution", type=float, default=8192)
    parser.add_argument("--filter-alpha", type=int, default=0,
                        help="Raster Filter Alpha（標準0）")
    parser.add_argument("--filter-image-boundary",
                        action=argparse.BooleanOptionalAction, default=True,
                        help="IMCの画像境界フィルターを有効化（標準）")
    parser.add_argument("--copy-to", type=Path,
                        help="Build成功後にAT5だけをコピーするフォルダー")
    parser.add_argument("--at5-prefix", default="",
                        help="AT5名の先頭文字とTi2用Atlas Description（例: Map01）")
    args = parser.parse_args(argv)
    if args.at5_prefix and not re.fullmatch(r"[A-Za-z0-9-]{1,32}", args.at5_prefix):
        parser.error("--at5-prefixは半角英数字とハイフンの1〜32文字で指定してください")
    if not args.imc_exe:
        parser.error("--imc-exe でInsightMapCreator.exeの場所を指定してください")
    supported_resolutions = {float(2 ** exponent) for exponent in range(14)}
    if (args.min_resolution not in supported_resolutions
            or args.max_resolution not in supported_resolutions
            or args.max_resolution < args.min_resolution):
        parser.error("Resolutionは1〜8192の2の累乗で、MaxはMin以上にしてください")

    root = Path(__file__).resolve().parent
    destination = args.copy_to.resolve() if args.copy_to else None
    if destination is not None and not destination.is_dir():
        parser.error(f"コピー先フォルダーがありません（SDカード接続・ドライブ文字を確認）: {destination}")
    bbox = args.bbox or (35.140, 139.130, 35.330, 139.590)
    bbox_tag = "-".join(("m" if v < 0 else "p") + f"{round(abs(v)*1_000_000):09d}" for v in bbox)
    default_output = Path("builds") / f"map-{bbox_tag}"
    if args.margin_nm:
        default_output = Path(f"{default_output}-margin-{args.margin_nm:g}nm")
    output_dir = (root / (args.output_dir or default_output)).resolve()
    imc_exe = args.imc_exe.expanduser().resolve()
    if not imc_exe.is_file():
        raise FileNotFoundError(f"IMCがありません: {imc_exe}")
    template_sap = (
        args.template_sap.expanduser().resolve()
        if args.template_sap
        else find_raster_template(imc_exe)
    )
    if not template_sap.is_file():
        raise FileNotFoundError(f"IMCの設定ファイルがありません: {template_sap}")
    print(f"IMC付属の設定を使用: {template_sap}")
    source_folder = output_dir / "imc-input"

    raster_command = [
        sys.executable, str(root / "build_map_raster.py"),
        "--max-tiles", str(args.max_tiles),
        "--margin-nm", str(args.margin_nm), "--out", str(output_dir),
    ]
    raster_command.extend(["--bbox", *[str(value) for value in bbox]])
    run(raster_command, cwd=root)

    metadata = json.loads((output_dir / "source-metadata.json").read_text(encoding="utf-8"))
    if metadata.get("complete") is not True:
        raise RuntimeError("PNG生成が未完了です")
    for chunk in metadata["chunks"]:
        png_path = source_folder / chunk["png"]
        if not png_path.is_file():
            raise FileNotFoundError(f"入力PNGがありません: {png_path}")

    resolution_label = f"{args.min_resolution:g}-{args.max_resolution:g}"
    run_tag, raster_sap, work_dir, _ = next_run_number(output_dir, resolution_label)
    make_keyhole_pgws(imc_exe, template_sap, source_folder, output_dir,
                      run_tag, metadata["chunks"])

    configure_sap(
        template_sap, raster_sap, work_dir, None,
        source_folder=source_folder,
        min_resolution=args.min_resolution,
        max_resolution=args.max_resolution,
        filter_alpha=args.filter_alpha,
        filter_image_boundary=args.filter_image_boundary,
        atlas_description=f"M={args.at5_prefix}" if args.at5_prefix else None,
    )
    raster_log = output_dir / f"imc-highres-{resolution_label}-{run_tag}.log"
    run_imc(imc_exe, raster_sap, raster_log)

    at5_files = list(work_dir.rglob("*.at5")) if work_dir.is_dir() else []
    if not at5_files:
        log_tail(raster_log)
        raise RuntimeError("Build完了ログはありますがAT5がありません")

    inspector = root / "inspect_imc_output.py"
    run([sys.executable, str(inspector), "--work-dir", str(work_dir)], cwd=root)
    print(f"Build成功: {work_dir / 'BoundAT5s'}")
    if args.copy_to:
        if not destination.is_dir():
            raise FileNotFoundError(f"Build後にコピー先が見つかりません: {destination}")
        expected_resolutions = set()
        resolution = float(args.min_resolution)
        while resolution <= args.max_resolution + 1e-9:
            expected_resolutions.add(resolution)
            resolution *= 2

        files_by_resolution = {}
        resolution_by_source = {}
        for path in at5_files:
            marker = "_3DTexture_"
            if not path.name.startswith(marker) or not path.name.endswith(".at5"):
                raise RuntimeError(
                    f"想定外のAT5ファイル名があるためコピーを中止します: {path.name}"
                )
            parts = path.name[len(marker):-4].split("_")
            level = None
            index = None
            # IMCがWork Directory名を挿入する場合があるため、
            # 末尾側から解像度と分割番号を読み取る。
            if len(parts) >= 2 and parts[-1].isdigit():
                try:
                    candidate = float(parts[-2])
                except ValueError:
                    candidate = None
                if candidate in expected_resolutions:
                    level = candidate
                    index = parts[-1]
            if level is None:
                try:
                    candidate = float(parts[-1])
                except (ValueError, IndexError):
                    candidate = None
                if candidate in expected_resolutions:
                    level = candidate
            if level is None:
                raise RuntimeError(
                    f"AT5名から想定解像度を読み取れません: {path.name}"
                )
            resolution_by_source[path] = (level, index)
            files_by_resolution.setdefault(level, []).append((index, path))

        actual_resolutions = set(files_by_resolution)
        if actual_resolutions != expected_resolutions:
            expected = ", ".join(f"{value:g}" for value in sorted(expected_resolutions))
            actual = ", ".join(f"{value:g}" for value in sorted(actual_resolutions))
            raise RuntimeError(
                f"想定したAT5レベルと一致しないためコピーを中止します。"
                f"想定=[{expected}] 実際=[{actual}]"
            )

        for level, entries in files_by_resolution.items():
            indices = [index for index, _ in entries]
            if len(entries) > 1:
                if any(index is None for index in indices):
                    raise RuntimeError(
                        f"分割AT5と通常AT5が混在しているためコピーを中止します: {level:g}"
                    )
                numeric_indices = sorted(int(index) for index in indices)
                if numeric_indices != list(range(len(numeric_indices))):
                    raise RuntimeError(
                        f"AT5分割番号が連続していないためコピーを中止します: {level:g}"
                    )
        required = sum(p.stat().st_size for p in at5_files)
        if shutil.disk_usage(destination).free < required:
            raise OSError(f"コピー先の空き容量が不足しています: {destination}")
        names_by_source = {}
        for source in at5_files:
            level, index = resolution_by_source[source]
            level_name = f"{level:g}"
            index_suffix = f"_{int(index)}" if index is not None else ""
            names_by_source[source] = (
                f"{args.at5_prefix}_3DTexture_{level_name}{index_suffix}.at5"
            )
        for source, target_name in names_by_source.items():
            temp = destination / (target_name + ".tmp")
            try:
                shutil.copy2(source, temp)
                temp.replace(destination / target_name)
            finally:
                temp.unlink(missing_ok=True)
            print(f"出力先へコピー: {target_name}")
        expected_names = set(names_by_source.values())
        raster_prefix = re.escape(args.at5_prefix) + r"_3DTexture_" if args.at5_prefix else r"_3DTexture_"
        pattern = re.compile(r"^" + raster_prefix + r"(\d+(?:\.\d+)?)(?:_(\d+))?\.at5$")
        for stale in destination.glob(f"{args.at5_prefix}_3DTexture_*.at5" if args.at5_prefix else "_3DTexture_*.at5"):
            match = pattern.fullmatch(stale.name)
            if match and float(match.group(1)) in expected_resolutions:
                if stale.name not in expected_names:
                    stale.unlink()
                    print(f"旧AT5を置換: {stale.name}")
        print(f"コピー完了: {destination}")
    else:
        print("コピー先は指定されていません。AT5はBuildフォルダー内にあります。")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, RuntimeError) as exc:
        print("エラー:", exc, file=sys.stderr)
        sys.exit(1)
