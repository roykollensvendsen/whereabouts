package no.roykollensvendsen.whereabouts

/** A place Hermes has described: where it is, how close counts, and what is said. */
data class Place(
    val id: Long,
    val name: String,
    val latitude: Double,
    val longitude: Double,
    val radiusM: Double,
    val said: String,
    val kind: String = "place",
)

/**
 * When to tell of a place. Roy, 2026-10-10: Hermes writes about places, they are
 * kept, and the phone tells of each as he passes, every time he passes. A place
 * is due when it is within its radius, widened by [LEAD_SECONDS] of driving so
 * the telling starts before he is level with it, and has not been told within
 * [QUIET_MS], so one pass tells it once.
 */
object Telling {
    const val LEAD_SECONDS = 8.0
    const val QUIET_MS = 6 * 60 * 60 * 1000L

    /** Fetch the places again after this long, or this far from where they were last fetched. */
    const val REFETCH_MS = 5 * 60 * 1000L
    const val REFETCH_METRES = 10_000.0

    /** Places due now, nearest first. */
    fun due(places: List<Place>, now: Reading, toldAt: Map<Long, Long>): List<Place> =
        places
            .map { it to Change.metres(now, at(it)) }
            .filter { (place, metres) -> metres <= reach(place, now) && !toldRecently(place, now, toldAt) }
            .sortedBy { it.second }
            .map { it.first }

    /** How close counts for this place at this speed. */
    fun reach(place: Place, now: Reading): Double = place.radiusM + (now.speed ?: 0.0) * LEAD_SECONDS

    fun toldRecently(place: Place, now: Reading, toldAt: Map<Long, Long>): Boolean {
        val last = toldAt[place.id] ?: return false
        return now.at - last < QUIET_MS
    }

    /** Whether the places near Roy should be fetched again. */
    fun refetch(lastFetched: Reading?, now: Reading): Boolean =
        lastFetched == null ||
            now.at - lastFetched.at >= REFETCH_MS ||
            Change.metres(lastFetched, now) >= REFETCH_METRES

    /**
     * What is said: where the place lies from the car right now, then the text.
     * Roy, 2026-10-10: say how far, and which way from the car, or it is hard
     * to know what is meant. A note he left is read as he said it.
     */
    fun spoken(place: Place, now: Reading?): String {
        if (now == null || place.kind == "note") return place.said
        val metres = Change.metres(now, at(place))
        val where = if (metres < HERE_METRES) "Her" else "${direction(place, now)}, ${distance(metres)} unna"
        val named = place.name.isBlank() || place.said.contains(place.name, ignoreCase = true)
        return "$where: " + if (named) place.said else "${place.name}. ${place.said}"
    }

    /** Which way the place lies from the car, or by compass when standing still. */
    fun direction(place: Place, now: Reading): String {
        val bearing = Trip.heading(now.latitude, now.longitude, place.latitude, place.longitude)
        val heading = now.heading
        if (heading == null || (now.speed ?: 0.0) < STILL) return "Mot " + COMPASS[((bearing + 22.5) / 45).toInt() % 8]
        val turn = ((bearing - heading + 540.0) % 360.0) - 180.0
        val side = if (turn < 0) "venstre" else "høyre"
        val off = kotlin.math.abs(turn)
        return when {
            off <= 20 -> "Rett frem"
            off <= 60 -> "Litt til $side"
            off <= 120 -> "Til $side"
            off <= 160 -> "Bak deg til $side"
            else -> "Bak deg"
        }
    }

    /** A distance as it is said: to the nearest 50 metres, or in kilometres with one decimal. */
    fun distance(metres: Double): String =
        if (metres < 1000) "${(Math.round(metres / 50) * 50).coerceAtLeast(50)} meter"
        else "%.1f kilometer".format(java.util.Locale.forLanguageTag("nb-NO"), metres / 1000)

    private const val HERE_METRES = 60.0
    private const val STILL = 1.5
    private val COMPASS = listOf("nord", "nordøst", "øst", "sørøst", "sør", "sørvest", "vest", "nordvest")

    private fun at(place: Place) = Reading(place.latitude, place.longitude, null, null, 0L)
}
