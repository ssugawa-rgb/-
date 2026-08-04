"""行組み立てロジックのテスト（実PDFが無くても動作確認できる）。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import builder  # noqa: E402


def test_build_rows():
    records = [
        {"証券番号": "12AB34567", "件数": 1, "保険料": 24190, "令和年": 8, "月": 7, "日": 16, "拠点コード": "038"},
        {"証券番号": "12CD34568", "件数": 1, "保険料": 18160, "令和年": 8, "月": 7, "日": 17, "拠点コード": "049"},
    ]
    conf = {"company_name": "損保ジャパン", "fee_per_unit": 1735}
    base_master = {
        "038": {"事業部": "ボルボ", "拠点": "板橋"},
        "049": {"事業部": "ボルボ", "拠点": "マーベラスコネクション"},
    }
    rows = builder.build_rows(records, conf, base_master)

    assert rows[0]["月"] == "7月"
    assert rows[0]["日"] == "16日"
    assert rows[0]["月日"] == "7月16日"
    assert rows[0]["拠点コード"] == "038"
    assert rows[0]["事業部"] == "ボルボ"
    assert rows[0]["拠点"] == "板橋"
    assert rows[0]["保険会社"] == "損保ジャパン"
    assert rows[0]["保険料"] == 24190
    assert rows[0]["手数料"] == 1735
    assert rows[0]["正味保険料"] == 24190 - 1735

    assert rows[1]["拠点"] == "マーベラスコネクション"
    assert rows[1]["正味保険料"] == 18160 - 1735


def test_unknown_code_leaves_blank():
    records = [{"証券番号": "12ZZ00000", "件数": 1, "保険料": 17650, "令和年": 8, "月": 7, "日": 20, "拠点コード": "999"}]
    conf = {"company_name": "損保ジャパン", "fee_per_unit": 1735}
    rows = builder.build_rows(records, conf, {})
    assert rows[0]["事業部"] == ""
    assert rows[0]["拠点"] == ""
    assert rows[0]["保険料"] == 17650


if __name__ == "__main__":
    test_build_rows()
    test_unknown_code_leaves_blank()
    print("✓ 全テスト成功")
