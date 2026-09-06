@echo off
rem ABM 电脑端一键启动（Windows）：在 pc/ 目录下运行本脚本
cd /d "%~dp0\.."
if not exist .venv (
  echo [1/3] 创建虚拟环境 .venv ...
  python -m venv .venv || goto :err
)
call .venv\Scripts\activate.bat
echo [2/3] 安装/校验依赖 ...
python -m pip install -q -r requirements.txt || goto :err
echo [3/3] 启动服务 http://0.0.0.0:8600 （浏览器打开 http://127.0.0.1:8600）
python server.py
goto :eof
:err
echo 启动失败：请确认已安装 Python 3.10+ 并加入 PATH（见 docs/SETUP.md）
pause
