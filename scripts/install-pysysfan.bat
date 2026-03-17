@echo off
setlocal EnableExtensions EnableDelayedExpansion

:: ================================================================
:: install-pysysfan.bat - Windows installer for PySysFan
::
:: Installs uv, PySysFan, LibreHardwareMonitor, and PawnIO.
:: Optionally installs the native desktop GUI and creates a
:: Start Menu app shortcut that launches without a console window.
::
:: Usage: Double-click this file or run it from a terminal.
::        Supports --silent / -y for unattended install.
::        Use --gui or --daemon-only to preselect the install mode.
:: ================================================================

title PySysFan Installer

set "SILENT=0"
set "GUI_MODE=ASK"
for %%a in (%*) do (
    if /I "%%~a"=="--silent" set "SILENT=1"
    if /I "%%~a"=="--unattended" set "SILENT=1"
    if /I "%%~a"=="/silent" set "SILENT=1"
    if /I "%%~a"=="-y" set "SILENT=1"
    if /I "%%~a"=="--yes" set "SILENT=1"
    if /I "%%~a"=="/y" set "SILENT=1"
    if /I "%%~a"=="--gui" set "GUI_MODE=GUI"
    if /I "%%~a"=="--desktop" set "GUI_MODE=GUI"
    if /I "%%~a"=="--daemon-only" set "GUI_MODE=DAEMON"
    if /I "%%~a"=="--no-gui" set "GUI_MODE=DAEMON"
)

set "REPO=lucashutch/pysysfan"
set "GITHUB_URL=https://github.com/%REPO%.git"
set "BIN_DIR=%USERPROFILE%\.local\bin"
set "GUI_EXE=%BIN_DIR%\pysysfan-gui.exe"
set "START_MENU_DIR=%APPDATA%\Microsoft\Windows\Start Menu\Programs\PySysFan"
set "SHORTCUT_PATH=%START_MENU_DIR%\PySysFan.lnk"
set "APP_DATA_DIR=%LOCALAPPDATA%\PySysFan"
set "ICON_PATH=%APP_DATA_DIR%\pysysfan.ico"

set "PYSYSFAN_STATUS=SKIPPED"
set "LHM_STATUS=SKIPPED"
set "PAWNIO_STATUS=SKIPPED"
set "GUI_APP_STATUS=SKIPPED"

call :print_banner

uv --version >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo  Installing uv...
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    set "PATH=%USERPROFILE%\.local\bin;%PATH%"
)

set "EXISTING_GUI=0"
if exist "%GUI_EXE%" set "EXISTING_GUI=1"

uv tool list 2>nul | findstr /C:"pysysfan" >nul
if %ERRORLEVEL% EQU 0 (
    echo  PySysFan is already installed.
    echo.
    if !SILENT! EQU 1 (
        call :resolve_install_mode
        goto :do_install
    )

    echo  What would you like to do?
    echo    1^) Update to the latest version
    echo    2^) Reinstall PySysFan
    echo    3^) Uninstall PySysFan
    echo    4^) Cancel
    echo.
    set /p CHOICE="  Enter your choice (1-4): "
    if "!CHOICE!"=="1" (
        call :resolve_install_mode
        goto :do_install
    )
    if "!CHOICE!"=="2" (
        call :resolve_install_mode
        goto :do_install
    )
    if "!CHOICE!"=="3" goto :do_uninstall
    echo  Cancelled.
    goto :end
)

if !SILENT! EQU 0 (
    set /p CONFIRM="  Install PySysFan? (y/n): "
    if /I not "!CONFIRM!"=="y" (
        echo  Cancelled.
        goto :end
    )
)

call :resolve_install_mode

:do_install
echo.
echo  ------------------------------------------------------------
echo  [1/4]  Installing PySysFan...
echo  ------------------------------------------------------------
echo.

echo  Fetching latest release tag...
set "TAG=main"
for /f "tokens=*" %%a in ('powershell -NoProfile -Command "$resp = Invoke-RestMethod -Uri 'https://api.github.com/repos/%REPO%/releases/latest'; if ($resp.tag_name) { echo $resp.tag_name } else { echo 'main' }"') do set "TAG=%%a"

set "INSTALL_PACKAGE=pysysfan"
set "INSTALL_LABEL=Daemon + CLI"
if "!INSTALL_GUI!"=="1" (
    set "INSTALL_PACKAGE=pysysfan[gui]"
    set "INSTALL_LABEL=Daemon + CLI + desktop GUI"
)

set "INSTALL_TARGET=!INSTALL_PACKAGE! @ git+%GITHUB_URL%"
if /I not "!TAG!"=="main" set "INSTALL_TARGET=!INSTALL_TARGET!@!TAG!"

echo  Selected install mode: !INSTALL_LABEL!
echo  Installing PySysFan (!TAG!) via uv tool...
uv tool install "!INSTALL_TARGET!" --force

if !ERRORLEVEL! NEQ 0 (
    echo.
    echo  [!] PySysFan installation failed.
    set "PYSYSFAN_STATUS=FAILED"
    goto :summary
)
set "PYSYSFAN_STATUS=OK"

echo.
echo  ------------------------------------------------------------
echo  [2/4]  Installing LibreHardwareMonitor...
echo  ------------------------------------------------------------
echo.

pysysfan-install-lhm
if !ERRORLEVEL! NEQ 0 (
    echo  [!] LibreHardwareMonitor installation failed.
    set "LHM_STATUS=FAILED"
) else (
    set "LHM_STATUS=OK"
)

echo.
echo  ------------------------------------------------------------
echo  [3/4]  Installing PawnIO driver...
echo  ------------------------------------------------------------
echo.

pysysfan-install-pawnio
if !ERRORLEVEL! NEQ 0 (
    echo  [!] PawnIO installation failed.
    set "PAWNIO_STATUS=FAILED"
) else (
    set "PAWNIO_STATUS=OK"
)

echo.
echo  ------------------------------------------------------------
echo  [4/4]  Configuring desktop app assets...
echo  ------------------------------------------------------------
echo.

if "!INSTALL_GUI!"=="1" (
    call :create_gui_shortcut
) else (
    call :cleanup_gui_shortcut
    set "GUI_APP_STATUS=SKIPPED"
    echo  Desktop GUI not selected. Start Menu app setup skipped.
)

:summary
echo.
echo  ============================================================
echo   Installation Summary
echo  ============================================================
echo.
echo   PySysFan         : !PYSYSFAN_STATUS!
echo   LibreHardwareMonitor: !LHM_STATUS!
echo   PawnIO           : !PAWNIO_STATUS!
echo   GUI app shortcut : !GUI_APP_STATUS!
echo.
echo  ------------------------------------------------------------
echo.
echo   Next steps:
echo     1. Open an Administrator PowerShell ^(or use sudo^)
echo     2. Run: pysysfan scan
echo     3. Run: pysysfan config init
echo     4. Edit %%USERPROFILE%%\.pysysfan\config.yaml to match your hardware
if "!INSTALL_GUI!"=="1" (
    echo     5. Launch PySysFan from the Start Menu or run: pysysfan-gui
    echo     6. Use the Service tab to install the startup service when ready
    echo        ^(the daemon runs invisibly - no CMD window will appear^)
) else (
    echo     5. Run ^(elevated^): sudo pysysfan service install
    echo        The daemon will then start invisibly at every logon.
    echo        Logs: %%USERPROFILE%%\.pysysfan\service.log
)
echo.
echo  ============================================================
goto :end

:do_uninstall
echo.
echo  Uninstalling PySysFan...
uv tool uninstall pysysfan
call :cleanup_gui_shortcut
echo  PySysFan has been uninstalled.
goto :end

:resolve_install_mode
set "INSTALL_GUI=0"

if /I "!GUI_MODE!"=="GUI" (
    set "INSTALL_GUI=1"
    goto :eof
)

if /I "!GUI_MODE!"=="DAEMON" goto :eof

if !SILENT! EQU 1 (
    if "!EXISTING_GUI!"=="1" set "INSTALL_GUI=1"
    goto :eof
)

set "DEFAULT_MODE=1"
if "!EXISTING_GUI!"=="1" set "DEFAULT_MODE=2"

:prompt_install_mode
echo.
echo  Choose installation mode:
echo    1^) Daemon + CLI only
echo    2^) Daemon + CLI + desktop GUI ^(Start Menu app with PySysFan icon^)
if "!EXISTING_GUI!"=="1" (
    echo  Current installation already includes the desktop GUI.
)
set /p INSTALL_MODE="  Enter your choice (1-2) [!DEFAULT_MODE!]: "
if "!INSTALL_MODE!"=="" set "INSTALL_MODE=!DEFAULT_MODE!"

if "!INSTALL_MODE!"=="1" (
    set "INSTALL_GUI=0"
    goto :eof
)

if "!INSTALL_MODE!"=="2" (
    set "INSTALL_GUI=1"
    goto :eof
)

echo  Please enter 1 or 2.
goto :prompt_install_mode

:create_gui_shortcut
if not exist "%GUI_EXE%" (
    echo  [!] Could not find the GUI launcher at:
    echo      %GUI_EXE%
    set "GUI_APP_STATUS=FAILED"
    goto :eof
)

if not exist "%APP_DATA_DIR%" mkdir "%APP_DATA_DIR%"
if not exist "%START_MENU_DIR%" mkdir "%START_MENU_DIR%"

echo  Exporting PySysFan icon...
uv tool run --from "!INSTALL_TARGET!" python -c "from pathlib import Path; from pysysfan.gui.desktop.icons import write_windows_icon_file; raise SystemExit(0 if write_windows_icon_file(Path(r'%ICON_PATH%')) else 1)"
if !ERRORLEVEL! NEQ 0 (
    echo  [!] Failed to create the GUI icon file.
    set "GUI_APP_STATUS=FAILED"
    goto :eof
)

echo  Creating Start Menu shortcut...
powershell -NoProfile -ExecutionPolicy Bypass -Command "$shell = New-Object -ComObject WScript.Shell; $shortcut = $shell.CreateShortcut('%SHORTCUT_PATH%'); $shortcut.TargetPath = '%GUI_EXE%'; $shortcut.WorkingDirectory = '%USERPROFILE%'; $shortcut.IconLocation = '%ICON_PATH%'; $shortcut.Description = 'PySysFan desktop GUI'; $shortcut.Save()"
if !ERRORLEVEL! NEQ 0 (
    echo  [!] Failed to create the Start Menu shortcut.
    set "GUI_APP_STATUS=FAILED"
    goto :eof
)

echo  Start Menu app created successfully.
set "GUI_APP_STATUS=OK"
goto :eof

:cleanup_gui_shortcut
if exist "%SHORTCUT_PATH%" del /f /q "%SHORTCUT_PATH%" >nul 2>&1
if exist "%START_MENU_DIR%" rmdir "%START_MENU_DIR%" >nul 2>&1
if exist "%ICON_PATH%" del /f /q "%ICON_PATH%" >nul 2>&1
if exist "%APP_DATA_DIR%" rmdir "%APP_DATA_DIR%" >nul 2>&1
goto :eof

:print_banner
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
echo   Windows-first fan control with an optional desktop GUI
echo  ============================================================
echo.
echo  This installer will:
echo    1. Install uv ^(Python package manager^) if needed
echo    2. Install PySysFan as daemon-only or daemon + GUI
echo    3. Download LibreHardwareMonitor
echo    4. Install the PawnIO driver
echo    5. Create a Start Menu app shortcut when the GUI is selected
echo.
echo  The background service ^(pysysfan-service.exe^) runs invisibly at logon -
echo  no CMD window will appear. Logs are written to:
echo    %%USERPROFILE%%\.pysysfan\service.log
echo.
goto :eof

:end
echo.
if !SILENT! EQU 0 pause
endlocal
