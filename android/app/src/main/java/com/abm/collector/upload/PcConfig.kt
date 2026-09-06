package com.abm.collector.upload

import android.content.Context
import java.util.UUID

/**
 * 本机采集配置（SharedPreferences 持久化）：
 * - [baseUrl] 电脑端地址（如 http://192.168.1.100:8600）；
 * - [deviceId] 首次生成并固定的 UUID（协议去重/多设备区分用）；
 * - [intervalMinutes] 全量采集周期（分钟）。
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

    var intervalMinutes: Int
        get() = sp.getInt(KEY_INTERVAL_MIN, DEFAULT_INTERVAL_MIN)
        set(value) {
            sp.edit().putInt(KEY_INTERVAL_MIN, value.coerceIn(1, 1440)).apply()
        }

    companion object {
        /** USB 有线传输（adb reverse）时固定填 127.0.0.1:8600；Wi-Fi 局域网模式改为电脑 IP。 */
        const val DEFAULT_BASE_URL = "http://127.0.0.1:8600"
        const val DEFAULT_INTERVAL_MIN = 5
        private const val PREFS = "abm_collector_config"
        private const val KEY_BASE_URL = "base_url"
        private const val KEY_DEVICE_ID = "device_id"
        private const val KEY_INTERVAL_MIN = "interval_min"
    }
}
