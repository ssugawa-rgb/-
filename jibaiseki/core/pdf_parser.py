"""自賠責保険料集計表 PDF を座標ベースで解析するモジュール。

各社で列レイアウトが異なるため、config/companies.yaml の列 x 座標に従って
明細行を復元する。1 明細 = 1 レコード。
"""
from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any

import pdfplumber

# 証券(証明書)番号のパターン 例: 12AB34567 / 12CD34568（2桁数字+2英字+英数5桁）
CERT_RE = re.compile(r"^[0-9]{2}[A-Z]{2}[A-Z0-9]{5}$")
# 入金日 例: R8.07.16 (令和8年7月16日)
DATE_RE = re.compile(r"R(\d+)\.(\d{1,2})\.(\d{1,2})")


def load_companies(path: str | Path) -> dict[str, Any]:
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def detect_company(pdf_text: str, companies: dict[str, Any]) -> tuple[str, dict] | tuple[None, None]:
    """PDF テキストから会社を判定し (会社キー, 設定) を返す。"""
    for key, conf in companies.items():
        kw = (conf or {}).get("detect_keyword")
        if kw and kw in pdf_text:
            return key, conf
    return None, None


def _which_col(x0: float, bounds: dict[str, float]) -> str | None:
    """x0 座標がどの列に属するかを返す(bounds は上限値の昇順で評価)。"""
    for name in ["cert", "ken", "prem", "date", "cum", "code"]:
        if name in bounds and x0 < bounds[name]:
            return name
    return None


def parse(pdf_path: str | Path, conf: dict[str, Any]) -> list[dict[str, Any]]:
    """1 つの PDF を解析して明細レコードのリストを返す。

    各レコード: {証券番号, 件数, 保険料, 入金日(令和), 令和年, 月, 日, 拠点コード}
    """
    bounds = conf["columns"]
    records: list[dict[str, Any]] = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            words = page.extract_words()
            # y 座標(±3px)で行にまとめる
            groups: dict[int, list] = defaultdict(list)
            for w in words:
                groups[round(w["top"] / 3)].append(w)

            for ws in groups.values():
                cells: dict[str, list[str]] = defaultdict(list)
                for w in sorted(ws, key=lambda w: w["x0"]):
                    col = _which_col(w["x0"], bounds)
                    if col:
                        cells[col].append(w["text"])

                cert = "".join(cells.get("cert", []))
                if not CERT_RE.match(cert):
                    continue

                prem = "".join(cells.get("prem", [])).replace(",", "")
                date_s = "".join(cells.get("date", []))
                m = DATE_RE.search(date_s)

                # 保険料と入金日が揃っていない行(書損証明書など)は除外
                if not prem.isdigit() or not m:
                    continue

                reiwa, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
                ken_s = "".join(cells.get("ken", []))
                records.append({
                    "証券番号": cert,
                    "件数": int(ken_s) if ken_s.isdigit() else 1,
                    "保険料": int(prem),
                    "令和年": reiwa,
                    "月": month,
                    "日": day,
                    "拠点コード": "".join(cells.get("code", [])).strip(),
                })
    return records


def read_text(pdf_path: str | Path) -> str:
    """会社判定用に PDF 全体のテキストを取得する。"""
    parts: list[str] = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n".join(parts)
