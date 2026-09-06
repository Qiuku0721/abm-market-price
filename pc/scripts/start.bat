@echo off
rem 以 UTF-8 运行本文件，避免中文提示乱码
chcp 65001 >nul
cd /d "%~dp0.."

echo ============================================
echo   ABM 电脑端程序启动
echo ============================================

rem 1) 已有虚拟环境则直接用其中的 python
if exist ".venv\Scripts\python.exe" goto :run

rem 2) 找系统 Python：优先 3.12（RapidOCR 需要 <3.13），其次 py 3.x，再 python
set "PY="
where py >nul 2>nul && set "PY=py -3.12"
if not defined PY (
    where py >nul 2>nul && set "PY=py -3"
)
if not defined PY (
    where python >nul 2>nul && set "PY=python"
)
if not defined PY (
    echo.
    echo [错误] 未检测到 Python。
    echo 请先安装 Python 3.10 或更高版本，安装时勾选 "Add python.exe to PATH"：
    echo   https://www.python.org/downloads/
    echo 安装完成后重新双击本脚本。详细步骤见 docs\SETUP.md
    pause
    exit /b 1
)

echo 使用 Python：%PY%
echo [1/3] 创建虚拟环境 .venv ...
%PY% -m venv .venv
if errorlevel 1 (
    echo.
    echo [错误] 虚拟环境创建失败。
    echo 常见原因：Python 只是 Microsoft Store 占位、未真正安装，
    echo 或安装后未重新打开终端（PATH 未刷新）。
    echo 请按 docs\SETUP.md 安装 Python 后重试。
    pause
    exit /b 1
)

echo [2/3] 安装依赖 ...
".venv\Scripts\python.exe" -m pip install -q -r requirements.txt
if errorlevel 1 (
    echo.
    echo [错误] 依赖安装失败，请检查网络后重新运行本脚本。
    pause
    exit /b 1
)

:run
echo [3/3] 启动服务：http://0.0.0.0:8600
echo 浏览器打开 http://127.0.0.1:8600 查看统计页面
echo 按 Ctrl+C 可停止服务
echo.
".venv\Scripts\python.exe" server.py

echo.
echo 服务已退出。按任意键关闭窗口。
pause >nul
