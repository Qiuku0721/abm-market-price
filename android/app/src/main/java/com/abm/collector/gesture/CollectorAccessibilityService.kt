package com.abm.collector.gesture

import android.accessibilityservice.AccessibilityService
import android.content.Intent
import android.util.Log
import android.view.accessibility.AccessibilityEvent

/**
 * 无障碍服务：为坐标手势注入提供宿主。
 *
 * - 由用户在系统设置中手动开启（Manifest 已声明，config 见 res/xml/accessibility_service_config.xml）；
 * - 仅提供「手势注入」能力（canPerformGestures=true），不读取窗口内容（canRetrieveWindowContent=false）；
 * - 采集流程通过 [GestureController] 调用本服务的实例执行 tap/swipe/back。
 */
class CollectorAccessibilityService : AccessibilityService() {

    companion object {
        private const val TAG = "ABM.Accessibility"

        @Volatile
        private var instanceRef: CollectorAccessibilityService? = null

        /** 服务是否已连接（用户是否已在系统设置中开启） */
        val isConnected: Boolean
            get() = instanceRef != null

        internal fun instance(): CollectorAccessibilityService? = instanceRef
    }

    override fun onServiceConnected() {
        super.onServiceConnected()
        instanceRef = this
        Log.i(TAG, "accessibility service connected")
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) {
        // 不读取窗口内容，无需处理事件
    }

    override fun onInterrupt() {
        // no-op
    }

    override fun onUnbind(intent: Intent?): Boolean {
        instanceRef = null
        Log.i(TAG, "accessibility service disconnected")
        return super.onUnbind(intent)
    }
}
