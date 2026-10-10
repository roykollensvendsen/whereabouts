package no.roykollensvendsen.whereabouts

/**
 * Whether GPS has gone silent on a drive, and why it likely has. Roy,
 * 2026-10-10: say so when GPS does not work as it should, and explain it.
 */
object GpsWatch {
    /** GPS silent this long, while following, is worth saying. */
    const val SILENT_MS = 60_000L

    /** How often to look. */
    const val LOOK_EVERY_MS = 15_000L

    /** Whether GPS has been silent too long: since its last fix, or since following began if none came. */
    fun silent(lastGps: Long, startedAt: Long, now: Long): Boolean = now - maxOf(lastGps, startedAt) >= SILENT_MS

    /** The likeliest reason, in a sentence to speak. `power` is what power saving is doing, or null. */
    fun reason(gpsEnabled: Boolean, power: String?): String = when {
        !gpsEnabled -> "GPS er slått av i telefonens innstillinger."
        power != null && power.contains("GPS") -> "Strømsparing er på og slår av GPS når skjermen er av."
        power != null && power.contains("strømsparing") -> "Strømsparing er på og kan holde GPS-en tilbake."
        else -> "Kanskje er du innendørs, i en tunnel eller under tett tak."
    }

    /** What is said when GPS has gone silent. */
    fun warning(silentMs: Long, reason: String, network: Boolean): String {
        val minutes = (silentMs / 60_000L).coerceAtLeast(1)
        val since = if (minutes == 1L) "et minutt" else "$minutes minutter"
        val meanwhile = if (network) " Jeg bruker grovere posisjon fra mobilnettet så lenge." else ""
        return "GPS-en har ikke svart på $since. $reason$meanwhile"
    }

    const val BACK = "GPS-en virker igjen."
}
