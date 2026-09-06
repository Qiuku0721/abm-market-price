"""ADB 设备封装：截图抓帧、坐标点击/滑动（USB 有线）。"""

from __future__ import annotations

import os
import shutil
import subprocess
import time
from pathlib import Path


def find_adb() -> str:
    """定位 adb：PATH -> ANDROID_HOME -> 常见位置。"""
    env = os.environ.get("ANDROID_HOME")
    candidates = []
    exe = shutil.which("adb")
    if exe:
        return exe
    if env:
        candidates.append(str(Path(env) / "platform-tools" / "adb.exe"))
    candidates += [
        str(Path.home() / "AppData" / "Local" / "Android" / "Sdk" / "platform-tools" / "adb.exe"),
        r"D:\IDEA\adb\platform-tools\adb.exe",
        "adb",
    ]
    for c in candidates:
        if c == "adb" or os.path.exists(c):
            return c
    raise FileNotFoundError(
        "未找到 adb。请安装 platform-tools 或设置 ANDROID_HOME，也可把 adb 加入 PATH。"
    )


class AdbError(RuntimeError):
    pass


class AdbDevice:
    def __init__(self, serial: str | None = None, adb_path: str | None = None):
        self.adb = adb_path or find_adb()
        self.serial = serial or os.environ.get("ANDROID_SERIAL")

    # ---------- 底层 ----------
    def _run(self, args: list[str], timeout: float = 15.0) -> bytes:
        cmd = [self.adb]
        if self.serial:
            cmd += ["-s", self.serial]
        cmd += args
        try:
            p = subprocess.run(
                cmd,
                capture_output=True,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as e:
            raise AdbError(f"adb 命令超时：{args[:2]}") from e
        if p.returncode != 0:
            raise AdbError(
                f"adb 失败({p.returncode}): {' '.join(args[:4])} {p.stderr.decode(errors='ignore')[:200]}"
            )
        return p.stdout

    def list_devices(self) -> list[str]:
        out = self._run(["devices"]).decode(errors="ignore")
        devs = []
        for line in out.splitlines()[1:]:
            if line.strip() and "device" in line and "offline" not in line:
                devs.append(line.split("\t")[0])
        return devs

    def pick_serial(self) -> str | None:
        """未显式指定时自动选唯一在线设备；多台则报错提示。"""
        devs = self.list_devices()
        if self.serial:
            if self.serial not in devs:
                raise AdbError(f"指定设备 {self.serial} 不在线（当前在线：{devs or '无'}）")
            return self.serial
        if len(devs) == 0:
            raise AdbError("未检测到设备：请插好数据线并开启「USB 调试」，允许本机授权")
        if len(devs) > 1:
            raise AdbError(f"检测到多台设备 {devs}，请设置 ANDROID_SERIAL 或用 --serial 指定")
        self.serial = devs[0]
        return self.serial

    # ---------- 动作 ----------
    def screenshot_png(self) -> bytes:
        """抓一帧全屏 PNG（经 USB）。"""
        return self._run(["exec-out", "screencap", "-p"], timeout=20.0)

    def tap(self, x: int, y: int) -> None:
        self._run(["shell", "input", "tap", str(int(x)), str(int(y))])

    def swipe(self, x1: int, y1: int, x2: int, y2: int, ms: int = 350) -> None:
        self._run(
            ["shell", "input", "swipe", str(int(x1)), str(int(y1)), str(int(x2)), str(int(y2)), str(int(ms))]
        )

    def back(self) -> None:
        self._run(["shell", "input", "keyevent", "4"])

    def wake_up(self) -> None:
        self._run(["shell", "input", "keyevent", "KEYCODE_WAKEUP"])

    def wait_online(self, tries: int = 10, pause: float = 1.0) -> None:
        for _ in range(tries):
            try:
                if self.pick_serial():
                    return
            except AdbError:
                pass
            time.sleep(pause)
        raise AdbError("等待设备上线超时")
