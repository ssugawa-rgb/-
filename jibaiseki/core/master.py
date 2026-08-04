"""集計Excel の「入力マスタ」から 拠点コード→事業部/拠点 を読み込むモジュール。

マスタは Excel 側にあるものをそのまま使うので、拠点の増減があっても
Excel を更新するだけで自動的に反映される。
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.utils import column_index_from_string


def load_base_master(workbook_path: str | Path, cfg: dict[str, Any]) -> dict[str, dict[str, str]]:
    """{拠点コード: {"事業部": .., "拠点": ..}} を返す。"""
    wb = openpyxl.load_workbook(workbook_path, data_only=True, read_only=True)
    ws = wb[cfg["master_sheet"]]

    code_c = column_index_from_string(cfg["master_code_col"])
    div_c = column_index_from_string(cfg["master_div_col"])
    base_c = column_index_from_string(cfg["master_base_col"])
    start = int(cfg.get("master_start_row", 3))

    result: dict[str, dict[str, str]] = {}
    for row in ws.iter_rows(min_row=start, values_only=False):
        code = row[code_c - 1].value
        if code is None or str(code).strip() == "":
            continue
        code = str(code).strip()
        div = row[div_c - 1].value
        base = row[base_c - 1].value
        result[code] = {
            "事業部": "" if div is None else str(div).strip(),
            "拠点": "" if base is None else str(base).strip(),
        }
    wb.close()
    return result
