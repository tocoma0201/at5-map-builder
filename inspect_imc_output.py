#!/usr/bin/env python3
"""IMCの出力を読み取り専用で検査し、AT5ファイルと容量を報告する。

SDカードに書き込まない。AT5の中身や対応機種は判定しない。
"""
import argparse
from pathlib import Path
import sys


# バイト数を見やすい単位の文字列へ変換する。
def size_text(value):
    if value < 1024:
        return f"{value} B"
    if value < 1024 ** 2:
        return f"{value / 1024:.1f} KiB"
    return f"{value / 1024 ** 2:.2f} MiB"


# IMC作業フォルダーのファイル一覧とAT5の容量を表示する。
def main():
    parser = argparse.ArgumentParser(description="Insight Map Creator出力を一覧・容量確認")
    parser.add_argument("--work-dir", type=Path, default=Path("builds/imc-work"),
                        help="IMCで指定したWork Directory")
    args = parser.parse_args()
    work = args.work_dir
    if not work.is_dir():
        raise RuntimeError(f"ディレクトリが存在しません: {work}")
    files = sorted(p for p in work.rglob("*") if p.is_file())
    if not files:
        raise RuntimeError("ファイルが見つかりません。IMCのBuildが完了しているか確認してください。")
    total = sum(p.stat().st_size for p in files)
    print("検査フォルダ:", work.resolve())
    print(f"ファイル数: {len(files)} / 合計: {size_text(total)}")
    print()
    at5s = [p for p in files if p.suffix.lower() == ".at5"]
    xmls = [p for p in files if p.name.lower() == "at5.xml"]
    print(f"AT5ファイル: {len(at5s)} / at5.xml: {len(xmls)}")
    for p in files:
        rel = p.relative_to(work).as_posix()
        print(f"{size_text(p.stat().st_size):>12}  {rel}")
    print()
    bounds = {p.parent for p in files if p.parent.name == "BoundAT5s"}
    if bounds:
        print("BoundAT5sの場所:")
        for p in sorted(bounds):
            print("  ", p.resolve())
    else:
        print("注意: BoundAT5sがまだ見つかりません。")
    if not at5s:
        print("注意: AT5出力が見つかりません。IMCのBuildログを確認してください。")
    print("注: この一覧だけではTi2での表示・Genesis Liveの共存は確認できません。")
    print("注: 既存SDカードへはまだコピーしないでください。")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError) as exc:
        print("エラー:", exc, file=sys.stderr)
        sys.exit(1)
