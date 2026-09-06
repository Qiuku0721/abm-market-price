@echo off
chcp 65001 >nul
echo.
echo  ABM 自动构建监听
echo  ================================
echo  保存代码后自动执行：
echo    - android 源码/配置变更 -^> 自动编译 APK
echo    - pc 代码变更          -^> 自动语法检查(装依赖后跑 pytest)
echo  本窗口请保持开启；日志同时写入 auto-build.log
echo  按 Ctrl+C 停止监听。
echo.
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0auto-build.ps1"
echo.
echo 监听已停止。
pause
