@echo off
rem Double-click to run LoNo. Pass -Docker to use Docker instead.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
if errorlevel 1 pause
