"""采集控制器主循环：adb 抓帧 → 在左栏「口径列表」逐个找到并点击口径 →
右侧网格下滑一次 → OCR 该口径全部子卡片（名称+卡片底部价格）→ 写入数据库/快照。

与电脑端既有 app（FastAPI / SQLite / Web）配合：本控制器直接写同一 SQLite，
网页展示不需要任何改动。运行：cd pc && python run_collector.py
"""

from __future__ import annotations

import logging
import re
import time
from collections.abc import Callable
from datetime import datetime
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image

from collector.config import load_config
from collector.device import AdbDevice
from collector.matcher import compact
from collector.ocr import OcrEngine, OcrLine

logger = logging.getLogger("collector.controller")

SNAP_ROOT = Path(__file__).resolve().parent.parent / "static" / "snapshots"
DEBUG_DIR = Path(__file__).resolve().parent / "debug"
PRICE_MAX = 10_000_000
GRID_X0_RATIO = 0.18  # 右侧网格左边界（屏幕宽度比例）。第一列卡片名起始约 0.19W，需 <该值，否则左列整列漏采


class CollectorController:
    def __init__(
        self,
        device: AdbDevice,
        db,
        cfg: dict | None = None,
        ocr: OcrEngine | None = None,
    ) -> None:
        self.device = device
        self.db = db
        self.cfg = cfg if cfg is not None else load_config()
        self.ocr = ocr or OcrEngine()
        self.device_id = f"adb-{device.serial or 'unknown'}"

    # ---------- 工具 ----------
    def _grab(self) -> np.ndarray:
        png = self.device.screenshot_png()
        img = Image.open(BytesIO(png)).convert("RGB")
        return np.asarray(img)[:, :, ::-1].copy()

    def _debug_save(self, img: np.ndarray, name: str) -> None:
        if not self.cfg.get("debug_save"):
            return
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        Image.fromarray(img[:, :, ::-1]).save(DEBUG_DIR / name, quality=85)

    def _sleep(self) -> None:
        time.sleep(float(self.cfg.get("action_delay_ms", 500)) / 1000)

    def _snapshot_save(self, crop: np.ndarray) -> str | None:
        if not self.cfg.get("save_snapshots", True):
            return None
        sid = f"snap_adb{self.device_id[-8:]}_{int(time.time() * 1000)}.jpg"
        day = datetime.now().strftime("%Y%m%d")
        dest = SNAP_ROOT / day
        dest.mkdir(parents=True, exist_ok=True)
        rel = f"{day}/{sid}"
        Image.fromarray(crop[:, :, ::-1]).save(dest / sid, quality=85)
        self.db.register_snapshot(sid, rel, self.device_id)
        return sid

    def _store_record(self, name: str, price: int, img: np.ndarray | None, line: OcrLine | None) -> None:
        sid = None
        if img is not None and line is not None:
            pad = 10
            H, W = img.shape[:2]
            y0, y1 = max(0, line.top - pad), min(H, line.bottom + pad)
            x0, x1 = max(0, line.left - pad), min(W, line.right + pad)
            sid = self._snapshot_save(img[y0:y1, x0:x1]) if (y1 > y0 and x1 > x0) else None
        now = datetime.now().astimezone().isoformat(timespec="seconds")
        rec = SimpleNamespace(
            bullet_name=name,
            price=int(price),
            currency="Koen",
            market_type="market",
            captured_at=now,
            source="pc_caliber",
            snapshot_id=sid,
        )
        res = self.db.add_records(self.device_id, None, [rec])
        if res["rejected"]:
            logger.warning("入库被拒：%s", res["rejected"])
        else:
            logger.info("入库成功：%s = %s", name, price)

    # ---------- 左栏口径定位与点击 ----------
    def _tap_left_caliber(self, caliber: str, W: int, H: int) -> bool:
        """在左栏滚动找目标口径：先向下小幅滑动，找不到转为向上滑动。命中即点击。"""
        lp = self.cfg.get("left_panel", {})
        x = int(W * lp.get("x", 0.12))
        from_y = int(H * lp.get("from_y", 0.60))
        to_y = int(H * lp.get("to_y", 0.46))
        dur = int(lp.get("duration_ms", 300))
        key = compact(caliber)
        max_tries = int(self.cfg.get("max_left_scrolls", 8))

        def _scan_and_tap() -> bool:
            img = self._grab()
            self._debug_save(img, "left_scan.jpg")
            h, w = img.shape[:2]
            lines = self.ocr.scan(img[:, : int(w * 0.38)])
            hit = [l for l in lines if key in compact(l.text) and l.height > 8 and l.right < int(w * 0.27)]
            if not hit:
                return False
            target = max(hit, key=lambda l: l.bottom)
            tx = int((target.left + target.right) / 2)
            ty = int((target.top + target.bottom) / 2)
            logger.info("命中口径 %s，点击 (%d,%d)", caliber, tx, ty)
            self.device.tap(tx, ty)
            self._sleep()
            return True

        # 向下找（内容向上滚，看更下面的口径）
        for _ in range(max_tries):
            if _scan_and_tap():
                return True
            self.device.swipe(x, from_y, x, to_y, dur)
            self._sleep()
        # 向下未找到 → 转向上找（内容向下滚回）
        logger.info("向下未找到 %s，转向上查找", caliber)
        for _ in range(max_tries):
            if _scan_and_tap():
                return True
            self.device.swipe(x, to_y, x, from_y, dur)
            self._sleep()
        logger.warning("左栏未找到口径：%s", caliber)
        return False

    # ---------- 右侧网格记录 ----------
    def _extract_grid_records(
        self, img: np.ndarray, lines: list[OcrLine], caliber: str, W: int, H: int
    ) -> list[tuple[str, int, OcrLine]]:
        grid_x0 = int(W * GRID_X0_RATIO)
        below = int(self.cfg.get("price_below_row_px", 120))
        name_lines = [
            l for l in lines
            if l.left >= grid_x0 and ("子弹" in l.text or "毫米" in l.text) and l.height > 8
        ]
        out: list[tuple[str, int, OcrLine]] = []
        for nl in name_lines:
            name = nl.text.strip()
            if not name:
                continue
            y0, y1 = nl.bottom, min(H, nl.bottom + below)
            x0, x1 = max(grid_x0, nl.left - 10), min(W, nl.right + 40)
            if y1 <= y0 or x1 <= x0:
                continue
            crop = img[y0:y1, x0:x1]
            texts = self.ocr.scan_texts(crop)
            price = self._max_number(texts)
            if price is not None and 1 <= price <= PRICE_MAX:
                out.append((name, price, nl))
        return out

    @staticmethod
    def _max_number(texts: list[str]) -> int | None:
        nums: list[int] = []
        for t in texts:
            nums += [int(m) for m in re.findall(r"\d+", t)]
        nums = [n for n in nums if n > 0]
        return max(nums) if nums else None

    def _grid_scroll_back_to_top(self, W: int, H: int) -> None:
        """右侧网格向上滚回顶部：手指下滑（内容向下滚回），避免上一口径残留位置。"""
        gp = self.cfg.get("grid_panel", {})
        x = int(W * gp.get("x", 0.62))
        from_y = int(H * gp.get("from_y", 0.72))
        to_y = int(H * gp.get("to_y", 0.30))
        dur = int(gp.get("duration_ms", 400))
        for _ in range(int(self.cfg.get("grid_back_to_top_swipes", 4))):
            self.device.swipe(x, to_y, x, from_y, dur)
            self._sleep()

    def _collect_grid_records(self, caliber: str, W: int, H: int) -> list[tuple[str, int]]:
        """枚举该口径右侧网格全部子弹：回顶部后逐屏下滑、合并去重，
        连续两屏内容无变化判到底即停；价格取卡片底部（名称行下方）。"""
        cfg = self.cfg
        self._grid_scroll_back_to_top(W, H)
        merged: dict[str, int] = {}
        prev_hash: int | None = None
        stagnant = 0
        max_pages = int(cfg.get("max_grid_pages", 6))
        for _ in range(max_pages):
            img = self._grab()
            self._debug_save(img, f"grid_{caliber}.jpg")
            H, W = img.shape[:2]
            lines = self.ocr.scan(img)
            for name, price, _nl in self._extract_grid_records(img, lines, caliber, W, H):
                if name not in merged:
                    merged[name] = price
            h = hash(tuple(compact(l.text) for l in lines))
            stagnant = stagnant + 1 if h == prev_hash else 0
            prev_hash = h
            if stagnant >= 2:
                logger.info("口径 %s 网格到底（%d 屏无变化），停止", caliber, stagnant)
                break
            gp = cfg.get("grid_panel", {})
            x = int(W * gp.get("x", 0.62))
            from_y = int(H * gp.get("from_y", 0.72))
            to_y = int(H * gp.get("to_y", 0.45))
            self.device.swipe(x, from_y, x, to_y, int(gp.get("duration_ms", 400)))
            self._sleep()
        return list(merged.items())

    # ---------- 单轮（口径遍历） ----------
    def run_round(self) -> dict:
        cfg = self.cfg
        img = self._grab()
        H, W = img.shape[:2]
        logger.info("屏幕 %dx%d，口径列表 %d 项", W, H, len(cfg.get("calibers", [])))

        for x, y in cfg.get("nav_taps", []):
            self.device.tap(int(W * x), int(H * y))
            self._sleep()
        self._sleep()

        processed = 0
        missed: list[str] = []
        for caliber in cfg.get("calibers", []):
            if not self._tap_left_caliber(caliber, W, H):
                missed.append(caliber)
                continue
            # 逐屏枚举该口径全部卡片（回顶+下滑+合并去重+到底停止）
            records = self._collect_grid_records(caliber, W, H)
            for name, price in records:
                self._store_record(name, price, None, None)
                processed += 1
            logger.info("口径 %s：记录 %d 条", caliber, len(records))

        logger.info("轮完成：共记录 %d 条，漏口径 %s", processed, missed or "无")
        return {"processed": processed, "missed": missed}

    # ---------- 周期循环 ----------
    def run_forever(self, once: bool = False) -> None:
        interval = float(self.cfg.get("interval_sec", 60))
        logger.info("开始采集：周期 %.0fs，口径 %d 个", interval, len(self.cfg.get("calibers", [])))
        while True:
            try:
                summary = self.run_round()
                logger.info("本轮：记录 %d 条，漏口径 %s", summary["processed"], summary["missed"] or "无")
            except Exception as e:  # noqa: BLE001
                logger.exception("本轮异常：%s", e)
            if once:
                break
            time.sleep(max(interval, 2))
