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
class Teller(private val context: Context, private val background: ExecutorService) {

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

    /** Called on the main thread with every reading, sent or not. */
    fun heard(now: Reading) {
        if (!Settings.telling(context)) return
        if (Telling.refetch(fetchedAt, now)) {
            fetchedAt = now
            val address = Settings.address(context) ?: return
            background.execute { fetch(address, now) }
        }
        val told = Settings.told(context)
        for (place in Telling.due(places, now, told)) {
            if (waiting.none { it.id == place.id }) waiting.addLast(place)
            // Marked as told when it is queued, so the next reading does not queue it again.
            Settings.markTold(context, place.id, now.at)
        }
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
    }

    private fun finished() {
        android.os.Handler(android.os.Looper.getMainLooper()).post {
            speaking = false
            if (waiting.isEmpty()) audio.abandonAudioFocusRequest(focus)
            next()
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
    }
}
