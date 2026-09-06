package com.abm.collector.pipeline

import android.content.Context
import org.json.JSONArray
import org.json.JSONObject
import java.io.File

/** 清单中的一颗子弹。active=false 时暂停采集。 */
data class BulletItem(
    val name: String,
    val active: Boolean = true
)

/**
 * 子弹清单存储：以 JSON 文件持久化在应用私有目录（filesDir/bullets.json），
 * 供 UI 编辑与采集流程读取。数据量小，读写直接、加锁串行化。
 */
class BulletStore(context: Context) {

    private val file = File(context.filesDir, FILE_NAME)
    private val lock = Any()

    fun load(): List<BulletItem> = synchronized(lock) {
        if (!file.exists()) return@synchronized emptyList()
        runCatching {
            val items = JSONObject(file.readText()).getJSONArray(KEY_ITEMS)
            (0 until items.length()).map { i ->
                val o = items.getJSONObject(i)
                BulletItem(
                    name = o.getString(KEY_NAME),
                    active = o.optBoolean(KEY_ACTIVE, true)
                )
            }
        }.getOrDefault(emptyList())
    }

    fun save(items: List<BulletItem>) = synchronized(lock) {
        val arr = JSONArray()
        items.forEach { item ->
            arr.put(
                JSONObject()
                    .put(KEY_NAME, item.name)
                    .put(KEY_ACTIVE, item.active)
            )
        }
        file.writeText(JSONObject().put(KEY_ITEMS, arr).toString())
    }

    /** 当前启用的清单名集合（采集流程使用）。 */
    fun activeNames(): Set<String> = load().filter { it.active }.map { it.name }.toSet()

    private companion object {
        const val FILE_NAME = "bullets.json"
        const val KEY_ITEMS = "items"
        const val KEY_NAME = "name"
        const val KEY_ACTIVE = "active"
    }
}
