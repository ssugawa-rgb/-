#!/usr/bin/env python3
"""全テストをまとめて実行する（実データ不要）。"""
import sys
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import test_builder  # noqa: E402
import test_e2e  # noqa: E402

TESTS = [
    ("行組み立て（拠点照合・手数料計算）", test_builder.test_build_rows),
    ("未登録コードは空欄のまま", test_builder.test_unknown_code_leaves_blank),
    ("エンドツーエンド（PDF解析→Excel追記）", test_e2e.test_end_to_end),
]


def main() -> int:
    ok = 0
    for name, fn in TESTS:
        try:
            fn()
            print(f"  ✓ {name}")
            ok += 1
        except Exception:  # noqa: BLE001
            print(f"  ✗ {name}")
            traceback.print_exc()
    print("-" * 50)
    print(f"結果: {ok}/{len(TESTS)} 件 成功")
    return 0 if ok == len(TESTS) else 1


if __name__ == "__main__":
    print("=" * 50)
    print("  自賠責 自動入力システム 自己テスト")
    print("=" * 50)
    sys.exit(main())
