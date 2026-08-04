"""PDF群 → 解析 → 入力シート用の行データ を作る共通処理。

run.py（手動実行）と watch.py（フォルダ監視アプリ）の両方から使う。
書き込み(Excel)は含まない＝抽出までを担当する。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import builder, master, pdf_parser


def gather_pdfs(pdf_dir: str | Path) -> list[Path]:
    pdf_dir = Path(pdf_dir)
    return sorted(pdf_dir.glob("*.pdf")) + sorted(pdf_dir.glob("*.PDF"))


def process_one(
    pdf_path: Path,
    companies: dict[str, Any],
    base_master: dict[str, dict[str, str]],
) -> tuple[str | None, list[dict[str, Any]], str | None]:
    """1つのPDFを処理して (会社キー, 行リスト, エラー文) を返す。"""
    text = pdf_parser.read_text(pdf_path)
    key, conf = pdf_parser.detect_company(text, companies)
    if not conf:
        return None, [], "会社を判定できませんでした（companies.yaml に様式を追加してください）"
    records = pdf_parser.parse(pdf_path, conf)
    if not records:
        return key, [], "明細を1件も抽出できませんでした（レイアウト設定を確認してください）"
    rows = builder.build_rows(records, conf, base_master)
    return key, rows, None


def process_dir(
    pdf_dir: str | Path,
    workbook_path: str | Path,
    companies_path: str | Path,
    settings: dict[str, Any],
) -> tuple[list[dict[str, Any]], list[tuple]]:
    """フォルダ内の全PDFを処理。(全行, レポート) を返す。

    レポート項目: (ファイル名, 会社キー, 件数, エラー文)
    """
    companies = pdf_parser.load_companies(companies_path)
    base_master = master.load_base_master(workbook_path, settings)

    all_rows: list[dict[str, Any]] = []
    reports: list[tuple] = []
    for pdf_path in gather_pdfs(pdf_dir):
        key, rows, err = process_one(pdf_path, companies, base_master)
        all_rows.extend(rows)
        reports.append((pdf_path.name, key, len(rows), err))
    return all_rows, reports
