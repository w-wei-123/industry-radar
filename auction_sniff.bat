@echo off
REM Auction sniffer - capture 9:25 auction volume/turnover for watchlist stocks
REM Scheduled Mon-Fri 09:26 by task "AuctionSniff9x25"
chcp 65001 >nul
cd /d D:\develop\industry-radar
set LOGFILE=engine\output\auction_live.log
set PYTHONIOENCODING=utf-8
echo [%date% %time%] ==== START ==== >> %LOGFILE%
python engine\auction_sniffer.py >> %LOGFILE% 2>&1
echo [%date% %time%] ==== DONE ==== >> %LOGFILE%
