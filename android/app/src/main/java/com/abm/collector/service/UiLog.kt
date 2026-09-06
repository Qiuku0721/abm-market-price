package com.abm.collector.service

import java.time.LocalTime
import java.time.format.DateTimeFormatter

/**
 * 进程内日志环形缓冲：CollectorService 写入，MainActivity 轮询展示（最多 500 行）。
 */
object UiLog {
    private const val MAX = 500
    private val lock = Any()
    private val lines = ArrayDeque<String>()
    private val fmt = DateTimeFormatter.ofPattern("HH:mm:ss")

    fun append(msg: String) {
        val stamp = LocalTime.now().format(fmt)
        synchronized(lock) {
            lines.addLast("$stamp  $msg")
            while (lines.size > MAX) lines.removeFirst()
        }
    }

    fun snapshot(): List<String> = synchronized(lock) { lines.toList() }

    fun clear() = synchronized(lock) { lines.clear() }
}
