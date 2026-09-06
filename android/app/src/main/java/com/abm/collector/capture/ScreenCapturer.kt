package com.abm.collector.capture

import android.graphics.Bitmap
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.Image
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.os.Handler
import android.os.HandlerThread
import android.util.Log
import java.util.concurrent.atomic.AtomicBoolean

/**
 * 屏幕采集模块：基于 MediaProjection 的虚拟显示 + ImageReader 的「按需单帧截图」。
 *
 * 本模块面向「周期性截屏识别」场景（非连续视频流）：
 * - [start] 建立 VirtualDisplay 镜像真实屏幕到 ImageReader；
 * - [captureFrame] 每帧同步取出最近一帧并转 Bitmap（无新帧返回 null，由调用方重试）；
 * - [stop] 释放虚拟显示与读取器（不停止 MediaProjection，其归属 CollectorService 统一管理）。
 *
 * 线程模型：captureFrame 在调用线程执行；ImageReader 事件在内部 HandlerThread 上。
 */
class ScreenCapturer(
    private val projection: MediaProjection,
    private val width: Int,
    private val height: Int,
    private val densityDpi: Int
) {
    private val tag = "ScreenCapturer"
    private val captureThread = HandlerThread("abm-capture-thread").apply { start() }
    private val handler = Handler(captureThread.looper)

    private var imageReader: ImageReader? = null
    private var virtualDisplay: VirtualDisplay? = null
    private val started = AtomicBoolean(false)

    /** 建立虚拟显示。重复调用幂等。 */
    fun start() {
        if (started.getAndSet(true)) return
        val reader = ImageReader.newInstance(width, height, PixelFormat.RGBA_8888, 2)
        imageReader = reader
        virtualDisplay = projection.createVirtualDisplay(
            "ABMCollectorDisplay",
            width,
            height,
            densityDpi,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR,
            reader.surface,
            null,
            handler
        )
        Log.i(tag, "virtual display started ${width}x${height}@$densityDpi")
    }

    /** 同步抓取最近一帧；无新帧或未启动时返回 null（调用方应短暂重试）。 */
    fun captureFrame(): Bitmap? {
        if (!started.get()) return null
        val reader = imageReader ?: return null
        val image = try {
            reader.acquireLatestImage() ?: return null
        } catch (e: IllegalStateException) {
            Log.w(tag, "acquireLatestImage failed", e)
            return null
        }
        return try {
            image.toBitmap()
        } finally {
            image.close()
        }
    }

    /**
     * 抓帧并等比缩略（供快照上报，节省带宽）。
     * @param maxDim 最长边像素；为 null 时不缩放。
     */
    fun captureThumb(maxDim: Int? = 720): Bitmap? {
        val frame = captureFrame() ?: return null
        val dim = maxDim ?: return frame
        if (frame.width <= dim && frame.height <= dim) return frame
        val scale = dim.toFloat() / maxOf(frame.width, frame.height)
        val w = (frame.width * scale).toInt().coerceAtLeast(1)
        val h = (frame.height * scale).toInt().coerceAtLeast(1)
        val thumb = Bitmap.createScaledBitmap(frame, w, h, true)
        if (thumb !== frame) frame.recycle()
        return thumb
    }

    /** 释放虚拟显示与 ImageReader（幂等）。之后如需继续采集需重建实例。 */
    fun stop() {
        if (!started.getAndSet(false)) return
        try {
            virtualDisplay?.release()
        } catch (_: Exception) {
        }
        try {
            imageReader?.close()
        } catch (_: Exception) {
        }
        virtualDisplay = null
        imageReader = null
        captureThread.quitSafely()
        Log.i(tag, "capturer released")
    }

    private fun Image.toBitmap(): Bitmap {
        val plane = planes[0]
        val pixelStride = plane.pixelStride
        val rowStride = plane.rowStride
        val rowPadding = rowStride - pixelStride * width
        // 先按含 padding 的行宽拷贝，再裁掉右侧 padding
        val padded = Bitmap.createBitmap(
            width + rowPadding / pixelStride,
            height,
            Bitmap.Config.ARGB_8888
        )
        padded.copyPixelsFromBuffer(plane.buffer)
        return if (rowPadding == 0) {
            padded
        } else {
            val cropped = Bitmap.createBitmap(padded, 0, 0, width, height)
            padded.recycle()
            cropped
        }
    }
}
