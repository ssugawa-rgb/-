#!/usr/bin/env python3
"""自賠責集計 自動入力システム — コマンドライン入口。

■ 基本の使い方
  1) まず抽出結果を確認（Excel には書き込まない）
       python run.py --excel 集計.xlsx --preview
  2) 問題なければ Excel に自動入力（元ファイルは変更せず output/ に保存）
       python run.py --excel 集計.xlsx

■ PDF の列位置を調べたいとき（新しい会社の様式を追加する時など）
       python run.py --inspect あるPDF.pdf
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

from core import excel_writer, pipeline

BASE = Path(__file__).parent
DEFAULT_PDF_DIR = BASE / "input_pdfs"
DEFAULT_COMPANIES = BASE / "config" / "companies.yaml"
DEFAULT_SETTINGS = BASE / "config" / "settings.yaml"
DEFAULT_OUTPUT_DIR = BASE / "output"


def _inspect(pdf_path: str) -> None:
    """PDF の単語を y 行ごとに並べ、x 座標付きで表示（列位置調査用）。"""
    import pdfplumber
    from collections import defaultdict
    with pdfplumber.open(pdf_path) as pdf:
        for pi, page in enumerate(pdf.pages, 1):
            print(f"\n===== ページ {pi} =====")
            rows = defaultdict(list)
            for w in page.extract_words():
                rows[round(w["top"])].append((round(w["x0"]), w["text"]))
            for y in sorted(rows):
                line = " | ".join(f"x{ x}:{t}" for x, t in sorted(rows[y]))
                print(f"y{y:>4}  {line}")


def _process_all(pdf_dir: Path, companies_path: Path, workbook: str):
    settings = excel_writer.load_settings(DEFAULT_SETTINGS)
    all_rows, reports = pipeline.process_dir(pdf_dir, workbook, companies_path, settings)
    return all_rows, reports, settings


def _print_preview(rows, reports):
    print("=" * 78)
    for name, company, n, err in reports:
        if err:
            print(f"■ {name} : ⚠ {err}")
        else:
            print(f"■ {name} : {company} → {n} 件")
    print("-" * 78)
    if rows:
        hdr = ["月", "日", "拠点コード", "事業部", "拠点", "保険会社", "保険料", "手数料", "正味保険料"]
        print("  " + "".join(f"{h:<8}" for h in hdr))
        for row in rows:
            print("  " + "".join(f"{str(row.get(h,'')):<8}" for h in hdr))
    print("-" * 78)
    total = sum(r["保険料"] for r in rows)
    print(f"合計 {len(rows)} 件 / 保険料合計 {total:,} 円 / 正味 {sum(r['正味保険料'] for r in rows):,} 円")
    print("=" * 78)


def main() -> None:
    p = argparse.ArgumentParser(description="自賠責 PDF → Excel 自動入力")
    p.add_argument("--excel", help="集計 Excel ファイル（書き込み先）")
    p.add_argument("--pdf-dir", default=str(DEFAULT_PDF_DIR), help="PDF フォルダ")
    p.add_argument("--companies", default=str(DEFAULT_COMPANIES))
    p.add_argument("--output", help="保存先。省略時は output/ に日時付きで保存")
    p.add_argument("--preview", action="store_true", help="Excel に書かず抽出結果だけ表示")
    p.add_argument("--inspect", metavar="PDF", help="PDF の列位置を調査して表示")
    args = p.parse_args()

    if args.inspect:
        _inspect(args.inspect)
        return

    if not args.excel:
        p.error("--excel <集計Excel> を指定してください")

    rows, reports, settings = _process_all(Path(args.pdf_dir), Path(args.companies), args.excel)

    if not rows:
        _print_preview(rows, reports)
        print("\n書き込む明細がありませんでした。input_pdfs に PDF を入れてください。")
        return

    if args.preview:
        _print_preview(rows, reports)
        print("\n※ 実際に書き込むには --preview を外して実行してください。")
        return

    if args.output:
        out_path = args.output
    else:
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        name = Path(args.excel).stem
        out_path = DEFAULT_OUTPUT_DIR / f"{name}_更新_{stamp}.xlsx"

    saved, start_row, n = excel_writer.append_rows(args.excel, rows, settings, out_path)
    _print_preview(rows, reports)
    print(f"\n✓ 「{settings['target_sheet']}」の {start_row} 行目から {n} 件を追記しました。")
    print(f"  保存先: {saved}")
    print("  ※ 元ファイルは変更していません。内容を確認してから差し替えてください。")


if __name__ == "__main__":
    main()
