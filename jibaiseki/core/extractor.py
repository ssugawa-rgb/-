"""抽出テキストから項目を切り出すモジュール（設定ファイル駆動）。"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import yaml

# post 処理で使う正規表現
_DIGITS_RE = re.compile(r"[0-9,]+")
_DATE_RE = re.compile(r"(\d{4})\D+(\d{1,2})\D+(\d{1,2})")


def load_company_rules(path: str | Path) -> dict[str, Any]:
    """companies.yaml を読み込む。"""
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def detect_company(text: str, rules: dict[str, Any]) -> str:
    """テキストからどの会社の様式かを判定し、会社キーを返す。

    どれにも一致しなければ "_default" を返す。
    """
    for key, rule in rules.items():
        if key.startswith("_"):
            continue
        detect = (rule or {}).get("detect") or {}
        for kw in detect.get("keywords", []):
            if kw and kw in text:
                return key
    return "_default"


def _apply_post(value: str, post: str | None) -> str:
    if not post:
        return value.strip()
    if post == "strip":
        return value.strip()
    if post == "digits":
        m = _DIGITS_RE.search(value)
        return m.group(0).replace(",", "") if m else value.strip()
    if post == "date":
        m = _DATE_RE.search(value)
        if m:
            y, mo, d = m.groups()
            return f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
        return value.strip()
    return value.strip()


def extract_fields(text: str, field_defs: dict[str, Any]) -> dict[str, str]:
    """field_defs(正規表現定義)に従って項目を切り出す。"""
    result: dict[str, str] = {}
    for name, spec in (field_defs or {}).items():
        spec = spec or {}
        pattern = spec.get("regex")
        if not pattern:
            continue
        flags = 0
        for fl in str(spec.get("flags", "")).split("|"):
            fl = fl.strip().upper()
            if fl and hasattr(re, fl):
                flags |= getattr(re, fl)
        m = re.search(pattern, text, flags)
        if m:
            raw = m.group(1) if m.groups() else m.group(0)
            result[name] = _apply_post(raw, spec.get("post"))
        else:
            result[name] = ""
    return result


def extract(text: str, rules: dict[str, Any]) -> dict[str, str]:
    """会社判定 → 項目抽出 をまとめて行う。

    _default のルールも常に併用し、会社固有ルールで取れなかった項目を補完する。
    戻り値には判定した会社名を "保険会社" として含める。
    """
    company = detect_company(text, rules)

    # まず default で下地を作り、会社固有ルールで上書きする
    merged: dict[str, str] = {}
    default_fields = (rules.get("_default") or {}).get("fields", {})
    merged.update(extract_fields(text, default_fields))

    if company != "_default":
        company_fields = (rules.get(company) or {}).get("fields", {})
        for k, v in extract_fields(text, company_fields).items():
            if v:  # 会社ルールで値が取れた項目だけ上書き
                merged[k] = v

    merged["保険会社"] = _company_label(company, rules)
    return merged


def _company_label(company: str, rules: dict[str, Any]) -> str:
    """会社キーから表示用ラベル(最初の検出キーワード)を返す。"""
    if company == "_default":
        return ""
    detect = (rules.get(company) or {}).get("detect") or {}
    kws = detect.get("keywords") or []
    return kws[0] if kws else company
