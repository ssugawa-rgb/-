# 自賠責集計 自動入力システム

各保険会社から届く自賠責保険の **PDF を読み取り、集計 Excel に自動で入力する** ツールです。
「PDF を入れる → コマンド実行 → Excel に行が追記される」という流れを自動化します。

```
  [各社PDF]  ──▶  このツール（読み取り・項目抽出）  ──▶  [集計Excel に自動追記]
```

---

## 1. できること

- `input_pdfs/` に入れた PDF を一括で読み取り
- どの保険会社の様式かを自動判定
- 証券番号・契約者名・保険料などの項目を抽出
- 既存の集計 Excel の**続きの行に自動で追記**（既存データは消しません）
- Excel に書き込む前に、抽出結果を画面で**プレビュー確認**できる

---

## 2. セットアップ（最初の一回だけ）

Python 3.10 以上が必要です。

```bash
cd jibaiseki
pip install -r requirements.txt
```

---

## 3. 使い方（毎回の作業）

### ステップ1: PDF を入れる
各社から届いた PDF を `input_pdfs/` フォルダに入れます。

### ステップ2: まず中身を確認（Excel には書き込まない）
```bash
python run.py --preview
```
抽出結果が画面に出ます。`← 未取得` と出た項目は、まだルール調整が必要な項目です。

### ステップ3: 問題なければ Excel に追記
```bash
python run.py --excel 集計.xlsx
```
元の Excel を残したい場合は別名保存：
```bash
python run.py --excel 集計.xlsx --output 集計_更新後.xlsx
```

---

## 4. 自社の PDF / Excel に合わせる（重要）

このツールは **設定ファイルを編集するだけ** で自社の様式に対応できます。
プログラム本体を書き換える必要はありません。

### 4-1. Excel の列を合わせる → `config/columns.yaml`

集計 Excel の見出し名に合わせて、対応表を編集します。

```yaml
columns:
  証券番号: "証券番号"      # 左=ツール内の項目名 / 右=Excelの見出し名
  契約者名: "契約者名"
  保険料:   "保険料"
```
右側を、実際の Excel の見出しと同じ文字に変えるだけです。

### 4-2. PDF の読み取りルールを合わせる → `config/companies.yaml`

各社の PDF に書かれている文言に合わせて、正規表現を調整します。
まず `--preview` で `← 未取得` になる項目を確認し、その項目の `regex` を直します。

会社を増やすときは、以下のブロックを追加するだけです：

```yaml
会社キー名:
  detect:
    keywords:
      - "○○損害保険株式会社"   # PDF内にこの文字があればこの会社と判定
  fields:
    証券番号:
      regex: "証券番号[\\s:：]*([A-Za-z0-9\\-]+)"
      post: strip
    保険料:
      regex: "保険料[\\s:：]*([0-9,]+)"
      post: digits           # digits=数字のみ / date=日付整形 / strip=空白除去
```

> どの会社にも一致しない場合は `_default` の汎用ルールが使われます。

---

## 5. スキャン画像 PDF の場合（OCR）

文字を選択できない**スキャン画像の PDF** は、そのままでは読み取れません
（`--preview` で「テキストがほとんど取れませんでした」と警告が出ます）。
その場合は OCR（文字認識）が必要です。対応が必要になったらご相談ください。

---

## 6. フォルダ構成

```
jibaiseki/
├── run.py                 … 実行コマンド（入口）
├── config/
│   ├── companies.yaml     … 各社PDFの読み取りルール（★ここを調整）
│   └── columns.yaml       … Excelの列マッピング（★ここを調整）
├── core/                  … 処理本体（通常は触りません）
│   ├── pdf_reader.py      … PDF読み取り
│   ├── extractor.py       … 項目抽出
│   ├── excel_writer.py    … Excel追記
│   └── pipeline.py        … 全体の流れ
├── input_pdfs/            … ここにPDFを入れる
├── output/               … 出力先
├── samples/              … サンプル置き場
└── tests/                … 動作テスト
```

---

## 7. テスト

```bash
python tests/test_extractor.py
```

---

## 8. 次のステップ

実際の **PDF サンプルと集計 Excel** をいただければ、
`companies.yaml` と `columns.yaml` を実物に合わせて設定し、そのまま使える状態にします。
