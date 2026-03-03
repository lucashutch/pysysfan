@echo off
setlocal EnableDelayedExpansion

:: ================================================================
:: install-pysysfan.bat - One-click installer for pysysfan
::
:: Downloads and installs UV, pysysfan, LibreHardwareMonitor,
:: and the PawnIO driver.
::
:: Usage: Double-click this file or run from a terminal.
::        Supports --silent / -y flags for unattended install.
:: ================================================================

title pysysfan Installer

set SILENT=0
for %%a in (%*) do (
    if "%%a"=="--silent" set SILENT=1
    if "%%a"=="--unattended" set SILENT=1
    if "%%a"=="/silent" set SILENT=1
    if "%%a"=="-y" set SILENT=1
    if "%%a"=="--yes" set SILENT=1
    if "%%a"=="/y" set SILENT=1
)

set REPO=lucashutch/pysysfan
set GITHUB_URL=https://github.com/%REPO%.git

echo.
echo  ============================================================
echo   _____                        __
echo   ^|  __ \                      / _^|
echo   ^| ^|__) ^|_   _ ___ _   _ ___ ^| ^|_ __ _ _ __
echo   ^|  ___/^| ^| ^| / __^| ^| ^| / __^|^|  _/ _` ^| '_ \
echo   ^| ^|    ^| ^|_^| \__ \ ^|_^| \__ \^| ^|^| (_^| ^| ^| ^| ^|
echo   ^|_^|     \__, ^|___/\__, ^|___/^|_^| \__,_^|_^| ^|_^|
echo            __/ ^|     __/ ^|
echo           ^|___/     ^|___/
echo.
echo   Python fan control daemon for Windows
echo  ============================================================
echo.
echo  This installer will:
echo    1. Install uv (Python package manager) if needed
echo    2. Install pysysfan via uv tool install
echo    3. Download LibreHardwareMonitor
echo    4. Install the PawnIO driver
echo.

:: -- Step 0: Ensure UV -------------------------------------------
uv --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  Installing uv...
    powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

:: -- Check if already installed ----------------------------------
uv tool list 2>nul | findstr /C:"pysysfan" >nul
if %ERRORLEVEL% EQU 0 (
    echo  pysysfan is already installed.
    echo.
    if !SILENT! EQU 1 goto :do_install
    echo  What would you like to do?
    echo    1^) Update to the latest version
    echo    2^) Reinstall pysysfan
    echo    3^) Uninstall pysysfan
    echo    4^) Cancel
    echo.
    set /p CHOICE="  Enter your choice (1-4): "
    if "!CHOICE!"=="1" goto :do_install
    if "!CHOICE!"=="2" goto :do_install
    if "!CHOICE!"=="3" goto :do_uninstall
    echo  Cancelled.
    goto :end
)

if !SILENT! EQU 1 goto :do_install

set /p CONFIRM="  Install pysysfan? (y/n): "
if /I not "!CONFIRM!"=="y" (
    echo  Cancelled.
    goto :end
)

:do_install
echo.
echo  ------------------------------------------------------------
echo  [1/3]  Installing pysysfan...
echo  ------------------------------------------------------------
echo.

:: Fetch latest release tag
echo  Fetching latest release tag...
for /f "tokens=*" %%a in ('powershell -Command "$resp = Invoke-RestMethod -Uri 'https://api.github.com/repos/%REPO%/releases/latest'; if ($resp.tag_name) { echo $resp.tag_name } else { echo 'main' }"') do set TAG=%%a

set INSTALL_URL=git+%GITHUB_URL%
if not "%TAG%"=="main" set INSTALL_URL=%INSTALL_URL%@%TAG%

echo  Installing pysysfan (!TAG!) via uv tool...
uv tool install %INSTALL_URL% --force

if !ERRORLEVEL! neq 0 (
    echo.
    echo  [!] pysysfan installation failed.
    set "PYSYSFAN_STATUS=FAILED"
    goto :summary
) else (
    set "PYSYSFAN_STATUS=OK"
)

echo.
echo  ------------------------------------------------------------
echo  [2/3]  Installing LibreHardwareMonitor...
echo  ------------------------------------------------------------
echo.

pysysfan-install-lhm
if !ERRORLEVEL! neq 0 (
    echo  [!] LHM installation failed.
    set "LHM_STATUS=FAILED"
) else (
    set "LHM_STATUS=OK"
)

echo.
echo  ------------------------------------------------------------
echo  [3/3]  Installing PawnIO driver...
echo  ------------------------------------------------------------
echo.

pysysfan-install-pawnio
if !ERRORLEVEL! neq 0 (
    echo  [!] PawnIO installation failed.
    set "PAWNIO_STATUS=FAILED"
) else (
    set "PAWNIO_STATUS=OK"
)

:summary
echo.
echo  ============================================================
echo   Installation Summary
echo  ============================================================
echo.
echo   pysysfan         : !PYSYSFAN_STATUS!
echo   LHM              : !LHM_STATUS!
echo   PawnIO           : !PAWNIO_STATUS!
echo.
echo  ------------------------------------------------------------
echo.
echo   Next steps:
echo     1. Open an Administrator PowerShell (or use sudo)
echo     2. Run: pysysfan scan
echo     3. Run: pysysfan config init
echo     4. Edit ~/.pysysfan/config.yaml to match your hardware
echo     5. Run: pysysfan service install
echo.
echo  ============================================================

goto :end

:do_uninstall
echo.
echo  Uninstalling pysysfan...
uv tool uninstall pysysfan
echo  pysysfan has been uninstalled.

:end
echo.
if !SILENT! EQU 0 pause
endlocal
