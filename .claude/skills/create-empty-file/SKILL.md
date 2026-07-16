---
name: create-empty-file
description: Create an empty file (or folder) with a user-specified name, sanitizing characters that are invalid in filesystem paths (e.g. "/"), optionally package it into a Zip archive, then commit and push to the designated branch. Use when the user asks to create a blank/empty file or folder by name (especially when the name contains a slash or other path-reserved characters) and/or wants the result zipped.
---

# 空ファイル / フォルダー作成スキル (Create empty file / folder)

ユーザーから「空のファイル（またはフォルダー）を作ってほしい」と依頼されたときの手順。
特に名前に `/` などパスで使えない文字が含まれる場合の扱いを標準化する。

## 前提の確認 (Preconditions)

1. **実行環境を明示する** — このセッションはクラウド上のリモートコンテナで動作しており、
   ユーザーPCの実際のデスクトップには書き込めない。作成できるのはリポジトリ内のみ。
   ユーザーが「デスクトップ」と言った場合は、この点を伝えたうえでリポジトリ内に作成する。

2. **無効な文字を検出する** — Linux/Unix のファイルシステムでは以下は名前にそのまま使えない:
   - `/`（パス区切り。名前に含めると階層とみなされる）
   - NUL 文字
   - 実用上避けるべきもの: 先頭の `-`、空白のみの名前など

## 手順 (Steps)

1. **名前をサニタイズする** — 無効文字が含まれる場合は、そのまま作らず必ず確認する。
   置き換え候補を提示してユーザーに選んでもらう:
   - `/` → `-` / `_` / 和暦表記（例: `7/16` → `7-16` / `7_16` / `7月16日`）

2. **作成対象を確認する** — 「ファイル」か「フォルダー」か曖昧なら確認する。
   - 空ファイル: `touch <name>`
   - 空フォルダー: `mkdir -p <name>`（Git は空ディレクトリを追跡しないため、
     コミットが必要なら `<name>/.gitkeep` を置く）

3. **指定ブランチで作業する** — 課題で指定された開発ブランチに切り替える:
   ```bash
   git checkout -B <designated-branch>
   ```

4. **作成する**:
   ```bash
   touch <sanitized-name>      # 空ファイルの場合
   # または
   mkdir -p <sanitized-name> && touch <sanitized-name>/.gitkeep  # 空フォルダーの場合
   ```

5. **Zip 化する** — 作成したファイル/フォルダーを Zip アーカイブにまとめる。
   アーカイブ名はサニタイズ済みの名前を使う（`.zip` を付与）:
   ```bash
   zip -r <sanitized-name>.zip <sanitized-name>   # ファイル・フォルダーどちらでも可
   ```
   - `zip` が無い環境では代替を使う: `python3 -c "import shutil; shutil.make_archive('<name>', 'zip', root_dir='.', base_dir='<name>')"`
   - 空フォルダーを Zip に含める場合、中身が無いと `zip` が空エントリを作れないことがあるため
     `.gitkeep` などのプレースホルダを入れておくと確実。
   - 作成後は `unzip -l <name>.zip` で中身を検証する。

6. **コミット & プッシュ**:
   ```bash
   git add <path> <sanitized-name>.zip
   git commit -m "Add empty file <name> and zip archive"
   git push -u origin <designated-branch>
   ```
   ネットワークエラー時のみ、指数バックオフ（2s, 4s, 8s, 16s）で最大4回リトライする。

7. **結果を報告する** — 作成したパス、Zip アーカイブ名、選んだ名前とその理由（サニタイズした場合）、
   コミット/プッシュ先ブランチを伝える。PR は明示的に依頼された場合のみ作成する。

## 例 (Example)

依頼: 「空のファイルをデスクトップに作成してほしい。フォルダー名を『7/16』に」

対応:
1. リモート環境なのでリポジトリ内に作成する旨と、`/` が使えない旨を伝える。
2. 置き換え案（`7-16` / `7_16` / `7月16日`）と、ファイル/フォルダーどちらかを確認。
3. 選ばれた名前（例: `7_16`）で `touch 7_16`。
4. `zip -r 7_16.zip 7_16` で Zip 化し、`unzip -l 7_16.zip` で検証。
5. 指定ブランチにコミットしてプッシュ。
