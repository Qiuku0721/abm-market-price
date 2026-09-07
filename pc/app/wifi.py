"""局域网无线调试连接（adb over Wi-Fi）：手机与电脑同一网络，无需数据线。

适用：Android 11+ 的「开发者选项 → 无线调试」（设置→无线调试→开启；用配对码配对时填
「使用配对码配对设备」的端口与 6 位码）；旧安卓可用 `adb tcpip 5555` 后连接。
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


def find_adb() -> str:
    env = os.environ.get("ANDROID_HOME")
    cands = [
        f"{env}/platform-tools/adb.exe" if env else None,
        str(Path.home() / "AppData" / "Local" / "Android" / "Sdk" / "platform-tools" / "adb.exe"),
        r"D:\IDEA\adb\platform-tools\adb.exe",
    ]
    for c in cands:
        if c and os.path.exists(c):
            return c
    raise RuntimeError("未找到 adb：请安装 platform-tools 或设置 ANDROID_HOME")


def _run(adb: str, args: list[str], input_text: str | None = None, timeout: int = 25) -> subprocess.CompletedProcess:
    return subprocess.run(
        [adb, *args],
        capture_output=True,
        text=True,
        input=input_text,
        timeout=timeout,
    )


def devices(adb: str | None = None) -> list[str]:
    adb = adb or find_adb()
    p = _run(adb, ["devices"])
    out = []
    for line in (p.stdout or "").splitlines()[1:]:
        s = line.strip()
        if s.endswith("\tdevice") or s.endswith(" device"):
            out.append(s.split("\t")[0].split(" ")[0])
    return out


def wifi_connect(
    host: str,
    dev_port: int,
    pair_port: int | None = None,
    pair_code: str | None = None,
    adb: str | None = None,
) -> dict:
    """连接手机无线调试。首次配对填 pair_port+pair_code；之后仅 connect。返回设备列表。"""
    adb = adb or find_adb()
    log: list[str] = []
    if pair_port and pair_code:
        r = _run(adb, ["pair", f"{host}:{pair_port}"], input_text=f"{pair_code}\n")
        log.append((r.stdout or "").strip() or (r.stderr or "").strip())
    c = _run(adb, ["connect", f"{host}:{dev_port}"])
    log.append((c.stdout or "").strip() or (c.stderr or "").strip())
    return {
        "ok": c.returncode == 0,
        "output": "\n".join(x for x in log if x),
        "devices": devices(adb),
    }
