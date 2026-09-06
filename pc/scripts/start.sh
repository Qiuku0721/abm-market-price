#!/usr/bin/env bash
# ABM 电脑端一键启动（macOS/Linux/WSL）
cd "$(dirname "$0")/.."
if [ ! -d .venv ]; then
  echo "[1/3] 创建虚拟环境 .venv ..."
  python3 -m venv .venv || exit 1
fi
source .venv/bin/activate
echo "[2/3] 安装依赖 ..."
python -m pip install -q -r requirements.txt || exit 1
echo "[3/3] 启动服务 http://0.0.0.0:8600"
python server.py
