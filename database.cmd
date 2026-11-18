@echo off
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0scripts\database.ps1" %*
