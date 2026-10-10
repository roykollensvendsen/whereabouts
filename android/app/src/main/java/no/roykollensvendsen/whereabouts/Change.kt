package no.roykollensvendsen.whereabouts

import kotlin.math.abs
import kotlin.math.asin
import kotlin.math.cos
import kotlin.math.sin
import kotlin.math.sqrt

/** One reading: where, which way in degrees from north, how fast in metres a second, and when. */
data class Reading(
    val latitude: Double,
    val longitude: Double,
    val heading: Double?,
    val speed: Double?,
    val at: Long,
)

/**
 * Whether a reading is worth sending. Roy, 2026-10-10: only when something has
 * actually changed. A reading goes when the phone has moved [METRES], turned
 * [DEGREES] while moving, changed speed by [KM_H], or when [HEARTBEAT_MS] has
 * passed, so the service can tell a still phone from a silent one.
 */
object Change {
    const val METRES = 10.0
    const val DEGREES = 15.0
    const val KM_H = 5.0
    const val HEARTBEAT_MS = 60_000L

    /** Below this a phone's heading is noise: standing still, it points anywhere. */
    private const val MOVING = 1.5

    fun worthSending(last: Reading?, now: Reading): Boolean {
        if (last == null) return true
        if (now.at - last.at >= HEARTBEAT_MS) return true
        if (metres(last, now) >= METRES) return true
        val speedNow = now.speed ?: 0.0
        val speedThen = last.speed ?: 0.0
        if (abs(speedNow - speedThen) * 3.6 >= KM_H) return true
        val turned = now.heading != null && last.heading != null && speedNow >= MOVING &&
            angle(now.heading, last.heading) >= DEGREES
        return turned
    }

    /** The smaller angle between two headings, in degrees. */
    fun angle(a: Double, b: Double): Double {
        val d = abs(a - b) % 360.0
        return if (d > 180.0) 360.0 - d else d
    }

    /** How far apart two readings are, on the ground, in metres. */
    fun metres(a: Reading, b: Reading): Double {
        val p1 = Math.toRadians(a.latitude)
        val p2 = Math.toRadians(b.latitude)
        val dp = p2 - p1
        val dl = Math.toRadians(b.longitude - a.longitude)
        val h = sin(dp / 2) * sin(dp / 2) + cos(p1) * cos(p2) * sin(dl / 2) * sin(dl / 2)
        return 2 * 6_371_000.0 * asin(sqrt(h))
    }
}
