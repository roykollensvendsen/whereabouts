package no.roykollensvendsen.whereabouts

import android.annotation.SuppressLint
import android.content.Context
import android.content.Intent
import android.net.Uri
import android.os.PowerManager
import android.provider.Settings as AndroidSettings

/**
 * What the phone's power saving does to following and telling. Roy,
 * 2026-10-10: readings stopped for minutes at a time while he drove, and he
 * suspected power saving. Battery saver can turn GPS off when the screen is
 * off, and battery optimisation can put the app to sleep.
 */
object Power {

    /** What is wrong, in words for the screen and the service, or null when nothing is. */
    fun trouble(context: Context): String? {
        val power = context.getSystemService(PowerManager::class.java)
        val found = mutableListOf<String>()
        if (power.isPowerSaveMode) {
            found += when (power.locationPowerSaveMode) {
                PowerManager.LOCATION_MODE_GPS_DISABLED_WHEN_SCREEN_OFF,
                PowerManager.LOCATION_MODE_ALL_DISABLED_WHEN_SCREEN_OFF,
                -> "strømsparing slår av GPS når skjermen er av"
                PowerManager.LOCATION_MODE_THROTTLE_REQUESTS_WHEN_SCREEN_OFF ->
                    "strømsparing gir sjeldnere posisjoner når skjermen er av"
                PowerManager.LOCATION_MODE_FOREGROUND_ONLY -> "strømsparing gir posisjon bare med appen åpen"
                else -> "strømsparing er på"
            }
        }
        if (!power.isIgnoringBatteryOptimizations(context.packageName)) {
            found += "batterioptimalisering kan stanse appen"
        }
        return found.takeIf { it.isNotEmpty() }?.joinToString(", ")
    }

    /** Ask Android to let the app run in the background without being put to sleep. */
    @SuppressLint("BatteryLife") // a sideloaded app that must follow a drive with the screen off
    fun askToStayAwake(context: Context) {
        val power = context.getSystemService(PowerManager::class.java)
        if (power.isIgnoringBatteryOptimizations(context.packageName)) return
        val asking = Intent(AndroidSettings.ACTION_REQUEST_IGNORE_BATTERY_OPTIMIZATIONS)
            .setData(Uri.parse("package:" + context.packageName))
        runCatching { context.startActivity(asking) }
    }

    /** The phone's own battery saver settings, where Roy can turn it off or exempt location. */
    fun openSaverSettings(context: Context) {
        runCatching { context.startActivity(Intent(AndroidSettings.ACTION_BATTERY_SAVER_SETTINGS)) }
    }
}
