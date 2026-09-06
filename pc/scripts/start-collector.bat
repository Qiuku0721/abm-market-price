@echo off
chcp 65001 >nul
rem ABM PC 采集控制器：手机插 USB 并开启调试后运行本脚本
cd /d "%~dp0\.."
if not exist ".venv\Scripts\python.exe" (
    echo [错误] 未找到虚拟环境，请先运行 scripts\start.bat 完成环境安装。
    pause
    exit /b 1
)
echo 依赖检查（首次会安装 RapidOCR 等）...
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
echo 开始采集（Ctrl+C 停止）...
".venv\Scripts\python.exe" run_collector.py %*
pause
