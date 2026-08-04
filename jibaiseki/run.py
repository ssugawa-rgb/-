#!/usr/bin/env python3
"""自賠責集計 自動入力システム — コマンドライン入口。

使い方の例:

  # 1) まず中身を確認（Excel には書き込まない・抽出結果を画面表示）
  python run.py --preview

  # 2) 問題なければ Excel に追記
  python run.py --excel 集計.xlsx

  # 3) 元 Excel を上書きせず、別名で出力
  python run.py --excel 集計.xlsx --output 集計_更新後.xlsx
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from core import pipeline

BASE = Path(__file__).parent
DEFAULT_PDF_DIR = BASE / "input_pdfs"
DEFAULT_COMPANIES = BASE / "config" / "companies.yaml"
DEFAULT_COLUMNS = BASE / "config" / "columns.yaml"
DEFAULT_OUTPUT_DIR = BASE / "output"

# 画面表示しない内部項目
_INTERNAL = {"_source", "_warning"}


def _print_preview(records: list[dict]) -> None:
    if not records:
        print("PDF が見つかりませんでした。input_pdfs フォルダに PDF を入れてください。")
        return
    for rec in records:
        print("=" * 60)
        print(f"■ ファイル: {rec.get('_source', '?')}")
        if rec.get("_warning"):
            print(f"  ⚠ {rec['_warning']}")
        for k, v in rec.items():
            if k in _INTERNAL:
                continue
            mark = "" if v else "  ← 未取得(要ルール調整)"
            print(f"    {k:12s}: {v}{mark}")
    print("=" * 60)
    print(f"合計 {len(records)} 件")


def main() -> None:
    p = argparse.ArgumentParser(description="自賠責 PDF → Excel 自動入力")
    p.add_argument("--pdf-dir", default=str(DEFAULT_PDF_DIR), help="PDF を入れたフォルダ")
    p.add_argument("--excel", help="追記先の集計 Excel ファイル")
    p.add_argument("--output", help="保存先（省略時は --excel を上書き）")
    p.add_argument("--companies", default=str(DEFAULT_COMPANIES))
    p.add_argument("--columns", default=str(DEFAULT_COLUMNS))
    p.add_argument("--preview", action="store_true", help="Excel に書かず抽出結果だけ表示")
    p.add_argument("--json", action="store_true", help="抽出結果を JSON で出力")
    args = p.parse_args()

    records = pipeline.collect_records(args.pdf_dir, args.companies)

    if args.json:
        clean = [{k: v for k, v in r.items() if k != "_warning"} for r in records]
        print(json.dumps(clean, ensure_ascii=False, indent=2))
        return

    if args.preview or not args.excel:
        _print_preview(records)
        if not args.excel and not args.preview:
            print("\n※ Excel に書き込むには --excel <ファイル> を指定してください。")
        return

    from core import excel_writer
    cfg = excel_writer.load_column_config(args.columns)
    out = excel_writer.write_rows(args.excel, records, cfg, args.output)
    print(f"✓ {len(records)} 件を書き込みました → {out}")


if __name__ == "__main__":
    main()
