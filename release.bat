@echo off
cd /d "%~dp0"

echo === Building EXE ===
pip show pyinstaller >nul 2>&1 || pip install pyinstaller
pyinstaller --onefile --windowed --name GameDevManager gdm/main.py

echo.
echo === Building Installer ===
"%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" installer.iss

echo.
echo === Done ===
echo EXE: dist\GameDevManager.exe
echo Installer: installer\GameDevManager_Setup.exe
pause
