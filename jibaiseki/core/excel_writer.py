"""入力シートへ明細行を追記するモジュール。"""
from __future__ import annotations

from pathlib import Path
from typing import Any

import openpyxl
from openpyxl.utils import column_index_from_string


def load_settings(path: str | Path) -> dict[str, Any]:
    import yaml
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _last_data_row(ws, col_idx: int, header_row: int) -> int:
    """指定列で、値が入っている最後の行を返す(header_row 以降)。"""
    last = header_row
    for r in range(header_row + 1, ws.max_row + 1):
        if ws.cell(row=r, column=col_idx).value not in (None, ""):
            last = r
    return last


def append_rows(
    workbook_path: str | Path,
    rows: list[dict[str, Any]],
    settings: dict[str, Any],
    output_path: str | Path,
) -> tuple[Path, int, int]:
    """rows を入力シートに追記し、別ファイルへ保存する。

    戻り値: (保存先, 追記開始行, 追記件数)
    元ファイルは変更しない(必ず output_path に保存)。
    """
    wb = openpyxl.load_workbook(workbook_path)
    ws = wb[settings["target_sheet"]]
    header_row = int(settings.get("header_row", 1))

    col_map = {k: column_index_from_string(v) for k, v in settings["columns"].items()}
    # 追記開始行 = 主要列(月)の最終データ行の次
    anchor_col = col_map["月"]
    start_row = _last_data_row(ws, anchor_col, header_row) + 1

    r = start_row
    for row in rows:
        for field, col_idx in col_map.items():
            val = row.get(field, "")
            ws.cell(row=r, column=col_idx, value=val)
        r += 1

    out = Path(output_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    wb.save(out)
    return out, start_row, len(rows)
