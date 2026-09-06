"""RapidOCR 封装：整图/区域文本识别，输出 (text, rect)。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np

logger = logging.getLogger("collector.ocr")


@dataclass
class OcrLine:
    text: str
    left: int
    top: int
    right: int
    bottom: int

    @property
    def width(self) -> int:
        return self.right - self.left

    @property
    def height(self) -> int:
        return self.bottom - self.top


class OcrEngine:
    """RapidOCR（onnxruntime）。首帧初始化会加载/下载模型。"""

    def __init__(self) -> None:
        self._engine = None

    def _lazy_init(self):
        if self._engine is not None:
            return
        try:
            from rapidocr_onnxruntime import RapidOCR
        except ImportError as e:  # pragma: no cover
            raise RuntimeError(
                "缺少 OCR 依赖：请先执行  pip install -r requirements.txt "
                "（或单独安装 rapidocr-onnxruntime）"
            ) from e
        logger.info("初始化 RapidOCR（首次会下载模型，约 15MB）…")
        self._engine = RapidOCR()

    def scan(self, img: np.ndarray) -> list[OcrLine]:
        """识别一张图（BGR 或 RGB ndarray）。"""
        self._lazy_init()
        result, _ = self._engine(img)
        lines: list[OcrLine] = []
        if not result:
            return lines
        for box, text, _score in result:
            text = (text or "").strip()
            if not text:
                continue
            xs = [p[0] for p in box]
            ys = [p[1] for p in box]
            lines.append(
                OcrLine(
                    text=text,
                    left=int(min(xs)),
                    top=int(min(ys)),
                    right=int(max(xs)),
                    bottom=int(max(ys)),
                )
            )
        return lines

    def scan_texts(self, img: np.ndarray) -> list[str]:
        return [l.text for l in self.scan(img)]
