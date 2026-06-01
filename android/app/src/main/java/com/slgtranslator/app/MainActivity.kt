package com.slgtranslator.app

import android.os.Bundle
import com.getcapacitor.BridgeActivity

class MainActivity : BridgeActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        // 必须在 super.onCreate() 之前注册插件，否则 bridge 初始化后不会再加载
        registerPlugin(FileManagerPlugin::class.java)
        super.onCreate(savedInstanceState)
    }
}