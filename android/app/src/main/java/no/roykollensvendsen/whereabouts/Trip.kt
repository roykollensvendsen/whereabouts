package no.roykollensvendsen.whereabouts

import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.sin

/**
 * A pretend drive along a road, for hearing what is told on the way without
 * driving it. Roy, 2026-10-10: and faster than real time if he likes. It is
 * never sent anywhere: the route keeps only real readings.
 */
class Trip(private val road: List<Pair<Double, Double>>) {

    /** How far along the road each point is, in metres. */
    private val along: DoubleArray = DoubleArray(road.size).also { at ->
        for (i in 1 until road.size) at[i] = at[i - 1] + Change.metres(point(i - 1), point(i))
    }

    val metres: Double get() = along.lastOrNull() ?: 0.0

    /** Where the drive is `distance` metres in, which way it heads, at `speed` m/s and time `at`. */
    fun reading(distance: Double, speed: Double, at: Long): Reading {
        if (road.size < 2) return point(0).copy(speed = speed, at = at)
        val d = distance.coerceIn(0.0, metres)
        var i = along.indexOfFirst { it >= d }.coerceAtLeast(1)
        if (along[i] == along[i - 1] && i < road.size - 1) i++
        val span = along[i] - along[i - 1]
        val part = if (span > 0) (d - along[i - 1]) / span else 0.0
        val (lat0, lon0) = road[i - 1]
        val (lat1, lon1) = road[i]
        return Reading(
            latitude = lat0 + (lat1 - lat0) * part,
            longitude = lon0 + (lon1 - lon0) * part,
            heading = heading(lat0, lon0, lat1, lon1),
            speed = speed,
            at = at,
        )
    }

    private fun point(i: Int) = Reading(road[i].first, road[i].second, null, null, 0L)

    companion object {
        /** The speed a pretend drive goes at before it is sped up: a country road. */
        const val SPEED_M_S = 80 / 3.6

        /** The choices for how much faster than real time it goes. */
        val FASTER = listOf(1, 2, 5, 10)

        fun heading(lat0: Double, lon0: Double, lat1: Double, lon1: Double): Double {
            val p0 = Math.toRadians(lat0)
            val p1 = Math.toRadians(lat1)
            val dl = Math.toRadians(lon1 - lon0)
            val y = sin(dl) * cos(p1)
            val x = cos(p0) * sin(p1) - sin(p0) * cos(p1) * cos(dl)
            return (Math.toDegrees(atan2(y, x)) + 360.0) % 360.0
        }
    }
}
