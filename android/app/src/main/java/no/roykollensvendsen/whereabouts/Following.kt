package no.roykollensvendsen.whereabouts

import android.Manifest
import android.annotation.SuppressLint
import android.app.Notification
import android.app.NotificationChannel
import android.app.NotificationManager
import android.app.PendingIntent
import android.app.Service
import android.content.Context
import android.content.Intent
import android.content.pm.PackageManager
import android.content.pm.ServiceInfo
import android.location.Location
import android.location.LocationListener
import android.location.LocationManager
import android.os.IBinder
import android.os.Looper
import android.util.Log
import java.net.HttpURLConnection
import java.net.URL
import java.util.concurrent.Executors

/**
 * Follows the phone while "Følg meg" is on, and sends a reading to whereabouts
 * whenever [Change] says it is worth it. A foreground service of type location
 * is what lets this go on with the screen locked.
 */
class Following : Service(), LocationListener {

    private var last: Reading? = null
    private val sender = Executors.newSingleThreadExecutor()
    private var teller: Teller? = null
    private val version: String by lazy { packageManager.getPackageInfo(packageName, 0).versionName ?: "?" }

    @SuppressLint("MissingPermission") // checked just below
    override fun onStartCommand(intent: Intent?, flags: Int, startId: Int): Int {
        startForeground(1, notification(), ServiceInfo.FOREGROUND_SERVICE_TYPE_LOCATION)
        if (checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION) != PackageManager.PERMISSION_GRANTED) {
            stopSelf()
            return START_NOT_STICKY
        }
        val locations = getSystemService(LOCATION_SERVICE) as LocationManager
        // Asked every two seconds; most are dropped by Change before they are sent.
        if (teller == null) teller = Teller(this, sender)
        locations.requestLocationUpdates(LocationManager.GPS_PROVIDER, ASK_EVERY_MS, 0f, this, Looper.getMainLooper())
        // Roy, 2026-10-10: with the battery low, power saving turned GPS off with the screen off, and
        // readings stopped for half an hour mid-drive. Masts and wifi still answer then; coarser, but there.
        if (locations.isProviderEnabled(LocationManager.NETWORK_PROVIDER)) {
            locations.requestLocationUpdates(
                LocationManager.NETWORK_PROVIDER, NETWORK_EVERY_MS, 0f, this, Looper.getMainLooper(),
            )
        }
        startedAt = System.currentTimeMillis()
        watching.removeCallbacks(watch)
        watching.postDelayed(watch, GpsWatch.LOOK_EVERY_MS)
        running = true
        return START_STICKY
    }

    /** When the last GPS reading came, so a coarser one is used only while GPS is silent. */
    private var lastGps = 0L
    private var startedAt = 0L

    /** Whether Roy has been told GPS is silent, so it is said once per silence. */
    private var warned = false
    private var gpsState = "ok"
    private val watching = android.os.Handler(Looper.getMainLooper())
    private val watch = object : Runnable {
        override fun run() {
            look()
            watching.postDelayed(this, GpsWatch.LOOK_EVERY_MS)
        }
    }

    /** Roy, 2026-10-10: say so when GPS does not work as it should, and why. */
    private fun look() {
        val now = System.currentTimeMillis()
        val silent = GpsWatch.silent(lastGps, startedAt, now)
        if (silent && !warned) {
            warned = true
            val locations = getSystemService(LOCATION_SERVICE) as LocationManager
            val reason = GpsWatch.reason(
                locations.isProviderEnabled(LocationManager.GPS_PROVIDER), Power.trouble(this),
            )
            val network = locations.isProviderEnabled(LocationManager.NETWORK_PROVIDER)
            val warning = GpsWatch.warning(now - maxOf(lastGps, startedAt), reason, network)
            gpsState = "stille: $reason"
            teller?.say(warning)
            show(warning)
        } else if (!silent && warned) {
            warned = false
            gpsState = "ok"
            teller?.say(GpsWatch.BACK)
            show(getString(R.string.following_text))
        }
    }

    private fun show(text: String) {
        getSystemService(NotificationManager::class.java).notify(1, notification(text))
    }

    override fun onLocationChanged(location: Location) {
        if (location.provider == LocationManager.GPS_PROVIDER) {
            lastGps = System.currentTimeMillis()
        } else if (System.currentTimeMillis() - lastGps < GPS_SILENT_MS) {
            return
        }
        val now = Reading(
            latitude = location.latitude,
            longitude = location.longitude,
            heading = if (location.hasBearing()) location.bearing.toDouble() else null,
            speed = if (location.hasSpeed()) location.speed.toDouble() else null,
            at = location.time,
        )
        // Every reading, sent or not, may bring Roy close to a place to tell of.
        teller?.heard(now)
        if (!Change.worthSending(last, now)) return
        last = now
        val address = Settings.address(this) ?: return
        sender.execute { send(address, now) }
    }

    private fun send(address: String, reading: Reading) {
        val body = buildString {
            append("{\"latitude\":").append(reading.latitude)
            append(",\"longitude\":").append(reading.longitude)
            reading.heading?.let { append(",\"heading\":").append(it) }
            reading.speed?.let { append(",\"speed\":").append(it) }
            append(",\"at\":").append(reading.at / 1000.0)
            // Roy, 2026-10-10: the phone says which app it runs and where its sound goes, so nobody asks him.
            append(",\"app\":\"").append(version).append('"')
            teller?.let { append(",\"sound\":\"").append(it.route()).append('"') }
            append(",\"power\":\"").append(Power.trouble(this@Following) ?: "ok").append('"')
            append(",\"gps\":\"").append(gpsState).append('"')
            append('}')
        }
        try {
            val connection = URL(address.trimEnd('/') + "/reading").openConnection() as HttpURLConnection
            connection.requestMethod = "POST"
            connection.doOutput = true
            connection.connectTimeout = 10_000
            connection.readTimeout = 10_000
            connection.setRequestProperty("Content-Type", "application/json")
            connection.outputStream.use { it.write(body.toByteArray()) }
            val status = connection.responseCode
            connection.disconnect()
            sent = System.currentTimeMillis()
            Log.i(TAG, "sent a reading: $status")
        } catch (failure: Exception) {
            // A tunnel or a dead zone: the next change, or the heartbeat, tries again.
            Log.w(TAG, "could not send: ${failure.message}")
            last = null
        }
    }

    override fun onDestroy() {
        watching.removeCallbacks(watch)
        (getSystemService(LOCATION_SERVICE) as LocationManager).removeUpdates(this)
        teller?.close()
        sender.shutdown()
        running = false
        super.onDestroy()
    }

    override fun onBind(intent: Intent?): IBinder? = null

    private fun notification(text: String = getString(R.string.following_text)): Notification {
        val channel = NotificationChannel("following", getString(R.string.channel), NotificationManager.IMPORTANCE_LOW)
        getSystemService(NotificationManager::class.java).createNotificationChannel(channel)
        val open = PendingIntent.getActivity(this, 0, Intent(this, MainActivity::class.java), PendingIntent.FLAG_IMMUTABLE)
        return Notification.Builder(this, "following")
            .setContentTitle(getString(R.string.following_title))
            .setContentText(text)
            .setStyle(Notification.BigTextStyle().bigText(text))
            .setSmallIcon(android.R.drawable.ic_menu_mylocation)
            .setContentIntent(open)
            .setOngoing(true)
            .build()
    }

    companion object {
        private const val TAG = "Whereabouts"
        private const val ASK_EVERY_MS = 2_000L

        /** How often to ask the masts and wifi, and how long GPS must be silent before they are used. */
        private const val NETWORK_EVERY_MS = 10_000L
        private const val GPS_SILENT_MS = 20_000L

        @Volatile var running = false
            private set

        /** When the last reading reached the service, for the screen. */
        @Volatile var sent = 0L
            private set

        fun start(context: Context) = context.startForegroundService(Intent(context, Following::class.java))

        fun stop(context: Context) = context.stopService(Intent(context, Following::class.java))
    }
}
