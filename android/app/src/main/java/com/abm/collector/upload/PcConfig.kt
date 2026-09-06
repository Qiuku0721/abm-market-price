package com.abm.collector.upload

import android.content.Context
import java.util.UUID

/**
 * 本机采集配置（SharedPreferences 持久化）：
 * - [baseUrl] 电脑端地址：USB 模式 http://127.0.0.1:8600（adb reverse）；Wi-Fi 模式填电脑 IP；
 * - [deviceId] 首次生成并固定的 UUID（协议去重/多设备区分用）；
 * - [intervalSeconds] 全量采集周期（秒，>= [MIN_INTERVAL_SEC]）；
 * - [navTapsText] 每轮扫描前先执行的「导航点击」序列（用于点进市场/子弹分类等），
 *   每行两个归一化坐标 "x,y"（0~1），可为空。
 */
class PcConfig(context: Context) {

    private val sp = context.getSharedPreferences(PREFS, Context.MODE_PRIVATE)

    var baseUrl: String
        get() = sp.getString(KEY_BASE_URL, DEFAULT_BASE_URL) ?: DEFAULT_BASE_URL
        set(value) {
            val cleaned = value.trim().trimEnd('/')
            sp.edit().putString(KEY_BASE_URL, cleaned).apply()
        }

    val deviceId: String by lazy {
        sp.getString(KEY_DEVICE_ID, null) ?: UUID.randomUUID().toString().also {
            sp.edit().putString(KEY_DEVICE_ID, it).apply()
        }
    }

    /** 采集周期（秒），范围 [MIN_INTERVAL_SEC, 86400]。 */
    var intervalSeconds: Int
        get() = sp.getInt(KEY_INTERVAL_SEC, DEFAULT_INTERVAL_SEC)
        set(value) {
            sp.edit().putInt(KEY_INTERVAL_SEC, value.coerceIn(MIN_INTERVAL_SEC, 86400)).apply()
        }

    /** 导航点击序列原始文本（每行 "x,y" 归一化 0~1，可为空）。 */
    var navTapsText: String
        get() = sp.getString(KEY_NAV_TAPS, "") ?: ""
        set(value) {
            sp.edit().putString(KEY_NAV_TAPS, value).apply()
        }

    /** 解析导航点击序列为归一化坐标列表；无效行忽略。 */
    fun parseNavTaps(): List<Pair<Float, Float>> =
        navTapsText.lineSequence()
            .map { it.trim() }
            .filter { it.isNotEmpty() }
            .mapNotNull { line ->
                val parts = line.split(',', '，', ' ', '\t').filter { it.isNotBlank() }
                if (parts.size >= 2) {
                    val x = parts[0].toFloatOrNull()?.coerceIn(0f, 1f)
                    val y = parts[1].toFloatOrNull()?.coerceIn(0f, 1f)
                    if (x != null && y != null) x to y else null
                } else {
                    null
                }
            }
            .toList()

    companion object {
        /** USB 有线传输（adb reverse）时固定填 127.0.0.1:8600；Wi-Fi 局域网模式改为电脑 IP。 */
        const val DEFAULT_BASE_URL = "http://127.0.0.1:8600"
        const val DEFAULT_INTERVAL_SEC = 60
        const val MIN_INTERVAL_SEC = 5
        private const val PREFS = "abm_collector_config"
        private const val KEY_BASE_URL = "base_url"
        private const val KEY_DEVICE_ID = "device_id"
        private const val KEY_INTERVAL_SEC = "interval_sec"
        private const val KEY_NAV_TAPS = "nav_taps"
    }
}
