@echo off
REM ============================================================================
REM  Scout Balls installer for the NDS Ironmon Tracker.
REM  1. Put scout_patcher.exe AND this .bat inside your Ironmon Tracker folder
REM     (the folder that contains "ironmon_tracker\QuickLoader.lua").
REM  2. Double-click this file.
REM  From then on, the Tracker's new-run hotkey auto-adds scout balls.
REM  (Re-run any time; run uninstall_scout_balls.bat to remove.)
REM ============================================================================
"%~dp0scout_patcher.exe" install "%~dp0"
echo.
pause
