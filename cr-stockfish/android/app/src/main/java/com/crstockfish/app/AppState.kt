package com.crstockfish.app

import androidx.lifecycle.MutableLiveData

/** Shared, observable state between the activity, the capture loop and the overlay. */
object AppState {
    val status = MutableLiveData("idle")
    val lastText = MutableLiveData("waiting for frames")
    val lastPlay = MutableLiveData("")
    @Volatile var armed: Boolean = false
    @Volatile var dryRun: Boolean = true
    @Volatile var minScore: Float = 0.6f
    @Volatile var capturing: Boolean = false
}
