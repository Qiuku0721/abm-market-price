@echo off
rem USB 有线传输一键连接：把手机的 127.0.0.1:8600 转发到电脑 8600
rem 用法：手机开 USB 调试并插数据线 -> 双击本脚本 -> App 地址填 http://127.0.0.1:8600
chcp 65001 >nul

echo ============================================
echo   ABM USB 有线传输连接
echo ============================================

rem 定位 adb（PATH -> ANDROID_HOME -> 常见位置）
set "ADB="
where adb >nul 2>nul && set "ADB=adb"
if not defined ADB if exist "%ANDROID_HOME%\platform-tools\adb.exe" set "ADB=%ANDROID_HOME%\platform-tools\adb.exe"
if not defined ADB if exist "D:\IDEA\adb\platform-tools\adb.exe" set "ADB=D:\IDEA\adb\platform-tools\adb.exe"
if not defined ADB (
    echo [错误] 未找到 adb，请安装 platform-tools 或设置 ANDROID_HOME。
    pause
    exit /b 1
)

echo 使用 adb：%ADB%
echo [1/2] 检查设备 ...
%ADB% devices
%ADB% get-state >nul 2>nul
if errorlevel 1 (
    echo.
    echo [错误] 没有检测到已授权的设备。
    echo 请确认：手机已开启「开发者选项 - USB 调试」，插好数据线，
    echo 并在手机上允许本电脑的 USB 调试授权。
    pause
    exit /b 1
)

echo [2/2] 建立反向转发（USB 有线通道）...
%ADB% reverse tcp:8600 tcp:8600
if errorlevel 1 (
    echo.
    echo [错误] adb reverse 失败，请重试或重启手机 USB 调试。
    pause
    exit /b 1
)
%ADB% reverse --list

echo.
echo 连接成功！请在 App 里把地址填为 http://127.0.0.1:8600
echo 注意：拔线/重启后需重新双击本脚本。
echo.
pause
