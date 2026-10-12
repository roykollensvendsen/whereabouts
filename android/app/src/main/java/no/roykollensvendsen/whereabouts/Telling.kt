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

/** One line of sight across the view ahead: which way it looks, and at which distances it sees ground. */
data class Ray(val bearing: Double, val seen: List<Int>)

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
    fun due(places: List<Place>, now: Reading, toldAt: Map<Long, Long>, view: List<Ray>? = null): List<Place> =
        places
            .map { it to Change.metres(now, at(it)) }
            .filter { (place, metres) -> told(place, now, metres, view) && !toldRecently(place, now, toldAt) }
            .sortedBy { it.second }
            .map { it.first }

    /**
     * Roy, 2026-10-10: tell of things mainly as they come into view. With a
     * view, a place within its reach is told when it can be seen, or when Roy
     * is close by it; without one, as soon as it is within reach.
     */
    private fun told(place: Place, now: Reading, metres: Double, view: List<Ray>?): Boolean {
        if (metres > reach(place, now)) return false
        if (view.isNullOrEmpty() || place.kind == TEST) return true
        return metres <= CLOSE_METRES || inView(place, now, view)
    }

    /** Whether Roy has left the place well behind: twice its reach away, or for a test point, TEST_LATE. */
    fun passed(place: Place, now: Reading): Boolean =
        Change.metres(now, at(place)) > if (place.kind == TEST) TEST_LATE else 2 * reach(place, now)

    /** Whether the place lies in the view ahead: on the ray nearest its bearing, at a distance that ray sees. */
    fun inView(place: Place, now: Reading, view: List<Ray>): Boolean {
        val bearing = Trip.heading(now.latitude, now.longitude, place.latitude, place.longitude)
        val ray = view.minByOrNull { kotlin.math.abs(((it.bearing - bearing + 540.0) % 360.0) - 180.0) } ?: return false
        if (kotlin.math.abs(((ray.bearing - bearing + 540.0) % 360.0) - 180.0) > RAY_SLACK) return false
        val metres = Change.metres(now, at(place))
        return ray.seen.any { kotlin.math.abs(it - metres) <= SAMPLE_SLACK }
    }

    /**
     * How close counts for this place at this speed. Roy, 2026-10-12: a test point
     * (a roundabout or a junction) is said when he is at it, with no lead, to hear
     * how accurate the telling is.
     */
    fun reach(place: Place, now: Reading): Double =
        if (place.kind == TEST) place.radiusM else place.radiusM + (now.speed ?: 0.0) * LEAD_SECONDS

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

    /** A test point, for hearing how accurate the telling is. */
    const val TEST = "test"

    /** A test point told this late, in metres behind, is still told: how late is what is measured. */
    private const val TEST_LATE = 300.0

    /** Close enough to tell of whether or not the view shows it: the grid cannot see through a roadside. */
    const val CLOSE_METRES = 200.0

    /** A ray covers this many degrees either side of it, and a sample this many metres either side. */
    private const val RAY_SLACK = 6.0
    private const val SAMPLE_SLACK = 60.0

    /** Fetch the view again after this long, or this far along. */
    const val REVIEW_MS = 10_000L
    const val REVIEW_METRES = 150.0
    private const val STILL = 1.5
    private val COMPASS = listOf("nord", "nordøst", "øst", "sørøst", "sør", "sørvest", "vest", "nordvest")

    private fun at(place: Place) = Reading(place.latitude, place.longitude, null, null, 0L)
}
