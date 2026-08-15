@echo off
setlocal
title Register AuctionSniff9x25

REM ===== Self-elevate =====
net session >nul 2>&1
if %errorlevel% neq 0 (
    echo Requesting administrator privileges...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

REM Re-register Mon-Fri 09:26
schtasks /delete /tn "AuctionSniff9x25" /f
schtasks /create /tn "AuctionSniff9x25" /tr "D:\develop\industry-radar\auction_sniff.bat" /sc weekly /d MON,TUE,WED,THU,FRI /st 09:26 /ru "%USERNAME%" /rl HIGHEST /f
echo Done. Task re-registered.
pause
