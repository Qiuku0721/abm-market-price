package com.abm.collector.ocr

import android.graphics.Bitmap
import android.graphics.Rect
import android.util.Log
import com.google.mlkit.vision.common.InputImage
import com.google.mlkit.vision.text.TextRecognition
import com.google.mlkit.vision.text.TextRecognizer
import com.google.mlkit.vision.text.chinese.ChineseTextRecognizerOptions
import com.google.android.gms.tasks.Tasks
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.withContext

/** 一条 OCR 识别出的文本行及其屏幕坐标（绝对像素）。 */
data class OcrLine(
    val text: String,
    val bounds: Rect
)

/**
 * 文本识别模块：Google ML Kit 中文模型（同时覆盖拉丁字母与阿拉伯数字）。
 *
 * - [scan] 在 IO 线程执行识别（内部用 Tasks.await 阻塞式等待，调用方须为协程）；
 * - 输出按「行」组织（每行一个 [OcrLine]），坐标供后续按名称/价格格裁剪与匹配；
 * - [close] 释放识别器（与 CollectorService 生命周期绑定）。
 */
class TextScanner {

    private val tag = "TextScanner"
    private val recognizer: TextRecognizer =
        TextRecognition.getClient(ChineseTextRecognizerOptions.Builder().build())

    /** 识别整张截图，返回所有文本行。失败返回空列表（由调用方决定重试）。 */
    suspend fun scan(bitmap: Bitmap): List<OcrLine> = withContext(Dispatchers.IO) {
        val image = InputImage.fromBitmap(bitmap, 0)
        try {
            val result = Tasks.await(recognizer.process(image))
            buildList {
                for (block in result.textBlocks) {
                    for (line in block.lines) {
                        val box = line.boundingBox
                        if (box != null && line.text.isNotBlank()) {
                            add(OcrLine(line.text.trim(), box))
                        }
                    }
                }
            }
        } catch (e: Exception) {
            Log.w(tag, "ocr process failed", e)
            emptyList()
        }
    }

    fun close() {
        recognizer.close()
    }
}
