package com.crstockfish.app

import android.app.Activity
import android.content.Context
import android.content.Intent
import android.media.projection.MediaProjectionManager
import android.net.Uri
import android.os.Build
import android.os.Bundle
import android.provider.Settings
import android.widget.Button
import android.widget.SeekBar
import android.widget.TextView
import androidx.activity.result.contract.ActivityResultContracts
import androidx.appcompat.app.AppCompatActivity
import com.google.android.material.switchmaterial.SwitchMaterial

class MainActivity : AppCompatActivity() {
    private val projectionLauncher = registerForActivityResult(ActivityResultContracts.StartActivityForResult()) { result ->
        if (result.resultCode == Activity.RESULT_OK && result.data != null) {
            val i = Intent(this, CaptureService::class.java)
                .putExtra(CaptureService.EXTRA_CODE, result.resultCode)
                .putExtra(CaptureService.EXTRA_DATA, result.data)
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) startForegroundService(i) else startService(i)
        } else {
            AppState.status.postValue("screen capture consent denied")
        }
    }

    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContentView(R.layout.activity_main)
        val status = findViewById<TextView>(R.id.status)
        val last = findViewById<TextView>(R.id.lastDecision)
        AppState.status.observe(this) { status.text = it }
        AppState.lastPlay.observe(this) { if (it.isNotEmpty()) last.text = it }

        findViewById<Button>(R.id.btnOverlay).setOnClickListener {
            if (!Settings.canDrawOverlays(this)) {
                startActivity(Intent(Settings.ACTION_MANAGE_OVERLAY_PERMISSION, Uri.parse("package:$packageName")))
            } else {
                AppState.status.postValue("overlay already allowed")
            }
        }
        findViewById<Button>(R.id.btnAccessibility).setOnClickListener {
            startActivity(Intent(Settings.ACTION_ACCESSIBILITY_SETTINGS))
        }
        findViewById<Button>(R.id.btnStart).setOnClickListener {
            if (!Settings.canDrawOverlays(this)) {
                AppState.status.postValue("allow the overlay first")
                return@setOnClickListener
            }
            val mgr = getSystemService(Context.MEDIA_PROJECTION_SERVICE) as MediaProjectionManager
            projectionLauncher.launch(mgr.createScreenCaptureIntent())
        }
        findViewById<Button>(R.id.btnStop).setOnClickListener {
            startService(Intent(this, CaptureService::class.java).setAction(CaptureService.ACTION_STOP))
        }
        findViewById<SwitchMaterial>(R.id.swArmed).setOnCheckedChangeListener { _, on ->
            AppState.armed = on
            AppState.status.postValue(if (on) (if (AppState.dryRun) "armed (dry run)" else "ARMED - live taps") else "disarmed")
        }
        findViewById<SwitchMaterial>(R.id.swDry).apply {
            isChecked = AppState.dryRun
            setOnCheckedChangeListener { _, on ->
                AppState.dryRun = on
                if (!on && TapService.instance == null) AppState.status.postValue("enable the tap service before going live")
            }
        }
        val lbl = findViewById<TextView>(R.id.lblMinScore)
        findViewById<SeekBar>(R.id.seekMinScore).setOnSeekBarChangeListener(object : SeekBar.OnSeekBarChangeListener {
            override fun onProgressChanged(sb: SeekBar, p: Int, fromUser: Boolean) {
                AppState.minScore = p / 10f
                lbl.text = getString(R.string.lbl_minscore) + "  ${AppState.minScore}"
                val dm = resources.displayMetrics
                Bridge.setConfig(AppState.minScore, 1.2f, dm.widthPixels, dm.heightPixels)
            }
            override fun onStartTrackingTouch(sb: SeekBar) = Unit
            override fun onStopTrackingTouch(sb: SeekBar) = Unit
        })
    }
}
