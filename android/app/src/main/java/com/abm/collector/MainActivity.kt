package com.abm.collector

import android.Manifest
import android.accessibilityservice.AccessibilityServiceInfo
import android.content.Intent
import android.content.pm.PackageManager
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.view.accessibility.AccessibilityManager
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import com.abm.collector.databinding.ActivityMainBinding
import com.abm.collector.gesture.CollectorAccessibilityService
import com.abm.collector.gesture.GestureController
import com.abm.collector.pipeline.BulletItem
import com.abm.collector.pipeline.BulletStore
import com.abm.collector.service.CollectorService
import com.abm.collector.service.UiLog
import com.abm.collector.upload.PcConfig

/**
 * 主界面：电脑端地址 / 采集周期 / 子弹清单编辑 + 开始/停止 + 权限引导 + 运行日志。
 *
 * 开始流程：校验无障碍服务已开启 → 保存输入 → 请求 MediaProjection 授权 →
 * 授权结果交由 CollectorService 启动周期采集（前台服务常驻）。
 */
class MainActivity : AppCompatActivity() {

    private lateinit var binding: ActivityMainBinding
    private lateinit var config: PcConfig
    private lateinit var store: BulletStore

    private val handler = Handler(Looper.getMainLooper())
    private val refreshTick = object : Runnable {
        override fun run() {
            refreshStatus()
            handler.postDelayed(this, 1000L)
        }
    }

    private val projectionLauncher =
        registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
            val data = result.data
            if (result.resultCode == RESULT_OK && data != null) {
                saveInputs()
                CollectorService.start(this, result.resultCode, data)
                toast("采集服务启动中…")
            } else {
                toast("未授予屏幕录制权限，无法开始")
            }
        }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        binding = ActivityMainBinding.inflate(layoutInflater)
        setContentView(binding.root)
        config = PcConfig(this)
        store = BulletStore(this)

        loadInputs()
        requestNotificationPermissionIfNeeded()

        binding.btnSaveBullets.setOnClickListener {
            saveBullets()
            toast("清单已保存（共 ${store.load().size} 项）")
        }
        binding.btnStart.setOnClickListener { onStartClicked() }
        binding.btnStop.setOnClickListener {
            CollectorService.stop(this)
            toast("已请求停止")
        }
        handler.post(refreshTick)
    }

    override fun onDestroy() {
        handler.removeCallbacks(refreshTick)
        super.onDestroy()
    }

    // ---------- 界面填充与读取 ----------

    private fun loadInputs() {
        binding.etPcUrl.setText(config.baseUrl)
        binding.etInterval.setText(config.intervalMinutes.toString())
        binding.etBullets.setText(store.load().joinToString("\n") { it.name })
    }

    private fun saveInputs() {
        config.baseUrl = binding.etPcUrl.text?.toString().orEmpty()
        config.intervalMinutes = binding.etInterval.text?.toString()?.toIntOrNull() ?: PcConfig.DEFAULT_INTERVAL_MIN
        saveBullets()
    }

    /** 多行输入 → 逐行解析去重 → 写回清单（默认全部启用）。 */
    private fun saveBullets() {
        val names = binding.etBullets.text?.toString().orEmpty()
            .lineSequence()
            .map { it.trim() }
            .filter { it.isNotEmpty() }
            .distinct()
            .toList()
        store.save(names.map { BulletItem(name = it, active = true) })
    }

    // ---------- 交互 ----------

    private fun onStartClicked() {
        saveInputs()
        if (!accessibilityServiceEnabled()) {
            toast("请先在系统设置中开启「ABM Collector 手势服务」")
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            return
        }
        // 系统已开启，但本进程内的服务连接可能尚未建立（开启后立刻返回 App 常见）
        if (!GestureController.isReady) {
            toast("无障碍服务已开启，等待连接…")
            waitForGestureReady(0)
            return
        }
        launchProjection()
    }

    /** 系统已开启但服务未连接时，短暂轮询等待 onServiceConnected。 */
    private fun waitForGestureReady(attempt: Int) {
        if (GestureController.isReady) {
            launchProjection()
            return
        }
        if (attempt >= GESTURE_WAIT_TRIES) {
            toast("服务连接超时：请完全退出 App 后重新打开一次")
            return
        }
        handler.postDelayed({ waitForGestureReady(attempt + 1) }, GESTURE_WAIT_INTERVAL_MS)
    }

    private fun launchProjection() {
        saveInputs()
        val mpm = getSystemService(MediaProjectionManager::class.java)
        projectionLauncher.launch(mpm.createScreenCaptureIntent())
    }

    private fun refreshStatus() {
        val acc = when {
            accessibilityServiceEnabled() && GestureController.isReady -> "无障碍：已连接"
            accessibilityServiceEnabled() -> "无障碍：已开启（连接中…）"
            else -> "无障碍：未开启"
        }
        binding.tvStatus.text = if (CollectorService.running) {
            "运行中：${CollectorService.lastSummary}\n$acc"
        } else {
            "服务未运行｜$acc"
        }
        val log = UiLog.snapshot().joinToString("\n")
        binding.tvLog.text = if (log.length > MAX_LOG_CHARS) log.takeLast(MAX_LOG_CHARS) else log
    }

    /**
     * 检测无障碍服务是否已开启。
     * 优先用系统 API 直接查询已启用服务列表（兼容澎湃/MIUI 等 ROM 的存储格式差异），
     * 字符串比对（兼容短/长类名两种写法）作为兜底。
     */
    private fun accessibilityServiceEnabled(): Boolean {
        val am = getSystemService(AccessibilityManager::class.java)
        if (am != null) {
            val fullName = CollectorAccessibilityService::class.java.name
            val enabled = am.getEnabledAccessibilityServiceList(AccessibilityServiceInfo.FEEDBACK_ALL_MASK)
            if (enabled.any { info ->
                    val si = info.resolveInfo?.serviceInfo
                    si != null && si.packageName == packageName && si.name == fullName
                }
            ) {
                return true
            }
        }
        val raw = Settings.Secure.getString(
            contentResolver,
            Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
        ) ?: return false
        val shortName = "$packageName/${CollectorAccessibilityService::class.java.simpleName}"
        val fullName = "$packageName/${CollectorAccessibilityService::class.java.name}"
        return raw.split(':').any {
            val v = it.trim()
            v.equals(shortName, ignoreCase = true) ||
                v.equals(fullName, ignoreCase = true) ||
                v.startsWith("$shortName;") ||
                v.startsWith("$fullName;")
        }
    }

    private fun requestNotificationPermissionIfNeeded() {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU &&
            ActivityCompat.checkSelfPermission(this, Manifest.permission.POST_NOTIFICATIONS) !=
            PackageManager.PERMISSION_GRANTED
        ) {
            requestPermissions(arrayOf(Manifest.permission.POST_NOTIFICATIONS), REQ_NOTIFICATION)
        }
    }

    private fun toast(msg: String) {
        Toast.makeText(this, msg, Toast.LENGTH_SHORT).show()
    }

    private companion object {
        const val REQ_NOTIFICATION = 100
        const val MAX_LOG_CHARS = 20_000
        const val GESTURE_WAIT_TRIES = 20
        const val GESTURE_WAIT_INTERVAL_MS = 300L
    }
}
