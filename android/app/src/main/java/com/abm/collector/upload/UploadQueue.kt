package com.abm.collector.upload

import android.content.Context
import android.util.Log
import com.abm.collector.pipeline.PriceRecord
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.SupervisorJob
import kotlinx.coroutines.launch
import kotlinx.coroutines.sync.Mutex
import kotlinx.coroutines.sync.withLock
import kotlinx.coroutines.withContext
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.OkHttpClient
import okhttp3.Request
import okhttp3.RequestBody.Companion.toRequestBody
import org.json.JSONObject
import java.io.File
import java.util.concurrent.TimeUnit

/**
 * 上报模块：把采集记录先持久化到本地文件队列（pending/），再尽力上报电脑端。
 *
 * - [add]：写入队列文件（记录 .json + 可选快照 .jpg），随后触发 [flush]；
 * - [flush]：按文件名序逐条发送：先 POST /snapshots（若带图）取 snapshot_id，
 *   再 POST /records；网络类失败中断（保序，剩余条目下次再试）；不可重试错误（4xx 校验类）
 *   丢弃并记日志；成功后删除对应文件 —— 进程被杀也不丢数据；
 * - 由采集调度（CollectorService）周期性调用 [flush] 兜底重传。
 *
 * 字段与协议对齐：见 docs/PROTOCOL.md §3/§4。
 */
class UploadQueue(
    context: Context,
    private val config: PcConfig,
    private val scope: CoroutineScope = CoroutineScope(SupervisorJob() + Dispatchers.IO)
) {
    private val tag = "UploadQueue"
    private val pendingDir = File(context.filesDir, "pending").apply { mkdirs() }
    private val client = OkHttpClient.Builder()
        .connectTimeout(5, TimeUnit.SECONDS)
        .readTimeout(15, TimeUnit.SECONDS)
        .build()
    private val mutex = Mutex()
    private val jsonType = "application/json; charset=utf-8".toMediaType()
    private var counter = 0L

    /** 入队一条记录（含可选 JPEG 缩略图）。 */
    fun add(record: PriceRecord) {
        val id = "p${System.currentTimeMillis()}_${counter++}"
        try {
            val json = JSONObject()
                .put("bullet_name", record.bulletName)
                .put("price", record.price)
                .put("captured_at", record.capturedAt)
                .put("source", record.source)
            if (record.snapshotJpeg != null) {
                json.put("has_snapshot", true)
                File(pendingDir, "$id.jpg").writeBytes(record.snapshotJpeg)
            }
            File(pendingDir, "$id.json").writeText(json.toString())
            Log.i(tag, "enqueued ${record.bulletName} id=$id")
        } catch (e: Exception) {
            Log.w(tag, "enqueue failed", e)
            return
        }
        scope.launch { flush() }
    }

    /** 尽力发送队列中所有待发条目。失败中断保序。可在任意线程调用。 */
    suspend fun flush() = withContext(Dispatchers.IO) {
        mutex.withLock {
            val files = pendingDir.listFiles { f -> f.extension == "json" }
                ?.sortedBy { it.name }
                ?: return@withLock
            for (jsonFile in files) {
                val id = jsonFile.nameWithoutExtension
                val jpgFile = File(pendingDir, "$id.jpg")
                val outcome = try {
                    send(jsonFile, jpgFile)
                } catch (e: Exception) {
                    Log.w(tag, "send error", e)
                    Outcome.RETRY
                }
                when (outcome) {
                    Outcome.SUCCESS, Outcome.DROP -> {
                        jsonFile.delete()
                        jpgFile.delete()
                        Log.i(tag, "sent/dropped $id ($outcome)")
                    }
                    Outcome.RETRY -> {
                        Log.w(tag, "retry later: $id")
                        break // 保序：剩余条目下次 flush
                    }
                }
            }
        }
    }

    private fun send(jsonFile: File, jpgFile: File): Outcome {
        val meta = JSONObject(jsonFile.readText())
        val name = meta.optString("bullet_name")
        val price = meta.optInt("price", -1)
        val capturedAt = meta.optString("captured_at")
        val source = meta.optString("source", "list_scan")

        if (name.isEmpty() || price <= 0) {
            Log.w(tag, "corrupt entry ${jsonFile.name}, drop")
            return Outcome.DROP
        }

        var snapshotId: String? = null
        if (meta.optBoolean("has_snapshot", false) && jpgFile.exists()) {
            snapshotId = uploadSnapshot(jpgFile, name, capturedAt) ?: return Outcome.RETRY
        }

        val body = JSONObject()
            .put("device_id", config.deviceId)
            .put(
                "records",
                org.json.JSONArray().put(
                    JSONObject()
                        .put("bullet_name", name)
                        .put("price", price)
                        .put("currency", "Koen")
                        .put("market_type", "market")
                        .put("captured_at", capturedAt)
                        .put("source", source)
                        .apply { snapshotId?.let { put("snapshot_id", it) } }
                )
            )

        val request = Request.Builder()
            .url("${config.baseUrl}/records")
            .post(body.toString().toRequestBody(jsonType))
            .addHeader("X-ABM-Protocol", "1")
            .build()

        client.newCall(request).execute().use { resp ->
            val code = resp.code
            val respBody = resp.body?.string().orEmpty()
            if (code in 200..299) {
                Log.i(tag, "records accepted: $respBody")
                return Outcome.SUCCESS
            }
            if (code in 400..499 && code != 429) {
                Log.w(tag, "records rejected($code): $respBody")
                return Outcome.DROP
            }
            Log.w(tag, "records retry($code)")
            return Outcome.RETRY
        }
    }

    /** 上传快照，成功返回服务器落盘的 snapshot_id（由本端生成的幂等文件名）。 */
    private fun uploadSnapshot(jpg: File, bulletName: String, capturedAt: String): String? {
        val snapshotId = "snap_${config.deviceId.take(8)}_${System.currentTimeMillis()}.jpg"
        val meta = JSONObject()
            .put("device_id", config.deviceId)
            .put("kind", "row")
            .put("bullet_name", bulletName)
            .put("captured_at", capturedAt)
        val multipart = MultipartBody.Builder()
            .setType(MultipartBody.FORM)
            .addFormDataPart("meta", meta.toString())
            .addFormDataPart("file", snapshotId, jpg.readBytes().toRequestBody("image/jpeg".toMediaType()))
            .build()
        val request = Request.Builder()
            .url("${config.baseUrl}/snapshots")
            .post(multipart)
            .addHeader("X-ABM-Protocol", "1")
            .build()
        client.newCall(request).execute().use { resp ->
            if (resp.code in 200..299) return snapshotId
            Log.w(tag, "snapshot upload failed(${resp.code})")
            return null
        }
    }

    private enum class Outcome { SUCCESS, RETRY, DROP }
}
