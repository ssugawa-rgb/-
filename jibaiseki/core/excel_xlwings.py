"""Excel本体(xlwings)を使って入力シートへ追記するモジュール。

openpyxl と違い、Excel アプリケーションそのものに書かせるため、
ドロップダウン(入力規則)・数式・書式・グラフを一切壊さずに追記できる。

【前提】Windows + Excel がインストールされていること / pip install xlwings
"""
from __future__ import annotations

from pathlib import Path
from typing import Any

from openpyxl.utils import column_index_from_string


def append_rows_inplace(
    workbook_path: str | Path,
    rows: list[dict[str, Any]],
    settings: dict[str, Any],
    visible: bool = False,
) -> tuple[int, int]:
    """rows を入力シートへ Excel 本体経由で追記し、上書き保存する。

    戻り値: (追記開始行, 追記件数)
    """
    import xlwings as xw

    workbook_path = str(Path(workbook_path).resolve())
    sheet_name = settings["target_sheet"]
    header_row = int(settings.get("header_row", 1))
    col_map = {k: column_index_from_string(v) for k, v in settings["columns"].items()}
    anchor_col = col_map["月"]

    app = xw.App(visible=visible, add_book=False)
    try:
        wb = app.books.open(workbook_path)
        ws = wb.sheets[sheet_name]

        # 主要列(月)の最終データ行を探す（Excelの下端から上に検索）
        last_row = ws.range((ws.cells.last_cell.row, anchor_col)).end("up").row
        if last_row < header_row:
            last_row = header_row
        start_row = last_row + 1

        # 2次元配列にまとめて一括書き込み（列順に整列）
        ordered_fields = sorted(col_map, key=lambda k: col_map[k])
        first_col = min(col_map.values())
        last_col = max(col_map.values())
        width = last_col - first_col + 1

        matrix = []
        for row in rows:
            line = [None] * width
            for f in ordered_fields:
                line[col_map[f] - first_col] = row.get(f, "")
            matrix.append(line)

        ws.range((start_row, first_col)).value = matrix
        wb.save()
        wb.close()
        return start_row, len(rows)
    finally:
        app.quit()
