package com.abm.collector.pipeline

/**
 * 市场界面布局参数 —— 真机调试时需按实际分辨率/界面微调。
 *
 * 全部为归一化坐标（∈[0,1] 相对屏幕宽高），屏幕为竖屏、市场列表占中上部。
 * 价格通常显示在每行右侧，因此价格格取「行右侧 + 屏幕右缘」区域。
 */
data class LayoutProfile(
    /** 向下滚动列表时，手指滑动起点 y（列表下侧） */
    val scrollFromY: Float = 0.72f,
    /** 向下滚动列表时，手指滑动终点 y（列表上侧） */
    val scrollToY: Float = 0.30f,
    /** 滚动手势 x 中心 */
    val scrollX: Float = 0.5f,
    /** 回列表顶部时向上滑动（手指下移）的次数 */
    val scrollToTopSwipes: Int = 6,
    /** 价格格区域左边界 x（行内右侧起） */
    val priceZoneLeftX: Float = 0.52f,
    /** 名称行 bbox 上下扩展像素（容纳行内文字误差） */
    val rowPaddingPx: Int = 22,
    /** 是否滚动完整屏的比例 */
    val scrollDistanceRatio: Float = 0.42f
) {
    companion object {
        val DEFAULT = LayoutProfile()
    }
}
