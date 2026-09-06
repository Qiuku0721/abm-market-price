"""RapidOCR 封装：整图/区域文本识别，输出 (text, rect)。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from PIL import Image

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

    MAX_DIM = 1600  # 识别前把长边压到该值，显著降低 CPU（像素约减 55%+），坐标自动还原

    def scan(self, img: np.ndarray) -> list[OcrLine]:
        """识别一张图（BGR 或 RGB ndarray）。内部先降采样以降低 CPU，结果坐标已还原为原图坐标。"""
        self._lazy_init()
        h, w = img.shape[:2]
        scale = min(1.0, self.MAX_DIM / max(h, w))
        run_img, inv = img, 1.0
        if scale < 1.0:
            pil = Image.fromarray(img[:, :, ::-1]).resize(
                (max(1, int(w * scale)), max(1, int(h * scale))), Image.LANCZOS
            )
            run_img = np.asarray(pil)[:, :, ::-1].copy()
            inv = 1.0 / scale

        result, _ = self._engine(run_img)
        lines: list[OcrLine] = []
        if not result:
            return lines
        for box, text, _score in result:
            text = (text or "").strip()
            if not text:
                continue
            xs = [p[0] * inv for p in box]
            ys = [p[1] * inv for p in box]
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
