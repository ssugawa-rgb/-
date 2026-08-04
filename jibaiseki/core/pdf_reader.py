"""PDF からテキストを抽出するモジュール。

文字が埋め込まれた(コピー可能な)PDF は pdfplumber でそのまま抽出します。
スキャン画像 PDF で文字がほとんど取れない場合は警告を出します。
（OCR が必要な場合は README の「OCR 対応」を参照）
"""
from __future__ import annotations

from pathlib import Path

import pdfplumber


def extract_text(pdf_path: str | Path) -> str:
    """PDF ファイル全ページのテキストを 1 つの文字列にして返す。"""
    pdf_path = Path(pdf_path)
    parts: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            parts.append(text)
    return "\n".join(parts)


def looks_like_scan(text: str, threshold: int = 20) -> bool:
    """抽出テキストが極端に少ない = スキャン画像の可能性が高い、を判定。"""
    return len(text.strip()) < threshold
