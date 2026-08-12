@echo off
chcp 65001 >nul
cd /d "C:\daily-stock-review"
echo ================================
echo   每日股票复盘 - 自动抓取推送
echo   %date% %time%
echo ================================

echo.
echo [1/4] 抓取今日行情...
python scripts\fetch_data.py
if errorlevel 1 (
  echo.
  echo [失败] 抓取出错！请检查：
  echo   1) 网络是否正常
  echo   2) 是否已安装 Python 和 akshare
  pause
  exit /b 1
)

echo.
echo [2/4] 生成复盘报告...
python scripts\generate_report.py

echo.
echo [3/4] 导出 Word / HTML...
python scripts\export_report.py

echo.
echo [4/4] 推送 GitHub...
git add -A
git commit -m "每日复盘 %date% %time%"
git push

echo.
echo ================================
echo   完成！
echo   报告位置：C:\daily-stock-review\export\
echo   页面稍后自动更新。
echo ================================
pause
