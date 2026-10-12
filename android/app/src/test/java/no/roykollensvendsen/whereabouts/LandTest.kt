package no.roykollensvendsen.whereabouts

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

class LandTest {
    private val grid = 0.00045

    /** Flat farmland around 58.5, 8.8, with a ridge 300 m north and a forest 300 m east. */
    private fun land(): Land {
        val cells = sortedMapOf<Long, Int>()
        val row0 = Math.round(58.5 / grid)
        val col0 = Math.round(8.8 / (grid * 2))
        for (row in row0 - 80..row0 + 80) for (col in col0 - 40..col0 + 40) {
            val north = (row - row0) * grid * 111_320
            val east = (col - col0) * grid * 2 * 111_320 * Math.cos(Math.toRadians(58.5))
            val ridge = north in 280.0..330.0 && Math.abs(east) < 100
            val forest = east in 280.0..400.0 && Math.abs(north) < 100
            val z = if (ridge) 600 else 100 // decimetres
            val code = if (forest) 0 else 1
            cells[(row shl 32) or (col and 0xFFFFFFFFL)] = (z shl 8) or code
        }
        return Land(
            cells.keys.toLongArray(), cells.values.toIntArray(), doubleArrayOf(12.0, 0.0), grid,
            eyes = 1.2, target = 3.0, openNear = 50, halfWidth = 90, rayStep = 10, sampleStep = 50, farthest = 2000,
        )
    }

    @Test
    fun aRidgeHidesWhatLiesBehindIt() {
        val ahead = land().view(58.5, 8.8, 0.0)!!.first { it.bearing == 0.0 }
        assertTrue(300 in ahead.seen)
        assertTrue(ahead.seen.none { it > 400 })
    }

    @Test
    fun aForestHidesWhatLiesBehindIt() {
        val east = land().view(58.5, 8.8, 0.0)!!.first { it.bearing == 90.0 }
        assertTrue(east.seen.none { it > 450 })
    }

    @Test
    fun openLandIsSeenAsFarAsThePhoneHasLand() {
        val west = land().view(58.5, 8.8, 0.0)!!.first { it.bearing == 270.0 }
        assertTrue(west.seen.contains(500))
    }

    @Test
    fun withoutLandHereThereIsNoView() {
        assertNull(land().view(59.9, 10.7, 0.0))
    }

    @Test
    fun theViewIsHalfACircleAhead() {
        assertEquals(19, land().view(58.5, 8.8, 0.0)!!.size)
    }

    @Test
    fun whatTheServicePacksIsReadBack() {
        val header = """{"grid": 0.00045, "count": 2, "eyes": 1.2, "target": 3.0, "open_near": 50, """ +
            """"half_width": 90, "ray_step": 10, "sample_step": 50, "farthest": 3000, "codes": [["Skog", 12.0]]}"""
        val row = Math.round(58.5 / grid).toInt()
        val col = Math.round(8.8 / (grid * 2)).toInt()
        val cells = java.nio.ByteBuffer.allocate(22).order(java.nio.ByteOrder.LITTLE_ENDIAN)
        cells.putInt(row).putInt(col).putShort(125).put(0)
        cells.putInt(row).putInt(col + 1).putShort(300).put(255.toByte())
        val land = Land.read(header.toByteArray() + "\n".toByteArray() + cells.array())
        assertEquals(2, land.size)
        assertEquals(12.5 to 12.0, land.at(58.5, 8.8))
        assertEquals(30.0 to 0.0, land.at(58.5, (col + 1) * grid * 2))
    }
}
