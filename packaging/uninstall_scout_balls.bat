@echo off
REM Removes the scout-ball hook from the Ironmon Tracker (leaves a .scoutbak backup).
REM Keep this next to scout_patcher.exe in your Tracker folder and double-click.
pushd "%~dp0"
"%~dp0scout_patcher.exe" uninstall
popd
echo.
pause
