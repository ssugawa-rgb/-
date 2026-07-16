---
name: create-empty-file
description: Create an empty file (or folder) with a user-specified name, sanitizing characters that are invalid in filesystem paths (e.g. "/"), then commit and push to the designated branch. Use when the user asks to create a blank/empty file or folder by name, especially when the requested name contains a slash or other path-reserved characters.
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

5. **コミット & プッシュ**:
   ```bash
   git add <path>
   git commit -m "Add empty file <name>"
   git push -u origin <designated-branch>
   ```
   ネットワークエラー時のみ、指数バックオフ（2s, 4s, 8s, 16s）で最大4回リトライする。

6. **結果を報告する** — 作成したパス、選んだ名前とその理由（サニタイズした場合）、
   コミット/プッシュ先ブランチを伝える。PR は明示的に依頼された場合のみ作成する。

## 例 (Example)

依頼: 「空のファイルをデスクトップに作成してほしい。フォルダー名を『7/16』に」

対応:
1. リモート環境なのでリポジトリ内に作成する旨と、`/` が使えない旨を伝える。
2. 置き換え案（`7-16` / `7_16` / `7月16日`）と、ファイル/フォルダーどちらかを確認。
3. 選ばれた名前（例: `7_16`）で `touch 7_16`。
4. 指定ブランチにコミットしてプッシュ。
