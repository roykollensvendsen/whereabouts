package no.roykollensvendsen.whereabouts

import android.content.Context
import android.media.AudioAttributes
import android.media.AudioFocusRequest
import android.media.AudioManager
import android.speech.tts.TextToSpeech
import android.speech.tts.UtteranceProgressListener
import android.util.Log
import org.json.JSONObject
import java.net.HttpURLConnection
import java.net.URL
import java.util.Locale
import java.util.concurrent.ExecutorService

/**
 * Tells of the places Hermes has described as Roy passes them, with Android's
 * own speech. [Telling] decides which are due; this fetches them, speaks them
 * one at a time, dims other sound while it speaks, and waits while a call, such
 * as the voice, holds the sound.
 */
class Teller(
    private val context: Context,
    private val background: ExecutorService,
    /** A pretend drive: told places are remembered only for this drive, and the switch is ignored. */
    private val pretend: Boolean = false,
) {

    private val toldOnThisDrive = HashMap<Long, Long>()

    /** Speaking, or with something waiting to be spoken. */
    val busy: Boolean get() = speaking || waiting.isNotEmpty()

    @Volatile private var places: List<Place> = emptyList()
    @Volatile private var fetchedAt: Reading? = null
    private val waiting = ArrayDeque<Place>()
    private var speaking = false
    private var ready = false
    private val audio = context.getSystemService(AudioManager::class.java)
    private val focus = AudioFocusRequest.Builder(AudioManager.AUDIOFOCUS_GAIN_TRANSIENT_MAY_DUCK)
        .setAudioAttributes(
            AudioAttributes.Builder()
                .setUsage(AudioAttributes.USAGE_ASSISTANCE_NAVIGATION_GUIDANCE)
                .setContentType(AudioAttributes.CONTENT_TYPE_SPEECH)
                .build(),
        )
        .build()
    private val speech: TextToSpeech = TextToSpeech(context) { status ->
        ready = status == TextToSpeech.SUCCESS
        if (ready) speech.language = Locale.forLanguageTag("nb-NO")
    }

    init {
        speech.setOnUtteranceProgressListener(object : UtteranceProgressListener() {
            override fun onStart(id: String?) {}
            override fun onDone(id: String?) = finished()
            @Deprecated("Deprecated in Java")
            override fun onError(id: String?) = finished()
        })
    }

    @Volatile private var lastHeard: Reading? = null

    /** Called on the main thread with every reading, sent or not. */
    fun heard(now: Reading) {
        lastHeard = now
        if (!pretend && !Settings.telling(context)) return
        if (Telling.refetch(fetchedAt, now)) {
            fetchedAt = now
            val address = Settings.address(context) ?: return
            background.execute { fetch(address, now) }
        }
        val told = if (pretend) toldOnThisDrive else Settings.told(context)
        for (place in Telling.due(places, now, told)) {
            if (waiting.none { it.id == place.id }) waiting.addLast(place)
            // Marked as told when it is queued, so the next reading does not queue it again.
            if (pretend) toldOnThisDrive[place.id] = now.at else Settings.markTold(context, place.id, now.at)
        }
        next()
    }

    /** Say something that is not a place, such as arriving at the destination of a pretend drive. */
    fun say(text: String) {
        waiting.addLast(Place(id = SAID, name = "", latitude = 0.0, longitude = 0.0, radiusM = 0.0, said = text))
        next()
    }

    private fun next() {
        if (speaking || !ready || waiting.isEmpty()) return
        // A call holds the sound, the voice's included: wait for it to end.
        if (audio.mode == AudioManager.MODE_IN_COMMUNICATION || audio.mode == AudioManager.MODE_IN_CALL) return
        if (audio.requestAudioFocus(focus) != AudioManager.AUDIOFOCUS_REQUEST_GRANTED) return
        val place = waiting.removeFirst()
        speaking = true
        speech.speak(place.said, TextToSpeech.QUEUE_ADD, null, "place-${place.id}")
        // The map points at the place while it is told, from where it was told.
        if (place.id != SAID) lastHeard?.let { from -> show("{\"id\":${place.id},\"from_latitude\":${from.latitude},\"from_longitude\":${from.longitude}}") }
    }

    private fun finished() {
        android.os.Handler(android.os.Looper.getMainLooper()).post {
            speaking = false
            if (waiting.isEmpty()) {
                audio.abandonAudioFocusRequest(focus)
                show("{\"id\":null}")
            }
            next()
        }
    }

    private fun show(body: String) {
        val address = Settings.address(context) ?: return
        background.execute {
            try {
                val connection = URL(address.trimEnd('/') + "/telling").openConnection() as HttpURLConnection
                connection.requestMethod = "POST"
                connection.doOutput = true
                connection.connectTimeout = 5_000
                connection.setRequestProperty("Content-Type", "application/json")
                connection.outputStream.use { it.write(body.toByteArray()) }
                connection.responseCode
                connection.disconnect()
            } catch (failure: Exception) {
                Log.w(TAG, "could not show what is told: ${failure.message}")
            }
        }
    }

    private fun fetch(address: String, near: Reading) {
        try {
            val url = URL(
                address.trimEnd('/') + "/described?latitude=${near.latitude}&longitude=${near.longitude}&km=30",
            )
            val connection = url.openConnection() as HttpURLConnection
            connection.connectTimeout = 10_000
            connection.readTimeout = 10_000
            val body = connection.inputStream.bufferedReader().use { it.readText() }
            connection.disconnect()
            val listed = JSONObject(body).getJSONArray("places")
            places = (0 until listed.length()).map { i ->
                val one = listed.getJSONObject(i)
                Place(
                    id = one.getLong("id"),
                    name = one.optString("name"),
                    latitude = one.getDouble("latitude"),
                    longitude = one.getDouble("longitude"),
                    radiusM = one.getDouble("radius_m"),
                    said = one.getString("said"),
                )
            }
            Log.i(TAG, "places near: ${places.size}")
        } catch (failure: Exception) {
            // Kept from the last fetch, so a tunnel or a dead zone tells as before.
            Log.w(TAG, "could not fetch places: ${failure.message}")
            fetchedAt = null
        }
    }

    fun close() {
        speech.stop()
        speech.shutdown()
        audio.abandonAudioFocusRequest(focus)
    }

    companion object {
        private const val TAG = "Whereabouts"

        /** The id of something said that is not a place, so it is never pointed at on the map. */
        private const val SAID = -1L
    }
}
