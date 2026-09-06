package com.abm.collector.service

import android.app.Activity
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.IBinder
import android.util.DisplayMetrics
import android.view.WindowManager
import androidx.core.app.NotificationCompat
import androidx.core.app.NotificationManagerCompat
import androidx.core.content.ContextCompat
import com.abm.collector.MainActivity
import com.abm.collector.R
import com.abm.collector.capture.ScreenCapturer
import com.abm.collector.gesture.GestureController
import com.abm.collector.ocr.TextScanner
import com.abm.collector.pipeline.BulletStore
import com.abm.collector.pipeline.LayoutProfile
import com.abm.collector.pipeline.ScanPipeline
import com.abm.collector.upload.PcConfig
import com.abm.collector.upload.UploadQueue
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.cancel
import kotlinx.coroutines.delay
import kotlinx.coroutines.isActive
import kotlinx.coroutines.launch
import java.util.Random

/**
 * 前台采集服务（mediaProjection 类型）：
 *
 * - 由 MainActivity 在拿到 MediaProjection 授权后经 [start] 启动（intent 携带授权结果）；
 * - 组装 ScreenCapturer / TextScanner / ScanPipeline / UploadQueue，启动周期采集循环；
 * - 每轮：flush 上报队列 → 一次全量扫描（runRound）→ 更新通知 → 按配置间隔（±25% 随机抖动防呆）等待；
 * - 前台通知常驻作为「状态入口」，点击回到 MainActivity；
 * - [stop] 停止循环并释放 MediaProjection / 虚拟显示 / OCR 识别器。
 */
class CollectorService : Service() {

    companion object {
        private const val TAG = "CollectorService"
        private const val CHANNEL_ID = "abm_collector"
        private const val NOTIF_ID = 1
        private const val ACTION_START = "com.abm.collector.action.START"
        private const val ACTION_STOP = "com.abm.collector.action.STOP"
        private const val EXTRA_CODE = "extra_result_code"
        private const val EXTRA_DATA = "extra_result_data"

        @Volatile
        var running: Boolean = false
            private set

        @Volatile
        var lastSummary: String = "未开始"
            private set

        /** 启动（带 MediaProjection 授权结果）。 */
        fun start(context: Context, resultCode: Int, data: Intent) {
            val intent = Intent(context, CollectorService::class.java)
                .setAction(ACTION_START)
                .putExtra(EXTRA_CODE, resultCode)
                .putExtra(EXTRA_DATA, data)
            ContextCompat.startForegroundService(context, intent)
        }

        /** 停止。 */
        fun stop(context: Context) {
            context.startService(
                Intent(context, CollectorService::class.java).setAction(ACTION_STOP)
            )
        }
    }

    private val scope = CoroutineScope(SupervisorJob() + Dispatchers.Default)
    private val random = Random(System.currentTimeMillis())

    private lateinit var config: PcConfig
    private var started = false
    private var screenW = 0
    private var screenH = 0

    private var projection: MediaProjection? = null
    private var capturer: ScreenCapturer? = null
    private var scanner: TextScanner? = null
    private var pipeline: ScanPipeline? = null
    private var uploadQueue: UploadQueue? = null

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        config = PcConfig(this)
        createChannel()
    }

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        when (intent?.action) {
            ACTION_START -> {
                if (started) {
                    UiLog.append("服务已在运行，忽略重复启动")
                    return START_NOT_STICKY
                }
                val code = intent.getIntExtra(EXTRA_CODE, Activity.RESULT_CANCELED)
                @Suppress("DEPRECATION")
                val data: Intent? = if (Build.VERSION.SDK_INT >= 33) {
                    intent.getParcelableExtra(EXTRA_DATA, Intent::class.java)
                } else {
                    intent.getParcelableExtra(EXTRA_DATA)
                }
                if (code != Activity.RESULT_OK || data == null) {
                    UiLog.append("启动被取消：缺少屏幕录制授权")
                    stopSelf()
                    return START_NOT_STICKY
                }
                startForegroundCompat()
                setup(code, data)
                started = true
                running = true
                scope.launch { runLoop() }
            }
            ACTION_STOP -> {
                shutdown()
                stopSelf()
            }
        }
        return START_NOT_STICKY
    }

    private fun setup(resultCode: Int, data: Intent) {
        val mpm = getSystemService(MediaProjectionManager::class.java)
        projection = mpm.getMediaProjection(resultCode, data)
        val wm = getSystemService(WindowManager::class.java)
        val metrics = DisplayMetrics().also { wm.defaultDisplay.getRealMetrics(it) }
        screenW = metrics.widthPixels
        screenH = metrics.heightPixels

        val proj = projection ?: run {
            UiLog.append("MediaProjection 创建失败")
            stopSelf()
            return
        }
        val cap = ScreenCapturer(proj, screenW, screenH, metrics.densityDpi).also { it.start() }
        val scan = TextScanner()
        capturer = cap
        scanner = scan

        val store = BulletStore(this)
        val queue = UploadQueue(this, config, scope)
        uploadQueue = queue
        pipeline = ScanPipeline(
            capturer = cap,
            scanner = scan,
            bullets = store,
            onRecord = { record, jpeg -> queue.add(record.copy(snapshotJpeg = jpeg)) },
            log = { UiLog.append(it) }
        )
        UiLog.append("采集服务就绪 ${screenW}x$screenH，无障碍：${GestureController.isReady}")
    }

    private suspend fun runLoop() {
        val pipe = pipeline ?: return
        UiLog.append("== 采集循环开始 ==")
        while (scope.isActive) {
            uploadQueue?.flush()
            if (!GestureController.isReady) {
                UiLog.append("警告：无障碍服务未连接，跳过本轮")
                delay(30_000L)
                continue
            }
            val summary = try {
                pipe.runRound(screenW, screenH)
            } catch (e: CancellationException) {
                throw e
            } catch (e: Exception) {
                UiLog.append("本轮异常：${e.message}")
                null
            }
            if (summary != null) {
                lastSummary = "命中 ${summary.hit.size}，未找到 ${summary.notFound.size}，解析失败 ${summary.parseFailures}"
                UiLog.append(lastSummary)
                updateNotification(lastSummary)
            }
            uploadQueue?.flush()

            // 防呆：采集间隔 ±25% 抖动，避免固定节律
            val base = config.intervalMinutes * 60_000L
            val jitter = (base * 0.25 * random.nextDouble()).toLong()
            val wait = if (random.nextBoolean()) base + jitter else (base - jitter).coerceAtLeast(30_000L)
            UiLog.append("下一轮在 ${wait / 1000}s 后")
            updateNotification("采集中，下一轮 ${wait / 1000}s 后")
            delay(wait)
        }
    }

    private fun shutdown() {
        if (!started && !running) return
        started = false
        running = false
        scope.cancel()
        try {
            capturer?.stop()
            scanner?.close()
        } catch (_: Exception) {
        }
        try {
            projection?.stop()
        } catch (_: Exception) {
        }
        capturer = null
        scanner = null
        pipeline = null
        uploadQueue = null
        projection = null
        stopForeground(STOP_FOREGROUND_REMOVE)
        UiLog.append("采集服务已停止")
    }

    override fun onDestroy() {
        shutdown()
        super.onDestroy()
    }

    // ---------- 前台服务与通知 ----------

    private fun createChannel() {
        val channel = NotificationChannel(
            CHANNEL_ID,
            "采集状态",
            NotificationManager.IMPORTANCE_LOW
        )
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
    }

    private fun baseNotification(text: String): Notification =
        NotificationCompat.Builder(this, CHANNEL_ID)
            .setContentTitle("ABM 价格记录器")
            .setContentText(text)
            .setSmallIcon(R.drawable.ic_launcher)
            .setOngoing(true)
            .setContentIntent(
                PendingIntent.getActivity(
                    this,
                    0,
                    Intent(this, MainActivity::class.java),
                    PendingIntent.FLAG_IMMUTABLE
                )
            )
            .build()

    private fun startForegroundCompat() {
        val notification = baseNotification("启动中…")
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIF_ID, notification, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
        } else {
            startForeground(NOTIF_ID, notification)
        }
    }

    private fun updateNotification(text: String) {
        if (NotificationManagerCompat.from(this).areNotificationsEnabled()) {
            NotificationManagerCompat.from(this).notify(NOTIF_ID, baseNotification(text))
        }
    }
}
