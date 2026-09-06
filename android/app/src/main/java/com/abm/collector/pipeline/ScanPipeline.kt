package com.abm.collector.pipeline

import android.graphics.Bitmap
import android.graphics.Rect
import com.abm.collector.capture.ScreenCapturer
import com.abm.collector.gesture.GestureController
import com.abm.collector.ocr.OcrLine
import com.abm.collector.ocr.PriceParser
import com.abm.collector.ocr.TextScanner
import kotlinx.coroutines.delay
import java.io.ByteArrayOutputStream
import java.time.OffsetDateTime
import java.time.ZoneId
import java.time.format.DateTimeFormatter
import java.util.Random

/** 一次命中：子弹名 → 价格记录（含可选 JPEG 缩略图字节，供快照留档）。 */
data class PriceRecord(
    val bulletName: String,
    val price: Int,
    val capturedAt: String,
    val source: String = "list_scan",
    val snapshotJpeg: ByteArray? = null
)

/** 一轮全量扫描的结果摘要（供调度层决定重试/间隔）。 */
data class RoundSummary(
    val hit: List<String>,
    val notFound: List<String>,
    val parseFailures: Int,
    val pagesScanned: Int,
    val aborted: Boolean
)

/**
 * 采集流程编排（一轮 = 回到列表顶部 → 逐屏向下扫描 → 匹配清单 → 读价格 → 上报回调）。
 *
 * 启发式规则（真机可调，见 [LayoutProfile]）：
 * - 名称匹配：OCR 行文本与清单名做「归一化子串匹配」（容忍 ×/x、全角、大小写）；
 * - 价格解析：先取名称行右侧的既有文本行，失败则裁剪「价格格」区域重 OCR；
 * - 停滞检测：连续 2 屏 OCR 文本无变化且无命中 → 判定已到列表底部，停止滚动；
 * - 超时兜底：整轮最多扫 [maxScrolls] 屏。
 *
 * @param onRecord 命中回调：(record, snapshotJpeg)——由上报模块消费并负责释放。
 */
class ScanPipeline(
    private val capturer: ScreenCapturer,
    private val scanner: TextScanner,
    private val bullets: BulletStore,
    private val profile: LayoutProfile = LayoutProfile.DEFAULT,
    private val onRecord: (PriceRecord, ByteArray?) -> Unit,
    private val log: (String) -> Unit = {}
) {
    private val tag = "ScanPipeline"
    private val random = Random(System.currentTimeMillis())

    suspend fun runRound(screenW: Int, screenH: Int, maxScrolls: Int = 12): RoundSummary {
        log("round 开始：先回列表顶部")
        scrollToTop(screenW, screenH)
        delay(actionDelay())

        val pending = bullets.activeNames().toMutableSet()
        val hit = mutableListOf<String>()
        var parseFailures = 0
        var prevHash = 0L
        var stagnant = 0
        var aborted = false
        var pages = 0

        for (page in 0 until maxScrolls) {
            pages = page + 1
            delay(actionDelay())
            val frame = captureWithRetry()
            if (frame == null) {
                log("截屏失败，中止本轮")
                aborted = true
                break
            }
            val lines = scanner.scan(frame)

            val matched = matchOnScreen(lines, pending)
            for ((name, nameLine) in matched) {
                pending.remove(name)
                hit.add(name)
                val price = resolvePrice(frame, lines, nameLine)
                if (price != null && price in 1..PRICE_MAX) {
                    val thumb = rowThumb(frame, nameLine.bounds)
                    val record = PriceRecord(
                        bulletName = name,
                        price = price,
                        capturedAt = isoNow(),
                        source = "list_scan"
                    )
                    onRecord(record, thumb)
                    log("命中 $name = $price")
                } else {
                    parseFailures++
                    log("价格解析失败：$name （OCR行：${nameLine.text}）")
                }
            }

            frame.recycle()

            if (pending.isEmpty()) {
                log("清单全部命中，提前结束本轮")
                break
            }
            if (page == maxScrolls - 1) break

            // 停滞判定（本屏与上一屏 OCR 内容无变化且无命中）
            val hash = lines.joinToString("|") { it.text }.hashCode()
            stagnant = if (hash == prevHash) stagnant + 1 else 0
            prevHash = hash
            if (stagnant >= STAGNANT_LIMIT) {
                log("列表已到底部，停止滚动")
                break
            }
            // 向下滚动一屏
            val fromY = (screenH * profile.scrollFromY).toInt()
            val toY = (screenH * (profile.scrollFromY - profile.scrollDistanceRatio)).toInt()
            GestureController.swipe(
                (screenW * profile.scrollX).toFloat(), fromY.toFloat(),
                (screenW * profile.scrollX).toFloat(), toY.toFloat(),
                400L
            )
        }
        log("round 结束：命中 ${hit.size}，未找到 ${pending.size}，解析失败 $parseFailures")
        return RoundSummary(hit, pending.toList(), parseFailures, pages, aborted)
    }

    /** 回到列表顶部：连续执行「手指下移」（列表内容向上滚）。 */
    private suspend fun scrollToTop(w: Int, h: Int) {
        val x = (w * profile.scrollX).toFloat()
        val yFrom = (h * 0.30f).toInt().toFloat()
        val yTo = (h * 0.85f).toInt().toFloat()
        repeat(profile.scrollToTopSwipes) {
            GestureController.swipe(x, yFrom, x, yTo, 300L)
            delay(actionDelay())
        }
    }

    private suspend fun captureWithRetry(): Bitmap? {
        repeat(CAPTURE_RETRY) {
            capturer.captureFrame()?.let { return it }
            delay(200L)
        }
        return null
    }

    /** 归一化匹配：容忍全角、×/x、大小写、多余空白。子串包含匹配。 */
    private fun matchOnScreen(lines: List<OcrLine>, pending: Set<String>): List<Pair<String, OcrLine>> {
        val found = mutableListOf<Pair<String, OcrLine>>()
        val seenNames = mutableSetOf<String>()
        for (line in lines) {
            val text = compact(line.text)
            for (name in pending) {
                val key = compact(name)
                if (key.length >= 2 && text.contains(key) && seenNames.add(name)) {
                    found.add(name to line)
                }
            }
        }
        return found
    }

    private fun compact(s: String): String {
        val norm = PriceParser.normalize(s).lowercase()
        return norm
            .replace('×', 'x')
            .replace('*', 'x')
            .replace(" ", "")
            .replace("\u00A0", "")
    }

    /** 解析名称行对应的价格：先复用同屏右侧文本行，否则裁剪价格格重 OCR。 */
    private suspend fun resolvePrice(frame: Bitmap, lines: List<OcrLine>, nameLine: OcrLine): Int? {
        val zone = Rect(
            (frame.width * profile.priceZoneLeftX).toInt(),
            (nameLine.bounds.top - profile.rowPaddingPx).coerceAtLeast(0),
            frame.width,
            (nameLine.bounds.bottom + profile.rowPaddingPx).coerceAtMost(frame.height)
        )
        if (zone.width() <= 20 || zone.height() <= 8) return null

        // 1) 已有文本行：位于价格格区域、与名称行垂直重叠 ≥ 50%，自下而上取
        val candidates = lines.filter { l ->
            l.bounds.left >= zone.left / 2 &&
                verticalOverlapRatio(l.bounds, zone) >= 0.5f
        }.sortedBy { it.bounds.top }
        for (l in candidates.asReversed()) {
            PriceParser.parsePrice(l.text)?.let { return it }
        }

        // 2) 裁剪价格格，缩小范围重 OCR
        val crop = Bitmap.createBitmap(frame, zone.left, zone.top, zone.width(), zone.height())
        val sub = scanner.scan(crop)
        val snippet = sub.joinToString(" ") { it.text }
        crop.recycle()
        return PriceParser.parsePrice(snippet)
    }

    /** 命中行截图缩略（≤ 420px 宽 JPEG 字节），用于电脑端人工抽查 OCR 是否正确。 */
    private fun rowThumb(frame: Bitmap, bounds: Rect): ByteArray? {
        val pad = profile.rowPaddingPx * 2
        val r = Rect(
            (bounds.left - pad).coerceAtLeast(0),
            (bounds.top - pad).coerceAtLeast(0),
            (bounds.right + pad).coerceAtMost(frame.width),
            (bounds.bottom + pad).coerceAtMost(frame.height)
        )
        if (r.width() <= 0 || r.height() <= 0) return null
        var crop = Bitmap.createBitmap(frame, r.left, r.top, r.width(), r.height())
        if (crop.width > 420) {
            val scale = 420f / crop.width
            val scaled = Bitmap.createScaledBitmap(
                crop,
                420,
                (crop.height * scale).toInt().coerceAtLeast(1),
                true
            )
            crop.recycle()
            crop = scaled
        }
        val out = ByteArrayOutputStream()
        if (!crop.compress(Bitmap.CompressFormat.JPEG, 70, out)) {
            crop.recycle()
            return null
        }
        crop.recycle()
        return out.toByteArray()
    }

    private fun verticalOverlapRatio(a: Rect, b: Rect): Float {
        val top = maxOf(a.top, b.top)
        val bottom = minOf(a.bottom, b.bottom)
        val overlap = (bottom - top).coerceAtLeast(0)
        val height = a.height().coerceAtLeast(1)
        return overlap.toFloat() / height
    }

    private fun actionDelay(): Long = ACTION_DELAY_MS + random.nextInt(300).toLong()

    private fun isoNow(): String =
        OffsetDateTime.now(ZoneId.systemDefault()).format(DateTimeFormatter.ISO_OFFSET_DATE_TIME)

    private companion object {
        const val PRICE_MAX = 10_000_000
        const val ACTION_DELAY_MS = 500L
        const val CAPTURE_RETRY = 6
        const val STAGNANT_LIMIT = 2
    }
}
