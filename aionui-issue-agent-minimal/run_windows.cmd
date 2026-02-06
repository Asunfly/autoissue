@echo off
setlocal EnableExtensions EnableDelayedExpansion
chcp 65001 >nul

REM ============================================================
REM AionUi Issue Agent (Windows) - v22
REM - Thin wrapper: delegate to python bootstrap
REM ============================================================

set "ROOT=%~dp0"
set "PYTHON_BIN=python"
where py >nul 2>nul
if %ERRORLEVEL% EQU 0 (
  set "PYTHON_BIN=py -3"
)

%PYTHON_BIN% "%ROOT%scripts\python\bootstrap.py" %*

endlocal & exit /b %ERRORLEVEL%
