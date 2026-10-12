package no.roykollensvendsen.whereabouts

import org.json.JSONObject
import java.nio.ByteBuffer
import java.nio.ByteOrder
import kotlin.math.asin
import kotlin.math.atan2
import kotlin.math.cos
import kotlin.math.roundToLong
import kotlin.math.sin

/**
 * The land along Roy's roads, kept on the phone: each 50 m cell's height and
 * how high what grows or stands on it is. Roy, 2026-10-12: work the view out
 * on the phone, so it works without network too. Read from what the service
 * packs at /land.bin; the numbers that shape a view come with it, so phone
 * and service work a view out the same way.
 */
class Land(
    private val keys: LongArray,
    private val values: IntArray,
    private val cover: DoubleArray,
    val grid: Double,
    val eyes: Double,
    val target: Double,
    val openNear: Int,
    val halfWidth: Int,
    val rayStep: Int,
    val sampleStep: Int,
    val farthest: Int,
) {
    val size: Int get() = keys.size

    /** The ground's height and what stands on it at a point, or null where the phone has no land. */
    fun at(latitude: Double, longitude: Double): Pair<Double, Double>? {
        val key = key((latitude / grid).roundToLong(), (longitude / (grid * 2)).roundToLong())
        val found = keys.binarySearch(key)
        if (found < 0) return null
        val value = values[found]
        val code = value and 0xFF
        return (value shr 8) / 10.0 to (if (code < cover.size) cover[code] else 0.0)
    }

    /** The half circle ahead, ray by ray: which distances along each can be seen. */
    fun view(latitude: Double, longitude: Double, heading: Double): List<Ray>? {
        val here = at(latitude, longitude) ?: return null
        val eyesAt = here.first + eyes
        return (-halfWidth..halfWidth step rayStep).map { turn ->
            val bearing = (heading + turn + 360.0) % 360.0
            var highest = Double.NEGATIVE_INFINITY
            val seen = mutableListOf<Int>()
            for (metres in sampleStep..farthest step sampleStep) {
                val (lat, lon) = ahead(latitude, longitude, bearing, metres.toDouble())
                val (z, standing) = at(lat, lon) ?: break
                // What lies behind higher ground or forest cannot be seen; the same rule as the service.
                if (atan2(z + target - eyesAt, metres.toDouble()) >= highest) seen += metres
                val blocking = if (metres > openNear) standing else 0.0
                highest = maxOf(highest, atan2(z + blocking - eyesAt, metres.toDouble()))
            }
            Ray(bearing, seen)
        }
    }

    companion object {
        private fun key(row: Long, col: Long) = (row shl 32) or (col and 0xFFFFFFFFL)

        /** Read what the service packed: a header line of JSON, then 11 bytes a cell, sorted. */
        fun read(bytes: ByteArray): Land {
            val newline = bytes.indexOf('\n'.code.toByte())
            val about = JSONObject(String(bytes, 0, newline, Charsets.UTF_8))
            val codes = about.getJSONArray("codes")
            val cover = DoubleArray(codes.length()) { codes.getJSONArray(it).getDouble(1) }
            val count = about.getInt("count")
            val buffer = ByteBuffer.wrap(bytes, newline + 1, bytes.size - newline - 1).order(ByteOrder.LITTLE_ENDIAN)
            val keys = LongArray(count)
            val values = IntArray(count)
            for (i in 0 until count) {
                val row = buffer.int.toLong()
                val col = buffer.int.toLong()
                val decimetres = buffer.short.toInt()
                val code = buffer.get().toInt() and 0xFF
                keys[i] = key(row, col)
                values[i] = (decimetres shl 8) or code
            }
            return Land(
                keys, values, cover, about.getDouble("grid"), about.getDouble("eyes"), about.getDouble("target"),
                about.getInt("open_near"), about.getInt("half_width"), about.getInt("ray_step"),
                about.getInt("sample_step"), about.getInt("farthest"),
            )
        }

        fun ahead(latitude: Double, longitude: Double, bearing: Double, metres: Double): Pair<Double, Double> {
            val angular = metres / 6_371_000.0
            val lat1 = Math.toRadians(latitude)
            val lon1 = Math.toRadians(longitude)
            val b = Math.toRadians(bearing)
            val lat2 = asin(sin(lat1) * cos(angular) + cos(lat1) * sin(angular) * cos(b))
            val lon2 = lon1 + atan2(sin(b) * sin(angular) * cos(lat1), cos(angular) - sin(lat1) * sin(lat2))
            return Math.toDegrees(lat2) to Math.toDegrees(lon2)
        }
    }
}
