package no.roykollensvendsen.whereabouts

/** A place Hermes has described: where it is, how close counts, and what is said. */
data class Place(
    val id: Long,
    val name: String,
    val latitude: Double,
    val longitude: Double,
    val radiusM: Double,
    val said: String,
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

    private fun at(place: Place) = Reading(place.latitude, place.longitude, null, null, 0L)
}
