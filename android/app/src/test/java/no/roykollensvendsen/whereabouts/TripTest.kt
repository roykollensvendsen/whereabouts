package no.roykollensvendsen.whereabouts

import org.junit.Assert.assertEquals
import org.junit.Test

class TripTest {
    // Straight north, then straight east; 0.01 degrees of latitude is about 1.1 km.
    private val road = listOf(58.40 to 8.70, 58.41 to 8.70, 58.41 to 8.72)
    private val trip = Trip(road)

    @Test
    fun theLengthIsTheRoadsLength() {
        assertEquals(1112.0 + 1167.0, trip.metres, 15.0)
    }

    @Test
    fun halfwayAlongTheFirstStretchIsHalfwayAndHeadsNorth() {
        val there = trip.reading(556.0, Trip.SPEED_M_S, 0L)
        assertEquals(58.405, there.latitude, 0.0002)
        assertEquals(8.70, there.longitude, 0.0001)
        assertEquals(0.0, there.heading!!, 1.0)
    }

    @Test
    fun onTheSecondStretchItHeadsEast() {
        val there = trip.reading(1700.0, Trip.SPEED_M_S, 0L)
        assertEquals(58.41, there.latitude, 0.0001)
        assertEquals(90.0, there.heading!!, 1.0)
    }

    @Test
    fun pastTheEndItStaysAtTheEnd() {
        val there = trip.reading(99_999.0, Trip.SPEED_M_S, 0L)
        assertEquals(58.41, there.latitude, 0.0001)
        assertEquals(8.72, there.longitude, 0.0001)
    }
}
