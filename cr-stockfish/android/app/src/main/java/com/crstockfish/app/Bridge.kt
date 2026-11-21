package com.crstockfish.app

import android.content.Context
import android.util.DisplayMetrics
import android.util.Log
import com.chaquo.python.PyObject
import com.chaquo.python.Python
import org.json.JSONObject
import java.io.File

/** Thin wrapper around the Python module app/src/main/python/crsf_android.py. */
object Bridge {
    private const val TAG = "CrBridge"
    private var mod: PyObject? = null
    @Volatile var ready: Boolean = false
        private set

    fun init(ctx: Context) {
        try {
            val py = Python.getInstance()
            val m = py.getModule("crsf_android")
            val templates = File(ctx.filesDir, "templates/cards").apply { mkdirs() }
            val units = File(ctx.filesDir, "templates/units").apply { mkdirs() }
            val dm: DisplayMetrics = ctx.resources.displayMetrics
            val res = m.callAttr("init", templates.absolutePath, units.absolutePath, "", dm.widthPixels, dm.heightPixels).toString()
            val json = JSONObject(res)
            ready = json.optBoolean("ok", false)
            mod = m
            AppState.status.postValue(if (ready) "engine ready (${json.optInt("templates")} card templates)" else "engine init failed: ${json.optString("error")}")
            Log.i(TAG, res)
        } catch (t: Throwable) {
            Log.e(TAG, "init failed", t)
            AppState.status.postValue("engine init failed: ${t.message}")
        }
    }

    fun setConfig(minScore: Float, minMargin: Float, screenW: Int, screenH: Int) {
        mod?.callAttr("set_config", minScore, minMargin, screenW, screenH)
    }

    /** Returns the parsed result or null on error (error text goes to AppState.status). */
    fun step(rgba: ByteArray, w: Int, h: Int, rowStride: Int, armed: Boolean): JSONObject? {
        val m = mod ?: return null
        return try {
            val res = m.callAttr("step", rgba, w, h, rowStride, armed).toString()
            val json = JSONObject(res)
            if (json.has("error")) {
                AppState.status.postValue("engine error: ${json.optString("error")}")
                null
            } else json
        } catch (t: Throwable) {
            Log.e(TAG, "step failed", t)
            AppState.status.postValue("step failed: ${t.message}")
            null
        }
    }

    fun command(line: String): String = try {
        mod?.callAttr("command", line)?.toString() ?: "engine not ready"
    } catch (t: Throwable) {
        "error: ${t.message}"
    }

    fun labelSlot(slot: Int, cardKey: String): String = try {
        mod?.callAttr("label_slot", slot, cardKey)?.toString() ?: "engine not ready"
    } catch (t: Throwable) {
        "error: ${t.message}"
    }
}
