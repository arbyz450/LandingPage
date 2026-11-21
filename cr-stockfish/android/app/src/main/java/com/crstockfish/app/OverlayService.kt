package com.crstockfish.app

import android.app.Service
import android.content.Context
import android.content.Intent
import android.graphics.PixelFormat
import android.os.Build
import android.os.IBinder
import android.view.Gravity
import android.view.LayoutInflater
import android.view.MotionEvent
import android.view.View
import android.view.WindowManager
import android.widget.Button
import android.widget.EditText
import android.widget.TextView
import androidx.lifecycle.Observer

/** Draggable floating panel: eval + top plays + a command box (o <card>, d ..., r ...). */
class OverlayService : Service() {
    private var wm: WindowManager? = null
    private var view: View? = null
    private var params: WindowManager.LayoutParams? = null
    private val textObserver = Observer<String> { t -> view?.findViewById<TextView>(R.id.overlayText)?.text = shorten(t) }
    private val playObserver = Observer<String> { p -> view?.findViewById<TextView>(R.id.overlayHeader)?.text = if (p.isEmpty()) "CR Stockfish  (drag me)" else p }

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onCreate() {
        super.onCreate()
        wm = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        val type = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O)
            WindowManager.LayoutParams.TYPE_APPLICATION_OVERLAY else @Suppress("DEPRECATION") WindowManager.LayoutParams.TYPE_PHONE
        params = WindowManager.LayoutParams(
            WindowManager.LayoutParams.WRAP_CONTENT, WindowManager.LayoutParams.WRAP_CONTENT, type,
            WindowManager.LayoutParams.FLAG_NOT_TOUCH_MODAL or WindowManager.LayoutParams.FLAG_WATCH_OUTSIDE_TOUCH,
            PixelFormat.TRANSLUCENT
        ).apply { gravity = Gravity.TOP or Gravity.START; x = 16; y = 120 }
        val v = LayoutInflater.from(this).inflate(R.layout.overlay, null)
        view = v
        v.findViewById<View>(R.id.overlayHeader).setOnTouchListener(DragListener())
        val cmd = v.findViewById<EditText>(R.id.overlayCmd)
        v.findViewById<Button>(R.id.overlaySend).setOnClickListener {
            val line = cmd.text.toString()
            if (line.isNotBlank()) {
                val reply = Bridge.command(line)
                AppState.lastPlay.postValue(reply.take(60))
                cmd.setText("")
            }
        }
        try {
            wm?.addView(v, params)
        } catch (t: Throwable) {
            AppState.status.postValue("overlay permission missing: ${t.message}")
            stopSelf()
            return
        }
        AppState.lastText.observeForever(textObserver)
        AppState.lastPlay.observeForever(playObserver)
    }

    private fun shorten(t: String): String {
        // keep the header lines and the top plays; drop the long notes block
        val lines = t.lines()
        val cut = lines.indexOfFirst { it.startsWith("Opp hand") || it.startsWith("Technique") || it.startsWith("Opp archetype") }
        return (if (cut > 0) lines.subList(0, cut) else lines).joinToString("\n").trim()
    }

    override fun onDestroy() {
        AppState.lastText.removeObserver(textObserver)
        AppState.lastPlay.removeObserver(playObserver)
        view?.let { runCatching { wm?.removeView(it) } }
        super.onDestroy()
    }

    private inner class DragListener : View.OnTouchListener {
        private var startX = 0
        private var startY = 0
        private var touchX = 0f
        private var touchY = 0f
        override fun onTouch(v: View, e: MotionEvent): Boolean {
            val p = params ?: return false
            when (e.action) {
                MotionEvent.ACTION_DOWN -> { startX = p.x; startY = p.y; touchX = e.rawX; touchY = e.rawY; return true }
                MotionEvent.ACTION_MOVE -> {
                    p.x = startX + (e.rawX - touchX).toInt()
                    p.y = startY + (e.rawY - touchY).toInt()
                    wm?.updateViewLayout(view, p)
                    return true
                }
            }
            return false
        }
    }
}
