@echo off
REM ============================================================================
REM  Scout Balls installer for the NDS Ironmon Tracker.
REM  1. Put scout_patcher.exe AND this .bat inside your Ironmon Tracker folder
REM     (the folder that contains "ironmon_tracker\QuickLoader.lua" -- i.e. the
REM     same folder as "Ironmon-Tracker.lua").
REM  2. Double-click this file.
REM  Then RELOAD the tracker in BizHawk. From then on the new-run hotkey adds
REM  scout balls. (Re-run any time; run uninstall_scout_balls.bat to remove.)
REM ============================================================================
pushd "%~dp0"
"%~dp0scout_patcher.exe" install
popd
echo.
pause
