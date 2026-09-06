"""采集控制器主循环：adb 抓帧 → OCR 匹配子弹 → 解析价格 → 写入数据库/快照。

与电脑端既有 app（FastAPI / SQLite / Web）配合：本控制器直接写同一 SQLite，
网页展示不需要任何改动。运行：cd pc && python run_collector.py
"""

from __future__ import annotations

import logging
import time
from datetime import datetime
from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

import numpy as np
from PIL import Image

from collector.config import load_config
from collector.device import AdbDevice
from collector.matcher import compact, match_lines, parse_price, vertical_overlap_ratio
from collector.ocr import OcrEngine, OcrLine

logger = logging.getLogger("collector.controller")

SNAP_ROOT = Path(__file__).resolve().parent.parent / "static" / "snapshots"
DEBUG_DIR = Path(__file__).resolve().parent / "debug"


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
        """抓一帧并转为 BGR ndarray（RapidOCR 按 BGR 处理）。"""
        png = self.device.screenshot_png()
        img = Image.open(BytesIO(png)).convert("RGB")
        return np.asarray(img)[:, :, ::-1].copy()

    def _debug_save(self, img: np.ndarray, name: str) -> None:
        if not self.cfg.get("debug_save"):
            return
        DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        Image.fromarray(img[:, :, ::-1]).save(DEBUG_DIR / name, quality=85)

    def _snapshot_save(self, crop: np.ndarray) -> str | None:
        """保存命中行快照，返回 snapshot_id。"""
        if not self.cfg.get("save_snapshots", True):
            return None
        sid = f"snap_adb{self.device_id[-8:]}_{int(time.time() * 1000)}.jpg"
        day = datetime.now().strftime("%Y%m%d")
        dest = SNAP_ROOT / day
        dest.mkdir(parents=True, exist_ok=True)
        rel = f"{day}/{sid}"
        Image.fromarray(crop[:, :, ::-1]).save(SNAP_ROOT / rel, quality=85)
        self.db.register_snapshot(sid, rel, self.device_id)
        return sid

    # ---------- 单轮扫描 ----------
    def run_round(self) -> dict:
        cfg = self.cfg
        H, W = None, None  # 由第一帧确定
        pending = {b.strip() for b in cfg.get("bullets", []) if b.strip()}
        hit: list[str] = []
        failures = 0

        # 1) 导航点击（进入市场/子弹分类）
        self._press_nav_taps(cfg.get("nav_taps", []))
        time.sleep(0.8)

        img = self._grab()
        H, W = img.shape[:2]
        logger.info("屏幕 %dx%d，目标清单 %d 项", W, H, len(pending))

        # 2) 回列表顶部（内容向上滚：手指向下拖）
        s = cfg["scroll"]
        self._swipe_up_scroll(s, repeat=cfg.get("top_swipes", 6), reverse=True)

        stagnant = 0
        prev_hash: int | None = None
        pages = 0
        for page in range(cfg.get("max_scrolls", 12)):
            pages = page + 1
            time.sleep(cfg.get("action_delay_ms", 500) / 1000)
            img = self._grab()
            H, W = img.shape[:2]
            lines = self.ocr.scan(img)
            self._debug_save(img, f"page_{page:02d}.jpg")

            for name, line in match_lines(lines, pending):
                pending.discard(name)
                price = self._resolve_price(img, lines, line)
                if price is not None and 1 <= price <= _PRICE_MAX:
                    hit.append(name)
                    self._store_record(name, price, img, line)
                    logger.info("命中 %s = %s", name, price)
                else:
                    failures += 1
                    logger.warning("价格解析失败：%s（OCR: %s）", name, line.text)

            if not pending:
                logger.info("清单全部命中")
                break
            if page == cfg.get("max_scrolls", 12) - 1:
                break

            # 停滞检测
            h = hash(tuple(compact(l.text) for l in lines))
            stagnant = stagnant + 1 if h == prev_hash else 0
            prev_hash = h
            if stagnant >= cfg.get("stagnant_limit", 2):
                logger.info("列表已到底（连续 %d 屏无变化）", stagnant)
                break

            self._swipe_up_scroll(s, repeat=1, reverse=False)
            time.sleep(0.3)

        return {"hit": hit, "notFound": sorted(pending), "failures": failures, "pages": pages}

    def _press_nav_taps(self, taps) -> None:
        if not taps:
            return
        # 先用一次截屏确定尺寸
        img = self._grab()
        h, w = img.shape[:2]
        logger.info("导航点击 %d 个（屏幕 %dx%d）", len(taps), w, h)
        for x, y in taps:
            self.device.tap(int(w * x), int(h * y))
            time.sleep(cfg_delay(self.cfg) / 1000)

    def _swipe_up_scroll(self, s: dict, repeat: int, reverse: bool) -> None:
        """reverse=False：手指上滑（列表向下滚，看下一屏）；
        reverse=True：手指下滑（列表向上滚，回顶部）。"""
        for _ in range(repeat):
            img = self._grab()
            h = img.shape[0]
            x = int(img.shape[1] * s["x"])
            y_from = int(h * (s["to_y"] if reverse else s["from_y"]))
            y_to = int(h * (s["from_y"] if reverse else s["to_y"]))
            self.device.swipe(x, y_from, x, y_to, int(s.get("duration_ms", 400)))
            time.sleep(cfg_delay(self.cfg) / 1000)

    def _resolve_price(self, img: np.ndarray, lines: list[OcrLine], name_line: OcrLine):
        H, W = img.shape[:2]
        left = int(W * self.cfg.get("price_zone_left_x", 0.52))
        pad = int(self.cfg.get("row_pad_px", 22))
        x0, x1 = max(0, left), W
        y0, y1 = max(0, name_line.top - pad), min(H, name_line.bottom + pad)
        if x1 - x0 <= 10 or y1 - y0 <= 4:
            return None

        # 1) 复用同屏右侧文本行
        for l in sorted(lines, key=lambda x: x.top):
            if l.left >= left // 2 and vertical_overlap_ratio(l, y0, y1) >= 0.5:
                price = parse_price(l.text)
                if price is not None:
                    return price
        # 2) 裁剪价格格重新识别
        crop = img[y0:y1, x0:x1]
        if crop.size == 0:
            return None
        sub = self.ocr.scan_texts(crop)
        return parse_price(" ".join(sub))

    def _store_record(self, name: str, price: int, img: np.ndarray, line: OcrLine) -> None:
        pad = int(self.cfg.get("row_pad_px", 22))
        H, W = img.shape[:2]
        y0, y1 = max(0, line.top - pad), min(H, line.bottom + pad)
        x0, x1 = max(0, line.left - pad), min(W, line.right + pad)
        sid = None
        if y1 > y0 and x1 > x0:
            sid = self._snapshot_save(img[y0:y1, x0:x1])

        now = datetime.now().astimezone().isoformat(timespec="seconds")
        rec = SimpleNamespace(
            bullet_name=name,
            price=int(price),
            currency="Koen",
            market_type="market",
            captured_at=now,
            source="pc_list_scan",
            snapshot_id=sid,
        )
        res = self.db.add_records(self.device_id, None, [rec])
        if res["rejected"]:
            logger.warning("入库被拒：%s", res["rejected"])
        else:
            logger.info("入库成功：%s = %s", name, price)

    # ---------- 周期循环 ----------
    def run_forever(self, once: bool = False) -> None:
        interval = float(self.cfg.get("interval_sec", 60))
        logger.info("开始采集：周期 %.0fs，目标 %s", interval, self.cfg.get("bullets"))
        while True:
            try:
                summary = self.run_round()
                logger.info(
                    "本轮完成：命中 %d，未找到 %d，解析失败 %d，扫 %d 屏",
                    len(summary["hit"]),
                    len(summary["notFound"]),
                    summary["failures"],
                    summary["pages"],
                )
            except Exception as e:  # noqa: BLE001
                logger.exception("本轮异常：%s", e)
            if once:
                break
            time.sleep(max(interval, 2))


def cfg_delay(cfg: dict) -> float:
    return float(cfg.get("action_delay_ms", 500))
