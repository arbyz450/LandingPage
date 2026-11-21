package com.crstockfish.app

import android.accessibilityservice.AccessibilityService
import android.accessibilityservice.GestureDescription
import android.graphics.Path
import android.os.Handler
import android.os.Looper
import android.view.accessibility.AccessibilityEvent

/**
 * Performs the two taps of a play (card slot, then arena tile) with
 * dispatchGesture. Enabled by the user under Settings > Accessibility.
 */
class TapService : AccessibilityService() {
    private val handler = Handler(Looper.getMainLooper())

    override fun onServiceConnected() {
        instance = this
        AppState.status.postValue("tap service connected")
    }

    override fun onAccessibilityEvent(event: AccessibilityEvent?) = Unit
    override fun onInterrupt() = Unit

    override fun onDestroy() {
        if (instance === this) instance = null
        super.onDestroy()
    }

    fun tap(x: Int, y: Int, durationMs: Long = 60L): Boolean {
        val path = Path().apply { moveTo(x.toFloat(), y.toFloat()) }
        val stroke = GestureDescription.StrokeDescription(path, 0L, durationMs)
        val gesture = GestureDescription.Builder().addStroke(stroke).build()
        return dispatchGesture(gesture, null, null)
    }

    /** Card slot first, arena tile ~90 ms later. */
    fun play(slotX: Int, slotY: Int, tileX: Int, tileY: Int) {
        tap(slotX, slotY)
        handler.postDelayed({ tap(tileX, tileY) }, 90L)
    }

    companion object {
        @Volatile var instance: TapService? = null
    }
}
