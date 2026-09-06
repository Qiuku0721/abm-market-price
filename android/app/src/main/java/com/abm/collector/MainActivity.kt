package com.abm.collector

import android.Manifest
import android.content.Intent
import android.content.pm.PackageManager
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.provider.Settings
import android.widget.Toast
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import androidx.core.app.ActivityCompat
import com.abm.collector.databinding.ActivityMainBinding
import com.abm.collector.gesture.CollectorAccessibilityService
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
        if (!accessibilityServiceEnabled()) {
            toast("请先在系统设置中开启「ABM Collector 手势服务」")
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
            return
        }
        saveInputs()
        val mpm = getSystemService(MediaProjectionManager::class.java)
        projectionLauncher.launch(mpm.createScreenCaptureIntent())
    }

    private fun refreshStatus() {
        binding.tvStatus.text = if (CollectorService.running) {
            "运行中：${CollectorService.lastSummary}"
        } else {
            "服务未运行"
        }
        val log = UiLog.snapshot().joinToString("\n")
        binding.tvLog.text = if (log.length > MAX_LOG_CHARS) log.takeLast(MAX_LOG_CHARS) else log
    }

    private fun accessibilityServiceEnabled(): Boolean {
        val enabled = Settings.Secure.getString(
            contentResolver,
            Settings.Secure.ENABLED_ACCESSIBILITY_SERVICES
        ) ?: return false
        val expected = "$packageName/${CollectorAccessibilityService::class.java.simpleName}"
        return enabled.split(':').any { it.equals(expected, ignoreCase = true) }
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
    }
}
