@echo off
chcp 65001 >nul
cd /d "C:\daily-stock-review"
echo ================================
echo   每日股票复盘 - 自动抓取推送
echo ================================

echo.
echo [1/2] 抓取今日行情...
python scripts\fetch_data.py
if errorlevel 1 (
  echo [失败] 抓取出错！请查看上方日志。
  pause
  exit /b 1
)

echo.
echo [2/2] 生成复盘报告...
python scripts\generate_report.py

echo.
echo [3/3] 推送 GitHub...
git add -A
git commit -m "每日复盘 %date% %time%"
git push

echo.
echo ================================
echo   完成！已自动推送，页面稍后更新。
echo ================================
pause