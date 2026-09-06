package com.abm.collector.gesture

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.util.Log
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.suspendCancellableCoroutine
import kotlinx.coroutines.withContext
import java.util.Random
import kotlin.coroutines.resume

/**
 * 手势控制器：把「点击 / 滑动 / 返回」封装为可挂起的手势操作，
 * 供采集流程按序串行调用。
 *
 * - 基于无障碍服务的 dispatchGesture（API 26+），坐标注入；
 * - 坐标带小范围随机抖动（默认 6px），减少固定坐标带来的操作特征；
 * - 所有手势必须在主线程派发，内部已切到 Dispatchers.Main；
 * - 服务未开启/未连接时返回 false，由调用方决定重试或提示。
 */
object GestureController {
    private const val TAG = "GestureController"
    private val random = Random(System.currentTimeMillis())

    /** 无障碍服务是否可用（用户已开启且已连接）。系统设置中的实际开关状态由 UI 层校验并引导开启。 */
    val isReady: Boolean
        get() = CollectorAccessibilityService.isConnected

    /** 绝对像素单击（调用方传入屏幕实际坐标）。 */
    suspend fun tap(xPx: Float, yPx: Float, jitterPx: Int = 6): Boolean =
        gesture(buildTap(xPx, yPx, jitterPx), 60L)

    /** 从 (x1,y1) 滑动到 (x2,y2)，用于列表滚动。向下滚动 = 手指上滑（dy<0）。 */
    suspend fun swipe(
        x1Px: Float,
        y1Px: Float,
        x2Px: Float,
        y2Px: Float,
        durationMs: Long = 350L
    ): Boolean {
        val path = Path().apply {
            moveTo(x1Px, y1Px)
            lineTo(x2Px, y2Px)
        }
        return gesture(path, durationMs)
    }

    /** 返回键（performGlobalAction），无返回结果。 */
    fun back() {
        val service = CollectorAccessibilityService.instance()
        if (service != null) {
            service.performGlobalAction(AccessibilityService.GLOBAL_ACTION_BACK)
        }
    }

    private fun buildTap(x: Float, y: Float, jitterPx: Int): Path {
        val jx = if (jitterPx > 0) (random.nextFloat() * 2 - 1) * jitterPx else 0f
        val jy = if (jitterPx > 0) (random.nextFloat() * 2 - 1) * jitterPx else 0f
        return Path().apply { moveTo(x + jx, y + jy) }
    }

    private suspend fun gesture(path: Path, durationMs: Long): Boolean =
        withContext(Dispatchers.Main) {
            val service = CollectorAccessibilityService.instance()
            if (service == null) {
                Log.w(TAG, "gesture skipped: accessibility service not connected")
                return@withContext false
            }
            val desc = GestureDescription.Builder()
                .addStroke(GestureDescription.StrokeDescription(path, 0L, durationMs))
                .build()
            suspendCancellableCoroutine { cont ->
                val dispatched = service.dispatchGesture(
                    desc,
                    object : AccessibilityService.GestureResultCallback() {
                        override fun onCompleted(gestureDescription: GestureDescription?) {
                            if (cont.isActive) cont.resume(true)
                        }

                        override fun onCancelled(gestureDescription: GestureDescription?) {
                            if (cont.isActive) cont.resume(false)
                        }
                    },
                    null
                )
                if (!dispatched && cont.isActive) {
                    cont.resume(false)
                }
            }
        }
}
