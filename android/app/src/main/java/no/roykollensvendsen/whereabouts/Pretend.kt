package no.roykollensvendsen.whereabouts

import android.content.Context
import android.os.Handler
import android.os.Looper
import android.util.Log
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.util.concurrent.Executors

/**
 * Plays a [Trip] from one place to another, `faster` times real time, telling
 * what is passed exactly as on a real drive. The drive stands still while a
 * place is being told, so a fast drive does not pile the tellings up. Nothing
 * is sent to the route.
 */
class Pretend(private val context: Context, private val said: (String) -> Unit) {

    private val background = Executors.newSingleThreadExecutor()
    private val ticking = Handler(Looper.getMainLooper())
    private var teller: Teller? = null
    private var trip: Trip? = null
    private var gone = 0.0
    private var clock = 0L
    private var faster = 1
    private var destination = ""
    private var arrived = false
    private var steps = 0

    var running = false
        private set

    fun start(from: String, to: String, faster: Int) {
        stop()
        val address = Settings.address(context) ?: return said("Skriv inn adressen til tjenesten først.")
        this.faster = faster
        destination = to
        arrived = false
        running = true
        said("Finner veien fra $from til $to …")
        background.execute {
            val road = fetch(address, from, to)
            ticking.post {
                if (!running) return@post
                if (road.size < 2) {
                    running = false
                    said("Fant ingen vei fra $from til $to.")
                    return@post
                }
                trip = Trip(road)
                gone = 0.0
                clock = System.currentTimeMillis()
                teller = Teller(context, background, pretend = true)
                ticking.post(step)
            }
        }
    }

    fun stop() {
        running = false
        ticking.removeCallbacksAndMessages(null)
        teller?.close()
        teller = null
    }

    private val step = object : Runnable {
        override fun run() {
            val trip = trip ?: return
            val teller = teller ?: return
            if (!teller.busy) {
                gone += Trip.SPEED_M_S * faster * STEP_MS / 1000.0
                clock += STEP_MS * faster
            }
            val now = trip.reading(gone, Trip.SPEED_M_S, clock)
            teller.heard(now)
            // The map follows the pretend drive; the service keeps it in memory only, never in the route.
            if (++steps % SHOW_EVERY == 0) show(now)
            val km = "%.1f av %.1f km".format(gone.coerceAtMost(trip.metres) / 1000, trip.metres / 1000)
            if (gone >= trip.metres && !teller.busy) {
                // Roy, 2026-10-10: say so on reaching the destination he typed.
                if (!arrived) {
                    arrived = true
                    teller.say("Du er fremme i $destination.")
                } else {
                    running = false
                    said("Prøveturen er ferdig: $km. Du er fremme i $destination.")
                    return
                }
            }
            said("Prøvetur, ${faster}× fart: $km" + if (teller.busy) ", forteller." else ".")
            ticking.postDelayed(this, STEP_MS)
        }
    }

    private fun show(now: Reading) {
        val address = Settings.address(context) ?: return
        background.execute {
            try {
                val connection = URL(address.trimEnd('/') + "/pretend").openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.doOutput = true
                connection.connectTimeout = 5_000
                connection.setRequestProperty("Content-Type", "application/json")
                val body = "{\"latitude\":${now.latitude},\"longitude\":${now.longitude}}"
                connection.outputStream.use { it.write(body.toByteArray()) }
                connection.responseCode
                connection.disconnect()
            } catch (failure: Exception) {
                Log.w("Whereabouts", "could not show the pretend drive: ${failure.message}")
            }
        }
    }

    private fun fetch(address: String, from: String, to: String): List<Pair<Double, Double>> = try {
        val query = "from=" + URLEncoder.encode(from, "UTF-8") + "&to=" + URLEncoder.encode(to, "UTF-8")
        val connection = URL(address.trimEnd('/') + "/road?" + query).openConnection() as HttpURLConnection
        connection.connectTimeout = 10_000
        connection.readTimeout = 30_000
        val body = connection.inputStream.bufferedReader().use { it.readText() }
        connection.disconnect()
        val points = JSONObject(body).getJSONArray("points")
        (0 until points.length()).map { points.getJSONArray(it).let { p -> p.getDouble(0) to p.getDouble(1) } }
    } catch (failure: Exception) {
        Log.w("Whereabouts", "no road: ${failure.message}")
        emptyList()
    }

    companion object {
        private const val STEP_MS = 500L

        /** Show the pretend drive on the map every this many steps: every two seconds. */
        private const val SHOW_EVERY = 4
    }
}
