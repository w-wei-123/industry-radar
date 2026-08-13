@echo off
REM Industry Radar daily auto deploy
chcp 65001 >nul
cd /d D:\develop\industry-radar
set LOGFILE=engine\output\auto_deploy.log
echo [%date% %time%] ==== START ==== >> %LOGFILE%

echo [%time%] daily_scan ... >> %LOGFILE%
python engine\daily_scan.py >> %LOGFILE% 2>&1

echo [%time%] yaogu_hunter ... >> %LOGFILE%
python engine\yaogu_hunter.py >> %LOGFILE% 2>&1

echo [%time%] build_static ... >> %LOGFILE%
python build_static.py >> %LOGFILE% 2>&1

echo %date:~0,4%-%date:~5,2%-%date:~8,2% > .last-scan-date

echo [%time%] git push ... >> %LOGFILE%
git add -A >> %LOGFILE% 2>&1
git commit -m "auto daily scan" >> %LOGFILE% 2>&1
git push origin gh-pages-latest >> %LOGFILE% 2>&1

echo [%date% %time%] ==== DONE ==== >> %LOGFILE%
echo Done.
