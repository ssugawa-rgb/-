"""抽出ロジックのテスト。実物 PDF が無くても動作確認できる。"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core import extractor  # noqa: E402

RULES_PATH = Path(__file__).resolve().parents[1] / "config" / "companies.yaml"


def test_default_extraction():
    rules = extractor.load_company_rules(RULES_PATH)
    text = (
        "自動車損害賠償責任保険\n"
        "証券番号: ABC-12345\n"
        "ご契約者 山田 太郎\n"
        "登録番号 品川 300 あ 12-34\n"
        "車台番号: ZVW30-1234567\n"
        "保険期間 2025年4月1日 から 2026年4月1日 まで\n"
        "保険料: ¥21,550\n"
    )
    rec = extractor.extract(text, rules)
    assert rec["証券番号"] == "ABC-12345"
    assert rec["契約者名"].startswith("山田")
    assert rec["車台番号"] == "ZVW30-1234567"
    assert rec["保険期間_開始"] == "2025-04-01"
    assert rec["保険料"] == "21550"


def test_company_detection():
    rules = extractor.load_company_rules(RULES_PATH)
    text = "A損害保険株式会社\n証券番号: XY-999\nご契約者 佐藤 花子\n保険料 ¥13,200\n"
    rec = extractor.extract(text, rules)
    assert rec["保険会社"] == "A損害保険株式会社"
    assert rec["証券番号"] == "XY-999"
    assert rec["保険料"] == "13200"


if __name__ == "__main__":
    test_default_extraction()
    test_company_detection()
    print("✓ 全テスト成功")
