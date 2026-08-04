@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo === Jibaiseki Auto-Input : Setup ===
echo Installing required components...
echo.
set PYCMD=
where py >nul 2>nul && set PYCMD=py
if not defined PYCMD where python >nul 2>nul && set PYCMD=python
if not defined PYCMD (
  echo [ERROR] Python not found.
  echo Install Python from https://www.python.org/downloads/
  echo IMPORTANT: check "Add python.exe to PATH" during install.
  echo.
  pause
  exit /b 1
)
%PYCMD% -m pip install -r requirements.txt
echo.
echo Setup done. You can close this window.
pause
