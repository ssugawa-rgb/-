"""解析レコード + マスタ + 会社設定 → 入力シートの行データ を組み立てる。"""
from __future__ import annotations

from typing import Any


def build_rows(
    records: list[dict[str, Any]],
    company_conf: dict[str, Any],
    base_master: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    """入力シート用の行(辞書)リストを返す。

    列: 月 / 日 / 月日 / 拠点コード / 事業部 / 拠点 / 保険会社 / 保険料 / 手数料 / 正味保険料
    """
    company_name = company_conf.get("company_name", "")
    fee = int(company_conf.get("fee_per_unit", 0))

    rows: list[dict[str, Any]] = []
    for rec in records:
        month = rec["月"]
        day = rec["日"]
        code = rec["拠点コード"]
        m = base_master.get(code, {})
        prem = rec["保険料"]
        rows.append({
            "月": f"{month}月",
            "日": f"{day}日",
            "月日": f"{month}月{day}日",
            "拠点コード": code,
            "事業部": m.get("事業部", ""),
            "拠点": m.get("拠点", ""),
            "保険会社": company_name,
            "保険料": prem,
            "手数料": fee,
            "正味保険料": prem - fee,
            # 参照用(Excelには書かないが照合に使える)
            "_証券番号": rec["証券番号"],
        })
    return rows
