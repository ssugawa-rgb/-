@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo 自賠責 自動入力アプリ - 初回セットアップ
echo 必要な部品をインストールします...
python -m pip install -r requirements.txt
if errorlevel 1 (
  echo.
  echo 【失敗】Python がインストールされていない可能性があります。
  echo   https://www.python.org/ から Python をインストールしてください。
)
echo.
echo 完了しました。
pause
