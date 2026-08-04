@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYCMD=
where py >nul 2>nul && set PYCMD=py
if not defined PYCMD where python >nul 2>nul && set PYCMD=python
if not defined PYCMD (
  echo [ERROR] Python not found. Run setup first.
  pause
  exit /b 1
)
%PYCMD% watch.py
pause
