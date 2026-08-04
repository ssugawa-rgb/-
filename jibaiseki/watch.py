#!/usr/bin/env python3
"""自賠責 自動入力アプリ（フォルダ監視型）。

「PDF投入」フォルダに PDF を入れるだけで、自動的に集計Excelへ入力します。

■ 起動
    自賠責_自動入力.bat をダブルクリック（またはこのファイルを python watch.py）
■ 停止
    ウィンドウを閉じる（Ctrl+C）

処理の流れ:
  1. PDF投入フォルダを一定間隔で監視
  2. 新しいPDFを見つけたら解析し、内容(件数・合計)を表示
  3. 集計Excelをバックアップしてから、入力シートへ追記
  4. 処理済みPDFを「処理済み」フォルダへ移動
  5. ログを output/処理ログ.csv に記録
"""
from __future__ import annotations

import csv
import shutil
import sys
import time
from datetime import datetime
from pathlib import Path

from core import excel_writer, pipeline

BASE = Path(__file__).parent
COMPANIES = BASE / "config" / "companies.yaml"
SETTINGS = BASE / "config" / "settings.yaml"
LOG_CSV = BASE / "output" / "処理ログ.csv"


def _stable(path: Path, tries: int = 3, wait: float = 0.5) -> bool:
    """コピー途中のPDFを掴まないよう、サイズが安定したか確認する。"""
    try:
        last = path.stat().st_size
    except FileNotFoundError:
        return False
    for _ in range(tries):
        time.sleep(wait)
        try:
            now = path.stat().st_size
        except FileNotFoundError:
            return False
        if now != last:
            last = now
            continue
        return True
    return True


def _log(rows_info: list) -> None:
    LOG_CSV.parent.mkdir(parents=True, exist_ok=True)
    new = not LOG_CSV.exists()
    with open(LOG_CSV, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        if new:
            w.writerow(["処理日時", "PDFファイル", "会社", "件数", "保険料合計", "結果"])
        for r in rows_info:
            w.writerow(r)


def _write_excel(workbook_path: str, rows: list, settings: dict) -> str:
    """設定エンジンに応じてExcelへ追記。結果メッセージを返す。"""
    engine = settings.get("engine", "xlwings")

    # 書き込み前にバックアップ
    backup_dir = BASE / settings.get("backup_dir", "バックアップ")
    backup_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    wp = Path(workbook_path)
    shutil.copy2(wp, backup_dir / f"{wp.stem}_{stamp}{wp.suffix}")

    if engine == "xlwings":
        from core import excel_xlwings
        start, n = excel_xlwings.append_rows_inplace(workbook_path, rows, settings)
        return f"入力シート {start}行目から {n}件を追記（本番ファイルを更新）"
    else:
        # openpyxl: コピーに保存（本番は変更しない）
        out = BASE / "output" / f"{wp.stem}_更新_{stamp}.xlsx"
        saved, start, n = excel_writer.append_rows(workbook_path, rows, settings, out)
        return f"入力シート {start}行目から {n}件を追記 → {saved}"


def main() -> None:
    settings = excel_writer.load_settings(SETTINGS)
    workbook_path = settings.get("workbook_path", "").strip()

    if not workbook_path or not Path(workbook_path).exists():
        print("【設定エラー】config/settings.yaml の workbook_path に、")
        print("             集計Excelのフルパスを設定してください。")
        print(f"  現在の設定: {workbook_path!r}")
        input("\nEnterキーで終了します...")
        sys.exit(1)

    watch_dir = BASE / settings.get("watch_dir", "PDF投入")
    processed_dir = BASE / settings.get("processed_dir", "処理済み")
    watch_dir.mkdir(parents=True, exist_ok=True)
    processed_dir.mkdir(parents=True, exist_ok=True)
    poll = float(settings.get("poll_seconds", 3))

    print("=" * 70)
    print("  自賠責 自動入力アプリ  — 起動しました")
    print("=" * 70)
    print(f"  監視フォルダ : {watch_dir}")
    print(f"  入力先Excel  : {workbook_path}")
    print(f"  書込エンジン : {settings.get('engine')}")
    print("-" * 70)
    print("  このフォルダにPDFを入れると自動で入力します。")
    print("  停止するにはこのウィンドウを閉じてください。")
    print("=" * 70)

    seen: set[str] = set()
    while True:
        try:
            pdfs = pipeline.gather_pdfs(watch_dir)
            for pdf in pdfs:
                if pdf.name in seen:
                    continue
                if not _stable(pdf):
                    continue
                seen.add(pdf.name)
                _handle(pdf, workbook_path, settings, processed_dir)
            time.sleep(poll)
        except KeyboardInterrupt:
            print("\n終了します。")
            break
        except Exception as e:  # noqa: BLE001 監視は止めない
            print(f"  ⚠ エラー: {e}")
            time.sleep(poll)


def _handle(pdf: Path, workbook_path: str, settings: dict, processed_dir: Path) -> None:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"\n[{ts}] 検出: {pdf.name}")
    companies = pipeline.pdf_parser.load_companies(COMPANIES)
    from core import master
    base_master = master.load_base_master(workbook_path, settings)
    key, rows, err = pipeline.process_one(pdf, companies, base_master)

    if err:
        print(f"  ⚠ {err}  → スキップ（PDFはそのまま残します）")
        _log([[ts, pdf.name, key or "?", 0, 0, f"エラー:{err}"]])
        seen_discard(pdf)
        return

    total = sum(r["保険料"] for r in rows)
    print(f"  会社: {key} / {len(rows)}件 / 保険料合計 {total:,}円")
    try:
        msg = _write_excel(workbook_path, rows, settings)
        print(f"  ✓ {msg}")
        dest = processed_dir / pdf.name
        if dest.exists():
            dest = processed_dir / f"{pdf.stem}_{datetime.now():%H%M%S}{pdf.suffix}"
        shutil.move(str(pdf), str(dest))
        print(f"  → 処理済みへ移動: {dest.name}")
        _log([[ts, pdf.name, key, len(rows), total, "成功"]])
    except Exception as e:  # noqa: BLE001
        print(f"  ⚠ 書き込み失敗: {e}  → PDFは残します")
        _log([[ts, pdf.name, key, len(rows), total, f"書込失敗:{e}"]])
        seen_discard(pdf)


def seen_discard(pdf: Path) -> None:
    """失敗時、再挑戦できるよう seen から外すためのフック（現状はログのみ）。"""
    # 監視ループ側の seen 集合はグローバルではないため、
    # 失敗PDFはファイル名を変えるまで再処理されない。運用上はPDFを入れ直す。
    pass


if __name__ == "__main__":
    main()
