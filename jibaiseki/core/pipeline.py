"""PDF フォルダ → 抽出 → Excel 追記 をつなぐパイプライン。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from . import excel_writer, extractor, pdf_reader


def process_pdf(pdf_path: Path, rules: dict[str, Any]) -> dict[str, Any]:
    """1 つの PDF を処理して抽出結果の辞書を返す。"""
    text = pdf_reader.extract_text(pdf_path)
    warning = None
    if pdf_reader.looks_like_scan(text):
        warning = "テキストがほとんど取れませんでした（スキャン画像の可能性。OCR が必要かもしれません）"
    record = extractor.extract(text, rules)
    record["_source"] = pdf_path.name
    record["_warning"] = warning
    return record


def collect_records(pdf_dir: str | Path, companies_yaml: str | Path) -> list[dict[str, Any]]:
    """フォルダ内の全 PDF を処理して結果リストを返す。"""
    pdf_dir = Path(pdf_dir)
    rules = extractor.load_company_rules(companies_yaml)
    records: list[dict[str, Any]] = []
    for pdf_path in sorted(pdf_dir.glob("*.pdf")):
        records.append(process_pdf(pdf_path, rules))
    for pdf_path in sorted(pdf_dir.glob("*.PDF")):
        records.append(process_pdf(pdf_path, rules))
    return records


def run(
    pdf_dir: str | Path,
    excel_path: str | Path,
    companies_yaml: str | Path,
    columns_yaml: str | Path,
    output_path: str | Path | None = None,
) -> tuple[Path, list[dict[str, Any]]]:
    """全体を実行。保存先パスと抽出結果リストを返す。"""
    records = collect_records(pdf_dir, companies_yaml)
    cfg = excel_writer.load_column_config(columns_yaml)
    out = excel_writer.write_rows(excel_path, records, cfg, output_path)
    return out, records
