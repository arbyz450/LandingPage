package com.crstockfish.app

import android.app.Notification
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.ServiceInfo
import android.graphics.PixelFormat
import android.hardware.display.DisplayManager
import android.hardware.display.VirtualDisplay
import android.media.ImageReader
import android.media.projection.MediaProjection
import android.media.projection.MediaProjectionManager
import android.os.Build
import android.os.Handler
import android.os.HandlerThread
import android.os.IBinder
import android.util.DisplayMetrics
import android.view.WindowManager
import androidx.core.app.NotificationCompat

/**
 * Foreground service: MediaProjection -> ImageReader at ~3 fps, downscaled to
 * 540 px wide, handed to the Python engine; plays dispatched to TapService.
 */
class CaptureService : Service() {
    private var projection: MediaProjection? = null
    private var display: VirtualDisplay? = null
    private var reader: ImageReader? = null
    private var thread: HandlerThread? = null
    private var handler: Handler? = null
    private var screenW = 1080
    private var screenH = 2400
    private var capW = 540
    private var capH = 1200
    private var lastStep = 0L

    override fun onBind(intent: Intent?): IBinder? = null

    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        if (intent?.action == ACTION_STOP) {
            stopSelf()
            return START_NOT_STICKY
        }
        val code = intent?.getIntExtra(EXTRA_CODE, 0) ?: 0
        val data: Intent? = intent?.getParcelableExtra(EXTRA_DATA)
        if (code == 0 || data == null) {
            stopSelf()
            return START_NOT_STICKY
        }
        startInForeground()
        measureScreen()
        val mgr = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
        projection = mgr.getMediaProjection(code, data)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.UPSIDE_DOWN_CAKE) {
            projection?.registerCallback(object : MediaProjection.Callback() {
                override fun onStop() { stopSelf() }
            }, null)
        }
        startCapture()
        AppState.capturing = true
        AppState.status.postValue("capturing ${capW}x${capH}")
        startService(Intent(this, OverlayService::class.java))
        return START_STICKY
    }

    private fun startInForeground() {
        val pi = PendingIntent.getActivity(
            this, 0, Intent(this, MainActivity::class.java),
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
        val notif: Notification = NotificationCompat.Builder(this, CrApp.CHANNEL_ID)
            .setContentTitle(getString(R.string.notif_title))
            .setContentText(getString(R.string.notif_text))
            .setSmallIcon(android.R.drawable.ic_menu_view)
            .setContentIntent(pi)
            .setOngoing(true)
            .build()
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            startForeground(NOTIF_ID, notif, ServiceInfo.FOREGROUND_SERVICE_TYPE_MEDIA_PROJECTION)
        } else {
            startForeground(NOTIF_ID, notif)
        }
    }

    @Suppress("DEPRECATION")
    private fun measureScreen() {
        val wm = getSystemService(Context.WINDOW_SERVICE) as WindowManager
        val dm = DisplayMetrics()
        wm.defaultDisplay.getRealMetrics(dm)
        screenW = dm.widthPixels
        screenH = dm.heightPixels
        capW = 540
        capH = (screenH.toLong() * capW / screenW).toInt().coerceAtLeast(2)
        Bridge.setConfig(AppState.minScore, 1.2f, screenW, screenH)
    }

    private fun startCapture() {
        thread = HandlerThread("crsf-capture").also { it.start() }
        handler = Handler(thread!!.looper)
        reader = ImageReader.newInstance(capW, capH, PixelFormat.RGBA_8888, 2)
        display = projection?.createVirtualDisplay(
            "crsf", capW, capH, resources.displayMetrics.densityDpi,
            DisplayManager.VIRTUAL_DISPLAY_FLAG_AUTO_MIRROR, reader!!.surface, null, handler
        )
        reader?.setOnImageAvailableListener({ r ->
            val img = r.acquireLatestImage() ?: return@setOnImageAvailableListener
            try {
                val now = System.currentTimeMillis()
                if (now - lastStep < 330L) return@try          // ~3 fps
                lastStep = now
                val plane = img.planes[0]
                val rowStride = plane.rowStride
                val buf = plane.buffer
                val bytes = ByteArray(buf.remaining())
                buf.get(bytes)
                val res = Bridge.step(bytes, img.width, img.height, rowStride, AppState.armed) ?: return@try
                AppState.lastText.postValue(res.optString("text"))
                val play = res.optJSONObject("play")
                if (play != null) {
                    val desc = "${play.optString("text")} [${"%.1f".format(play.optDouble("score"))}]"
                    if (AppState.dryRun) {
                        AppState.lastPlay.postValue("[dry] $desc")
                    } else {
                        val svc = TapService.instance
                        if (svc == null) {
                            AppState.lastPlay.postValue("tap service not enabled: $desc")
                        } else {
                            svc.play(play.optInt("slot_px"), play.optInt("slot_py"), play.optInt("px"), play.optInt("py"))
                            AppState.lastPlay.postValue("PLAYED $desc")
                        }
                    }
                }
            } finally {
                img.close()
            }
        }, handler)
    }

    override fun onDestroy() {
        AppState.capturing = false
        AppState.status.postValue("stopped")
        display?.release()
        reader?.close()
        projection?.stop()
        thread?.quitSafely()
        stopService(Intent(this, OverlayService::class.java))
        super.onDestroy()
    }

    companion object {
        const val EXTRA_CODE = "code"
        const val EXTRA_DATA = "data"
        const val ACTION_STOP = "com.crstockfish.app.STOP"
        private const val NOTIF_ID = 42
    }
}
