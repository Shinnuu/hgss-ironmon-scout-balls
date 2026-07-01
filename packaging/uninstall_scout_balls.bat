@echo off
REM Removes the scout-ball hook from the Ironmon Tracker (leaves a .scoutbak backup).
REM Keep this next to scout_patcher.exe in your Tracker folder and double-click.
"%~dp0scout_patcher.exe" uninstall "%~dp0"
echo.
pause
