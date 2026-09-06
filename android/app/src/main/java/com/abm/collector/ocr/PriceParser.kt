package com.abm.collector.ocr

/**
 * OCR 文本清洗与价格解析工具。
 *
 * 用途：
 * - [normalize] 归一化文本（全角空白/全角数字 → 半角）；
 * - [extractNumbers] 提取片段内全部数字；
 * - [parsePrice] 从「价格格」片段解析价格：取最后一段数字（价格通常位于单元格右侧/末尾）。
 *
 * 重要：价格片段应在图像上先做区域裁剪（只框出价格单元格），
 * 避免把名称里的型号数字（如 “M80 5.56x45”）误解析为价格。
 */
object PriceParser {

    private val digits = Regex("\\d+")

    /** 全角空白/数字转半角，并去除首尾空白。 */
    fun normalize(raw: String): String {
        var s = raw.replace('\u3000', ' ') // 全角空格
        s = s.map { c ->
            if (c in '\uFF10'..'\uFF19') (c.code - 0xFF10 + 0x30).toChar() else c
        }.joinToString("")
        return s.trim()
    }

    /** 提取文本中全部正整数（过滤 0）。 */
    fun extractNumbers(text: String): List<Int> =
        digits.findAll(text)
            .mapNotNull { it.value.toIntOrNull() }
            .filter { it > 0 }
            .toList()

    /**
     * 解析价格：返回片段中最后一段数字；无数字返回 null。
     * 例："3,200" → 3200；"320" → 320；"售价 320 科恩币" → 320。
     */
    fun parsePrice(snippet: String): Int? {
        val numbers = extractNumbers(normalize(snippet))
        return numbers.lastOrNull()
    }

    /** 片段是否含数字（可用于粗筛「价格行」）。 */
    fun containsNumber(text: String): Boolean = extractNumbers(text).isNotEmpty()
}
