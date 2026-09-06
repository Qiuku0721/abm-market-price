package com.abm.collector

import android.os.Bundle
import androidx.appcompat.app.AppCompatActivity

/**
 * 主界面：骨架阶段仅展示占位内容；配置项（PC IP / 清单 / 权限引导 /
 * 开始停止 / 状态日志）随功能模块在后续步骤接入，见 service 与 pipeline 包。
 */
class MainActivity : AppCompatActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
    }
}
