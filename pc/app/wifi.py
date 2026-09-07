"""局域网无线调试连接（adb over Wi-Fi）：自动发现 + 连接 + 断开 + 状态。

- 自动发现：`adb mdns services` 列出局域网内开启了「无线调试」的手机；
- 连接：`adb connect ip:port`；首次可 `adb pair`（配对端口+6位码）；
- 状态：区分「无线设备（ip:port）」与「USB 设备」。
"""

from __future__ import annotations

import os
import re
import subprocess
import time
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


def _run(adb: str, args: list[str], input_text: str | None = None, timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(
        [adb, *args], capture_output=True, text=True, input=input_text, timeout=timeout
    )


def _parse_mdns(text: str) -> list[dict]:
    """解析 `adb mdns services` 输出为候选设备列表（按多空格分列，名可含单空格）。"""
    out: list[dict] = []
    for line in (text or "").splitlines():
        s = line.strip()
        if not s or s.startswith(("Name", "List of", "mdns daemon")):
            continue
        cols = re.split(r"\s{2,}", s)
        if len(cols) >= 4:
            try:
                port = int(cols[3])
            except ValueError:
                continue
            out.append({
                "name": cols[0],
                "host": cols[2],
                "port": port,
                "tls": (cols[4] == "tls") if len(cols) > 4 else False,
            })
    return out


def mdns_scan(adb: str | None = None) -> list[dict]:
    """先激活 adb discovery，再扫描（部分环境需先 check 才收到广播）。"""
    adb = adb or find_adb()
    try:
        _run(adb, ["mdns", "check"], timeout=6)
        time.sleep(1.2)
        p = _run(adb, ["mdns", "services"], timeout=10)
    except subprocess.TimeoutExpired:
        return []
    return _parse_mdns(p.stdout or "")


def devices(adb: str | None = None) -> list[str]:
    """在线设备地址列表（含无线与 USB）。"""
    adb = adb or find_adb()
    p = _run(adb, ["devices"])
    out = []
    for line in (p.stdout or "").splitlines()[1:]:
        s = line.strip()
        if s.endswith("\tdevice") or s.endswith(" device"):
            out.append(s.split("\t")[0].split(" ")[0])
    return out


def devices_status(adb: str | None = None) -> dict:
    adb = adb or find_adb()
    ids = devices(adb)
    wireless = [a for a in ids if ":" in a]
    usb = [a for a in ids if ":" not in a]
    return {"wireless": wireless, "usb": usb, "all": ids}


def wifi_connect(
    host: str,
    dev_port: int,
    pair_port: int | None = None,
    pair_code: str | None = None,
    adb: str | None = None,
) -> dict:
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


def disconnect(addr: str, adb: str | None = None) -> dict:
    adb = adb or find_adb()
    p = _run(adb, ["disconnect", addr])
    return {"ok": p.returncode == 0, "output": (p.stdout or p.stderr or "").strip()}
